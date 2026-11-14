"""Constants shared by the Zeekr Home Assistant integration."""

from datetime import timedelta

DOMAIN = "zeekr"
NAME = "Zeekr"
PLATFORMS = ["sensor", "binary_sensor", "device_tracker", "button", "switch", "number"]
SCAN_INTERVAL = timedelta(seconds=60)

# After a remote command, re-poll the vehicle status up to this many times,
# waiting this many seconds between tries, to confirm execution quickly instead
# of waiting for the next regular poll. The command path is cloud -> car -> cloud.
COMMAND_CONFIRM_ATTEMPTS = 6
COMMAND_CONFIRM_DELAY = 5
# How long a switch keeps showing the commanded state while the car has not yet
# reported it. After this window the next poll's reported state wins again.
COMMAND_OPTIMISTIC_HOLD = 120
# The official app waits up to 23 s for a command's execution result.
COMMAND_RESULT_TIMEOUT = 25
COMMAND_RESULT_INTERVAL = 1.5

CONF_MOBILE = "mobile"
CONF_DEVICE_ID = "device_id"
CONF_JWT_TOKEN = "jwt_token"
CONF_USER_ID = "user_id"
CONF_CLIENT_ID = "client_id"
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_VEHICLES = "vehicles"

BASE_GATEWAY = "https://api-gw-toc.zeekrlife.com"
BASE_LEGACY = "https://api.zeekrline.com"
BASE_NEW = "https://snc-tsp-api.zeekrlife.com"
BASE_STATIC = "https://snc-static.zeekrlife.com"

APP_ID = "ZEEKRCNCH001M0001"
APP_SIGNING_ID = "ZEEKRCNCH001M0000"

WS_LIST_VEHICLES = f"{DOMAIN}/list_vehicles"
WS_START_SENTINEL = f"{DOMAIN}/start_sentinel"

# Local defaults for climate convenience controls (not reported by the car).
DEFAULT_AC_TEMP = 22.0
DEFAULT_AC_DURATION_MIN = 15
MIN_AC_TEMP = 16.0
MAX_AC_TEMP = 30.0
RAPID_COOL_TEMP = 15.5
RAPID_WARM_TEMP = 28.5
