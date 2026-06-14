"""Print pairing info for the 2brn mobile companion.

Run on the desktop (same machine as the daemon):

    uv run python -m brn_daemon.pair [--name "My phone"]

Mints a fresh **per-device** token (never the master loopback token), then shows
the LAN URL + token (for manual entry) and, if the optional ``qrcode`` package is
installed, a scannable QR encoding the ``twobrn://pair`` deep link. Revoke a
device later from the desktop app (Connect a device) or by deleting its row.
"""
import asyncio
import sys
from urllib.parse import quote

from brn_daemon.config import load_config
from brn_daemon.db import init_db
from brn_daemon.repository import create_device
from brn_daemon.routes.connection_info import DAEMON_PORT, _lan_ipv4_addresses


def build_pairing_url(base_url: str, token: str) -> str:
    """Match the deep link the mobile app parses: twobrn://pair?u=<url>&t=<token>."""
    return f"twobrn://pair?u={quote(base_url, safe='')}&t={quote(token, safe='')}"


def _name_from_argv(argv: list[str]) -> str:
    if "--name" in argv:
        i = argv.index("--name")
        if i + 1 < len(argv):
            return argv[i + 1]
    return "phone"


async def _mint_device_token(name: str) -> str:
    await init_db()
    _id, token = await create_device(name)
    return token


def main() -> int:
    cfg = load_config()
    ips = _lan_ipv4_addresses()

    if not ips:
        print("No LAN IP found. Connect to Wi-Fi or Ethernet and try again.")
        return 1
    if not cfg.lan_access:
        print('⚠  LAN access is OFF — the phone cannot reach the daemon yet.')
        print('   Set {"lan_access": true} in ~/.2brn/config.json (or Settings →')
        print("   Connect a device), then restart the daemon and rerun this.\n")

    name = _name_from_argv(sys.argv[1:])
    token = asyncio.run(_mint_device_token(name))
    base_url = f"http://{ips[0]}:{DAEMON_PORT}"
    url = build_pairing_url(base_url, token)

    print("2brn — pair a phone")
    print("===================")
    print(f"Device: {name}")
    print(f"URL   : {base_url}")
    print(f"Token : {token}")
    if len(ips) > 1:
        print(f"(other addresses: {', '.join(ips[1:])})")
    print()

    try:
        import qrcode  # pyright: ignore[reportMissingModuleSource]  # optional dep

        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
        print("Scan this in the 2brn app: Connect a device → Scan QR.")
    except ImportError:
        print("Tip: `uv pip install qrcode` to render a scannable QR here.")
        print("Otherwise, in the app pick 'Enter manually' and type the URL + token above.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
