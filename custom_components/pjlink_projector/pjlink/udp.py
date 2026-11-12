"""PJLink Class 2 UDP: projector search and status notifications."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
import logging
import re
import socket

from .models import DEFAULT_PORT

_LOGGER = logging.getLogger(__name__)

_UDP_RE = re.compile(r"%2(?P<body>[A-Za-z]{4})=(?P<value>[^\r\n\x00]*)")
_MAC_RE = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")

# callback(source ip, command body, value)
NotificationCallback = Callable[[str, str, str], None]


def normalize_mac(value: str) -> str | None:
    """Return aa:bb:cc:dd:ee:ff, or None if the value is not a MAC."""
    mac = value.strip().lower().replace("-", ":")
    if len(mac) == 12 and ":" not in mac:
        mac = ":".join(mac[i : i + 2] for i in range(0, 12, 2))
    return mac if _MAC_RE.match(mac) else None


class _Protocol(asyncio.DatagramProtocol):
    def __init__(self, owner: PJLinkUDP) -> None:
        self._owner = owner

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        self._owner._handle(data, addr[0])  # noqa: SLF001

    def error_received(self, exc: Exception) -> None:
        _LOGGER.debug("PJLink UDP error: %s", exc)


class PJLinkUDP:
    """One UDP socket shared by search and status notifications.

    Projectors send notifications (and some of them their search replies) to
    port 4352, so we try to own that port. If something else has it we fall
    back to a random port: search still works with projectors that reply to
    the sender's port, notifications do not.
    """

    def __init__(self, port: int = DEFAULT_PORT, bind_host: str = "0.0.0.0") -> None:
        self.port = port
        self.bind_host = bind_host
        self.bound_port: int | None = None
        self._transport: asyncio.DatagramTransport | None = None
        self._listeners: list[NotificationCallback] = []
        self._search_results: dict[str, str] | None = None
        self._search_lock = asyncio.Lock()
        self._start_lock = asyncio.Lock()

    @property
    def can_receive_notifications(self) -> bool:
        """True when we own the well-known port."""
        return self.bound_port == self.port

    async def start(self) -> None:
        """Open the socket. Does nothing when already open."""
        async with self._start_lock:
            if self._transport is not None:
                return
            loop = asyncio.get_running_loop()
            last_error: OSError | None = None
            for fallback, port in enumerate((self.port, 0)):
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                try:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    sock.setblocking(False)
                    sock.bind((self.bind_host, port))
                except OSError as err:
                    sock.close()
                    last_error = err
                    _LOGGER.debug("Cannot bind UDP port %s: %s", port, err)
                    continue
                self._transport, _ = await loop.create_datagram_endpoint(
                    lambda: _Protocol(self), sock=sock
                )
                self.bound_port = sock.getsockname()[1]
                if fallback:
                    _LOGGER.warning(
                        "UDP port %s is in use; PJLink status notifications are "
                        "disabled and projectors will be polled only",
                        self.port,
                    )
                return
            raise last_error or OSError("Cannot open a UDP socket")

    def stop(self) -> None:
        """Close the socket."""
        if self._transport is not None:
            self._transport.close()
            self._transport = None
            self.bound_port = None

    def add_listener(self, callback: NotificationCallback) -> Callable[[], None]:
        """Subscribe to status notifications; returns an unsubscribe function."""
        self._listeners.append(callback)

        def _remove() -> None:
            if callback in self._listeners:
                self._listeners.remove(callback)

        return _remove

    def _handle(self, data: bytes, source: str) -> None:
        text = data.decode("ascii", errors="replace")
        for match in _UDP_RE.finditer(text):
            body, value = match["body"].upper(), match["value"].strip()
            if body == "SRCH":
                continue  # someone else's search (or our own broadcast)
            if body == "ACKN":
                mac = normalize_mac(value)
                if self._search_results is not None and mac:
                    self._search_results[source] = mac
                continue
            for listener in list(self._listeners):
                try:
                    listener(source, body, value)
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("PJLink notification listener failed")

    async def search(
        self,
        addresses: Iterable[str] = ("255.255.255.255",),
        timeout: float = 3.0,
        target_port: int | None = None,
    ) -> dict[str, str]:
        """Send %2SRCH to the given (broadcast or unicast) addresses.

        Returns {projector ip: mac}. Only Class 2 projectors answer.
        """
        await self.start()
        assert self._transport is not None
        port = target_port or self.port
        async with self._search_lock:
            self._search_results = results = {}
            try:
                targets = list(dict.fromkeys(addresses))
                # Send twice: UDP is lossy and the search is cheap.
                for attempt in range(2):
                    for address in targets:
                        try:
                            self._transport.sendto(b"%2SRCH\r", (address, port))
                        except OSError as err:
                            _LOGGER.debug("SRCH to %s failed: %s", address, err)
                    await asyncio.sleep(timeout / 2)
                    if attempt == 0 and results and len(targets) == 1 and (
                        targets[0] in results
                    ):
                        break  # unicast probe already answered
            finally:
                self._search_results = None
        return results
