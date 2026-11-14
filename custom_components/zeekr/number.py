"""Local climate-setting number helpers used by the experimental AC controls."""

from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEFAULT_AC_DURATION_MIN,
    DEFAULT_AC_TEMP,
    MAX_AC_TEMP,
    MIN_AC_TEMP,
)
from .coordinator import ZeekrRuntimeData
from .entity import ZeekrVehicleEntity


class _ZeekrClimateNumber(ZeekrVehicleEntity, RestoreNumber, NumberEntity):
    """Base for a locally stored climate parameter (not reported by the car)."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _setting_key = ""
    _default: float = 0.0

    def __init__(self, runtime: ZeekrRuntimeData, vin: str) -> None:
        """Bind a local climate number to one vehicle's shared settings."""
        super().__init__(runtime.coordinator, vin)
        self._runtime = runtime

    @property
    def available(self) -> bool:
        """Local settings are always available regardless of vehicle connectivity."""
        return True

    @property
    def native_value(self) -> float:
        """Return the current stored value for this vehicle."""
        return float(
            self._runtime.climate_setting(self.vin).get(self._setting_key, self._default)
        )

    async def async_set_native_value(self, value: float) -> None:
        """Persist the new value into the shared per-vehicle climate settings."""
        self._runtime.climate_setting(self.vin)[self._setting_key] = value
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore the last stored value after a restart."""
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last is not None and last.native_value is not None:
            self._runtime.climate_setting(self.vin)[self._setting_key] = (
                last.native_value
            )


class ZeekrAcTemperatureNumber(_ZeekrClimateNumber):
    """Target cabin temperature used by the experimental AC start command."""

    _attr_name = "AC Target Temperature"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = MIN_AC_TEMP
    _attr_native_max_value = MAX_AC_TEMP
    _attr_native_step = 0.5
    _setting_key = "temp"
    _default = DEFAULT_AC_TEMP

    def __init__(self, runtime: ZeekrRuntimeData, vin: str) -> None:
        """Bind the AC target-temperature helper to one vehicle."""
        super().__init__(runtime, vin)
        self._attr_unique_id = f"{vin}_ac_target_temperature"


class ZeekrAcDurationNumber(_ZeekrClimateNumber):
    """Run duration (minutes) used by the experimental AC/vent commands."""

    _attr_name = "AC Duration"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_native_min_value = 1
    _attr_native_max_value = 30
    _attr_native_step = 1
    _setting_key = "duration"
    _default = float(DEFAULT_AC_DURATION_MIN)

    def __init__(self, runtime: ZeekrRuntimeData, vin: str) -> None:
        """Bind the AC duration helper to one vehicle."""
        super().__init__(runtime, vin)
        self._attr_unique_id = f"{vin}_ac_duration"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the local climate number helpers for each supported vehicle."""
    runtime: ZeekrRuntimeData = entry.runtime_data
    entities: list = []
    for vin in runtime.api.vehicles:
        entities.append(ZeekrAcTemperatureNumber(runtime, vin))
        entities.append(ZeekrAcDurationNumber(runtime, vin))
    async_add_entities(entities)
