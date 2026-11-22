"""Constants shared across the Crafty Controller integration."""

from datetime import timedelta
import re

from aiohttp import ClientError, ClientTimeout
from homeassistant.const import Platform

# Integration domain. Must match the folder name and manifest.json.
DOMAIN = "crafty_controller"

# The entity platforms this integration provides (see switch.py / binary_sensor.py).
PLATFORMS = [Platform.SWITCH, Platform.BINARY_SENSOR]

# How often Crafty is polled for the state of every server.
UPDATE_INTERVAL = timedelta(seconds=30)

# Per-request network timeout, so an unresponsive Crafty can never stall Home Assistant.
TIMEOUT = ClientTimeout(total=10)

# Limits on what Crafty may send back, so a broken or hostile reply can't use up Home Assistant's memory or time.
MAX_RESPONSE_BYTES = 1024 * 1024  # one reply's body; a real one is a few kilobytes
MAX_SERVERS = 200  # servers taken from the list; any beyond this are left out (with a warning)
MAX_NAME_LENGTH = 100  # a longer server name is cut to this length

# How many stats requests run at once during a poll, so many servers don't flood Crafty (or Home Assistant).
MAX_PARALLEL_STATS = 4

# A Crafty server ID is a UUID (older Crafty: a number). Anything else is skipped, so a strange ID can never change
# the shape of an API path. IDs are still percent-encoded when put in a URL.
SERVER_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}")

# How long the switch keeps showing the state it was just set to while Crafty catches up (two polls).
PENDING_STATE_SECONDS = 60

# Everything that can go wrong when talking to Crafty. Callers catch this one tuple:
#   ClientError  - connection refused, DNS failure, TLS error, HTTP 4xx/5xx status
#   TimeoutError - Crafty did not answer within TIMEOUT
#   ValueError   - the reply was not JSON, too big, a redirect, or Crafty said {"status": "error"}
ERRORS = (ClientError, TimeoutError, ValueError)
