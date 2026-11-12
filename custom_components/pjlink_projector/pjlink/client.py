"""Asyncio PJLink client (Class 1 and Class 2) with no dependencies."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re

from .errors import (
    COMMAND_ERRORS,
    PJLinkAuthError,
    PJLinkCommandError,
    PJLinkConnectionError,
    PJLinkError,
    PJLinkParameterError,
    PJLinkProtocolError,
    PJLinkUnsupportedError,
)
from .models import (
    DEFAULT_PORT,
    ERROR_CATEGORIES,
    ERROR_LEVELS,
    NO_SIGNAL,
    POWER_STATES,
    ErrorLevel,
    Lamp,
    PowerState,
    ProjectorInfo,
    ProjectorStatus,
    default_input_name,
)

_LOGGER = logging.getLogger(__name__)

_RESPONSE_RE = re.compile(r"%(?P<cls>[0-9A-Za-z])(?P<body>[A-Za-z0-9]{4})=(?P<value>.*)$")
_COMMAND_RE = re.compile(r"^[A-Za-z0-9]{4}$")
_INPUT_RE = re.compile(r"^[1-6][0-9A-Za-z]$")
_MAX_LINE = 4096
# How many unrelated lines we skip while waiting for the answer to a command.
_MAX_STALE_LINES = 4


class PJLinkClient:
    """Talk to one projector over TCP.

    The connection is opened on demand and reused until ``disconnect()`` is
    called or the projector drops it (the spec makes projectors hang up after
    30 seconds of silence). A dropped connection is reopened transparently.
    """

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        password: str | None = None,
        timeout: float = 5.0,
    ) -> None:
        self.host = host
        self.port = port
        self.password = password or None
        self.timeout = timeout
        self.auth_required: bool | None = None
        self.peer_ip: str | None = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._auth_prefix = ""
        self._lock = asyncio.Lock()
        self._unsupported: set[str] = set()
        self._pjlink_class = 1

    # ------------------------------------------------------------------ #
    # Connection handling
    # ------------------------------------------------------------------ #

    @property
    def connected(self) -> bool:
        """True while a TCP session is open."""
        return self._writer is not None and not self._writer.is_closing()

    async def connect(self) -> None:
        """Open the session now (otherwise it opens on the first command)."""
        async with self._lock:
            if not self.connected:
                await self._open()

    async def disconnect(self) -> None:
        """Close the session. Safe to call at any time."""
        async with self._lock:
            await self._close()

    async def _open(self) -> None:
        await self._close()
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port, limit=_MAX_LINE),
                self.timeout,
            )
        except (OSError, asyncio.TimeoutError) as err:
            raise PJLinkConnectionError(
                f"Cannot connect to {self.host}:{self.port}: {err or 'timed out'}"
            ) from err

        peer = self._writer.get_extra_info("peername")
        if peer:
            self.peer_ip = peer[0]

        try:
            greeting = await self._read_line()
        except PJLinkError:
            await self._close()
            raise

        parts = greeting.split()
        if not parts or parts[0].upper() != "PJLINK" or len(parts) < 2:
            await self._close()
            raise PJLinkProtocolError(
                f"{self.host}:{self.port} is not a PJLink device (got {greeting!r})"
            )
        if parts[1].upper() == "ERRA":
            await self._close()
            raise PJLinkAuthError("Projector rejected the connection (ERRA)")
        if parts[1] == "0":
            self.auth_required = False
            self._auth_prefix = ""
        elif parts[1] == "1" and len(parts) >= 3:
            self.auth_required = True
            if not self.password:
                await self._close()
                raise PJLinkAuthError(
                    "Projector requires a password", password_missing=True
                )
            self._auth_prefix = hashlib.md5(
                (parts[2] + self.password).encode("utf-8")
            ).hexdigest()
        else:
            await self._close()
            raise PJLinkProtocolError(f"Unexpected PJLink greeting {greeting!r}")

    async def _close(self) -> None:
        writer, self._writer, self._reader = self._writer, None, None
        self._auth_prefix = ""
        if writer is None:
            return
        try:
            writer.close()
            await asyncio.wait_for(writer.wait_closed(), 1.0)
        except (OSError, asyncio.TimeoutError):
            pass

    async def _read_line(self) -> str:
        assert self._reader is not None
        try:
            raw = await asyncio.wait_for(self._reader.readuntil(b"\r"), self.timeout)
        except asyncio.TimeoutError as err:
            raise PJLinkConnectionError(
                f"Timed out waiting for {self.host} to answer"
            ) from err
        except asyncio.IncompleteReadError as err:
            raise PJLinkConnectionError(
                f"{self.host} closed the connection"
            ) from err
        except asyncio.LimitOverrunError as err:
            raise PJLinkProtocolError(f"{self.host} sent an oversized line") from err
        except OSError as err:
            raise PJLinkConnectionError(f"Connection to {self.host} lost: {err}") from err
        return raw.decode("utf-8", errors="replace").strip("\r\n\x00 \t")

    # ------------------------------------------------------------------ #
    # Raw command layer
    # ------------------------------------------------------------------ #

    async def command(self, body: str, parameter: str = "?", pjlink_class: int = 1) -> str:
        """Send ``%<class><body> <parameter>`` and return the answer's value.

        Returns ``"OK"`` for accepted set commands and the reported value for
        queries. Raises a ``PJLinkCommandError`` subclass for ERR1..ERR4.
        """
        body = body.upper()
        if not _COMMAND_RE.match(body):
            raise PJLinkParameterError(body, "ERR2")
        if any(ch in parameter for ch in "\r\n"):
            raise PJLinkParameterError(body, "ERR2")
        line = f"%{pjlink_class}{body} {parameter}\r"

        async with self._lock:
            reused = self.connected
            try:
                value = await self._transact(line, body)
            except PJLinkConnectionError:
                # A reused session may simply have idled out; try once more
                # on a fresh one. A brand new session failing is a real error.
                await self._close()
                if not reused:
                    raise
                _LOGGER.debug("%s: session dropped, reconnecting", self.host)
                try:
                    value = await self._transact(line, body)
                except PJLinkError:
                    await self._close()
                    raise
            except PJLinkCommandError:
                raise
            except PJLinkError:
                await self._close()
                raise

        code = value.upper()
        if code in COMMAND_ERRORS:
            raise COMMAND_ERRORS[code](body)
        return value

    async def _transact(self, line: str, body: str) -> str:
        if not self.connected:
            await self._open()
        assert self._writer is not None
        payload = (self._auth_prefix + line).encode("utf-8")
        self._auth_prefix = ""  # the digest goes on the first command only
        try:
            self._writer.write(payload)
            await asyncio.wait_for(self._writer.drain(), self.timeout)
        except (OSError, asyncio.TimeoutError) as err:
            raise PJLinkConnectionError(f"Cannot send to {self.host}: {err}") from err

        for _ in range(_MAX_STALE_LINES):
            answer = await self._read_line()
            if not answer:
                continue
            if answer.upper().startswith("PJLINK ERRA"):
                raise PJLinkAuthError("Wrong PJLink password")
            match = _RESPONSE_RE.search(answer)
            if match and match["body"].upper() == body:
                return match["value"].strip()
            _LOGGER.debug("%s: ignoring unexpected line %r", self.host, answer)
        raise PJLinkProtocolError(f"{self.host} gave no valid answer to {body}")

    async def _optional(self, body: str, pjlink_class: int = 1) -> str | None:
        """Query something a projector may not offer; None when it doesn't."""
        if body in self._unsupported:
            return None
        try:
            return await self.command(body, "?", pjlink_class)
        except PJLinkUnsupportedError:
            self._unsupported.add(body)
        except PJLinkCommandError as err:
            _LOGGER.debug("%s: %s", self.host, err)
        return None

    def _input_class(self) -> int:
        """Class 2 projectors list their extended inputs only via %2."""
        return 2 if self._pjlink_class >= 2 and "INPT2" not in self._unsupported else 1

    # ------------------------------------------------------------------ #
    # Class 1
    # ------------------------------------------------------------------ #

    async def get_power(self) -> PowerState:
        """Return the power status."""
        value = await self.command("POWR")
        try:
            return POWER_STATES[value]
        except KeyError as err:
            raise PJLinkProtocolError(f"Unknown power status {value!r}") from err

    async def set_power(self, on: bool) -> None:
        """Turn the projector on, or send it to standby."""
        await self.command("POWR", "1" if on else "0")

    async def get_input(self) -> str:
        """Return the active input code, e.g. '31'."""
        return (await self.command("INPT", "?", self._input_class())).upper()

    async def set_input(self, code: str) -> None:
        """Switch to an input by code, e.g. '31' for Digital 1."""
        code = code.strip().upper()
        if not _INPUT_RE.match(code):
            raise PJLinkParameterError("INPT", "ERR2")
        try:
            await self.command("INPT", code, self._input_class())
        except PJLinkUnsupportedError:
            if self._input_class() == 1:
                raise
            self._unsupported.add("INPT2")
            await self.command("INPT", code, 1)

    async def get_inputs(self) -> list[str]:
        """Return the input codes the projector offers."""
        try:
            value = await self.command("INST", "?", self._input_class())
        except PJLinkUnsupportedError:
            if self._input_class() == 1:
                raise
            self._unsupported.add("INPT2")
            value = await self.command("INST", "?", 1)
        return [tok.upper() for tok in value.split() if _INPUT_RE.match(tok)]

    async def get_av_mute(self) -> tuple[bool, bool]:
        """Return (video muted, audio muted)."""
        value = await self.command("AVMT")
        return value in ("11", "31"), value in ("21", "31")

    async def set_av_mute(self, video: bool | None = None, audio: bool | None = None) -> None:
        """Mute or unmute picture and/or sound. ``None`` leaves a side alone."""
        if video is None and audio is None:
            return
        if video is not None and audio is not None and video == audio:
            await self.command("AVMT", f"3{int(video)}")
            if not video:
                # Some projectors (Optoma) track "sound mute" apart from
                # "AV mute", so 30 alone leaves a 21 in place.
                try:
                    await self.command("AVMT", "20")
                except PJLinkCommandError:
                    pass
            return
        if video is not None:
            # Some projectors (Optoma) have no picture-only mute and answer
            # ERR2; their only way to blank the picture is the combined mute.
            if "AVMT1" not in self._unsupported:
                try:
                    await self.command("AVMT", f"1{int(video)}")
                except PJLinkParameterError:
                    self._unsupported.add("AVMT1")
            if "AVMT1" in self._unsupported:
                await self.command("AVMT", f"3{int(video)}")
        if audio is not None:
            await self.command("AVMT", f"2{int(audio)}")

    async def get_errors(self) -> dict[str, ErrorLevel]:
        """Return the level of each error category."""
        value = await self.command("ERST")
        if len(value) < len(ERROR_CATEGORIES):
            raise PJLinkProtocolError(f"Malformed error status {value!r}")
        return {
            name: ERROR_LEVELS.get(digit, ErrorLevel.ERROR)
            for name, digit in zip(ERROR_CATEGORIES, value)
        }

    async def get_lamps(self) -> list[Lamp]:
        """Return usage hours and on/off state of every light source."""
        tokens = (await self.command("LAMP")).split()
        lamps: list[Lamp] = []
        for idx in range(0, len(tokens), 2):
            try:
                hours = int(tokens[idx])
            except ValueError:
                continue
            state = tokens[idx + 1] if idx + 1 < len(tokens) else None
            lamps.append(Lamp(hours, None if state is None else state == "1"))
        return lamps

    async def get_class(self) -> int:
        """Return the PJLink class (1 or 2)."""
        value = await self._optional("CLSS")
        try:
            self._pjlink_class = max(1, int(value)) if value else 1
        except ValueError:
            self._pjlink_class = 1
        return self._pjlink_class

    # ------------------------------------------------------------------ #
    # Class 2
    # ------------------------------------------------------------------ #

    async def get_input_name(self, code: str) -> str | None:
        """Return the projector's own name for an input (Class 2)."""
        if "INNM" in self._unsupported:
            return None
        try:
            return await self.command("INNM", f"?{code}", 2) or None
        except PJLinkUnsupportedError:
            self._unsupported.add("INNM")
        except PJLinkCommandError:
            pass
        return None

    async def get_freeze(self) -> bool:
        """Return True when the picture is frozen (Class 2)."""
        return await self.command("FREZ", "?", 2) == "1"

    async def set_freeze(self, frozen: bool) -> None:
        """Freeze or release the picture (Class 2)."""
        await self.command("FREZ", "1" if frozen else "0", 2)

    async def speaker_volume(self, up: bool) -> None:
        """Nudge the speaker volume one step (Class 2)."""
        await self.command("SVOL", "1" if up else "0", 2)

    async def microphone_volume(self, up: bool) -> None:
        """Nudge the microphone volume one step (Class 2)."""
        await self.command("MVOL", "1" if up else "0", 2)

    # ------------------------------------------------------------------ #
    # Aggregates
    # ------------------------------------------------------------------ #

    async def fetch_info(self) -> ProjectorInfo:
        """Read everything that identifies the projector."""
        info = ProjectorInfo(pjlink_class=await self.get_class())
        info.name = await self._optional("NAME") or None
        info.manufacturer = await self._optional("INF1") or None
        info.product = await self._optional("INF2") or None
        info.other_info = await self._optional("INFO") or None
        if info.pjlink_class >= 2:
            info.serial = await self._optional("SNUM", 2) or None
            info.software_version = await self._optional("SVER", 2) or None
            info.recommended_resolution = _resolution(await self._optional("RRES", 2))
            info.lamp_model = await self._optional("RLMP", 2) or None
            info.filter_model = await self._optional("RFIL", 2) or None
        info.inputs = await self.fetch_inputs()
        return info

    async def fetch_inputs(self) -> dict[str, str]:
        """Return {input code: unique display name}; empty if not available now."""
        try:
            codes = await self.get_inputs()
        except PJLinkCommandError as err:
            _LOGGER.debug("%s: input list unavailable: %s", self.host, err)
            return {}
        inputs: dict[str, str] = {}
        for code in codes:
            name = None
            if self._pjlink_class >= 2:
                name = await self.get_input_name(code)
            name = name or default_input_name(code)
            if name in inputs.values():
                name = f"{name} ({code})"
            inputs[code] = name
        return inputs

    async def fetch_status(self) -> ProjectorStatus:
        """Read everything that changes at runtime."""
        status = ProjectorStatus(power=await self.get_power())
        if status.power is PowerState.ON and self._unsupported:
            # Some projectors answer ERR1 instead of ERR3 while in standby.
            self._unsupported.clear()

        value = await self._optional("ERST")
        if value and len(value) >= len(ERROR_CATEGORIES):
            status.errors = {
                name: ERROR_LEVELS.get(digit, ErrorLevel.ERROR)
                for name, digit in zip(ERROR_CATEGORIES, value)
            }

        if "LAMP" not in self._unsupported:
            try:
                status.lamps = await self.get_lamps()
            except PJLinkUnsupportedError:
                self._unsupported.add("LAMP")
            except PJLinkCommandError:
                pass

        value = await self._optional("INPT", self._input_class())
        status.input = value.upper() if value and _INPUT_RE.match(value) else None

        value = await self._optional("AVMT")
        if value and status.is_on:
            status.video_mute = value in ("11", "31")
            status.audio_mute = value in ("21", "31")

        if self._pjlink_class >= 2:
            value = await self._optional("FILT", 2)
            status.filter_hours = int(value) if value and value.isdigit() else None
            if status.is_on:
                value = await self._optional("FREZ", 2)
                status.freeze = None if value is None else value == "1"
                status.input_resolution = _resolution(await self._optional("IRES", 2))
        return status


def _resolution(value: str | None) -> str | None:
    """Normalise an IRES/RRES answer."""
    if not value or value == "*":
        return None
    if value == "-":
        return NO_SIGNAL
    return value.replace(" ", "").lower()
