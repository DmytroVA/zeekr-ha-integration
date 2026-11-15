"""Base for entities whose state is commanded remotely and confirmed by the car."""

import time
from typing import Any, Dict, List, Optional

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

from .commands import async_run_command
from .const import COMMAND_OPTIMISTIC_HOLD
from .coordinator import ZeekrRuntimeData
from .entity import ZeekrVehicleEntity, boolean_value, value_at

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
    After a confirmed command the value is held until the car's status document
    reports it too (or a hold time expires, after which the report wins).
    """

    def __init__(self, runtime: ZeekrRuntimeData, vin: str) -> None:
        """Bind the entity to one vehicle and the shared account runtime."""
        super().__init__(runtime.coordinator, vin)
        self._runtime = runtime
        self._pending: Any = None
        self._pending_until = 0.0

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

    @callback
    def _handle_coordinator_update(self) -> None:
        """Drop the held value once the car reports it or the hold expires."""
        if self._pending is not None and (
            self._reported_value() == self._pending
            or time.monotonic() >= self._pending_until
        ):
            self._pending = None
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
        self._pending = target
        self._pending_until = time.monotonic() + COMMAND_OPTIMISTIC_HOLD
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
            self._pending = None
            self.async_write_ha_state()
            raise
        if self._pending is not None:
            self._pending_until = time.monotonic() + COMMAND_OPTIMISTIC_HOLD
        self.async_write_ha_state()
