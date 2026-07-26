"""Shared deterministic inspection for recognizable sensitive text."""

from dataclasses import dataclass
import re
from typing import Tuple


_BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_COOKIE_PATTERN = re.compile(r"(?i)\b(cookie|set-cookie)\s*:\s*[^\r\n]+")
_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(api[\s_-]?key|password|passwd|access[\s_-]?token|"
    r"refresh[\s_-]?token|token|secret|credentials?)\s*([:=])\s*"
    r"(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)


@dataclass(frozen=True)
class SensitiveTextRedaction:
    """One redacted value plus deterministic rule/count evidence."""

    text: str
    rule_counts: Tuple[Tuple[str, int], ...]


def redact_recognizable_sensitive_text(value: str) -> SensitiveTextRedaction:
    """Redact high-confidence credential shapes without retaining originals."""

    if not isinstance(value, str):
        raise TypeError("value must be a string")

    result, bearer_count = _BEARER_PATTERN.subn("Bearer [REDACTED]", value)

    def redact_cookie(match: re.Match) -> str:
        return f"{match.group(1)}: [REDACTED]"

    result, cookie_count = _COOKIE_PATTERN.subn(redact_cookie, result)

    def redact_assignment(match: re.Match) -> str:
        return f"{match.group(1)}{match.group(2)}[REDACTED]"

    result, assignment_count = _ASSIGNMENT_PATTERN.subn(
        redact_assignment,
        result,
    )
    counts = tuple(
        (rule, count)
        for rule, count in (
            ("bearer-value-redaction", bearer_count),
            ("cookie-header-redaction", cookie_count),
            ("secret-assignment-redaction", assignment_count),
        )
        if count
    )
    return SensitiveTextRedaction(text=result, rule_counts=counts)


def contains_recognizable_sensitive_text(value: str) -> bool:
    """Return whether the shared high-confidence inspection matched."""

    return bool(redact_recognizable_sensitive_text(value).rule_counts)


__all__ = [
    "SensitiveTextRedaction",
    "contains_recognizable_sensitive_text",
    "redact_recognizable_sensitive_text",
]
