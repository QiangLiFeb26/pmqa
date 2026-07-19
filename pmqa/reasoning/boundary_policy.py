"""Canonical prohibited-key policy for the reasoning trust boundary."""

import re


PROHIBITED_REASONING_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "authorization",
        "browser",
        "browser_context",
        "browser_state",
        "cookie",
        "cookies",
        "credential",
        "credentials",
        "dom",
        "html",
        "passwd",
        "password",
        "playwright",
        "raw_dom",
        "refresh_token",
        "runtime",
        "screenshot",
        "secret",
        "session",
        "session_id",
        "storage_state",
        "token",
        "tokens",
    }
)


def normalize_reasoning_key(value: str) -> str:
    """Normalize case and separators before reasoning-boundary comparison."""

    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def is_prohibited_reasoning_key(value: str) -> bool:
    """Return whether a field name is prohibited at the reasoning boundary."""

    return normalize_reasoning_key(value) in PROHIBITED_REASONING_KEYS
