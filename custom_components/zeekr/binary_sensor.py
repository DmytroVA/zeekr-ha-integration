"""Binary sensor entities for charging, openings, and GPS-jamming detection."""

from typing import Any, List, Tuple

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import ZeekrRuntimeData
from .entity import ZeekrVehicleEntity, boolean_value, value_at

_POS_TRUST = "basicVehicleStatus.position.posCanBeTrusted"

# First two keys are preserved from the superseded integration (unique_ids).
BINARY_SENSOR_FIELDS: List[Tuple[BinarySensorEntityDescription, str]] = [
    (
        BinarySensorEntityDescription(
            key="charging",
            name="Charging",
            device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        ),
        "additionalVehicleStatus.electricVehicleStatus.isCharging",
    ),
    (
        BinarySensorEntityDescription(
            key="hv_battery_optimization",
            name="HV Battery Optimization",
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        "additionalVehicleStatus.electricVehicleStatus.hvBatteryOptimizeFlag",
    ),
    (
        BinarySensorEntityDescription(
            key="plugged_in",
            name="Plugged In",
            device_class=BinarySensorDeviceClass.PLUG,
        ),
        "additionalVehicleStatus.electricVehicleStatus.isPluggedIn",
    ),
    (
        BinarySensorEntityDescription(
            key="door_front_left",
            name="Door Front Left",
            device_class=BinarySensorDeviceClass.DOOR,
        ),
        "additionalVehicleStatus.drivingSafetyStatus.doorOpenStatusDriver",
    ),
    (
        BinarySensorEntityDescription(
            key="door_front_right",
            name="Door Front Right",
            device_class=BinarySensorDeviceClass.DOOR,
        ),
        "additionalVehicleStatus.drivingSafetyStatus.doorOpenStatusPassenger",
    ),
    (
        BinarySensorEntityDescription(
            key="door_rear_left",
            name="Door Rear Left",
            device_class=BinarySensorDeviceClass.DOOR,
        ),
        "additionalVehicleStatus.drivingSafetyStatus.doorOpenStatusDriverRear",
    ),
    (
        BinarySensorEntityDescription(
            key="door_rear_right",
            name="Door Rear Right",
            device_class=BinarySensorDeviceClass.DOOR,
        ),
        "additionalVehicleStatus.drivingSafetyStatus.doorOpenStatusPassengerRear",
    ),
    (
        BinarySensorEntityDescription(
            key="trunk",
            name="Trunk",
            device_class=BinarySensorDeviceClass.DOOR,
        ),
        "additionalVehicleStatus.drivingSafetyStatus.trunkOpenStatus",
    ),
    (
        BinarySensorEntityDescription(
            key="hood",
            name="Hood",
            device_class=BinarySensorDeviceClass.DOOR,
        ),
        "additionalVehicleStatus.drivingSafetyStatus.engineHoodOpenStatus",
    ),
]


class ZeekrBinarySensor(ZeekrVehicleEntity, BinarySensorEntity):
    """Represent a supported vehicle's boolean status as a binary sensor."""

    entity_description: BinarySensorEntityDescription

    def __init__(
        self,
        coordinator: Any,
        vin: str,
        description: BinarySensorEntityDescription,
        path: str,
    ) -> None:
        """Bind the binary sensor description and provider field to one vehicle."""
        super().__init__(coordinator, vin)
        self.entity_description = description
        self._path = path
        self._attr_unique_id = f"{vin}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return the parsed provider flag; availability tracks missing values."""
        return boolean_value(value_at(self.vehicle_data, self._path)) is True

    @property
    def available(self) -> bool:
        """Keep a missing or unknown provider flag from appearing as an off state."""
        value = boolean_value(value_at(self.vehicle_data, self._path))
        return super().available and value is not None


class ZeekrGpsSpoofSensor(ZeekrVehicleEntity, BinarySensorEntity):
    """On when the vehicle reports its own GPS position as untrusted.

    The status payload carries ``posCanBeTrusted``; the car sets it to ``0`` when
    its GNSS fix is being jammed or spoofed (e.g. electronic warfare). While this
    is on, the device tracker holds the last trusted point instead of following
    the false position.
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_name = "GPS Spoofed"

    def __init__(self, coordinator: Any, vin: str) -> None:
        """Bind the GPS-trust problem sensor to one vehicle."""
        super().__init__(coordinator, vin)
        self._attr_unique_id = f"{vin}_gps_spoofed"

    @property
    def is_on(self) -> bool:
        """Return True when the reported position is not trustworthy."""
        return str(value_at(self.vehicle_data, _POS_TRUST)) != "1"

    @property
    def available(self) -> bool:
        """Only report once the vehicle actually sends a trust flag."""
        trust = value_at(self.vehicle_data, _POS_TRUST)
        return super().available and trust not in (None, "")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create binary sensor entities for each supported vehicle."""
    runtime: ZeekrRuntimeData = entry.runtime_data
    entities: list = [
        ZeekrBinarySensor(runtime.coordinator, vin, description, path)
        for vin in runtime.api.vehicles
        for description, path in BINARY_SENSOR_FIELDS
    ]
    entities.extend(
        ZeekrGpsSpoofSensor(runtime.coordinator, vin)
        for vin in runtime.api.vehicles
    )
    async_add_entities(entities)
