"""Refresh and remote-command buttons for configured Zeekr vehicles."""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import ZeekrApiError, ZeekrAuthError
from .const import RAPID_COOL_TEMP, RAPID_WARM_TEMP
from .coordinator import ZeekrRuntimeData, start_reauth
from .entity import ZeekrVehicleEntity


class ZeekrRefreshButton(ZeekrVehicleEntity, ButtonEntity):
    """Request an immediate status refresh for the parent vehicle."""

    _attr_name = "Refresh"

    def __init__(self, coordinator: Any, vin: str) -> None:
        """Bind a stateless refresh button to one vehicle's status coordinator."""
        super().__init__(coordinator, vin)
        self._attr_unique_id = f"{vin}_refresh"

    async def async_press(self) -> None:
        """Refresh this vehicle immediately and surface API failures to Home Assistant."""
        try:
            await self.coordinator.async_refresh_vehicle(self.vin)
        except ZeekrAuthError as err:
            start_reauth(self.hass)
            raise HomeAssistantError("Zeekr credentials expired") from err
        except ZeekrApiError as err:
            raise HomeAssistantError("Unable to refresh Zeekr vehicle status") from err


@dataclass(frozen=True)
class ZeekrCommandSpec:
    """A remote command exposed as a button, built from the extracted app model."""

    key: str
    name: str
    # (setting) -> {service_id, command, parameters, duration}
    build: Callable[[Dict[str, Any]], Dict[str, Any]]
    experimental: bool = True


def _ac_start(setting: Dict[str, Any]) -> Dict[str, Any]:
    temp = setting.get("temp", 22.0)
    duration = int(setting.get("duration", 15))
    return {
        "service_id": "ZAF",
        "command": "",
        "parameters": [
            {"key": "AC", "value": True},
            {"key": "AC.temp", "value": str(temp)},
            {"key": "AC.duration", "value": duration},
        ],
    }


def _ac_stop(_setting: Dict[str, Any]) -> Dict[str, Any]:
    return {"service_id": "ZAF", "command": "", "parameters": [{"key": "AC", "value": False}]}


def _rapid(temp: float) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    def _build(setting: Dict[str, Any]) -> Dict[str, Any]:
        duration = int(setting.get("duration", 15))
        return {
            "service_id": "ZAF",
            "command": "",
            "parameters": [
                {"key": "AC", "value": True},
                {"key": "AC.temp", "value": str(temp)},
                {"key": "AC.duration", "value": duration},
            ],
        }

    return _build


def _defrost_start(_setting: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "service_id": "ZAF",
        "command": "",
        "parameters": [
            {"key": "DF", "value": True},
            {"key": "DF.level", "value": "2"},
            {"key": "DF.duration", "value": 15},
        ],
    }


def _defrost_stop(_setting: Dict[str, Any]) -> Dict[str, Any]:
    return {"service_id": "ZAF", "command": "", "parameters": [{"key": "DF", "value": False}]}


def _cabin_vent(start: bool) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    def _build(setting: Dict[str, Any]) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "service_id": "RCC",
            "command": "start" if start else "stop",
            "parameters": [
                {"key": "rcc.conditioner", "value": "50"},
                {"key": "rcc.ventilation", "value": "0"},
            ],
        }
        if start:
            # RCC schedules in six-second units in the app model.
            result["duration"] = int(setting.get("duration", 15)) * 6
        return result

    return _build


def _flash_horn(_setting: Dict[str, Any]) -> Dict[str, Any]:
    return {"service_id": "RHL", "command": "", "parameters": [{"key": "rhl", "value": "1"}]}


def _trunk_open(_setting: Dict[str, Any]) -> Dict[str, Any]:
    return {"service_id": "RTU", "command": "start", "parameters": []}


COMMAND_BUTTONS: List[ZeekrCommandSpec] = [
    ZeekrCommandSpec("ac_start", "AC Start (experimental)", _ac_start),
    ZeekrCommandSpec("ac_stop", "AC Stop (experimental)", _ac_stop),
    ZeekrCommandSpec("rapid_cool", "Rapid Cool (experimental)", _rapid(RAPID_COOL_TEMP)),
    ZeekrCommandSpec("rapid_warm", "Rapid Warm (experimental)", _rapid(RAPID_WARM_TEMP)),
    ZeekrCommandSpec("defrost_start", "Defrost Start (experimental)", _defrost_start),
    ZeekrCommandSpec("defrost_stop", "Defrost Stop (experimental)", _defrost_stop),
    ZeekrCommandSpec(
        "cabin_vent_start", "Cabin Ventilation Start (experimental)", _cabin_vent(True)
    ),
    ZeekrCommandSpec(
        "cabin_vent_stop", "Cabin Ventilation Stop (experimental)", _cabin_vent(False)
    ),
    ZeekrCommandSpec("flash_horn", "Flash & Horn (experimental)", _flash_horn),
    ZeekrCommandSpec("trunk_open", "Trunk Open (experimental)", _trunk_open),
]


class ZeekrCommandButton(ZeekrVehicleEntity, ButtonEntity):
    """Send one remote command built from the reverse-engineered app model."""

    _attr_entity_registry_enabled_default = False

    def __init__(self, runtime: ZeekrRuntimeData, vin: str, spec: ZeekrCommandSpec) -> None:
        """Bind a command button to one vehicle and the shared account API client."""
        super().__init__(runtime.coordinator, vin)
        self._runtime = runtime
        self._spec = spec
        self._attr_name = spec.name
        self._attr_unique_id = f"{vin}_cmd_{spec.key}"

    async def async_press(self) -> None:
        """Build and send the command, then refresh and surface any API failure."""
        setting = self._runtime.climate_setting(self.vin)
        command = self._spec.build(setting)
        try:
            await self._runtime.api.async_remote_control(
                self.vin,
                service_id=command["service_id"],
                command=command.get("command"),
                parameters=command.get("parameters"),
                duration=command.get("duration"),
            )
            await self.coordinator.async_refresh_vehicle(self.vin)
        except ZeekrAuthError as err:
            start_reauth(self.hass)
            raise HomeAssistantError("Zeekr credentials expired") from err
        except ZeekrApiError as err:
            raise HomeAssistantError(
                f"Zeekr rejected command {self._spec.key}: {err}"
            ) from err


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the refresh button and experimental command buttons per vehicle."""
    runtime: ZeekrRuntimeData = entry.runtime_data
    entities: list = [
        ZeekrRefreshButton(runtime.coordinator, vin) for vin in runtime.api.vehicles
    ]
    entities.extend(
        ZeekrCommandButton(runtime, vin, spec)
        for vin in runtime.api.vehicles
        for spec in COMMAND_BUTTONS
    )
    async_add_entities(entities)
