"""Command-line helper for the bundled PJLink library (no Home Assistant needed).

    python tools/pjlink_cli.py discover [--network 192.168.1.0/24]
    python tools/pjlink_cli.py status 192.168.1.50 [--password secret]
    python tools/pjlink_cli.py raw 192.168.1.50 POWR ? [--class 1]
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
import importlib.util
import ipaddress
import json
from pathlib import Path
import socket
import sys

_PKG = Path(__file__).resolve().parents[1] / "custom_components" / "pjlink_projector" / "pjlink"


def load_pjlink():
    """Import the library without importing the Home Assistant integration."""
    if "pjlink_lib" in sys.modules:
        return sys.modules["pjlink_lib"]
    spec = importlib.util.spec_from_file_location(
        "pjlink_lib", _PKG / "__init__.py", submodule_search_locations=[str(_PKG)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["pjlink_lib"] = module
    spec.loader.exec_module(module)
    return module


def local_networks() -> list[str]:
    """Best-effort guess of the local /24 networks."""
    addresses = set()
    try:
        addresses.update(i[4][0] for i in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET))
    except OSError:
        pass
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            sock.connect(("192.0.2.1", 9))
            addresses.add(sock.getsockname()[0])
        except OSError:
            pass
    return sorted(
        str(ipaddress.ip_network(f"{a}/24", strict=False))
        for a in addresses
        if not a.startswith(("127.", "169.254."))
    )


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("discover")
    p.add_argument("--network", action="append", help="CIDR to sweep (repeatable)")
    for name in ("status", "raw"):
        p = sub.add_parser(name)
        p.add_argument("host")
        if name == "raw":
            p.add_argument("command")
            p.add_argument("parameter", nargs="?", default="?")
            p.add_argument("--class", dest="cls", type=int, default=1)
        p.add_argument("--port", type=int, default=4352)
        p.add_argument("--password")
    args = parser.parse_args()
    pj = load_pjlink()

    if args.action == "discover":
        networks = args.network or local_networks()
        broadcasts = ["255.255.255.255"] + [
            str(ipaddress.ip_network(n, strict=False).broadcast_address) for n in networks
        ]
        print(f"Searching {', '.join(networks) or 'broadcast only'} ...")
        found = await pj.discover(broadcast_addresses=broadcasts, networks=networks)
        for item in found:
            print(f"  {item.label}  mac={item.mac}  class={item.pjlink_class}")
        if not found:
            print("  nothing found")
        return 0

    client = pj.PJLinkClient(args.host, args.port, args.password)
    try:
        if args.action == "raw":
            print(await client.command(args.command, args.parameter, args.cls))
        else:
            info = await client.fetch_info()
            status = await client.fetch_status()
            print(json.dumps({"info": asdict(info), "status": asdict(status)}, indent=2, default=str))
    except pj.PJLinkError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    finally:
        await client.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
