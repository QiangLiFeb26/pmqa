"""Reasoning-boundary compatibility helpers backed by shared policy."""

from pmqa.security.boundary_policy import (
    REASONING_PROHIBITED_KEYS,
    is_prohibited_key,
    normalize_boundary_key,
)


PROHIBITED_REASONING_KEYS = REASONING_PROHIBITED_KEYS


def normalize_reasoning_key(value: str) -> str:
    """Normalize case and separators before reasoning-boundary comparison."""

    return normalize_boundary_key(value)


def is_prohibited_reasoning_key(value: str) -> bool:
    """Return whether a field name is prohibited at the reasoning boundary."""

    return is_prohibited_key(value, REASONING_PROHIBITED_KEYS)
