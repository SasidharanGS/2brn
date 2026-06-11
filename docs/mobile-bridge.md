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
`/status` liveness probe still requires the per-machine bearer token
(`~/.2brn/api_token`), so exposure on the LAN does not weaken auth — the token is
the gate.

You can toggle it from the API: `PUT /settings { "lan_access": true }` (also
returned by `GET /settings`), then restart the daemon.

> Security note: transport is plain HTTP over the LAN in this version; the bearer
> token is the protection. TLS / a relay for off-network access are future work.

## Endpoints added

All are token-gated (not public).

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
2. The desktop builds a pairing payload from `GET /connection-info` + the local
   `api_token`, encoded as a deep link: `2brn://pair?u=<base64url(url)>&t=<token>`,
   and shows it as a QR code (desktop UI panel, or a terminal QR helper).
3. The phone scans it, stores `{baseUrl, token}` in the Android Keystore, and
   attaches `Authorization: Bearer <token>` to every request.

## Schema

A single additive table; no existing table is modified:

```sql
CREATE TABLE shared_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT, text TEXT NOT NULL, source_url TEXT, tags TEXT,
    source TEXT NOT NULL DEFAULT 'mobile-share',
    chroma_id TEXT, embedded INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL
);
```

## Tests

`daemon/tests/test_mobile_bridge.py` covers the config round-trip, `/connection-info`
shape, the `/settings` `lan_access` round-trip, and ingest persist/list/delete plus
the embed path. The full suite stays green (`ruff`, `pyright` 0 errors, `pytest`).
