"""Find PJLink projectors on a LAN.

Class 2 projectors answer a UDP search. Class 1 projectors do not, so we
also knock on TCP 4352 of every address in the local subnets and look for
the PJLink greeting.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
import ipaddress
import logging

from .client import PJLinkClient
from .errors import PJLinkAuthError, PJLinkError
from .models import DEFAULT_PORT, DiscoveredProjector
from .udp import PJLinkUDP

_LOGGER = logging.getLogger(__name__)

# Never sweep anything bigger than a /22 (1022 hosts).
MAX_SCAN_PREFIX = 22


def hosts_in_networks(networks: Iterable[str], skip: Iterable[str] = ()) -> list[str]:
    """Expand 'a.b.c.d/nn' networks to host addresses, ignoring huge ones."""
    skipped = set(skip)
    hosts: dict[str, None] = {}
    for cidr in networks:
        try:
            net = ipaddress.ip_network(cidr, strict=False)
        except ValueError:
            continue
        if net.version != 4 or net.is_loopback or net.is_link_local:
            continue
        if net.prefixlen < MAX_SCAN_PREFIX:
            _LOGGER.debug("Not sweeping %s: network too large", net)
            continue
        for host in net.hosts():
            if str(host) not in skipped:
                hosts[str(host)] = None
    return list(hosts)


async def probe_greeting(host: str, port: int = DEFAULT_PORT, timeout: float = 1.0) -> bool | None:
    """Return auth_required if host speaks PJLink, None if it does not."""
    writer = None
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout
        )
        raw = await asyncio.wait_for(reader.readuntil(b"\r"), max(timeout, 2.0))
    except (OSError, asyncio.TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
        return None
    finally:
        if writer is not None:
            writer.close()
    parts = raw.decode("ascii", errors="replace").split()
    if len(parts) < 2 or parts[0].upper() != "PJLINK":
        return None
    return parts[1] == "1"


async def tcp_sweep(
    hosts: Iterable[str],
    port: int = DEFAULT_PORT,
    timeout: float = 1.0,
    concurrency: int = 64,
) -> dict[str, bool]:
    """Return {ip: auth_required} for every host that greets with PJLINK."""
    semaphore = asyncio.Semaphore(concurrency)
    found: dict[str, bool] = {}

    async def _one(host: str) -> None:
        async with semaphore:
            auth = await probe_greeting(host, port, timeout)
        if auth is not None:
            found[host] = auth

    await asyncio.gather(*(_one(host) for host in hosts))
    return found


async def describe(found: DiscoveredProjector, timeout: float = 4.0) -> DiscoveredProjector:
    """Fill in name/model for a discovered projector when no password is needed."""
    client = PJLinkClient(found.host, found.port, timeout=timeout)
    try:
        found.pjlink_class = await client.get_class()
        found.auth_required = False
        found.name = await client._optional("NAME") or None  # noqa: SLF001
        found.manufacturer = await client._optional("INF1") or None  # noqa: SLF001
        found.product = await client._optional("INF2") or None  # noqa: SLF001
        if found.pjlink_class >= 2:
            found.serial = await client._optional("SNUM", 2) or None  # noqa: SLF001
    except PJLinkAuthError:
        found.auth_required = True
    except PJLinkError as err:
        _LOGGER.debug("Could not describe %s: %s", found.host, err)
    finally:
        await client.disconnect()
    return found


async def discover(
    udp: PJLinkUDP | None = None,
    broadcast_addresses: Iterable[str] = ("255.255.255.255",),
    networks: Iterable[str] = (),
    port: int = DEFAULT_PORT,
    timeout: float = 3.0,
    skip_hosts: Iterable[str] = (),
) -> list[DiscoveredProjector]:
    """Run the UDP search and the TCP sweep together and merge the results."""
    own_udp = udp is None
    udp = udp or PJLinkUDP(port)

    async def _search() -> dict[str, str]:
        try:
            return await udp.search(broadcast_addresses, timeout, port)
        except OSError as err:
            _LOGGER.debug("UDP search failed: %s", err)
            return {}

    try:
        macs, greeted = await asyncio.gather(
            _search(), tcp_sweep(hosts_in_networks(networks, skip_hosts), port)
        )
    finally:
        if own_udp:
            udp.stop()

    found = {
        host: DiscoveredProjector(host, port, auth_required=auth)
        for host, auth in greeted.items()
    }
    for host, mac in macs.items():
        found.setdefault(host, DiscoveredProjector(host, port)).mac = mac

    semaphore = asyncio.Semaphore(8)

    async def _describe(item: DiscoveredProjector) -> None:
        async with semaphore:
            await describe(item)

    await asyncio.gather(*(_describe(item) for item in found.values()))
    return sorted(
        found.values(), key=lambda p: tuple(int(x) if x.isdigit() else 0 for x in p.host.split("."))
    )
