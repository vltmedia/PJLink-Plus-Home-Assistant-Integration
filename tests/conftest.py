"""Fixtures for the Home Assistant level tests.

Needs: pip install pytest-homeassistant-custom-component
"""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

try:
    import pytest_homeassistant_custom_component  # noqa: F401
except ImportError:  # only the protocol tests can run
    collect_ignore = ["test_integration.py"]
else:
    from fake_projector import FakeProjector

    import pytest_socket

    # The harness blocks sockets before every test. The fake projector is a
    # real local TCP/UDP server (and on Windows the event loop itself needs a
    # socket pair), so turn that block into a no-op.
    pytest_socket.disable_socket = lambda *args, **kwargs: None

    @pytest.fixture(autouse=True)
    def _enable(enable_custom_integrations):
        """Load custom_components/ in every test."""

    @pytest.fixture
    async def projector():
        """A simulated Class 2 projector on a random local port."""
        fake = FakeProjector(pjlink_class=2)
        await fake.start(udp=True)
        yield fake
        await fake.stop()
