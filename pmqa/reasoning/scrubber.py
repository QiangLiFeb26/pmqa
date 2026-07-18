"""Provider-independent security boundary for reasoning requests."""

import math
import re
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from pmqa.models import Element, Interaction, Page
from pmqa.reasoning.models import ReasoningRequest
from pmqa.reasoning.validation import ReasoningValidationError, validate_reasoning_request
from pmqa.utils.hashing import canonical_json_sha256


class ScrubStatus(str, Enum):
    """Describes whether a scrub operation completed successfully."""

    COMPLETED = "completed"


class RedactionRecord(BaseModel):
    """Describes a redaction without retaining its original sensitive value."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=1)
    rule: str = Field(min_length=1)
    replacement: str = "[REDACTED]"


class ScrubReport(BaseModel):
    """Explains deterministic removals, redactions, and provenance hashes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str = Field(min_length=1)
    status: ScrubStatus
    rules_applied: List[str] = Field(default_factory=list)
    removed_fields: List[str] = Field(default_factory=list)
    redacted_values: List[RedactionRecord] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class ScrubInput(BaseModel):
    """Carries approved structured knowledge for boundary sanitization."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    task_type: str = Field(min_length=1)
    provider_hint: Optional[str] = None
    product_id: str = Field(min_length=1)
    artifact_version: str = Field(min_length=1)
    pages: List[Page] = Field(default_factory=list)
    elements: List[Element] = Field(default_factory=list)
    interactions: List[Interaction] = Field(default_factory=list)
    constraints: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ScrubResult(BaseModel):
    """Returns the validated safe request and its immutable scrub report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request: ReasoningRequest
    report: ScrubReport


class ScrubValidationError(ValueError):
    """Reports unsafe or unsupported data at the scrub boundary."""


class ReasoningScrubber(ABC):
    """Converts approved structured knowledge into a safe reasoning request."""

    @abstractmethod
    def scrub(self, source: ScrubInput) -> ScrubResult:
        """Scrub, validate, and explain one reasoning-boundary request."""


class DeterministicReasoningScrubber(ReasoningScrubber):
    """Apply one deterministic boundary policy recursively.

    Prohibited dictionary fields are removed, sensitive values embedded in
    useful strings are replaced with ``[REDACTED]``, and unsupported runtime
    objects are rejected before either operation can hide them.
    """

    def scrub(self, source: ScrubInput) -> ScrubResult:
        """Return a validated request and a report that never contains secrets."""

        try:
            valid_source = ScrubInput.model_validate(source)
        except ValidationError as error:
            raise ScrubValidationError(_validation_message(error)) from error

        removed: List[str] = []
        redactions: List[RedactionRecord] = []
        rules: set[str] = set()
        source_payload = valid_source.model_dump(mode="python")
        _reject_runtime_objects(source_payload, "")
        sanitized = _sanitize(
            source_payload,
            "",
            removed,
            redactions,
            rules,
        )
        input_hash = canonical_json_sha256(sanitized)
        try:
            request = validate_reasoning_request(ReasoningRequest.model_validate(sanitized))
        except (ValidationError, ReasoningValidationError) as error:
            raise ScrubValidationError(f"Scrubbed request is invalid: {error}") from error
        output = request.model_dump(mode="json")
        report = ScrubReport(
            request_id=request.request_id,
            status=ScrubStatus.COMPLETED,
            rules_applied=sorted(rules),
            removed_fields=sorted(removed),
            redacted_values=sorted(
                redactions,
                key=lambda item: (item.path, item.rule, item.replacement),
            ),
            input_hash=input_hash,
            output_hash=canonical_json_sha256(output),
        )
        return ScrubResult(request=request, report=report)


_PROHIBITED_KEYS = {
    "password",
    "passwd",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "api_key",
    "apikey",
    "cookie",
    "cookies",
    "credential",
    "credentials",
    "storage_state",
    "browser",
    "browser_context",
    "playwright",
    "raw_dom",
    "html",
}

_BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_COOKIE_PATTERN = re.compile(r"(?i)\b(cookie)\s*:\s*[^\r\n]+")
_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(api[\s_-]?key|password|passwd|access[\s_-]?token|"
    r"refresh[\s_-]?token|token)\s*([:=])\s*"
    r"(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)


def _sanitize(
    value: Any,
    path: str,
    removed: List[str],
    redactions: List[RedactionRecord],
    rules: set[str],
) -> Any:
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ScrubValidationError(f"Unsupported non-finite number at {_display_path(path)}")
        return value
    if isinstance(value, str):
        return _redact_string(value, _display_path(path), redactions, rules)
    if isinstance(value, Enum):
        return _sanitize(value.value, path, removed, redactions, rules)
    if isinstance(value, dict):
        sanitized: Dict[str, Any] = {}
        for key in sorted(value):
            if not isinstance(key, str):
                raise ScrubValidationError(
                    f"Unsupported non-string key at {_display_path(path)}"
                )
            child_path = f"{path}.{key}" if path else key
            if _normalize_key(key) in _PROHIBITED_KEYS:
                removed.append(child_path)
                rules.add("prohibited-key-removal")
                continue
            sanitized[key] = _sanitize(
                value[key], child_path, removed, redactions, rules
            )
        return sanitized
    if isinstance(value, (list, tuple)):
        return [
            _sanitize(item, f"{path}[{index}]", removed, redactions, rules)
            for index, item in enumerate(value)
        ]
    raise ScrubValidationError(f"Unsupported runtime object at {_display_path(path)}")


def _reject_runtime_objects(value: Any, path: str) -> None:
    if value is None or isinstance(value, (str, bool, int, Enum)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ScrubValidationError(f"Unsupported non-finite number at {_display_path(path)}")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ScrubValidationError(
                    f"Unsupported non-string key at {_display_path(path)}"
                )
            child_path = f"{path}.{key}" if path else key
            _reject_runtime_objects(item, child_path)
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_runtime_objects(item, f"{path}[{index}]")
        return
    raise ScrubValidationError(f"Unsupported runtime object at {_display_path(path)}")


def _redact_string(
    value: str,
    path: str,
    redactions: List[RedactionRecord],
    rules: set[str],
) -> str:
    result, count = _BEARER_PATTERN.subn("Bearer [REDACTED]", value)
    if count:
        _record_redaction(path, "bearer-value-redaction", count, redactions, rules)

    def redact_cookie(match: re.Match) -> str:
        return f"{match.group(1)}: [REDACTED]"

    result, count = _COOKIE_PATTERN.subn(redact_cookie, result)
    if count:
        _record_redaction(path, "cookie-header-redaction", count, redactions, rules)

    def redact_assignment(match: re.Match) -> str:
        return f"{match.group(1)}{match.group(2)}[REDACTED]"

    result, count = _ASSIGNMENT_PATTERN.subn(redact_assignment, result)
    if count:
        _record_redaction(path, "secret-assignment-redaction", count, redactions, rules)
    return result


def _record_redaction(
    path: str,
    rule: str,
    count: int,
    redactions: List[RedactionRecord],
    rules: set[str],
) -> None:
    rules.add(rule)
    redactions.extend(RedactionRecord(path=path, rule=rule) for _ in range(count))


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def _display_path(path: str) -> str:
    return path or "input"


def _validation_message(error: ValidationError) -> str:
    paths = [".".join(str(part) for part in item["loc"]) for item in error.errors()]
    return "Invalid scrub input at " + ", ".join(paths)
