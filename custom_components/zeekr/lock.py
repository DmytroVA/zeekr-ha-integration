"""Central door lock (it also locks the tailgate)."""

from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .command_entity import ZeekrCommandEntity
from .coordinator import ZeekrRuntimeData
from .entity import status_value

_LOCK_PATH = "additionalVehicleStatus.drivingSafetyStatus.centralLockingStatus"


class ZeekrDoorLock(ZeekrCommandEntity, LockEntity):
    """Lock or unlock all doors (the app's ``RDL`` / ``RDU`` with ``door=all``)."""

    _attr_translation_key = "door_lock"

    def __init__(self, runtime: ZeekrRuntimeData, vin: str) -> None:
        """Bind the central lock to one vehicle."""
        super().__init__(runtime, vin)
        self._attr_unique_id = f"{vin}_door_lock"

    def _reported_value(self) -> bool:
        """True when the car reports the central locking as locked."""
        return str(status_value(self.vehicle_data, _LOCK_PATH)) == "1"

    @property
    def is_locked(self) -> bool:
        """Return the commanded state while it is pending, else the reported one."""
        return bool(self._current_value())

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock all doors."""
        await self._async_command(
            True,
            service_id="RDL",
            command="start",
            parameters=[{"key": "door", "value": "all"}],
        )

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock all doors."""
        await self._async_command(
            False,
            service_id="RDU",
            command="start",
            parameters=[{"key": "door", "value": "all"}],
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the central door lock for each vehicle."""
    runtime: ZeekrRuntimeData = entry.runtime_data
    async_add_entities(ZeekrDoorLock(runtime, vin) for vin in runtime.api.vehicles)
