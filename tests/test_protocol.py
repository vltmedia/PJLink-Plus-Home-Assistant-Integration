"""Tests for the bundled PJLink library. Need only the standard library.

    python -m unittest tests.test_protocol
"""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from fake_projector import FakeProjector  # noqa: E402
from pjlink_cli import load_pjlink  # noqa: E402

pj = load_pjlink()


class ProtocolTest(unittest.IsolatedAsyncioTestCase):
    async def _projector(self, **kwargs) -> FakeProjector:
        projector = FakeProjector(**kwargs)
        await projector.start(udp=kwargs.get("pjlink_class", 2) >= 2)
        self.addAsyncCleanup(projector.stop)
        return projector

    async def _client(self, projector: FakeProjector, password=None):
        client = pj.PJLinkClient("127.0.0.1", projector.port, password, timeout=2)
        self.addAsyncCleanup(client.disconnect)
        return client

    async def test_class2_info_and_status(self):
        projector = await self._projector()
        client = await self._client(projector)
        info = await client.fetch_info()
        self.assertEqual(info.pjlink_class, 2)
        self.assertEqual(info.display_name, "Test Projector")
        self.assertEqual(info.serial, "SN12345678")
        self.assertEqual(info.inputs, {"11": "COMPUTER", "31": "HDMI1", "32": "HDMI2", "51": "LAN"})
        self.assertEqual(info.input_code("hdmi2"), "32")

        status = await client.fetch_status()
        self.assertIs(status.power, pj.PowerState.STANDBY)
        self.assertIsNone(status.input)  # ERR3 in standby must not raise
        self.assertIsNone(status.video_mute)
        self.assertEqual(status.lamps[0].hours, 1234)
        self.assertEqual(status.filter_hours, 321)
        self.assertFalse(status.has_problem)

        await client.set_power(True)
        await client.set_input("32")
        await client.set_av_mute(video=True)
        await client.set_freeze(True)
        status = await client.fetch_status()
        self.assertTrue(status.is_on)
        self.assertEqual(status.input, "32")
        self.assertEqual((status.video_mute, status.audio_mute), (True, False))
        self.assertTrue(status.freeze)
        self.assertEqual(status.input_resolution, "1920x1080")
        await client.set_av_mute(audio=True)
        self.assertEqual(await client.get_av_mute(), (True, True))
        await client.set_av_mute(video=False, audio=False)
        self.assertEqual(await client.get_av_mute(), (False, False))

    async def test_class1_skips_class2_commands(self):
        projector = await self._projector(pjlink_class=1)
        client = await self._client(projector)
        info = await client.fetch_info()
        await client.set_power(True)
        status = await client.fetch_status()
        self.assertEqual(info.pjlink_class, 1)
        self.assertEqual(info.inputs["31"], "Digital 1")
        self.assertIsNone(status.freeze)
        self.assertFalse([line for line in projector.received if line.startswith("%2")])

    async def test_authentication(self):
        projector = await self._projector(password="JBMIAProjectorLink")
        client = await self._client(projector, "JBMIAProjectorLink")
        self.assertIs(await client.get_power(), pj.PowerState.STANDBY)
        self.assertIs(await client.get_power(), pj.PowerState.STANDBY)  # no digest twice

        wrong = await self._client(projector, "nope")
        with self.assertRaises(pj.PJLinkAuthError) as ctx:
            await wrong.get_power()
        self.assertFalse(ctx.exception.password_missing)

        missing = await self._client(projector)
        with self.assertRaises(pj.PJLinkAuthError) as ctx:
            await missing.get_power()
        self.assertTrue(ctx.exception.password_missing)

    async def test_spec_digest_example(self):
        # Example from the PJLink specification.
        import hashlib

        self.assertEqual(
            hashlib.md5(b"498e4a67JBMIAProjectorLink").hexdigest(),
            "5d8409bc1c3fa39749434aa3a5c38682",
        )

    async def test_command_errors(self):
        projector = await self._projector()
        client = await self._client(projector)
        with self.assertRaises(pj.PJLinkUnavailableError):
            await client.set_input("31")  # standby
        await client.set_power(True)
        with self.assertRaises(pj.PJLinkParameterError):
            await client.set_input("39")
        with self.assertRaises(pj.PJLinkUnsupportedError):
            await client.command("ZZZZ", "1")
        with self.assertRaises(pj.PJLinkParameterError):
            await client.command("POWR", "1\r%1POWR 0")  # no command injection

    async def test_picture_mute_falls_back_to_combined_mute(self):
        projector = await self._projector()
        projector.combined_mute_only = True
        client = await self._client(projector)
        await client.set_power(True)
        await client.set_av_mute(video=True)
        self.assertEqual(projector.avmt, "31")
        await client.set_av_mute(video=False)
        self.assertEqual(projector.avmt, "30")
        self.assertEqual(projector.received.count("%1AVMT 11"), 1)  # asked only once

    async def test_reconnects_after_projector_hangs_up(self):
        projector = await self._projector()
        projector.drop_after_command = True
        client = await self._client(projector)
        for _ in range(3):
            self.assertIs(await client.get_power(), pj.PowerState.STANDBY)
        self.assertEqual(projector.connections, 3)

    async def test_connection_refused(self):
        projector = await self._projector()
        port = projector.port
        await projector.stop()
        client = pj.PJLinkClient("127.0.0.1", port, timeout=1)
        with self.assertRaises(pj.PJLinkConnectionError):
            await client.get_power()

    async def test_udp_search_and_notifications(self):
        projector = await self._projector(warm_up=0)
        udp = pj.PJLinkUDP(port=0, bind_host="127.0.0.1")
        self.addCleanup(udp.stop)
        seen = []
        udp.add_listener(lambda ip, body, value: seen.append((ip, body, value)))
        found = await udp.search(["127.0.0.1"], timeout=1, target_port=projector.port)
        self.assertEqual(found, {"127.0.0.1": "02:00:00:aa:bb:cc"})

        client = await self._client(projector)
        await client.set_power(True)
        import asyncio

        await asyncio.sleep(0.1)
        self.assertIn(("127.0.0.1", "POWR", "1"), seen)

    async def test_tcp_sweep_and_describe(self):
        projector = await self._projector(pjlink_class=1)
        locked = await self._projector(pjlink_class=1, password="x")
        self.assertEqual(await pj.tcp_sweep(["127.0.0.1"], projector.port), {"127.0.0.1": False})
        self.assertEqual(await pj.tcp_sweep(["127.0.0.1"], locked.port), {"127.0.0.1": True})
        self.assertEqual(await pj.tcp_sweep(["127.0.0.1"], 1), {})
        item = await pj.scan.describe(pj.DiscoveredProjector("127.0.0.1", projector.port))
        self.assertEqual(item.label, "Test Projector - Acme Lumen 9000 (127.0.0.1)")

    def test_helpers(self):
        self.assertEqual(len(pj.hosts_in_networks(["192.168.1.7/24"], skip=["192.168.1.7"])), 253)
        self.assertEqual(pj.hosts_in_networks(["10.0.0.0/8", "127.0.0.1/8"]), [])
        self.assertEqual(pj.normalize_mac("AA-BB-CC-DD-EE-FF"), "aa:bb:cc:dd:ee:ff")
        self.assertIsNone(pj.normalize_mac("nonsense"))
        self.assertEqual(pj.models.friendly_name("000000", "Optoma", "Optoma 1080P"), "Optoma 1080P")


if __name__ == "__main__":
    unittest.main()
