"""Remote switches: sentry mode, air conditioning, defrost, ventilation, wheel heat."""

from typing import Any, Optional

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .command_entity import ZeekrCommandEntity
from .coordinator import ZeekrRuntimeData
from .entity import boolean_value, has_v2, value_at


class ZeekrCommandSwitch(ZeekrCommandEntity, SwitchEntity):
    """A switch driven by a remote command (see ``ZeekrCommandEntity``)."""

    @property
    def is_on(self) -> bool:
        """Return the commanded state while it is pending, else the reported one."""
        return bool(self._current_value())


class ZeekrSentrySwitch(ZeekrCommandSwitch):
    """Control the RSM sentry service and reflect the reported sentry state."""

    _attr_name = "Sentry Mode"

    def __init__(self, runtime: ZeekrRuntimeData, vin: str) -> None:
        """Bind the RSM control to one vehicle."""
        super().__init__(runtime, vin)
        self._attr_unique_id = f"{vin}_sentry_mode"

    def _reported_value(self) -> bool:
        """Read sentry state the way the app does: ``basic.vstdModeStatus`` 1-4.

        (``usageMode`` is not a sentry flag: it is 1 whenever the car is awake.)
        """
        return str(value_at(self.vehicle_data, "v2.basic.vstdModeStatus")) in (
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
    """Remote air conditioning (pre-conditioning) using the ZAF climate command.

    Target temperature and run time come from the two local number entities.
    """

    _attr_name = "Air Conditioning"

    def __init__(self, runtime: ZeekrRuntimeData, vin: str) -> None:
        """Bind the AC switch to one vehicle and the shared climate settings."""
        super().__init__(runtime, vin)
        self._attr_unique_id = f"{vin}_ac"

    def _reported_value(self) -> bool:
        """Reflect the vehicle's reported pre-conditioning state."""
        value = value_at(self.vehicle_data, "v2.climateStatus.preClimateActive")
        if value is None:
            value = value_at(
                self.vehicle_data,
                "additionalVehicleStatus.climateStatus.preClimateActive",
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
                {"key": "AC.duration", "value": self._duration()},
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


class ZeekrDefrostSwitch(ZeekrCommandSwitch):
    """Windscreen defrost (ZAF ``DF``); state from ``climateStatus.defrost``."""

    _attr_name = "Defrost"
    _attr_icon = "mdi:car-defrost-front"
    STATE_PATH = "v2.climateStatus.defrost"

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

    _attr_name = "Cabin Ventilation"
    _attr_icon = "mdi:fan"
    STATE_PATH = "v2.climateStatus.airBlowerActive"
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

    _attr_name = "Steering Wheel Heating"
    _attr_icon = "mdi:steering"
    STATE_PATH = "v2.climateStatus.steerWhlHeatingSts"

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
            if not has_v2(data) or value_at(data, path) is not None:
                entities.append(cls(runtime, vin))
    async_add_entities(entities)
