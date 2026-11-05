"""Constants shared across the Crafty Controller integration."""

from __future__ import annotations

from datetime import timedelta

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

# Everything that can go wrong when talking to Crafty. Callers catch this one tuple:
#   ClientError  - connection refused, DNS failure, TLS error, HTTP 4xx/5xx status
#   TimeoutError - Crafty did not answer within TIMEOUT
#   ValueError   - the reply was not JSON, or Crafty said {"status": "error"}
ERRORS = (ClientError, TimeoutError, ValueError)
