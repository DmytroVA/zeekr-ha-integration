"""Base for entities whose state is commanded remotely and confirmed by the car."""

import logging
import time
from typing import Any, Dict, List, Optional

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

from .commands import async_run_command
from .const import COMMAND_OPTIMISTIC_HOLD
from .coordinator import ZeekrRuntimeData
from .entity import ZeekrVehicleEntity, boolean_value, value_at

_LOGGER = logging.getLogger(__name__)

# A held value is released only after this many separate status documents in a
# row report it: a single matching document can be followed by an older-looking
# one that rolls the field back (seen when two commands ran back to back).
CONFIRMATIONS_TO_RELEASE = 2

def climate_is_on(data: Dict[str, Any]) -> bool:
    """True when the car reports cabin pre-conditioning as running.

    The same flag covers normal air conditioning and rapid warming/cooling.
    """
    value = value_at(data, "v2.climateStatus.preClimateActive")
    if value is None:
        value = value_at(data, "additionalVehicleStatus.climateStatus.preClimateActive")
    return boolean_value(value) is True


def climate_start_parameters(setting: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build the ZAF parameters that start air conditioning at the set temperature."""
    return [
        {"key": "AC", "value": True},
        {"key": "AC.temp", "value": str(setting.get("temp", 22.0))},
        {"key": "AC.duration", "value": int(setting.get("duration", 15))},
    ]


def climate_stop_parameters() -> List[Dict[str, Any]]:
    """Build the ZAF parameters that stop the climate (also stops rapid warming/cooling)."""
    return [{"key": "AC", "value": False}]


class ZeekrCommandEntity(ZeekrVehicleEntity):
    """Show a commanded value at once, then keep the UI truthful.

    The new value is shown immediately and the command's verdict is awaited. A
    refusal or timeout puts the old value back and raises the car's reason.
    After a confirmed command the value is held until
    ``CONFIRMATIONS_TO_RELEASE`` status documents in a row report it too, or a
    hold time expires, after which the report wins.
    """

    def __init__(self, runtime: ZeekrRuntimeData, vin: str) -> None:
        """Bind the entity to one vehicle and the shared account runtime."""
        super().__init__(runtime.coordinator, vin)
        self._runtime = runtime
        self._pending: Any = None
        self._pending_until = 0.0
        self._confirmations = 0
        self._confirmed_stamp: Any = None

    def _reported_value(self) -> Any:
        """Return the value the car's status document currently reports."""
        raise NotImplementedError

    def _current_value(self) -> Any:
        """Return the commanded value while it is pending, else the reported one."""
        if self._pending is not None:
            return self._pending
        return self._reported_value()

    def _duration(self) -> int:
        """Return the shared run time (minutes) configured for climate commands."""
        return int(self._runtime.climate_setting(self.vin).get("duration", 15))

    def _document_stamp(self) -> Any:
        """Return the status document's upload time, used to tell documents apart."""
        data = self.vehicle_data
        stamp = value_at(data, "v2.updateTime")
        return stamp if stamp not in (None, "") else value_at(data, "updateTime")

    def _set_pending(self, target: Any) -> None:
        """Hold a commanded value and restart the confirmation count."""
        self._pending = target
        self._pending_until = time.monotonic() + COMMAND_OPTIMISTIC_HOLD
        self._confirmations = 0
        self._confirmed_stamp = None

    def _release_pending(self, reason: str) -> None:
        """Stop holding the commanded value."""
        _LOGGER.debug(
            "%s: releasing held %r (%s), reported %r",
            self.entity_id,
            self._pending,
            reason,
            self._reported_value(),
        )
        self._pending = None
        self._confirmations = 0
        self._confirmed_stamp = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Release the held value once the car confirms it or the hold expires.

        Each distinct status document that reports the held value counts once;
        one that reports something else resets the count but keeps the hold.
        """
        if self._pending is not None:
            reported = self._reported_value()
            stamp = self._document_stamp()
            if reported == self._pending:
                if stamp is None or stamp != self._confirmed_stamp:
                    self._confirmations += 1
                    self._confirmed_stamp = stamp
            elif self._confirmations:
                _LOGGER.debug(
                    "%s: report went back to %r after %d match(es); holding %r",
                    self.entity_id,
                    reported,
                    self._confirmations,
                    self._pending,
                )
                self._confirmations = 0
                self._confirmed_stamp = None
            _LOGGER.debug(
                "%s: status update (document %s) reports %r, holding %r, matches %d",
                self.entity_id,
                stamp,
                reported,
                self._pending,
                self._confirmations,
            )
            if self._confirmations >= CONFIRMATIONS_TO_RELEASE:
                self._release_pending("confirmed by the car")
            elif time.monotonic() >= self._pending_until:
                self._release_pending("hold expired")
        super()._handle_coordinator_update()

    async def _async_command(
        self,
        target: Any,
        *,
        service_id: str,
        command: Optional[str],
        parameters: List[Dict[str, Any]],
        duration: Optional[int] = None,
    ) -> None:
        """Send the command behind a value change."""
        self._set_pending(target)
        self.async_write_ha_state()
        try:
            await async_run_command(
                self.hass,
                self._runtime,
                self.vin,
                service_id=service_id,
                command=command,
                parameters=parameters,
                duration=duration,
            )
        except HomeAssistantError:
            self._release_pending("command failed")
            self.async_write_ha_state()
            raise
        if self._pending is not None:
            self._pending_until = time.monotonic() + COMMAND_OPTIMISTIC_HOLD
        self.async_write_ha_state()
