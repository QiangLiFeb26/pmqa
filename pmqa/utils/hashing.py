"""Deterministic hashing helpers for JSON-compatible values."""

import hashlib
import json
from typing import Any


def canonical_json_sha256(value: Any) -> str:
    """Return a SHA-256 digest over canonical UTF-8 JSON."""

    canonical = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
