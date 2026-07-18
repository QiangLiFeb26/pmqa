"""Tests for the capture normalization boundary."""

from pmqa.core.normalization import PassthroughNormalizer


def test_normalizer_removes_sensitive_keys_recursively() -> None:
    raw = {
        "url": "https://example.test",
        "cookie": "private",
        "nested": {"accessToken": "private", "text": "safe"},
        "password_value": "private",
    }

    assert PassthroughNormalizer().normalize(raw) == {
        "url": "https://example.test",
        "nested": {"text": "safe"},
    }
