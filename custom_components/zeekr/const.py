"""Constants shared by the Zeekr Home Assistant integration."""

from datetime import timedelta

DOMAIN = "zeekr"
NAME = "Zeekr"
PLATFORMS = [
    "sensor",
    "binary_sensor",
    "device_tracker",
    "button",
    "switch",
    "select",
    "number",
]
SCAN_INTERVAL = timedelta(seconds=60)

# Remote commands: how often to ask the cloud for a command's execution result
# and how long to wait for it (the official app gives a command 45 seconds).
COMMAND_RESULT_INTERVAL = 2
COMMAND_RESULT_TIMEOUT = 45
# The car refreshes its status document about once a minute, so after a confirmed
# command a switch keeps showing the commanded state for up to this many seconds
# until the status document catches up.
COMMAND_OPTIMISTIC_HOLD = 180

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
