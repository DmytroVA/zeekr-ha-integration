"""Cabin climate as a thermostat: on/off and target temperature."""

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
    ZeekrCommandEntity,
    climate_is_on,
    climate_start_parameters,
    climate_stop_parameters,
)
from .const import MAX_AC_TEMP, MIN_AC_TEMP
from .coordinator import RESTORED_KEYS, ZeekrRuntimeData
from .entity import numeric_value, status_value

# Home Assistant 2026.11 renamed the climate temperature properties to native_*
# (the old names stop working in 2027.11). Older cores only know the old names,
# so the entity defines whichever set the running core expects.
_NATIVE_TEMPERATURE = hasattr(ClimateEntity, "native_temperature_unit")


class ZeekrClimate(ZeekrCommandEntity, RestoreEntity, ClimateEntity):
    """Remote pre-conditioning of the cabin at a target temperature.

    Rapid warming and rapid cooling are separate one-press buttons; the car
    reports all three simply as "pre-conditioning is running".

    The car does not report the target, so it is restored from the last state
    after a restart (the AC temperature number, disabled by default, does the
    same when enabled).
    """

    _attr_translation_key = "climate"
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT_COOL]
    _attr_min_temp = MIN_AC_TEMP
    _attr_max_temp = MAX_AC_TEMP
    _attr_target_temperature_step = 0.5
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, runtime: ZeekrRuntimeData, vin: str) -> None:
        """Bind the thermostat to one vehicle and the shared climate settings."""
        super().__init__(runtime, vin)
        self._attr_unique_id = f"{vin}_climate"

    async def async_added_to_hass(self) -> None:
        """Restore the target temperature unless the number already did."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is None:
            return
        restored = numeric_value(last.attributes.get(ATTR_TEMPERATURE))
        restored_keys = self._setting.setdefault(RESTORED_KEYS, set())
        if (
            restored is not None
            and MIN_AC_TEMP <= restored <= MAX_AC_TEMP
            and "temp" not in restored_keys
        ):
            self._setting["temp"] = float(restored)
            restored_keys.add("temp")

    @property
    def _setting(self) -> dict:
        """Return this vehicle's local climate settings (temperature, run time)."""
        return self._runtime.climate_setting(self.vin)

    def _reported_value(self) -> bool:
        """Reflect the vehicle's reported pre-conditioning state."""
        return climate_is_on(self.vehicle_data)

    def _cabin_temperature(self) -> Optional[float]:
        """Return the cabin temperature in degrees Celsius."""
        return numeric_value(
            status_value(
                self.vehicle_data, "additionalVehicleStatus.climateStatus.interiorTemp"
            )
        )

    def _target(self) -> float:
        """Return the configured target temperature in degrees Celsius."""
        return float(self._setting.get("temp", 22.0))

    if _NATIVE_TEMPERATURE:
        _attr_native_temperature_unit = UnitOfTemperature.CELSIUS

        @property
        def native_current_temperature(self) -> Optional[float]:
            """Return the cabin temperature."""
            return self._cabin_temperature()

        @property
        def native_target_temperature(self) -> float:
            """Return the target temperature."""
            return self._target()

    else:
        _attr_temperature_unit = UnitOfTemperature.CELSIUS

        @property
        def current_temperature(self) -> Optional[float]:
            """Return the cabin temperature."""
            return self._cabin_temperature()

        @property
        def target_temperature(self) -> float:
            """Return the target temperature."""
            return self._target()

    @property
    def hvac_mode(self) -> HVACMode:
        """Return whether pre-conditioning runs (or was just commanded to)."""
        return HVACMode.HEAT_COOL if self._current_value() else HVACMode.OFF

    async def _async_start(self) -> None:
        """Start (or restart with a new temperature) air conditioning."""
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
