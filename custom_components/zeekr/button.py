"""Refresh and remote-command buttons for configured Zeekr vehicles."""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import ZeekrApiError, ZeekrAuthError
from .commands import async_run_command
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


def _rapid(key: str) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    """Rapid warming (``RW``) / rapid cooling (``RC``): the app's own one-press
    presets that pre-condition the cabin as fast as possible for the run time."""

    def _build(setting: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "service_id": "ZAF",
            "command": "",
            "parameters": [
                {"key": key, "value": True},
                {"key": f"{key}.duration", "value": int(setting.get("duration", 15))},
            ],
        }

    return _build


def _horn_light(kind: str) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    """Find-my-car signal (``RHL``); ``kind`` is the app's ``rhl`` value.

    The app offers two modes: ``light-flash`` (闪灯, lights only) and
    ``horn-light-flash`` (闪灯鸣笛, lights and horn).
    """

    def _build(_setting: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "service_id": "RHL",
            "command": "",
            "parameters": [{"key": "rhl", "value": kind}],
        }

    return _build


def _trunk_unlock(_setting: Dict[str, Any]) -> Dict[str, Any]:
    """Release the tailgate latch (``RDU`` + ``target=trunk``), as the app does.

    The tailgate is not raised: it is then opened with its own button, and the
    car locks it again by itself if nobody opens it. The car refuses a separate
    tailgate lock; locking the doors locks the tailgate too.
    """
    return {
        "service_id": "RDU",
        "command": "start",
        "parameters": [{"key": "target", "value": "trunk"}],
    }


COMMAND_BUTTONS: List[ZeekrCommandSpec] = [
    ZeekrCommandSpec("rapid_warm", "Rapid Warming", _rapid("RW"), False),
    ZeekrCommandSpec("rapid_cool", "Rapid Cooling", _rapid("RC"), False),
    ZeekrCommandSpec("trunk_unlock", "Unlock Trunk", _trunk_unlock, False),
    # Signal: built from the app's code, not yet verified on a car, so these are
    # disabled by default.
    ZeekrCommandSpec("flash_lights", "Flash Lights", _horn_light("light-flash")),
    ZeekrCommandSpec(
        "flash_lights_horn", "Flash Lights & Horn", _horn_light("horn-light-flash")
    ),
]

# Buttons of earlier versions that were replaced or whose command was wrong;
# their registry entries are removed by the config-entry migration (current
# buttons with the same key are then registered afresh).
REMOVED_BUTTON_KEYS = (
    "ac_start",
    "ac_stop",
    "defrost_start",
    "defrost_stop",
    "cabin_vent_start",
    "cabin_vent_stop",
    "rapid_cool",
    "rapid_warm",
    "flash_horn",
    "trunk_open",
)


class ZeekrCommandButton(ZeekrVehicleEntity, ButtonEntity):
    """Send one remote command built from the reverse-engineered app model."""

    def __init__(self, runtime: ZeekrRuntimeData, vin: str, spec: ZeekrCommandSpec) -> None:
        """Bind a command button to one vehicle and the shared account API client."""
        super().__init__(runtime.coordinator, vin)
        self._runtime = runtime
        self._spec = spec
        self._attr_name = spec.name
        self._attr_entity_registry_enabled_default = not spec.experimental
        self._attr_unique_id = f"{vin}_cmd_{spec.key}"

    async def async_press(self) -> None:
        """Send the command and fail with the car's reason if it is not executed."""
        setting = self._runtime.climate_setting(self.vin)
        command = self._spec.build(setting)
        await async_run_command(
            self.hass,
            self._runtime,
            self.vin,
            service_id=command["service_id"],
            command=command.get("command"),
            parameters=command.get("parameters"),
            duration=command.get("duration"),
        )


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
