"""Deterministic hashing helpers for JSON-compatible values."""

import hashlib
import json
from typing import Any


def canonical_json(value: Any) -> str:
    """Serialize a JSON-compatible value with deterministic formatting."""

    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def canonical_json_sha256(value: Any) -> str:
    """Return a SHA-256 digest over canonical UTF-8 JSON."""

    canonical = canonical_json(value)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
