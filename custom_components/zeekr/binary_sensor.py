"""Binary sensor entities for plug, openings, lights, activity, and GPS-jamming detection."""

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

from .coordinator import POWER_MODE_PATH, ZeekrRuntimeData
from .entity import ZeekrVehicleEntity, boolean_value, value_at

_POS_TRUST = "basic.position.posCanBeTrusted"

# Keys are part of unique_ids and must not change.
BINARY_SENSOR_FIELDS: List[Tuple[BinarySensorEntityDescription, str]] = [
    (
        BinarySensorEntityDescription(
            key="hv_battery_optimization",
            translation_key="hv_battery_optimization",
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        "electricVehicleStatus.hvBatteryOptimizeFlag",
    ),
    (
        BinarySensorEntityDescription(
            key="plugged_in",
            translation_key="plugged_in",
            device_class=BinarySensorDeviceClass.PLUG,
        ),
        "electricVehicleStatus.isPluggedIn",
    ),
    (
        BinarySensorEntityDescription(
            key="door_front_left",
            translation_key="door_front_left",
            device_class=BinarySensorDeviceClass.DOOR,
        ),
        "drivingSafetyStatus.doorOpenStatusDriver",
    ),
    (
        BinarySensorEntityDescription(
            key="door_front_right",
            translation_key="door_front_right",
            device_class=BinarySensorDeviceClass.DOOR,
        ),
        "drivingSafetyStatus.doorOpenStatusPassenger",
    ),
    (
        BinarySensorEntityDescription(
            key="door_rear_left",
            translation_key="door_rear_left",
            device_class=BinarySensorDeviceClass.DOOR,
        ),
        "drivingSafetyStatus.doorOpenStatusDriverRear",
    ),
    (
        BinarySensorEntityDescription(
            key="door_rear_right",
            translation_key="door_rear_right",
            device_class=BinarySensorDeviceClass.DOOR,
        ),
        "drivingSafetyStatus.doorOpenStatusPassengerRear",
    ),
    (
        BinarySensorEntityDescription(
            key="trunk",
            translation_key="trunk",
            device_class=BinarySensorDeviceClass.DOOR,
        ),
        "drivingSafetyStatus.trunkOpenStatus",
    ),
    (
        BinarySensorEntityDescription(
            key="hood",
            translation_key="hood",
            device_class=BinarySensorDeviceClass.DOOR,
        ),
        "drivingSafetyStatus.engineHoodOpenStatus",
    ),
    (
        BinarySensorEntityDescription(
            key="trunk_lock",
            translation_key="trunk_lock",
            device_class=BinarySensorDeviceClass.LOCK,
        ),
        "drivingSafetyStatus.trunkLockStatus",
    ),
    (
        BinarySensorEntityDescription(
            key="low_beam", translation_key="low_beam", device_class=BinarySensorDeviceClass.LIGHT
        ),
        "runningStatus.loBeam",
    ),
    (
        BinarySensorEntityDescription(
            key="high_beam", translation_key="high_beam", device_class=BinarySensorDeviceClass.LIGHT
        ),
        "runningStatus.hiBeam",
    ),
    (
        BinarySensorEntityDescription(
            key="hazard_lights",
            translation_key="hazard_lights",
            device_class=BinarySensorDeviceClass.LIGHT,
        ),
        "runningStatus.hwl",
    ),
    (
        BinarySensorEntityDescription(
            key="park_comfort", translation_key="park_comfort", icon="mdi:sofa"
        ),
        "basic.parkComfortState",
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
        value = boolean_value(value_at(self.vehicle_data, self._path)) is True
        # The car reports locks as 1 = locked; Home Assistant's lock class is on = unlocked.
        if self.entity_description.device_class == BinarySensorDeviceClass.LOCK:
            return not value
        return value

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
    _attr_translation_key = "gps_spoofed"

    def __init__(self, coordinator: Any, vin: str) -> None:
        """Bind the GPS-trust problem sensor to one vehicle."""
        super().__init__(coordinator, vin)
        self._attr_unique_id = f"{vin}_gps_spoofed"

    @property
    def is_on(self) -> bool:
        """Return True when the reported position is not trustworthy."""
        return boolean_value(value_at(self.vehicle_data, _POS_TRUST)) is not True

    @property
    def available(self) -> bool:
        """Only report once the vehicle actually sends a trust flag."""
        trust = value_at(self.vehicle_data, _POS_TRUST)
        return super().available and trust not in (None, "")


class ZeekrActiveSensor(ZeekrVehicleEntity, BinarySensorEntity):
    """On while the car is powered up (awake), from ``temStatus.powerMode``.

    The car reports ``1`` while it is awake (driving, someone inside, a remote
    command running) and ``0`` once it falls asleep. The same signal speeds up
    polling: see ``VehicleStatusCoordinator``.
    """

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_translation_key = "active"

    def __init__(self, coordinator: Any, vin: str) -> None:
        """Bind the power-mode sensor to one vehicle."""
        super().__init__(coordinator, vin)
        self._attr_unique_id = f"{vin}_active"

    def _power_mode(self) -> Any:
        """Return the raw power mode code, or None when not reported."""
        return value_at(self.vehicle_data, POWER_MODE_PATH)

    @property
    def is_on(self) -> bool:
        """Return True while the car reports power mode ``1``."""
        return str(self._power_mode()) == "1"

    @property
    def available(self) -> bool:
        """Only report once the status document carries the power mode."""
        return super().available and self._power_mode() not in (None, "")


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
    entities.extend(
        ZeekrActiveSensor(runtime.coordinator, vin) for vin in runtime.api.vehicles
    )
    async_add_entities(entities)
