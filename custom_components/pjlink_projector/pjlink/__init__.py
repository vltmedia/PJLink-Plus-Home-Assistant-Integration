"""Dependency-free asyncio implementation of PJLink Class 1 and Class 2.

This package does not import Home Assistant and can be used on its own.
"""

from .client import PJLinkClient
from .errors import (
    PJLinkAuthError,
    PJLinkCommandError,
    PJLinkConnectionError,
    PJLinkError,
    PJLinkParameterError,
    PJLinkProjectorFailureError,
    PJLinkProtocolError,
    PJLinkUnavailableError,
    PJLinkUnsupportedError,
)
from .models import (
    DEFAULT_PORT,
    ERROR_CATEGORIES,
    INPUT_TYPES,
    NO_SIGNAL,
    DiscoveredProjector,
    ErrorLevel,
    Lamp,
    PowerState,
    ProjectorInfo,
    ProjectorStatus,
    default_input_name,
)
from .scan import discover, hosts_in_networks, probe_greeting, tcp_sweep
from .udp import PJLinkUDP, normalize_mac

__all__ = [
    "DEFAULT_PORT",
    "ERROR_CATEGORIES",
    "INPUT_TYPES",
    "NO_SIGNAL",
    "DiscoveredProjector",
    "ErrorLevel",
    "Lamp",
    "PJLinkAuthError",
    "PJLinkClient",
    "PJLinkCommandError",
    "PJLinkConnectionError",
    "PJLinkError",
    "PJLinkParameterError",
    "PJLinkProjectorFailureError",
    "PJLinkProtocolError",
    "PJLinkUDP",
    "PJLinkUnavailableError",
    "PJLinkUnsupportedError",
    "PowerState",
    "ProjectorInfo",
    "ProjectorStatus",
    "default_input_name",
    "discover",
    "hosts_in_networks",
    "normalize_mac",
    "probe_greeting",
    "tcp_sweep",
]
