"""Exceptions raised by the PJLink protocol library."""

from __future__ import annotations


class PJLinkError(Exception):
    """Base class for all PJLink errors."""


class PJLinkConnectionError(PJLinkError):
    """The projector could not be reached or the connection dropped."""


class PJLinkProtocolError(PJLinkError):
    """The peer answered with something that is not PJLink."""


class PJLinkAuthError(PJLinkError):
    """The projector requires a password, or the password was rejected."""

    def __init__(self, message: str, *, password_missing: bool = False) -> None:
        super().__init__(message)
        self.password_missing = password_missing


class PJLinkCommandError(PJLinkError):
    """The projector answered a command with ERR1..ERR4."""

    code = "ERR?"
    reason = "command failed"

    def __init__(self, command: str, code: str | None = None) -> None:
        self.command = command
        if code is not None:
            self.code = code
        super().__init__(f"{command}: {self.reason} ({self.code})")


class PJLinkUnsupportedError(PJLinkCommandError):
    """ERR1: the projector does not implement this command."""

    code = "ERR1"
    reason = "command not supported by this projector"


class PJLinkParameterError(PJLinkCommandError):
    """ERR2: the parameter is out of range (e.g. an input that does not exist)."""

    code = "ERR2"
    reason = "parameter out of range"


class PJLinkUnavailableError(PJLinkCommandError):
    """ERR3: the command cannot be handled right now (standby, warming up...)."""

    code = "ERR3"
    reason = "not available in the current projector state"


class PJLinkProjectorFailureError(PJLinkCommandError):
    """ERR4: the projector reports a hardware failure."""

    code = "ERR4"
    reason = "projector failure"


COMMAND_ERRORS: dict[str, type[PJLinkCommandError]] = {
    "ERR1": PJLinkUnsupportedError,
    "ERR2": PJLinkParameterError,
    "ERR3": PJLinkUnavailableError,
    "ERR4": PJLinkProjectorFailureError,
}
