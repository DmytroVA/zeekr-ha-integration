"""GPS device tracker entities for supported Zeekr vehicles."""

from typing import Any, Dict, Optional

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import ZeekrRuntimeData
from .entity import ZeekrVehicleEntity, numeric_value


class ZeekrTracker(ZeekrVehicleEntity, TrackerEntity):
    """Expose a vehicle's latest trusted GPS point; ignore jammed/spoofed fixes.

    When ``posCanBeTrusted`` is not ``"1"`` (GPS jamming/spoofing, e.g. during
    electronic warfare) the reported coordinates are false. The tracker then holds
    the last trusted position instead of jumping the car across the globe.
    """

    _attr_source_type = SourceType.GPS
    _attr_name = "Location"
    _attr_location_accuracy = 10

    def __init__(self, coordinator: Any, vin: str) -> None:
        """Bind the device tracker to one VIN and its coordinator data."""
        super().__init__(coordinator, vin)
        self._attr_unique_id = f"{vin}_location"
        self._last_lat: Optional[float] = None
        self._last_lon: Optional[float] = None

    def _position(self) -> Dict[str, Any]:
        """Return the current position sub-object, or an empty mapping."""
        return self.vehicle_data.get("basicVehicleStatus", {}).get("position", {}) or {}

    def _trusted(self) -> bool:
        """True only when the vehicle marks its own GPS fix trustworthy."""
        return str(self._position().get("posCanBeTrusted")) == "1"

    @property
    def latitude(self) -> Optional[float]:
        """Return the latest trusted latitude, holding the last good one otherwise."""
        if self._trusted():
            value = numeric_value(self._position().get("latitude"))
            if value is not None:
                self._last_lat = value
            return value
        return self._last_lat

    @property
    def longitude(self) -> Optional[float]:
        """Return the latest trusted longitude, holding the last good one otherwise."""
        if self._trusted():
            value = numeric_value(self._position().get("longitude"))
            if value is not None:
                self._last_lon = value
            return value
        return self._last_lon

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Expose battery, speed, odometer, and GPS-trust on the location entity."""
        basic = self.vehicle_data.get("basicVehicleStatus", {})
        additional = self.vehicle_data.get("additionalVehicleStatus", {})
        electric = additional.get("electricVehicleStatus", {})
        maintenance = additional.get("maintenanceStatus", {})
        return {
            "battery": electric.get("chargeLevel"),
            "speed": basic.get("speed"),
            "odometer": maintenance.get("odometer"),
            "gps_trusted": self._trusted(),
        }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create one GPS tracker for each configured supported vehicle."""
    runtime: ZeekrRuntimeData = entry.runtime_data
    async_add_entities(
        ZeekrTracker(runtime.coordinator, vin) for vin in runtime.api.vehicles
    )
