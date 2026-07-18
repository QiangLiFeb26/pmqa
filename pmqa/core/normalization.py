"""Normalization boundary for knowledge captured from external systems."""

from typing import Any, Dict, Protocol


class SnapshotNormalizer(Protocol):
    """Removes unsafe data and normalizes captured snapshot values."""

    def normalize(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """Return a safe JSON-compatible snapshot."""


class PassthroughNormalizer:
    """Keeps already-safe evidence while dropping sensitive field names."""

    _blocked_terms = ("cookie", "token", "password", "secret", "storage")

    def normalize(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively omit keys that commonly carry authentication data."""

        return self._clean(snapshot)

    def _clean(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: self._clean(item)
                for key, item in value.items()
                if not any(term in key.lower() for term in self._blocked_terms)
            }
        if isinstance(value, list):
            return [self._clean(item) for item in value]
        return value
