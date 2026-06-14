"""Device management for mobile pairing (per-device LAN tokens).

Mint, list, and revoke the tokens that paired phones use over the LAN. These
endpoints are gated to **loopback + the master token** by the auth middleware
(``main._require_api_token``): only the local desktop UI manages devices — a
phone (on the LAN, holding a device token) gets a 403. The minted token is
returned exactly once, at creation, for the pairing QR / manual entry; it is
stored only as a SHA-256 hash, so it can never be read back.
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field

from brn_daemon import repository

router = APIRouter()


class DeviceCreate(BaseModel):
    name: str = Field(default="device", max_length=100)


class CreatedDevice(BaseModel):
    id: int
    name: str
    token: str


class DeviceRecord(BaseModel):
    id: int
    name: str
    created_at: str
    last_seen_at: str | None = None


@router.post("/devices", response_model=CreatedDevice)
async def create_device(body: DeviceCreate):
    """Mint a per-device token. The plaintext token is returned only here."""
    name = body.name.strip() or "device"
    device_id, token = await repository.create_device(name)
    return CreatedDevice(id=device_id, name=name, token=token)


@router.get("/devices", response_model=list[DeviceRecord])
async def list_devices():
    """Paired devices, newest first. Never includes the token."""
    return [DeviceRecord(**row) for row in await repository.list_devices()]


@router.delete("/devices/{device_id}")
async def delete_device(device_id: int):
    """Revoke a device. Its token stops authenticating immediately."""
    deleted = await repository.delete_device(device_id)
    return {"ok": True, "deleted": deleted}
