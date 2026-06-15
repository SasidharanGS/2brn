# Mobile bridge (companion app support)

These are **additive, opt-in** changes that let the 2brn mobile companion
(React Native / Expo Android) reach the daemon and feed it shared content. They are
**off by default** — with no config change the daemon behaves exactly as before
(loopback-only, no new behavior).

## LAN access (opt-in)

The daemon normally binds `127.0.0.1`, so only the local machine can reach it. A
phone on the same Wi-Fi needs the daemon to listen on the LAN. This is gated by a
single config flag:

```jsonc
// ~/.2brn/config.json
{ "lan_access": true }
```

When `lan_access` is `true`, the daemon binds `0.0.0.0:7842` instead of loopback.
**The change takes effect on the next daemon restart.** Every endpoint except the
`/status` liveness probe still requires a token, so exposure on the LAN does not
weaken auth — see [Authentication](#authentication-master-token-vs-device-tokens)
for which token gates what.

You can toggle it from the API: `PUT /settings { "lan_access": true }` (also
returned by `GET /settings`), then restart the daemon.

> Security note: transport is plain HTTP over the LAN in this version; the bearer
> token is the protection. TLS / a relay for off-network access are future work.

## Authentication (master token vs. device tokens)

There are **two kinds of token**, enforced by the auth middleware
(`main._require_api_token`):

- **Master token** — `~/.2brn/api_token`, shared with the desktop UI through a
  `0600` file. Accepted **only on loopback** (`127.0.0.1`/`::1`). The desktop
  talks only to loopback, so the master key never needs to be valid over the
  LAN.
- **Per-device tokens** — minted one per paired phone, stored only as a SHA-256
  hash, and **independently revocable**. A phone on the LAN must present its own
  device token (`Authorization: Bearer <device-token>`); the master token is
  *rejected* off-loopback.

Device-management endpoints (`/devices*`) require the **master token on
loopback**, so a phone holding a device token cannot enumerate or revoke
devices — it gets a `403`. Revoking a device deletes its row, and its token
stops authenticating immediately (the phone then self-heals to its pairing
screen on the next `401`).

## Endpoints added

All are token-gated (not public). The `/devices*` endpoints additionally require
the master token on loopback (desktop-only); the `/ingest*` and read endpoints
accept a per-device token over the LAN.

### `POST /devices`  *(loopback + master only)*
Mints a per-device token. The plaintext token is returned **once** here (for the
pairing QR / manual entry) and is otherwise stored only as a SHA-256 hash.

```jsonc
// request
{ "name": "My phone" }            // optional, defaults to "device"
// response
{ "id": 3, "name": "My phone", "token": "…" }
```

### `GET /devices`  *(loopback + master only)*
Lists paired devices, newest first. Never includes the token (or its hash).

```json
[{ "id": 3, "name": "My phone", "created_at": "…", "last_seen_at": "…" }]
```

### `DELETE /devices/{id}`  *(loopback + master only)*
Revokes a device. Its token stops authenticating immediately.

```json
{ "ok": true, "deleted": true }
```

### `GET /connection-info`
Returns the candidate URLs a phone can use, for rendering a pairing QR code:

```json
{
  "hostname": "mymac.local",
  "port": 7842,
  "lan_access": true,
  "lan_urls": ["http://192.168.1.23:7842"]
}
```

`lan_urls` are computed regardless of `lan_access`; `lan_access` tells the client
whether the daemon is actually bound to them yet.

### `POST /ingest/note`
The "Save to 2brn" share target. Persists the shared item to the additive
`shared_notes` table **and** embeds it into the `note_memories` ChromaDB
collection (so it surfaces in chat RAG alongside Joplin notes). Persisting is the
guaranteed step; embedding is best-effort (a row with `embedded=0` is healed on a
future resync if the provider is offline).

```jsonc
// request
{ "text": "…", "title": "optional", "source_url": "optional", "tags": "optional" }
// response
{ "ok": true, "id": 42, "embedded": true }
```

### `GET /ingest/notes?limit=50`
Lists recent shared notes (newest first) for the phone's "Saved" screen.

### `DELETE /ingest/notes/{id}`
Removes a shared note from SQLite and (best-effort) from ChromaDB.

## Pairing flow (how the phone connects)

1. Enable `lan_access` and restart the daemon.
2. On the desktop, open the **Devices** screen ("Connect a device") or run the
   terminal helper (`uv run python -m brn_daemon.pair [--name "…"]`). Either one
   mints a fresh **per-device** token via `POST /devices` and builds a deep
   link: `twobrn://pair?u=<encodeURIComponent(url)>&t=<token>`, shown as a QR
   (and as a copyable URL + token for manual entry).
   - The scheme is `twobrn://` (not `2brn://`) because URI schemes can't start
     with a digit (RFC 3986); the URL is `encodeURIComponent`-encoded so the app
     decodes it with the built-in `decodeURIComponent`.
3. The phone scans it (or the user types the URL + token), validates the
   connection, stores `{baseUrl, token}` in the Android Keystore, and attaches
   `Authorization: Bearer <device-token>` to every request.
4. To revoke a phone, delete it from the Devices screen (or
   `DELETE /devices/{id}`). The token stops working immediately and the phone
   returns to its pairing screen on the next `401`.

## Schema

Two additive tables; no existing table is modified:

```sql
CREATE TABLE shared_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT, text TEXT NOT NULL, source_url TEXT, tags TEXT,
    source TEXT NOT NULL DEFAULT 'mobile-share',
    chroma_id TEXT, embedded INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL
);

-- One row per paired phone. Only the SHA-256 hash of the token is stored, so a
-- DB leak never exposes a live credential; revoke = delete the row.
CREATE TABLE devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    last_seen_at TEXT
);
```

## Tests

`daemon/tests/test_mobile_bridge.py` covers the config round-trip, `/connection-info`
shape, the `/settings` `lan_access` round-trip, and ingest persist/list/delete plus
the embed path; `daemon/tests/test_devices_routes.py` and
`daemon/tests/test_auth.py` cover minting/listing/revoking device tokens and the
loopback-vs-LAN auth rules. The full suite stays green (`ruff`, `pyright` 0
errors, `pytest`).
