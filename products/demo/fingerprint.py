"""Canonical SauceDemo structural fingerprints shared by capture adapters."""

import hashlib
import json
from typing import Any


def canonical_saucedemo_structure(value: Any) -> str:
    """Return compact key-sorted UTF-8 JSON without ASCII escaping."""

    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def saucedemo_structural_fingerprint(value: Any) -> str:
    """Hash one bounded structural value as lowercase SHA-256 hex."""

    canonical = canonical_saucedemo_structure(value)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = [
    "canonical_saucedemo_structure",
    "saucedemo_structural_fingerprint",
]
