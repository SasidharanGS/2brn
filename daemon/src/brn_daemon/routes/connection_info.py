"""Connection-info endpoint for mobile pairing.

Reports the URLs a phone on the same network can use to reach this daemon, so the
desktop UI can render a pairing QR code. Token-gated (not in PUBLIC_PATHS); never
exposes the token itself — the desktop UI already holds it and builds the QR.
"""
import asyncio
import socket

from fastapi import APIRouter
from pydantic import BaseModel

from brn_daemon.config import load_config

router = APIRouter()

DAEMON_PORT = 7842


def _lan_ipv4_addresses() -> list[str]:
    """Best-effort enumeration of this machine's non-loopback IPv4 addresses.

    Combines a hostname lookup with the classic "connect a UDP socket toward a
    public IP" trick (no packets are actually sent) to discover the primary LAN
    address even when the hostname doesn't resolve to it.
    """
    ips: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = str(info[4][0])
            if not ip.startswith("127."):
                ips.add(ip)
    except OSError:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ips.add(s.getsockname()[0])
        finally:
            s.close()
    except OSError:
        pass
    return sorted(ip for ip in ips if not ip.startswith("127."))


class ConnectionInfoResponse(BaseModel):
    hostname: str
    port: int
    lan_access: bool
    lan_urls: list[str]


@router.get("/connection-info", response_model=ConnectionInfoResponse)
async def get_connection_info():
    """Candidate LAN URLs for pairing a phone.

    ``lan_access`` reports whether the daemon is actually bound to the LAN (a
    restart is needed after toggling it). ``lan_urls`` are the candidate base URLs
    regardless, so the desktop can show the user what to enable.
    """
    loop = asyncio.get_event_loop()
    cfg = await loop.run_in_executor(None, load_config)
    ips = await loop.run_in_executor(None, _lan_ipv4_addresses)
    return ConnectionInfoResponse(
        hostname=socket.gethostname(),
        port=DAEMON_PORT,
        lan_access=cfg.lan_access,
        lan_urls=[f"http://{ip}:{DAEMON_PORT}" for ip in ips],
    )
