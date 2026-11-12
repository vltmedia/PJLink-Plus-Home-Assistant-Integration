"""Constants for the PJLink Projector integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "pjlink_projector"

CONF_MAC = "mac"

DEFAULT_SCAN_INTERVAL = 15
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 600
# Poll faster while the projector is warming up or cooling down.
TRANSITION_SCAN_INTERVAL = 3
DEFAULT_TIMEOUT = 5.0

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.MEDIA_PLAYER,
    Platform.REMOTE,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

SERVICE_SEND_COMMAND = "send_command"
ATTR_COMMAND = "command"
ATTR_PARAMETER = "parameter"
ATTR_PJLINK_CLASS = "pjlink_class"
