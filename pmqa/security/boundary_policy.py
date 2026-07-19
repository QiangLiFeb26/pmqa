"""Dependency-free prohibited-key policies for serializable boundaries."""

import re
from typing import AbstractSet


COMMON_PROHIBITED_KEYS = frozenset(
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

# Reasoning requests currently need no restrictions beyond the shared policy.
REASONING_PROHIBITED_KEYS = COMMON_PROHIBITED_KEYS

WORKFLOW_STATE_PROHIBITED_KEY_EXTENSIONS = frozenset(
    {
        "connection",
        "llm_client",
        "locator",
        "provider_instance",
    }
)
WORKFLOW_STATE_PROHIBITED_KEYS = (
    COMMON_PROHIBITED_KEYS | WORKFLOW_STATE_PROHIBITED_KEY_EXTENSIONS
)


def normalize_boundary_key(value: str) -> str:
    """Normalize case and separators before boundary-policy comparison."""

    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def is_prohibited_key(value: str, policy: AbstractSet[str]) -> bool:
    """Return whether a normalized field name is prohibited by ``policy``."""

    return normalize_boundary_key(value) in policy
