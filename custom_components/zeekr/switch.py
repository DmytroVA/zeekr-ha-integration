"""Remote switches: sentry mode, air conditioning, defrost, ventilation, wheel heat."""

from typing import Any, Optional

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .command_entity import (
    ZeekrCommandEntity,
    climate_is_on,
    climate_start_parameters,
    climate_stop_parameters,
)
from .coordinator import ZeekrRuntimeData
from .entity import boolean_value, value_at


class ZeekrCommandSwitch(ZeekrCommandEntity, SwitchEntity):
    """A switch driven by a remote command (see ``ZeekrCommandEntity``)."""

    @property
    def is_on(self) -> bool:
        """Return the commanded state while it is pending, else the reported one."""
        return bool(self._current_value())


class ZeekrSentrySwitch(ZeekrCommandSwitch):
    """Control the RSM sentry service and reflect the reported sentry state."""

    _attr_translation_key = "sentry_mode"

    def __init__(self, runtime: ZeekrRuntimeData, vin: str) -> None:
        """Bind the RSM control to one vehicle."""
        super().__init__(runtime, vin)
        self._attr_unique_id = f"{vin}_sentry_mode"

    def _reported_value(self) -> bool:
        """Read sentry state the way the app does: ``basic.vstdModeStatus`` 1-4.

        (``usageMode`` is not a sentry flag: it is 1 whenever the car is awake.)
        """
        return str(value_at(self.vehicle_data, "basic.vstdModeStatus")) in (
            "1",
            "2",
            "3",
            "4",
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
    """On/off shortcut for the cabin climate (same state as the climate entity).

    Target temperature and run time come from the shared local settings.
    """

    _attr_translation_key = "air_conditioning"
    # Duplicates the climate entity's on/off.
    _attr_entity_registry_enabled_default = False

    def __init__(self, runtime: ZeekrRuntimeData, vin: str) -> None:
        """Bind the AC switch to one vehicle and the shared climate settings."""
        super().__init__(runtime, vin)
        self._attr_unique_id = f"{vin}_ac"

    def _reported_value(self) -> bool:
        """Reflect the vehicle's reported pre-conditioning state."""
        return climate_is_on(self.vehicle_data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start the climate with the configured temperature and run time."""
        await self._async_command(
            True,
            service_id="ZAF",
            command="",
            parameters=climate_start_parameters(
                self._runtime.climate_setting(self.vin)
            ),
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop the climate."""
        await self._async_command(
            False,
            service_id="ZAF",
            command="",
            parameters=climate_stop_parameters(),
        )


class ZeekrDefrostSwitch(ZeekrCommandSwitch):
    """Windscreen defrost (ZAF ``DF``); state from ``climateStatus.defrost``."""

    _attr_translation_key = "defrost"
    _attr_icon = "mdi:car-defrost-front"
    STATE_PATH = "climateStatus.defrost"

    def __init__(self, runtime: ZeekrRuntimeData, vin: str) -> None:
        """Bind the defrost switch to one vehicle."""
        super().__init__(runtime, vin)
        self._attr_unique_id = f"{vin}_defrost"

    def _reported_value(self) -> bool:
        """Reflect the reported defrost state."""
        return boolean_value(value_at(self.vehicle_data, self.STATE_PATH)) is True

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start defrosting for the configured run time."""
        await self._async_command(
            True,
            service_id="ZAF",
            command="",
            parameters=[
                {"key": "DF", "value": True},
                {"key": "DF.level", "value": "2"},
                {"key": "DF.duration", "value": self._duration()},
            ],
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop defrosting."""
        await self._async_command(
            False,
            service_id="ZAF",
            command="",
            parameters=[{"key": "DF", "value": False}],
        )


class ZeekrCabinVentSwitch(ZeekrCommandSwitch):
    """Cabin ventilation (RCC); state from ``climateStatus.airBlowerActive``."""

    _attr_translation_key = "cabin_ventilation"
    _attr_icon = "mdi:fan"
    STATE_PATH = "climateStatus.airBlowerActive"
    _PARAMETERS = [
        {"key": "rcc.conditioner", "value": "50"},
        {"key": "rcc.ventilation", "value": "0"},
    ]

    def __init__(self, runtime: ZeekrRuntimeData, vin: str) -> None:
        """Bind the ventilation switch to one vehicle."""
        super().__init__(runtime, vin)
        self._attr_unique_id = f"{vin}_cabin_ventilation"

    def _reported_value(self) -> bool:
        """Reflect the reported blower state."""
        return boolean_value(value_at(self.vehicle_data, self.STATE_PATH)) is True

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start ventilation; RCC schedules its run time in six-second units."""
        await self._async_command(
            True,
            service_id="RCC",
            command="start",
            parameters=list(self._PARAMETERS),
            duration=self._duration() * 6,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop ventilation."""
        await self._async_command(
            False,
            service_id="RCC",
            command="stop",
            parameters=list(self._PARAMETERS),
        )


class ZeekrSteeringWheelHeatSwitch(ZeekrCommandSwitch):
    """Steering-wheel heating (ZAF ``SW``); ``steerWhlHeatingSts`` 1 = on."""

    _attr_translation_key = "steering_wheel_heating"
    _attr_icon = "mdi:steering"
    STATE_PATH = "climateStatus.steerWhlHeatingSts"

    def __init__(self, runtime: ZeekrRuntimeData, vin: str) -> None:
        """Bind the steering-wheel heating switch to one vehicle."""
        super().__init__(runtime, vin)
        self._attr_unique_id = f"{vin}_steering_wheel_heating"

    def _reported_value(self) -> bool:
        """Reflect the reported steering-wheel heating state."""
        return str(value_at(self.vehicle_data, self.STATE_PATH)) == "1"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start steering-wheel heating for the configured run time."""
        await self._async_command(
            True,
            service_id="ZAF",
            command="",
            parameters=[
                {"key": "SW", "value": True},
                {"key": "SW.level", "value": "1"},
                {"key": "SW.duration", "value": self._duration()},
            ],
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop steering-wheel heating."""
        await self._async_command(
            False,
            service_id="ZAF",
            command="",
            parameters=[{"key": "SW", "value": False}],
        )


# Created only when the car reports the matching status field.
_OPTIONAL_SWITCHES = (
    ZeekrDefrostSwitch,
    ZeekrCabinVentSwitch,
    ZeekrSteeringWheelHeatSwitch,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the remote switches each vehicle supports."""
    runtime: ZeekrRuntimeData = entry.runtime_data
    entities: list = []
    for vin in runtime.api.vehicles:
        data = (runtime.coordinator.data or {}).get(vin, {})
        entities.append(ZeekrSentrySwitch(runtime, vin))
        entities.append(ZeekrAcSwitch(runtime, vin))
        for cls in _OPTIONAL_SWITCHES:
            path: Optional[str] = cls.STATE_PATH
            if not data or value_at(data, path) is not None:
                entities.append(cls(runtime, vin))
    async_add_entities(entities)
