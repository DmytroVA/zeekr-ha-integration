"""Seat heating and ventilation level selectors."""

from dataclasses import dataclass
from typing import List

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .command_entity import ZeekrCommandEntity
from .coordinator import ZeekrRuntimeData
from .entity import has_v2, value_at

# The app's own seat screen uses levels 0-3 and cycles 0 -> 3 -> 2 -> 1 -> 0 on
# each tap (strongest first), with icons hot_1 .. hot_3: 1 is the weakest level.
LEVELS = {"low": "1", "medium": "2", "high": "3"}
OPTIONS = ["off", *LEVELS]
_OPTION_BY_LEVEL = {level: option for option, level in LEVELS.items()}


@dataclass(frozen=True)
class ZeekrSeatSpec:
    """One seat comfort function: its command key and its status field."""

    key: str
    name: str
    # ZAF parameter prefix, e.g. ``SH.11`` (heating, driver) / ``SV.19`` (vent, passenger).
    param: str
    path: str
    icon: str


SEAT_SELECTS: List[ZeekrSeatSpec] = [
    ZeekrSeatSpec("seat_heat_driver", "Seat Heating Driver", "SH.11", "v2.climateStatus.drvHeatLv", "mdi:car-seat-heater"),
    ZeekrSeatSpec("seat_heat_passenger", "Seat Heating Passenger", "SH.19", "v2.climateStatus.passHeatLv", "mdi:car-seat-heater"),
    ZeekrSeatSpec("seat_heat_rear_left", "Seat Heating Rear Left", "SH.21", "v2.climateStatus.rlHeatLv", "mdi:car-seat-heater"),
    ZeekrSeatSpec("seat_heat_rear_right", "Seat Heating Rear Right", "SH.29", "v2.climateStatus.rrHeatLv", "mdi:car-seat-heater"),
    ZeekrSeatSpec("seat_vent_driver", "Seat Ventilation Driver", "SV.11", "v2.climateStatus.drvVentDetail", "mdi:car-seat-cooler"),
    ZeekrSeatSpec("seat_vent_passenger", "Seat Ventilation Passenger", "SV.19", "v2.climateStatus.passVentDetail", "mdi:car-seat-cooler"),
    ZeekrSeatSpec("seat_vent_rear_left", "Seat Ventilation Rear Left", "SV.21", "v2.climateStatus.rlVentDetail", "mdi:car-seat-cooler"),
    ZeekrSeatSpec("seat_vent_rear_right", "Seat Ventilation Rear Right", "SV.29", "v2.climateStatus.rrVentDetail", "mdi:car-seat-cooler"),
]


class ZeekrSeatSelect(ZeekrCommandEntity, SelectEntity):
    """Pick a seat heating/ventilation level: off, low, medium or high."""

    _attr_options = OPTIONS
    _attr_translation_key = "seat_level"

    def __init__(self, runtime: ZeekrRuntimeData, vin: str, spec: ZeekrSeatSpec) -> None:
        """Bind one seat function of one vehicle."""
        super().__init__(runtime, vin)
        self._spec = spec
        self._attr_name = spec.name
        self._attr_icon = spec.icon
        self._attr_unique_id = f"{vin}_{spec.key}"

    def _reported_value(self) -> str:
        """Map the reported level to an option; unknown codes read as ``off``."""
        level = str(value_at(self.vehicle_data, self._spec.path))
        return _OPTION_BY_LEVEL.get(level, "off")

    @property
    def current_option(self) -> str:
        """Return the commanded level while it is pending, else the reported one."""
        return self._current_value()

    async def async_select_option(self, option: str) -> None:
        """Send the ZAF seat command for the chosen level."""
        param = self._spec.param
        if option == "off":
            parameters = [{"key": param, "value": False}]
        else:
            parameters = [
                {"key": param, "value": True},
                {"key": f"{param}.level", "value": LEVELS[option]},
                {"key": f"{param}.duration", "value": self._duration()},
            ]
        await self._async_command(
            option, service_id="ZAF", command="", parameters=parameters
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create a selector for every seat function the car reports."""
    runtime: ZeekrRuntimeData = entry.runtime_data
    entities: list = []
    for vin in runtime.api.vehicles:
        data = (runtime.coordinator.data or {}).get(vin, {})
        for spec in SEAT_SELECTS:
            if not has_v2(data) or value_at(data, spec.path) is not None:
                entities.append(ZeekrSeatSelect(runtime, vin, spec))
    async_add_entities(entities)
