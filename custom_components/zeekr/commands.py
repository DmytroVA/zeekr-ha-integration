"""One shared way to send a remote command and learn whether the car executed it.

Mirrors the official app's flow: ``remoteControl/control`` returns a ``sessionId``
and the outcome is then read from ``remoteControl/queryProcessResult`` (status
``1`` = executed, ``2`` = failed, anything else = still in progress). The app
gives a command 45 seconds before calling it timed out. The regular status
document is only refreshed by the car about once a minute, so it is used as the
final reconciliation, not as the confirmation.
"""

import asyncio
import time
from typing import Any, Dict, List, Optional

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .api import ZeekrApiError, ZeekrAuthError
from .const import COMMAND_RESULT_INTERVAL, COMMAND_RESULT_TIMEOUT
from .coordinator import ZeekrRuntimeData, start_reauth

STATUS_EXECUTED = "1"
STATUS_FAILED = "2"


async def async_run_command(
    hass: HomeAssistant,
    runtime: ZeekrRuntimeData,
    vin: str,
    *,
    service_id: str,
    command: Optional[str] = None,
    parameters: Optional[List[Dict[str, Any]]] = None,
    duration: Optional[int] = None,
    wait_result: bool = True,
) -> Dict[str, Any]:
    """Send a command, wait for the car's verdict, then refresh the status.

    Returns ``{"response": <cloud answer>, "result": {...}}``. Raises
    ``HomeAssistantError`` when the cloud rejects the command, the car reports
    that it failed, or no verdict arrives in time.
    """
    try:
        response = await runtime.api.async_remote_control(
            vin,
            service_id=service_id,
            command=command,
            parameters=parameters,
            duration=duration,
        )
    except ZeekrAuthError as err:
        start_reauth(hass)
        raise HomeAssistantError("Zeekr credentials expired") from err
    except ZeekrApiError as err:
        raise HomeAssistantError(f"Zeekr rejected the command: {err}") from err

    outcome: Dict[str, Any] = {"response": response}
    data = response.get("data")
    session_id = data.get("sessionId") if isinstance(data, dict) else None
    try:
        if wait_result and session_id:
            outcome["result"] = await _async_wait_result(
                hass, runtime, vin, str(session_id)
            )
    finally:
        try:
            await runtime.coordinator.async_refresh_vehicle(vin)
        except ZeekrApiError:
            pass
    return outcome


async def _async_wait_result(
    hass: HomeAssistant, runtime: ZeekrRuntimeData, vin: str, session_id: str
) -> Dict[str, Any]:
    """Poll the execution result until the car answers or the wait times out."""
    started = time.monotonic()
    while True:
        await asyncio.sleep(COMMAND_RESULT_INTERVAL)
        elapsed = round(time.monotonic() - started, 1)
        try:
            data = await runtime.api.async_query_process_result(vin, session_id)
        except ZeekrAuthError as err:
            start_reauth(hass)
            raise HomeAssistantError("Zeekr credentials expired") from err
        except ZeekrApiError:
            # A failed result query must not fail a command the cloud accepted.
            data = {}
        status = str(data.get("status"))
        description = data.get("description")
        code = data.get("descriptionCode")
        if status == STATUS_EXECUTED:
            return {
                "status": 1,
                "description": description,
                "descriptionCode": code,
                "after_s": elapsed,
                "session_id": session_id,
            }
        if status == STATUS_FAILED:
            reason = description or "no reason given"
            suffix = f" (code {code})" if code else ""
            raise HomeAssistantError(
                f"The car did not execute the command: {reason}{suffix}"
            )
        if elapsed >= COMMAND_RESULT_TIMEOUT:
            raise HomeAssistantError(
                f"The car did not confirm the command within "
                f"{COMMAND_RESULT_TIMEOUT} seconds"
            )
