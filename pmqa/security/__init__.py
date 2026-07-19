"""Low-level security policies shared across PMQA trust boundaries."""

from pmqa.security.boundary_policy import (
    COMMON_PROHIBITED_KEYS,
    REASONING_PROHIBITED_KEYS,
    WORKFLOW_STATE_PROHIBITED_KEYS,
    WORKFLOW_STATE_PROHIBITED_KEY_EXTENSIONS,
    is_prohibited_key,
    normalize_boundary_key,
)

__all__ = [
    "COMMON_PROHIBITED_KEYS",
    "REASONING_PROHIBITED_KEYS",
    "WORKFLOW_STATE_PROHIBITED_KEYS",
    "WORKFLOW_STATE_PROHIBITED_KEY_EXTENSIONS",
    "is_prohibited_key",
    "normalize_boundary_key",
]
