"""Diagnostics support that redacts location and identifiers."""

from __future__ import annotations

import copy
from typing import Any, Dict

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .coordinator import ZeekrRuntimeData

TO_REDACT = {
    "vin",
    "latitude",
    "longitude",
    "access_token",
    "refresh_token",
    "jwt_token",
    "legacy_access_token",
    "legacy_refresh_token",
    "device_id",
    "client_id",
    "user_id",
    "mobile",
}


def _redact_status(status: Dict[str, Any]) -> Dict[str, Any]:
    """Redact position coordinates inside a vehicle status payload."""
    data = copy.deepcopy(status)
    position = data.get("basicVehicleStatus", {}).get("position")
    if isinstance(position, dict):
        for key in ("latitude", "longitude"):
            if key in position:
                position[key] = "**REDACTED**"
    return data


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> Dict[str, Any]:
    """Return redacted account and per-vehicle status for support purposes."""
    runtime: ZeekrRuntimeData = entry.runtime_data
    vehicles = {
        f"vehicle_{index}": _redact_status(status)
        for index, (_vin, status) in enumerate(
            (runtime.coordinator.data or {}).items()
        )
    }
    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "vehicle_count": len(runtime.api.vehicles),
        "vehicles": vehicles,
    }
