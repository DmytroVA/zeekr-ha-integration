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
    for position in (data.get("basic", {}).get("position"),):
        if isinstance(position, dict):
            for key in ("latitude", "longitude"):
                if key in position:
                    position[key] = "**REDACTED**"
    return data


def _redact_observations(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Hide coordinate values in the field summary but keep their change counts."""
    data = copy.deepcopy(summary)
    for path, record in data["changing"].items():
        if path.endswith((".latitude", ".longitude")):
            record["samples"] = "**REDACTED**"
    for path in data["constant"]:
        if path.endswith((".latitude", ".longitude")):
            data["constant"][path] = "**REDACTED**"
    return data


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> Dict[str, Any]:
    """Return redacted account and per-vehicle status for support purposes."""
    runtime: ZeekrRuntimeData = entry.runtime_data
    statuses = runtime.coordinator.data or {}
    vehicles = {}
    field_observations = {}
    for index, vin in enumerate(runtime.api.vehicles):
        if vin in statuses:
            vehicles[f"vehicle_{index}"] = _redact_status(statuses[vin])
        field_observations[f"vehicle_{index}"] = _redact_observations(
            runtime.coordinator.observer.summary(vin)
        )
    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "vehicle_count": len(runtime.api.vehicles),
        "vehicles": vehicles,
        # Which status fields this car really fills and how often they change.
        "field_observations": field_observations,
    }
