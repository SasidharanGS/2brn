"""Loopback API authentication.

The daemon binds to 127.0.0.1, but loopback alone does not stop *other* local
processes (or local web content) from calling the API and reading captures,
journals, or driving the plugin system. A random bearer token — shared with the
UI through a ``0600`` file in ``~/.2brn/`` (both run as the same OS user) — gates
every endpoint except the liveness probe.

Enforcement is wired in ``main.create_app`` and is active only once a token has
been loaded into the app context (which happens in the real daemon lifespan), so
the test harness, which doesn't run the lifespan, is unaffected.
"""
from __future__ import annotations

import logging
import os
import secrets

from brn_daemon.db import get_brn_home

logger = logging.getLogger(__name__)

TOKEN_FILENAME = "api_token"

# Paths reachable without a token: the liveness probe used by the Electron main
# process (and the launchd auto-start check). It exposes only capture status.
PUBLIC_PATHS = frozenset({"/status"})


def _token_path():
    return get_brn_home() / TOKEN_FILENAME


def load_or_create_token() -> str:
    """Return the API token, creating a fresh ``0600`` file on first run.

    ``BRN_API_TOKEN`` overrides the file (handy for tests and advanced setups).
    Returns ``""`` only if the token can neither be read nor written — in which
    case the caller leaves auth disabled (fail-open) and logs a warning, rather
    than locking the user out of their own app.
    """
    env = os.environ.get("BRN_API_TOKEN")
    if env:
        return env
    path = _token_path()
    try:
        if path.exists():
            existing = path.read_text().strip()
            if existing:
                return existing
        get_brn_home().mkdir(parents=True, exist_ok=True)
        token = secrets.token_urlsafe(32)
        path.write_text(token)
        try:
            os.chmod(path, 0o600)
        except OSError:
            logger.warning("Could not chmod the API token file to 0600")
        return token
    except OSError:
        logger.exception("Could not read or create the API token file — API auth disabled")
        return ""
