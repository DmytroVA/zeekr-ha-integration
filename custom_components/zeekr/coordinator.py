"""Shared account runtime and coordinated vehicle status updates."""

from dataclasses import dataclass, field
import json
import logging
from typing import Any, Dict, Iterator, Optional, Set, Tuple

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ZeekrApi, ZeekrApiError, ZeekrAuthError
from .const import DEFAULT_AC_DURATION_MIN, DEFAULT_AC_TEMP, DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

_OBSERVATION_STORE_VERSION = 1
_OBSERVATION_SAVE_DELAY = 300
_OBSERVATION_MAX_SAMPLES = 8
_OBSERVATION_MAX_VALUE_LEN = 80
_EMPTY_VALUES = ("", "None", "null", "[]", "{}")


def _flatten(data: Dict[str, Any], prefix: str = "") -> Iterator[Tuple[str, Any]]:
    """Yield ``(dotted.path, leaf value)`` for every field of a status document."""
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            yield from _flatten(value, path)
        else:
            yield path, value


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

    async def async_load(self) -> None:
        """Load the summaries collected before the last restart."""
        stored = await self._store.async_load()
        if isinstance(stored, dict):
            self.data = stored

    async def async_remove(self) -> None:
        """Delete the stored summaries when the integration is removed."""
        await self._store.async_remove()

    def observe(self, vin: str, status: Dict[str, Any]) -> None:
        """Fold one status document into the per-field summary for a vehicle."""
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
        if dirty:
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
        self._missing_v2_vins: Set[str] = set()

    def _keep_v2(self, vin: str, status: Dict[str, Any]) -> Dict[str, Any]:
        """Carry the previous v2.0 document over when this poll did not get one.

        The v2.0 request is best effort: when it fails the status holds only
        v1.0, and entities that read only ``v2.*`` (sentry, defrost, seats,
        steering wheel, windows ...) would flip to off/closed for one cycle.
        Keeping the last known v2.0 document leaves their state unchanged.
        """
        if "v2" in status:
            if vin in self._missing_v2_vins:
                self._missing_v2_vins.discard(vin)
                _LOGGER.info("Zeekr vehicle ...%s v2.0 status is back", vin[-6:])
            return status
        previous = (self.data or {}).get(vin, {}).get("v2")
        if previous is None:
            return status
        if vin not in self._missing_v2_vins:
            self._missing_v2_vins.add(vin)
            _LOGGER.warning(
                "Zeekr vehicle ...%s: v2.0 status unavailable, keeping the last one",
                vin[-6:],
            )
        return {**status, "v2": previous}

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
                result[vin] = self._keep_v2(vin, result[vin])
                if vin in self._failed_vins:
                    self._failed_vins.discard(vin)
                    _LOGGER.info("Zeekr vehicle ...%s is updating again", vin[-6:])
        if last_error is not None and not result:
            raise UpdateFailed("Unable to update Zeekr vehicle status") from last_error
        return result

    async def async_refresh_vehicle(self, vin: str) -> None:
        """Refresh one vehicle immediately and preserve the other vehicles' data."""
        status = await self.api.async_get_vehicle_status(vin)
        self.observer.observe(vin, status)
        status = self._keep_v2(vin, status)
        updated = dict(self.data or {})
        updated[vin] = status
        self.async_set_updated_data(updated)


@dataclass
class ZeekrRuntimeData:
    """Runtime objects shared by platforms, services, and the live-video card."""

    api: ZeekrApi
    coordinator: VehicleStatusCoordinator
    # Per-VIN local climate convenience settings, not reported by the vehicle.
    climate_settings: Dict[str, Dict[str, Any]] = field(default_factory=dict)

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
