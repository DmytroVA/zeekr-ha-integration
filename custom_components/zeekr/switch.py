"""Remote sentry-mode and experimental AC switches for Zeekr vehicles."""

import asyncio
import time
from typing import Any, Optional

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import ZeekrApiError, ZeekrAuthError
from .const import (
    COMMAND_CONFIRM_ATTEMPTS,
    COMMAND_CONFIRM_DELAY,
    COMMAND_OPTIMISTIC_HOLD,
)
from .coordinator import ZeekrRuntimeData, start_reauth
from .entity import ZeekrVehicleEntity, boolean_value, value_at


class ZeekrSentrySwitch(ZeekrVehicleEntity, SwitchEntity):
    """Control the RSM sentry service and reflect the last reported usage mode."""

    _attr_name = "Sentry Mode"
    _attr_assumed_state = True

    def __init__(self, runtime: ZeekrRuntimeData, vin: str) -> None:
        """Bind the RSM control to one vehicle and the shared account API client."""
        super().__init__(runtime.coordinator, vin)
        self._api = runtime.api
        self._attr_unique_id = f"{vin}_sentry_mode"
        # Commanded state shown until the car reports it (or the hold expires).
        self._pending: Optional[bool] = None
        self._pending_until = 0.0
        self._confirm_task: Optional[asyncio.Task] = None

    def _reported(self) -> bool:
        """Read sentry state from the latest vehicle usage mode field."""
        value = self.vehicle_data.get("basicVehicleStatus", {}).get("usageMode")
        return str(value) == "1"

    @property
    def is_on(self) -> bool:
        """Return the commanded state while it is pending, else the reported one."""
        if self._pending is not None:
            return self._pending
        return self._reported()

    @property
    def available(self) -> bool:
        """Require a reported usage mode before presenting the switch as available."""
        return (
            super().available
            and self.vehicle_data.get("basicVehicleStatus", {}).get("usageMode")
            is not None
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Drop the optimistic state once the car confirms it or the hold expires."""
        if self._pending is not None and (
            self._reported() == self._pending
            or time.monotonic() >= self._pending_until
        ):
            self._pending = None
        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send the RSM start command and confirm the resulting state in background."""
        await self._set_sentry(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send the RSM stop command and confirm the resulting state in background."""
        await self._set_sentry(False)

    async def async_will_remove_from_hass(self) -> None:
        """Stop a running confirmation poll when the entity is removed."""
        self._cancel_confirm()
        await super().async_will_remove_from_hass()

    def _cancel_confirm(self) -> None:
        """Cancel the confirmation poll of a previous command, if still running."""
        if self._confirm_task is not None and not self._confirm_task.done():
            self._confirm_task.cancel()
        self._confirm_task = None

    async def _set_sentry(self, enabled: bool) -> None:
        """Execute a sentry command and surface provider failures to Home Assistant.

        Only a rejected command raises. Once the cloud accepted it, the switch
        shows the commanded state right away and a background task polls for the
        car's confirmation, so a lagging or failing status poll never turns an
        accepted command into an error.
        """
        self._cancel_confirm()
        try:
            await self._api.async_set_sentry(self.vin, enabled)
        except ZeekrAuthError as err:
            start_reauth(self.hass)
            raise HomeAssistantError("Zeekr credentials expired") from err
        except ZeekrApiError as err:
            raise HomeAssistantError("Unable to change Zeekr sentry mode") from err
        self._pending = enabled
        self._pending_until = time.monotonic() + COMMAND_OPTIMISTIC_HOLD
        self.async_write_ha_state()
        self._confirm_task = self.hass.async_create_background_task(
            self._async_confirm(), f"zeekr_sentry_confirm_{self.vin[-6:]}"
        )

    async def _async_confirm(self) -> None:
        """Poll over a short window and stop as soon as the car confirms.

        The command round-trips cloud -> car -> cloud. If the car does not confirm
        within the window, the optimistic state stays until the hold expires and
        the next regular poll reflects the truth.
        """
        for _ in range(COMMAND_CONFIRM_ATTEMPTS):
            await asyncio.sleep(COMMAND_CONFIRM_DELAY)
            try:
                await self.coordinator.async_refresh_vehicle(self.vin)
            except ZeekrAuthError:
                start_reauth(self.hass)
                return
            except ZeekrApiError:
                continue
            if self._pending is None:
                return


class ZeekrAcSwitch(ZeekrVehicleEntity, SwitchEntity):
    """Experimental pre-conditioning (AC) switch using the ZAF climate command.

    State is read back from ``climateStatus.preClimateActive``; the command path
    (serviceId ``ZAF``) is reverse-engineered from the app and not verified on every
    vehicle generation, so this entity is disabled by default.
    """

    _attr_name = "Air Conditioning (experimental)"
    _attr_entity_registry_enabled_default = False

    def __init__(self, runtime: ZeekrRuntimeData, vin: str) -> None:
        """Bind the experimental AC switch to one vehicle and shared settings."""
        super().__init__(runtime.coordinator, vin)
        self._runtime = runtime
        self._attr_unique_id = f"{vin}_ac"

    @property
    def is_on(self) -> bool:
        """Reflect the vehicle's reported pre-conditioning state."""
        value = value_at(self.vehicle_data, "additionalVehicleStatus.climateStatus.preClimateActive")
        return boolean_value(value) is True

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start AC with the locally configured target temperature and duration."""
        setting = self._runtime.climate_setting(self.vin)
        await self._send(
            "start",
            [
                {"key": "AC", "value": True},
                {"key": "AC.temp", "value": str(setting.get("temp", 22.0))},
                {"key": "AC.duration", "value": int(setting.get("duration", 15))},
            ],
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop AC pre-conditioning."""
        await self._send("stop", [{"key": "AC", "value": False}])

    async def _send(self, _mode: str, parameters: list) -> None:
        """Dispatch the ZAF climate command and refresh, surfacing API failures."""
        try:
            await self._runtime.api.async_remote_control(
                self.vin, service_id="ZAF", command="", parameters=parameters
            )
            await self.coordinator.async_refresh_vehicle(self.vin)
        except ZeekrAuthError as err:
            start_reauth(self.hass)
            raise HomeAssistantError("Zeekr credentials expired") from err
        except ZeekrApiError as err:
            raise HomeAssistantError(f"Zeekr rejected the AC command: {err}") from err


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the sentry switch and experimental AC switch for each vehicle."""
    runtime: ZeekrRuntimeData = entry.runtime_data
    entities: list = []
    for vin in runtime.api.vehicles:
        entities.append(ZeekrSentrySwitch(runtime, vin))
        entities.append(ZeekrAcSwitch(runtime, vin))
    async_add_entities(entities)
