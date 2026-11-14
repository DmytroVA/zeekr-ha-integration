"""Sentry-mode and air-conditioning switches for Zeekr vehicles."""

import time
from typing import Any, Dict, List, Optional

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .commands import async_run_command
from .const import COMMAND_OPTIMISTIC_HOLD
from .coordinator import ZeekrRuntimeData
from .entity import ZeekrVehicleEntity, boolean_value, value_at


class ZeekrCommandSwitch(ZeekrVehicleEntity, SwitchEntity):
    """A switch whose state is commanded remotely and confirmed by the car.

    Turning it shows the new state at once, then waits for the car's verdict on
    the command. A refusal or timeout puts the old state back and raises the
    reason. After a confirmed command the commanded state is held until the
    car's status document (refreshed about once a minute) reports it too.
    """

    def __init__(self, runtime: ZeekrRuntimeData, vin: str) -> None:
        """Bind the switch to one vehicle and the shared account runtime."""
        super().__init__(runtime.coordinator, vin)
        self._runtime = runtime
        self._pending: Optional[bool] = None
        self._pending_until = 0.0

    def _reported(self) -> bool:
        """Return the state the car's status document currently reports."""
        raise NotImplementedError

    @property
    def is_on(self) -> bool:
        """Return the commanded state while it is pending, else the reported one."""
        if self._pending is not None:
            return self._pending
        return self._reported()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Drop the held state once the car reports it or the hold expires."""
        if self._pending is not None and (
            self._reported() == self._pending
            or time.monotonic() >= self._pending_until
        ):
            self._pending = None
        super()._handle_coordinator_update()

    async def _async_command(
        self,
        enabled: bool,
        *,
        service_id: str,
        command: Optional[str],
        parameters: List[Dict[str, Any]],
    ) -> None:
        """Send the command behind a state change and keep the UI truthful."""
        self._pending = enabled
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
            )
        except HomeAssistantError:
            self._pending = None
            self.async_write_ha_state()
            raise
        if self._pending is not None:
            self._pending_until = time.monotonic() + COMMAND_OPTIMISTIC_HOLD
        self.async_write_ha_state()


class ZeekrSentrySwitch(ZeekrCommandSwitch):
    """Control the RSM sentry service and reflect the last reported usage mode."""

    _attr_name = "Sentry Mode"
    _attr_assumed_state = True

    def __init__(self, runtime: ZeekrRuntimeData, vin: str) -> None:
        """Bind the RSM control to one vehicle."""
        super().__init__(runtime, vin)
        self._attr_unique_id = f"{vin}_sentry_mode"

    def _reported(self) -> bool:
        """Read sentry state from the latest vehicle usage mode field."""
        value = self.vehicle_data.get("basicVehicleStatus", {}).get("usageMode")
        return str(value) == "1"

    @property
    def available(self) -> bool:
        """Require a reported usage mode before presenting the switch as available."""
        return (
            super().available
            and self.vehicle_data.get("basicVehicleStatus", {}).get("usageMode")
            is not None
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start sentry mode."""
        await self._set_sentry(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop sentry mode."""
        await self._set_sentry(False)

    async def _set_sentry(self, enabled: bool) -> None:
        """Send the RSM start/stop command."""
        await self._async_command(
            enabled,
            service_id="RSM",
            command="start" if enabled else "stop",
            parameters=[{"key": "rsm", "value": "6"}],
        )


class ZeekrAcSwitch(ZeekrCommandSwitch):
    """Remote air conditioning (pre-conditioning) using the ZAF climate command.

    State is read back from ``climateStatus.preClimateActive``. Target
    temperature and run time come from the two local number entities.
    """

    _attr_name = "Air Conditioning"

    def __init__(self, runtime: ZeekrRuntimeData, vin: str) -> None:
        """Bind the AC switch to one vehicle and the shared climate settings."""
        super().__init__(runtime, vin)
        self._attr_unique_id = f"{vin}_ac"

    def _reported(self) -> bool:
        """Reflect the vehicle's reported pre-conditioning state."""
        value = value_at(
            self.vehicle_data, "additionalVehicleStatus.climateStatus.preClimateActive"
        )
        return boolean_value(value) is True

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start AC with the locally configured target temperature and duration."""
        setting = self._runtime.climate_setting(self.vin)
        await self._async_command(
            True,
            service_id="ZAF",
            command="",
            parameters=[
                {"key": "AC", "value": True},
                {"key": "AC.temp", "value": str(setting.get("temp", 22.0))},
                {"key": "AC.duration", "value": int(setting.get("duration", 15))},
            ],
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop AC pre-conditioning."""
        await self._async_command(
            False,
            service_id="ZAF",
            command="",
            parameters=[{"key": "AC", "value": False}],
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the sentry switch and AC switch for each vehicle."""
    runtime: ZeekrRuntimeData = entry.runtime_data
    entities: list = []
    for vin in runtime.api.vehicles:
        entities.append(ZeekrSentrySwitch(runtime, vin))
        entities.append(ZeekrAcSwitch(runtime, vin))
    async_add_entities(entities)
