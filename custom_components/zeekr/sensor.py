"""Vehicle sensor entities from the current Zeekr status endpoint."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

import json

from .entity import ZeekrVehicleEntity, numeric_value, status_value, value_at
from .coordinator import ZeekrRuntimeData
from .fields import RAW_FIELDS

# Paths already surfaced by a typed binary_sensor; excluded from raw coverage.
_BINARY_PATHS = {
    "additionalVehicleStatus.electricVehicleStatus.isCharging",
    "additionalVehicleStatus.electricVehicleStatus.hvBatteryOptimizeFlag",
    "additionalVehicleStatus.electricVehicleStatus.isPluggedIn",
    "additionalVehicleStatus.drivingSafetyStatus.doorOpenStatusDriver",
    "additionalVehicleStatus.drivingSafetyStatus.doorOpenStatusPassenger",
    "additionalVehicleStatus.drivingSafetyStatus.doorOpenStatusDriverRear",
    "additionalVehicleStatus.drivingSafetyStatus.doorOpenStatusPassengerRear",
    "additionalVehicleStatus.drivingSafetyStatus.trunkOpenStatus",
    "additionalVehicleStatus.drivingSafetyStatus.engineHoodOpenStatus",
}


@dataclass(frozen=True)
class ZeekrSensorSpec:
    """A status field mapped to a sensor, with optional invalid-value filtering."""

    description: SensorEntityDescription
    path: str
    numeric: bool = True
    invalid: Tuple[float, ...] = ()
    value_map: Optional[Dict[str, str]] = None
    # False for fields whose v2.0 encoding differs from the v1.0 one this sensor
    # has always reported (keeps existing states and automations stable).
    prefer_v2: bool = True


# Original keys below are preserved verbatim so existing entity unique_ids
# (``{vin}_{key}``), history, and dashboards keep working after migration.
SENSOR_FIELDS: List[ZeekrSensorSpec] = [
    ZeekrSensorSpec(
        SensorEntityDescription(
            key="distance_to_empty",
            name="Distance to Empty",
            native_unit_of_measurement=UnitOfLength.KILOMETERS,
            device_class=SensorDeviceClass.DISTANCE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        "additionalVehicleStatus.electricVehicleStatus.distanceToEmptyOnBatteryOnly",
    ),
    ZeekrSensorSpec(
        SensorEntityDescription(
            key="battery",
            name="Battery",
            native_unit_of_measurement=PERCENTAGE,
            device_class=SensorDeviceClass.BATTERY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        "additionalVehicleStatus.electricVehicleStatus.chargeLevel",
    ),
    ZeekrSensorSpec(
        SensorEntityDescription(
            key="interior_temperature",
            name="Interior Temperature",
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        "additionalVehicleStatus.climateStatus.interiorTemp",
    ),
    ZeekrSensorSpec(
        SensorEntityDescription(key="engine_status", name="Engine Status"),
        "basicVehicleStatus.engineStatus",
        numeric=False,
        prefer_v2=False,
    ),
    ZeekrSensorSpec(
        SensorEntityDescription(
            key="tire_pressure_front_left",
            name="Tire Pressure Front Left",
            device_class=SensorDeviceClass.PRESSURE,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=0,
            native_unit_of_measurement=UnitOfPressure.CBAR,
        ),
        "additionalVehicleStatus.maintenanceStatus.tyreStatusDriver",
    ),
    ZeekrSensorSpec(
        SensorEntityDescription(
            key="tire_pressure_front_right",
            name="Tire Pressure Front Right",
            device_class=SensorDeviceClass.PRESSURE,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=0,
            native_unit_of_measurement=UnitOfPressure.CBAR,
        ),
        "additionalVehicleStatus.maintenanceStatus.tyreStatusPassenger",
    ),
    ZeekrSensorSpec(
        SensorEntityDescription(
            key="tire_pressure_rear_left",
            name="Tire Pressure Rear Left",
            device_class=SensorDeviceClass.PRESSURE,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=0,
            native_unit_of_measurement=UnitOfPressure.CBAR,
        ),
        "additionalVehicleStatus.maintenanceStatus.tyreStatusDriverRear",
    ),
    ZeekrSensorSpec(
        SensorEntityDescription(
            key="tire_pressure_rear_right",
            name="Tire Pressure Rear Right",
            device_class=SensorDeviceClass.PRESSURE,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=0,
            native_unit_of_measurement=UnitOfPressure.CBAR,
        ),
        "additionalVehicleStatus.maintenanceStatus.tyreStatusPassengerRear",
    ),
    ZeekrSensorSpec(
        SensorEntityDescription(
            key="distance_to_service",
            name="Distance to Service",
            native_unit_of_measurement=UnitOfLength.KILOMETERS,
            device_class=SensorDeviceClass.DISTANCE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        "additionalVehicleStatus.maintenanceStatus.distanceToService",
    ),
    ZeekrSensorSpec(
        SensorEntityDescription(
            key="odometer",
            name="Odometer",
            native_unit_of_measurement=UnitOfLength.KILOMETERS,
            device_class=SensorDeviceClass.DISTANCE,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        "additionalVehicleStatus.maintenanceStatus.odometer",
    ),
    ZeekrSensorSpec(
        SensorEntityDescription(
            key="main_battery_voltage",
            name="Main Battery Voltage",
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        "additionalVehicleStatus.maintenanceStatus.mainBatteryStatus.voltage",
    ),
    ZeekrSensorSpec(
        SensorEntityDescription(
            key="average_power_consumption",
            name="Average Power Consumption",
            native_unit_of_measurement="kWh/100 km",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        "additionalVehicleStatus.electricVehicleStatus.averPowerConsumption",
    ),
    ZeekrSensorSpec(
        SensorEntityDescription(
            key="central_locking_status",
            name="Central Locking Status",
            translation_key="central_locking_status",
            device_class=SensorDeviceClass.ENUM,
            options=["unlocked", "locked"],
        ),
        "additionalVehicleStatus.drivingSafetyStatus.centralLockingStatus",
        numeric=False,
        value_map={"0": "unlocked", "1": "locked"},
    ),
    ZeekrSensorSpec(
        SensorEntityDescription(
            key="electric_park_brake_status",
            name="Electric Park Brake Status",
            translation_key="electric_park_brake_status",
            device_class=SensorDeviceClass.ENUM,
            options=["released", "engaged"],
        ),
        "additionalVehicleStatus.drivingSafetyStatus.electricParkBrakeStatus",
        numeric=False,
        value_map={"0": "released", "1": "engaged"},
    ),
    # ---- New sensors added by this integration (new keys, new unique_ids) ----
    ZeekrSensorSpec(
        SensorEntityDescription(
            key="exterior_temperature",
            name="Exterior Temperature",
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            # Neither status document carries exteriorTemp: always unknown.
            entity_registry_enabled_default=False,
        ),
        "additionalVehicleStatus.climateStatus.exteriorTemp",
    ),
    ZeekrSensorSpec(
        SensorEntityDescription(
            key="speed",
            name="Speed",
            native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
            device_class=SensorDeviceClass.SPEED,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        "basicVehicleStatus.speed",
    ),
    ZeekrSensorSpec(
        SensorEntityDescription(
            key="charge_current",
            name="Charge Current",
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        "additionalVehicleStatus.electricVehicleStatus.chargeIAct",
    ),
    ZeekrSensorSpec(
        SensorEntityDescription(
            key="charge_voltage",
            name="Charge Voltage",
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        "additionalVehicleStatus.electricVehicleStatus.chargeUAct",
    ),
    ZeekrSensorSpec(
        SensorEntityDescription(
            key="time_to_full_charge",
            name="Time to Full Charge",
            native_unit_of_measurement=UnitOfTime.MINUTES,
            device_class=SensorDeviceClass.DURATION,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        "additionalVehicleStatus.electricVehicleStatus.timeToFullyCharged",
        invalid=(2047,),
    ),
    ZeekrSensorSpec(
        SensorEntityDescription(
            key="tire_temp_front_left",
            name="Tire Temperature Front Left",
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        "additionalVehicleStatus.maintenanceStatus.tyreTempDriver",
    ),
    ZeekrSensorSpec(
        SensorEntityDescription(
            key="tire_temp_front_right",
            name="Tire Temperature Front Right",
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        "additionalVehicleStatus.maintenanceStatus.tyreTempPassenger",
    ),
    ZeekrSensorSpec(
        SensorEntityDescription(
            key="tire_temp_rear_left",
            name="Tire Temperature Rear Left",
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        "additionalVehicleStatus.maintenanceStatus.tyreTempDriverRear",
    ),
    ZeekrSensorSpec(
        SensorEntityDescription(
            key="tire_temp_rear_right",
            name="Tire Temperature Rear Right",
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        "additionalVehicleStatus.maintenanceStatus.tyreTempPassengerRear",
    ),
    ZeekrSensorSpec(
        SensorEntityDescription(
            key="trip_meter_1",
            name="Trip Meter 1",
            native_unit_of_measurement=UnitOfLength.KILOMETERS,
            device_class=SensorDeviceClass.DISTANCE,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        "additionalVehicleStatus.runningStatus.tripMeter1",
    ),
    ZeekrSensorSpec(
        SensorEntityDescription(
            key="trip_meter_2",
            name="Trip Meter 2",
            native_unit_of_measurement=UnitOfLength.KILOMETERS,
            device_class=SensorDeviceClass.DISTANCE,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        "additionalVehicleStatus.runningStatus.tripMeter2",
    ),
    ZeekrSensorSpec(
        SensorEntityDescription(
            key="days_to_service",
            name="Days to Service",
            native_unit_of_measurement=UnitOfTime.DAYS,
            device_class=SensorDeviceClass.DURATION,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        "additionalVehicleStatus.maintenanceStatus.daysToService",
    ),
    ZeekrSensorSpec(
        SensorEntityDescription(
            key="interior_pm25",
            name="Interior PM2.5",
            device_class=SensorDeviceClass.PM25,
            native_unit_of_measurement="µg/m³",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        "additionalVehicleStatus.pollutionStatus.interiorPM25",
    ),
]


class ZeekrSensor(ZeekrVehicleEntity, SensorEntity):
    """Expose one typed value from a vehicle status response as a sensor."""

    entity_description: SensorEntityDescription

    def __init__(self, coordinator: Any, vin: str, spec: ZeekrSensorSpec) -> None:
        """Bind the sensor description and provider field path to one vehicle."""
        super().__init__(coordinator, vin)
        self.entity_description = spec.description
        self._path = spec.path
        self._prefer_v2 = spec.prefer_v2
        self._numeric = spec.numeric
        self._invalid = spec.invalid
        self._value_map = spec.value_map
        self._attr_unique_id = f"{vin}_{spec.description.key}"

    @property
    def native_value(self) -> Any:
        """Return the current provider field in a Home Assistant-compatible type."""
        if self._prefer_v2:
            value = status_value(self.vehicle_data, self._path)
        else:
            value = value_at(self.vehicle_data, self._path)
        if self._numeric:
            number = numeric_value(value)
            if number is not None and number in self._invalid:
                return None
            return number
        if isinstance(value, bool):
            return "On" if value else "Off"
        if value is None or value == "":
            return None
        text = str(value)
        if self._value_map:
            # Enum sensors: states are stable language-neutral keys translated by
            # the frontend; a code the map does not know is reported as unknown.
            return self._value_map.get(text)
        return text


class ZeekrLastUpdateSensor(ZeekrVehicleEntity, SensorEntity):
    """Timestamp of the vehicle's last successful cloud upload (top-level updateTime).

    This is the honest data-freshness signal — unlike Home Assistant's own poll
    time it reflects when the car last reached the cloud. During GPS jamming /
    clock skew the car may stop uploading, so this value can lag well behind now.
    """

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_name = "Last Cloud Update"

    def __init__(self, coordinator: Any, vin: str) -> None:
        """Bind the last-upload timestamp sensor to one vehicle."""
        super().__init__(coordinator, vin)
        self._attr_unique_id = f"{vin}_last_cloud_update"

    @property
    def native_value(self) -> Optional[datetime]:
        """Convert the millisecond epoch ``updateTime`` to an aware datetime."""
        stamps = [
            numeric_value(value_at(self.vehicle_data, path))
            for path in ("updateTime", "v2.updateTime")
        ]
        ms = max((stamp for stamp in stamps if stamp), default=None)
        if ms is None or ms <= 0:
            return None
        try:
            return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None


class ZeekrRawSensor(ZeekrVehicleEntity, SensorEntity):
    """Diagnostic passthrough for any status field without a dedicated sensor.

    Exhaustive coverage: every field the Zeekr app's status model defines is
    surfaced here (as a raw string, under the Diagnostic category) so no datum the
    cloud returns is hidden, even codes and nested JSON whose meaning is unknown.

    Disabled by default: most of these fields are empty or never change on a given
    car. Enable the ones you need from the device page; the diagnostics download
    lists which fields the cloud actually fills and how often they change.
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: Any, vin: str, key: str, path: str, name: str) -> None:
        """Bind a raw diagnostic sensor to one status field of one vehicle."""
        super().__init__(coordinator, vin)
        self.entity_description = SensorEntityDescription(
            key=key, name=name, entity_category=EntityCategory.DIAGNOSTIC
        )
        self._path = path
        self._attr_unique_id = f"{vin}_raw_{key}"

    @property
    def native_value(self) -> Any:
        """Return the raw field value as a short string, or None when absent."""
        value = status_value(self.vehicle_data, self._path)
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            try:
                value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            except (TypeError, ValueError):
                value = str(value)
        text = str(value)
        return text[:255] if len(text) > 255 else text


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the sensor entities for every supported vehicle."""
    runtime: ZeekrRuntimeData = entry.runtime_data
    covered = {spec.path for spec in SENSOR_FIELDS} | _BINARY_PATHS
    entities: list = [
        ZeekrSensor(runtime.coordinator, vin, spec)
        for vin in runtime.api.vehicles
        for spec in SENSOR_FIELDS
    ]
    entities.extend(
        ZeekrLastUpdateSensor(runtime.coordinator, vin)
        for vin in runtime.api.vehicles
    )
    entities.extend(
        ZeekrRawSensor(runtime.coordinator, vin, key, path, name)
        for vin in runtime.api.vehicles
        for key, path, name in RAW_FIELDS
        if path not in covered
    )
    async_add_entities(entities)
