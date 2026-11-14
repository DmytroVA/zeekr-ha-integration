"""Shared account runtime and coordinated vehicle status updates."""

from dataclasses import dataclass, field
import logging
from typing import Any, Dict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ZeekrApi, ZeekrApiError, ZeekrAuthError
from .const import DEFAULT_AC_DURATION_MIN, DEFAULT_AC_TEMP, DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class VehicleStatusCoordinator(DataUpdateCoordinator[Dict[str, Dict[str, Any]]]):
    """Poll all supported vehicles once and share each response with entities."""

    def __init__(self, hass: HomeAssistant, api: ZeekrApi) -> None:
        """Create the account coordinator with the configured 60-second interval."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.api = api

    async def _async_update_data(self) -> Dict[str, Dict[str, Any]]:
        """Fetch the newest status for every configured supported vehicle."""
        result: Dict[str, Dict[str, Any]] = {}
        try:
            for vin in self.api.vehicles:
                result[vin] = await self.api.async_get_vehicle_status(vin)
        except ZeekrAuthError as err:
            raise ConfigEntryAuthFailed("Zeekr credentials expired") from err
        except ZeekrApiError as err:
            raise UpdateFailed("Unable to update Zeekr vehicle status") from err
        return result

    async def async_refresh_vehicle(self, vin: str) -> None:
        """Refresh one vehicle immediately and preserve the other vehicles' data."""
        status = await self.api.async_get_vehicle_status(vin)
        updated = dict(self.data or {})
        updated[vin] = status
        self.async_set_updated_data(updated)


@dataclass
class ZeekrRuntimeData:
    """Runtime objects shared by platforms, services, and the live-video card."""

    api: ZeekrApi
    coordinator: VehicleStatusCoordinator
    # Per-VIN local climate convenience settings, not reported by the vehicle.
    climate_settings: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def climate_setting(self, vin: str) -> Dict[str, Any]:
        """Return (creating if needed) the local climate settings for one vehicle."""
        return self.climate_settings.setdefault(
            vin,
            {"temp": DEFAULT_AC_TEMP, "duration": DEFAULT_AC_DURATION_MIN},
        )


def get_runtime(hass: HomeAssistant) -> ZeekrRuntimeData:
    """Return the active Zeekr account runtime or raise a clear setup error."""
    runtimes = hass.data.get(DOMAIN, {})
    runtimes = {k: v for k, v in runtimes.items() if isinstance(v, ZeekrRuntimeData)}
    if not runtimes:
        raise RuntimeError("Zeekr integration is not configured")
    return next(iter(runtimes.values()))


def start_reauth(hass: HomeAssistant) -> None:
    """Start the configured account's UI reauthentication flow."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if entries:
        entries[0].async_start_reauth(hass)
