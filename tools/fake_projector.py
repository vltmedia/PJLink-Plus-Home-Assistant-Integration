"""A simulated PJLink projector for development and tests.

    python tools/fake_projector.py [--class 2] [--password secret] [--port 4352]

Speaks PJLink over TCP, answers the Class 2 UDP search, and sends Class 2
status notifications. Point the integration at this machine's address.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging

_LOGGER = logging.getLogger("fake_projector")


class FakeProjector:
    """In-memory projector state plus the servers that expose it."""

    def __init__(
        self,
        pjlink_class: int = 2,
        password: str | None = None,
        host: str = "127.0.0.1",
        port: int = 0,
        mac: str = "02:00:00:aa:bb:cc",
        warm_up: float = 0.0,
    ) -> None:
        self.pjlink_class = pjlink_class
        self.password = password
        self.host = host
        self.port = port
        self.mac = mac
        self.warm_up = warm_up
        self.salt = "498e4a67"
        self.power = "0"
        self.input = "31"
        self.inputs = {"11": "COMPUTER", "31": "HDMI1", "32": "HDMI2", "51": "LAN"}
        self.avmt = "30"
        self.freeze = "0"
        self.errors = "000000"
        self.lamps = "1234 0"
        self.name = "Test Projector"
        self.connections = 0
        self.received: list[str] = []
        self.drop_after_command = False
        self.combined_mute_only = False  # like Optoma: no picture-only mute
        self._server: asyncio.Server | None = None
        self._udp: asyncio.DatagramTransport | None = None
        self.notify_target: tuple[str, int] | None = None

    # -- lifecycle ------------------------------------------------------ #

    async def start(self, udp: bool = False) -> None:
        self._server = await asyncio.start_server(self._serve, self.host, self.port)
        self.port = self._server.sockets[0].getsockname()[1]
        if udp:
            loop = asyncio.get_running_loop()
            self._udp, _ = await loop.create_datagram_endpoint(
                lambda: _Udp(self), local_addr=(self.host, self.port)
            )

    async def stop(self) -> None:
        if self._udp:
            self._udp.close()
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    def notify(self, body: str, value: str) -> None:
        """Send a Class 2 status notification."""
        if self._udp and self.notify_target:
            self._udp.sendto(f"%2{body}={value}\r".encode(), self.notify_target)

    # -- TCP ------------------------------------------------------------ #

    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.connections += 1
        authed = self.password is None
        writer.write(b"PJLINK 0\r" if authed else f"PJLINK 1 {self.salt}\r".encode())
        digest = hashlib.md5((self.salt + (self.password or "")).encode()).hexdigest()
        try:
            while True:
                line = (await reader.readuntil(b"\r")).decode().rstrip("\r")
                if not authed:
                    if not line.startswith(digest):
                        writer.write(b"PJLINK ERRA\r")
                        await writer.drain()
                        break
                    line, authed = line[len(digest):], True
                self.received.append(line)
                writer.write((self.handle(line) + "\r").encode())
                await writer.drain()
                if self.drop_after_command:
                    break
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            writer.close()

    def handle(self, line: str) -> str:
        """Answer one command line."""
        if len(line) < 8 or line[0] != "%" or line[6] != " ":
            return "PJLINK ERR1"
        cls, body, param = line[1], line[2:6].upper(), line[7:]
        head = f"%{cls}{body}="
        if cls not in "12" or int(cls) > self.pjlink_class:
            return head + "ERR1"
        on = self.power == "1"
        query = param == "?"

        if body == "POWR":
            if query:
                return head + self.power
            if param not in ("0", "1"):
                return head + "ERR2"
            self._set_power(param)
            return head + "OK"
        if body == "INPT":
            if not on:
                return head + "ERR3"
            if query:
                return head + self.input
            if param not in self.inputs:
                return head + "ERR2"
            self.input = param
            self.notify("INPT", param)
            return head + "OK"
        if body == "AVMT":
            if not on:
                return head + "ERR3"
            if query:
                return head + self.avmt
            if param not in ("10", "11", "20", "21", "30", "31"):
                return head + "ERR2"
            if self.combined_mute_only and param[0] == "1":
                return head + "ERR2"
            video = self.avmt in ("11", "31")
            audio = self.avmt in ("21", "31")
            if param[0] in "13":
                video = param[1] == "1"
            if param[0] in "23":
                audio = param[1] == "1"
            self.avmt = {(False, False): "30", (True, False): "11", (False, True): "21", (True, True): "31"}[video, audio]
            return head + "OK"
        simple = {
            "ERST": self.errors,
            "LAMP": self.lamps,
            "INST": " ".join(self.inputs),
            "NAME": self.name,
            "INF1": "Acme",
            "INF2": "Lumen 9000",
            "INFO": "simulator",
            "CLSS": str(self.pjlink_class),
        }
        if body in simple and cls == "1" or body == "INST":
            return head + simple[body] if query else head + "ERR2"
        if cls == "2":
            if body == "INNM":
                return head + self.inputs.get(param.lstrip("?"), "ERR2")
            if body == "FREZ":
                if not on:
                    return head + "ERR3"
                if query:
                    return head + self.freeze
                if param not in ("0", "1"):
                    return head + "ERR2"
                self.freeze = param
                return head + "OK"
            if body in ("SVOL", "MVOL"):
                return head + ("OK" if param in ("0", "1") else "ERR2")
            class2 = {
                "SNUM": "SN12345678",
                "SVER": "1.2.3",
                "IRES": "1920x1080" if on else "-",
                "RRES": "1920x1200",
                "FILT": "321",
                "RLMP": "LMP-1",
                "RFIL": "FLT-1",
            }
            if body in class2:
                return head + class2[body] if query else head + "ERR2"
        return head + "ERR1"

    def _set_power(self, target: str) -> None:
        if target == self.power:
            return
        if self.warm_up <= 0:
            self.power = target
            self.notify("POWR", target)
            return
        self.power = "3" if target == "1" else "2"
        self.notify("POWR", self.power)

        def _done() -> None:
            self.power = target
            self.notify("POWR", target)

        asyncio.get_running_loop().call_later(self.warm_up, _done)


class _Udp(asyncio.DatagramProtocol):
    def __init__(self, projector: FakeProjector) -> None:
        self.projector = projector
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport) -> None:
        self.transport = transport

    def datagram_received(self, data: bytes, addr) -> None:
        if data.strip() == b"%2SRCH" and self.projector.pjlink_class >= 2:
            self.projector.notify_target = addr
            self.transport.sendto(f"%2ACKN={self.projector.mac}\r".encode(), addr)


async def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--class", dest="cls", type=int, default=2, choices=(1, 2))
    parser.add_argument("--password")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=4352)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    projector = FakeProjector(args.cls, args.password, args.host, args.port, warm_up=8.0)
    await projector.start(udp=True)
    _LOGGER.info("Fake Class %s projector on %s:%s", args.cls, args.host, projector.port)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(_main())
