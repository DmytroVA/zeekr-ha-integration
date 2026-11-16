"""Shared account runtime and coordinated vehicle status updates."""

import asyncio
from dataclasses import dataclass, field
import json
import logging
import time
from typing import Any, Dict, Iterator, Optional, Set, Tuple

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ZeekrApi, ZeekrApiError, ZeekrAuthError
from .const import (
    DEFAULT_AC_DURATION_MIN,
    DEFAULT_AC_TEMP,
    DOMAIN,
    IDLE_AFTER,
    IDLE_SCAN_INTERVAL,
    SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

_OBSERVATION_STORE_VERSION = 1
_OBSERVATION_SAVE_DELAY = 300
_OBSERVATION_MAX_SAMPLES = 8
_OBSERVATION_MAX_VALUE_LEN = 80
_EMPTY_VALUES = ("", "None", "null", "[]", "{}")
# Key in a vehicle's climate settings: the setting keys already restored after a
# restart. The number helpers restore with priority; the climate entity restores
# the temperature only when its number did not (it is disabled by default).
RESTORED_KEYS = "restored"
# Status field that is "1" while the car is powered up (not asleep).
POWER_MODE_PATH = "temStatus.powerMode"


def _flatten(data: Dict[str, Any], prefix: str = "") -> Iterator[Tuple[str, Any]]:
    """Yield ``(dotted.path, leaf value)`` for every field of a status document."""
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            yield from _flatten(value, path)
        else:
            yield path, value


def _v2_only_observations(fields: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only v2.0 fields of summaries recorded before 1.9.0.

    Up to 1.8.x the status held the v1.0 document with v2.0 nested under ``v2``,
    so paths were ``v2.<path>`` or v1.0 paths. Now the status is the v2.0
    document itself: v1.0 paths are dropped and the ``v2.`` prefix removed.
    Already migrated summaries have no ``v2.`` paths and are returned as is.
    """
    if not any(path.startswith("v2.") for path in fields):
        return fields
    return {path[3:]: record for path, record in fields.items() if path.startswith("v2.")}


class FieldObserver:
    """Record which status fields the cloud really fills and how often they change.

    The status document has hundreds of fields and most are empty or constant on
    a given car. Instead of recording every one as an entity, this keeps a small
    per-field summary (change count and a few sample values) that survives
    restarts and is shown in the diagnostics download, so it is possible to tell
    which raw fields are worth enabling or promoting to a typed entity.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Create the observer with its own storage file."""
        self._store: Store = Store(
            hass, _OBSERVATION_STORE_VERSION, f"{DOMAIN}.field_observations"
        )
        self.data: Dict[str, Dict[str, Dict[str, Any]]] = {}
        # Change counters move on almost every poll (timestamps). They are kept in
        # memory and written with the next structural save or on shutdown/unload.
        self._unsaved = False

    async def async_load(self) -> None:
        """Load the summaries collected before the last restart."""
        stored = await self._store.async_load()
        if isinstance(stored, dict):
            self.data = {
                vin: _v2_only_observations(fields) for vin, fields in stored.items()
            }

    async def async_remove(self) -> None:
        """Delete the stored summaries when the integration is removed."""
        await self._store.async_remove()

    async def async_flush(self) -> None:
        """Write change counters that were only updated in memory."""
        if self._unsaved:
            self._unsaved = False
            await self._store.async_save(self.data)

    def observe(self, vin: str, status: Dict[str, Any]) -> None:
        """Fold one status document into the per-field summary for a vehicle.

        Only a new field or a new sample value schedules a disk write; a value
        changing between known samples (timestamps on every poll) only moves the
        counter in memory.
        """
        fields = self.data.setdefault(vin, {})
        dirty = False
        for path, value in _flatten(status):
            if isinstance(value, (list, dict)):
                text = json.dumps(value, ensure_ascii=False, sort_keys=True)
            else:
                text = str(value)
            text = text[:_OBSERVATION_MAX_VALUE_LEN]
            record = fields.get(path)
            if record is None:
                fields[path] = {"last": text, "changes": 0, "samples": [text]}
                dirty = True
            elif record["last"] != text:
                record["last"] = text
                record["changes"] += 1
                if (
                    text not in record["samples"]
                    and len(record["samples"]) < _OBSERVATION_MAX_SAMPLES
                ):
                    record["samples"].append(text)
                    dirty = True
                else:
                    self._unsaved = True
        if dirty:
            # The delayed write serialises self.data at write time, counters included.
            self._unsaved = False
            self._store.async_delay_save(lambda: self.data, _OBSERVATION_SAVE_DELAY)

    def summary(self, vin: str) -> Dict[str, Dict[str, Any]]:
        """Group a vehicle's fields into changing, constant, and always-empty."""
        changing: Dict[str, Any] = {}
        constant: Dict[str, Any] = {}
        empty = []
        for path, record in sorted(self.data.get(vin, {}).items()):
            if record["changes"]:
                changing[path] = {
                    "changes": record["changes"],
                    "samples": record["samples"],
                }
            elif record["last"] in _EMPTY_VALUES:
                empty.append(path)
            else:
                constant[path] = record["last"]
        return {"changing": changing, "constant": constant, "always_empty": empty}


class VehicleStatusCoordinator(DataUpdateCoordinator[Dict[str, Dict[str, Any]]]):
    """Poll all supported vehicles once and share each response with entities."""

    def __init__(self, hass: HomeAssistant, api: ZeekrApi) -> None:
        """Create the account coordinator with the configured polling interval."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.api = api
        self.observer = FieldObserver(hass)
        self._failed_vins: Set[str] = set()
        # Per VIN: last seen upload stamp and the monotonic time it last changed.
        self._stamps: Dict[str, Tuple[Any, float]] = {}

    def _track_activity(self, vin: str, status: Dict[str, Any]) -> None:
        """Remember when the car's status document last changed its upload time."""
        stamp = status.get("updateTime")
        seen = self._stamps.get(vin)
        if seen is None or seen[0] != stamp:
            self._stamps[vin] = (stamp, time.monotonic())

    def _is_active(self, vin: str, status: Dict[str, Any]) -> bool:
        """True while the car is awake: powered up or uploading recently."""
        section, key = POWER_MODE_PATH.split(".")
        if str((status.get(section) or {}).get(key)) == "1":
            return True
        seen = self._stamps.get(vin)
        if seen is None:
            return True
        return time.monotonic() - seen[1] < IDLE_AFTER.total_seconds()

    def _mark_active(self, vin: str) -> None:
        """Treat the car as awake now (a command was sent or a refresh asked)."""
        stamp = self._stamps.get(vin, (None, 0.0))[0]
        self._stamps[vin] = (stamp, time.monotonic())

    def _adapt_interval(self, data: Dict[str, Dict[str, Any]]) -> None:
        """Poll every 60 s while any car is awake, else every IDLE_SCAN_INTERVAL."""
        active = any(self._is_active(vin, data.get(vin, {})) for vin in self.api.vehicles)
        interval = SCAN_INTERVAL if active else IDLE_SCAN_INTERVAL
        if interval != self.update_interval:
            _LOGGER.debug(
                "Zeekr polling every %s s (%s)",
                int(interval.total_seconds()),
                "a vehicle is active" if active else "all vehicles idle",
            )
            self.update_interval = interval

    async def _async_update_data(self) -> Dict[str, Dict[str, Any]]:
        """Fetch the newest status for every configured supported vehicle.

        One account can hold several cars. A failure for one VIN only makes that
        car's entities unavailable; the poll as a whole fails only when no car
        could be read.
        """
        result: Dict[str, Dict[str, Any]] = {}
        last_error: Optional[ZeekrApiError] = None
        for vin in self.api.vehicles:
            try:
                result[vin] = await self.api.async_get_vehicle_status(vin)
            except ZeekrAuthError as err:
                raise ConfigEntryAuthFailed("Zeekr credentials expired") from err
            except ZeekrApiError as err:
                last_error = err
                if vin not in self._failed_vins:
                    self._failed_vins.add(vin)
                    _LOGGER.warning(
                        "Unable to update Zeekr vehicle ...%s: %s", vin[-6:], err
                    )
            else:
                self.observer.observe(vin, result[vin])
                self._track_activity(vin, result[vin])
                if vin in self._failed_vins:
                    self._failed_vins.discard(vin)
                    _LOGGER.info("Zeekr vehicle ...%s is updating again", vin[-6:])
        if last_error is not None and not result:
            raise UpdateFailed("Unable to update Zeekr vehicle status") from last_error
        # Interval for the next poll: the base class schedules it after this returns.
        self._adapt_interval(result)
        return result

    async def async_refresh_vehicle(self, vin: str) -> None:
        """Refresh one vehicle immediately and preserve the other vehicles' data.

        Used after a command and by the refresh button: marks the car awake and
        returns to 60 s polling, so the command's effect is picked up as quickly
        as before even if the car was idle.
        """
        self._mark_active(vin)
        self.update_interval = SCAN_INTERVAL
        status = await self.api.async_get_vehicle_status(vin)
        self.observer.observe(vin, status)
        self._track_activity(vin, status)
        updated = dict(self.data or {})
        updated[vin] = status
        # Reschedules the next poll with the 60 s interval set above.
        self.async_set_updated_data(updated)


@dataclass
class ZeekrRuntimeData:
    """Runtime objects shared by platforms, services, and the live-video card."""

    api: ZeekrApi
    coordinator: VehicleStatusCoordinator
    # Per-VIN local climate convenience settings, not reported by the vehicle.
    climate_settings: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # One command at a time per vehicle: held from sending until the verdict.
    command_locks: Dict[str, asyncio.Lock] = field(default_factory=dict)

    def command_lock(self, vin: str) -> asyncio.Lock:
        """Return (creating if needed) the command queue lock for one vehicle."""
        return self.command_locks.setdefault(vin, asyncio.Lock())

    def climate_setting(self, vin: str) -> Dict[str, Any]:
        """Return (creating if needed) the local climate settings for one vehicle."""
        return self.climate_settings.setdefault(
            vin,
            {"temp": DEFAULT_AC_TEMP, "duration": DEFAULT_AC_DURATION_MIN},
        )


def get_runtime(hass: HomeAssistant) -> ZeekrRuntimeData:
    """Return the active Zeekr account runtime or raise a clear setup error."""
    runtimes = hass.data.get(DOMAIN, {})
    runtimes = {k: v for k, v in runtimes.items() if isinstance(v, ZeekrRuntimeData)}
    if not runtimes:
        raise RuntimeError("Zeekr integration is not configured")
    return next(iter(runtimes.values()))


def start_reauth(hass: HomeAssistant) -> None:
    """Start the configured account's UI reauthentication flow."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if entries:
        entries[0].async_start_reauth(hass)
