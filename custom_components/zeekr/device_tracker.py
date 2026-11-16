"""GPS device tracker entities for supported Zeekr vehicles."""

from typing import Any, Dict, Optional

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .coordinator import ZeekrRuntimeData
from .entity import ZeekrVehicleEntity, boolean_value, has_v2, numeric_value, value_at


class ZeekrTracker(ZeekrVehicleEntity, TrackerEntity, RestoreEntity):
    """Expose a vehicle's latest trusted GPS point; ignore jammed/spoofed fixes.

    When ``posCanBeTrusted`` is not ``"1"`` (GPS jamming/spoofing, e.g. during
    electronic warfare) the reported coordinates are false. The tracker then holds
    the last trusted position instead of jumping the car across the globe. The
    held position is restored after a Home Assistant restart, so a restart during
    jamming does not lose the car's last known good location.
    """

    _attr_source_type = SourceType.GPS
    _attr_translation_key = "location"
    _attr_location_accuracy = 10

    def __init__(self, coordinator: Any, vin: str) -> None:
        """Bind the device tracker to one VIN and its coordinator data."""
        super().__init__(coordinator, vin)
        self._attr_unique_id = f"{vin}_location"
        self._last_lat: Optional[float] = None
        self._last_lon: Optional[float] = None

    def _position(self) -> Dict[str, Any]:
        """Return the current position sub-object, or an empty mapping."""
        if has_v2(self.vehicle_data):
            position = value_at(self.vehicle_data, "v2.basic.position")
            if isinstance(position, dict) and position.get("latitude") not in (None, ""):
                return position
        return self.vehicle_data.get("basicVehicleStatus", {}).get("position", {}) or {}

    def _trusted(self) -> bool:
        """True only when the vehicle marks its own GPS fix trustworthy."""
        return boolean_value(self._position().get("posCanBeTrusted")) is True

    def _remember_trusted_position(self) -> None:
        """Store the reported point as the held position when it is trustworthy."""
        if not self._trusted():
            return
        lat = numeric_value(self._position().get("latitude"))
        lon = numeric_value(self._position().get("longitude"))
        if lat is not None and lon is not None:
            self._last_lat = float(lat)
            self._last_lon = float(lon)

    async def async_added_to_hass(self) -> None:
        """Restore the last held position, then apply the current trusted fix."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            lat = numeric_value(last_state.attributes.get(ATTR_LATITUDE))
            lon = numeric_value(last_state.attributes.get(ATTR_LONGITUDE))
            if lat is not None and lon is not None:
                self._last_lat = float(lat)
                self._last_lon = float(lon)
        self._remember_trusted_position()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Track the newest trusted fix before the state is written."""
        self._remember_trusted_position()
        super()._handle_coordinator_update()

    @property
    def latitude(self) -> Optional[float]:
        """Return the last trusted latitude."""
        return self._last_lat

    @property
    def longitude(self) -> Optional[float]:
        """Return the last trusted longitude."""
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
