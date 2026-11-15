"""Cabin climate as one thermostat: on/off, target temperature and rapid presets."""

from typing import Any, List, Optional

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .command_entity import (
    CLIMATE_PRESETS,
    PRESET_NONE,
    ZeekrCommandEntity,
    climate_is_on,
    climate_start_parameters,
    climate_stop_parameters,
)
from .const import MAX_AC_TEMP, MIN_AC_TEMP
from .coordinator import ZeekrRuntimeData
from .entity import numeric_value, status_value


class ZeekrClimate(ZeekrCommandEntity, ClimateEntity, RestoreEntity):
    """Remote pre-conditioning of the cabin.

    The car only reports whether pre-conditioning runs, not which variant, so the
    preset (normal / rapid warming / rapid cooling) is the one chosen here and is
    applied the next time the climate is switched on, or at once if it is running.
    """

    _attr_name = "Climate"
    _attr_translation_key = "cabin"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT_COOL]
    _attr_preset_modes = list(CLIMATE_PRESETS)
    _attr_min_temp = MIN_AC_TEMP
    _attr_max_temp = MAX_AC_TEMP
    _attr_target_temperature_step = 0.5
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, runtime: ZeekrRuntimeData, vin: str) -> None:
        """Bind the thermostat to one vehicle and the shared climate settings."""
        super().__init__(runtime, vin)
        self._attr_unique_id = f"{vin}_climate"

    @property
    def _setting(self) -> dict:
        """Return this vehicle's local climate settings (temp, duration, preset)."""
        return self._runtime.climate_setting(self.vin)

    def _reported_value(self) -> bool:
        """Reflect the vehicle's reported pre-conditioning state."""
        return climate_is_on(self.vehicle_data)

    @property
    def hvac_mode(self) -> HVACMode:
        """Return whether pre-conditioning runs (or was just commanded to)."""
        return HVACMode.HEAT_COOL if self._current_value() else HVACMode.OFF

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the cabin temperature."""
        return numeric_value(
            status_value(
                self.vehicle_data, "additionalVehicleStatus.climateStatus.interiorTemp"
            )
        )

    @property
    def target_temperature(self) -> float:
        """Return the temperature used by the normal preset."""
        return float(self._setting.get("temp", 22.0))

    @property
    def preset_mode(self) -> str:
        """Return the chosen preset."""
        preset = self._setting.get("preset", PRESET_NONE)
        return preset if preset in CLIMATE_PRESETS else PRESET_NONE

    async def async_added_to_hass(self) -> None:
        """Restore the chosen preset after a restart."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.attributes.get("preset_mode") in CLIMATE_PRESETS:
            self._setting["preset"] = last.attributes["preset_mode"]

    async def _async_start(self) -> None:
        """Start (or restart with new settings) pre-conditioning."""
        await self._async_command(
            True,
            service_id="ZAF",
            command="",
            parameters=climate_start_parameters(self._setting),
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Switch pre-conditioning on or off."""
        if hvac_mode == HVACMode.OFF:
            await self._async_command(
                False,
                service_id="ZAF",
                command="",
                parameters=climate_stop_parameters(),
            )
        else:
            await self._async_start()

    async def async_turn_on(self) -> None:
        """Switch pre-conditioning on."""
        await self.async_set_hvac_mode(HVACMode.HEAT_COOL)

    async def async_turn_off(self) -> None:
        """Switch pre-conditioning off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Store the target temperature; apply it at once if the climate runs."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self._setting["temp"] = float(temperature)
        self.async_write_ha_state()
        if self._current_value() and self.preset_mode == PRESET_NONE:
            await self._async_start()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Store the preset; apply it at once if the climate runs."""
        self._setting["preset"] = preset_mode
        self.async_write_ha_state()
        if self._current_value():
            await self._async_start()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create one cabin thermostat per vehicle."""
    runtime: ZeekrRuntimeData = entry.runtime_data
    entities: List[ZeekrClimate] = [
        ZeekrClimate(runtime, vin) for vin in runtime.api.vehicles
    ]
    async_add_entities(entities)
