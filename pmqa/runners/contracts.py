"""Canonical provider-neutral runner request and response contracts."""

from __future__ import annotations

from typing import Any, Literal, Optional, Tuple

from pydantic import Field, ValidationError, field_validator, model_validator

from pmqa.run import (
    PMQARunContext,
    RunArtifact,
    RunErrorCategory,
    RunRequest,
    RunnerInvocationRecord,
    RunnerInvocationStatus,
    StructuredResult,
    validate_run_identifier,
)
from pmqa.run.models import _RunContract


RUNNER_CONTRACT_SCHEMA_VERSION = "1"
MAX_RUNNER_TIMEOUT_MS = 3_600_000
_MAX_CAPABILITIES = 1024
_MAX_DISPLAY_NAME_LENGTH = 160
_INVALID_RUNNER_BOUNDARY_MESSAGE = "invalid PMQA runner boundary"
_TERMINAL_STATUSES = frozenset(
    {
        RunnerInvocationStatus.SUCCEEDED,
        RunnerInvocationStatus.PARTIALLY_SUCCEEDED,
        RunnerInvocationStatus.FAILED,
        RunnerInvocationStatus.CANCELLED,
    }
)


class RunnerBoundaryValidationError(ValueError):
    """Reports a fixed safe runner-boundary correlation failure."""

    def __init__(self) -> None:
        super().__init__(_INVALID_RUNNER_BOUNDARY_MESSAGE)


class RunnerMetadata(_RunContract):
    """Stable runner identity and capabilities without runtime configuration."""

    schema_version: Literal["1"]
    runner_id: str
    runner_version: str
    display_name: str
    capabilities: Tuple[str, ...]

    @field_validator("runner_id", "runner_version")
    @classmethod
    def validate_identifiers(cls, value: str) -> str:
        return validate_run_identifier(value)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        if (
            type(value) is not str
            or not value
            or len(value) > _MAX_DISPLAY_NAME_LENGTH
            or value.strip() != value
            or not value.isprintable()
        ):
            raise ValueError("display_name must be bounded printable text")
        return value

    @field_validator("capabilities", mode="before")
    @classmethod
    def validate_capabilities(cls, value: Any) -> Tuple[str, ...]:
        if type(value) not in {list, tuple} or len(value) > _MAX_CAPABILITIES:
            raise ValueError("capabilities must be a bounded ordered array")
        if any(type(item) is not str for item in value):
            raise ValueError("capabilities must contain identifiers")
        capabilities = tuple(validate_run_identifier(item) for item in value)
        if len(capabilities) != len(set(capabilities)):
            raise ValueError("capabilities must be duplicate-free")
        return tuple(sorted(capabilities))


class RunnerRequest(_RunContract):
    """One fully correlated pending invocation supplied to a runner."""

    schema_version: Literal["1"]
    run_request: RunRequest
    context: PMQARunContext
    invocation: RunnerInvocationRecord
    expected_result_schema_id: str
    expected_result_schema_version: str
    timeout_ms: int = Field(ge=1, le=MAX_RUNNER_TIMEOUT_MS)

    @field_validator(
        "expected_result_schema_id",
        "expected_result_schema_version",
    )
    @classmethod
    def validate_identifiers(cls, value: str) -> str:
        return validate_run_identifier(value)

    @model_validator(mode="after")
    def validate_correlations(self) -> "RunnerRequest":
        request = self.run_request
        context = self.context
        invocation = self.invocation
        if (
            request.request_id != context.request_id
            or request.session_id != context.session_id
            or request.workflow_id != context.workflow_id
            or request.workflow_version != context.workflow_version
            or request.runner_id != context.runner_id
            or request.references != context.references
            or invocation.run_id != context.run_id
            or invocation.runner_id != context.runner_id
            or invocation.started_at != context.started_at
        ):
            raise ValueError("runner request correlation is inconsistent")
        if request.requested_at > context.started_at:
            raise ValueError("runner request timestamp order is inconsistent")
        if (
            invocation.status is not RunnerInvocationStatus.PENDING
            or invocation.errors
        ):
            raise ValueError("runner invocation must be pending")
        return self


class RunnerResponse(_RunContract):
    """One terminal runner invocation with canonical result and artifacts."""

    schema_version: Literal["1"]
    invocation: RunnerInvocationRecord
    result: Optional[StructuredResult] = None
    artifacts: Tuple[RunArtifact, ...]

    @field_validator("artifacts", mode="before")
    @classmethod
    def validate_artifacts(cls, value: Any) -> Tuple[Any, ...]:
        if type(value) not in {list, tuple} or len(value) > 1024:
            raise ValueError("artifacts must be a bounded ordered array")
        return tuple(value)

    @model_validator(mode="after")
    def validate_lifecycle(self) -> "RunnerResponse":
        status = self.invocation.status
        errors = self.invocation.errors
        if status not in _TERMINAL_STATUSES:
            raise ValueError("runner response invocation must be terminal")
        if status is RunnerInvocationStatus.SUCCEEDED:
            if self.result is None or errors:
                raise ValueError("successful response requires result without errors")
        elif status is RunnerInvocationStatus.PARTIALLY_SUCCEEDED:
            if self.result is None or not errors:
                raise ValueError("partial response requires result and errors")
        elif status is RunnerInvocationStatus.FAILED:
            if self.result is not None or not errors:
                raise ValueError("failed response requires errors without result")
        else:
            if self.result is not None or not errors:
                raise ValueError("cancelled response requires errors without result")
            if not any(
                error.category is RunErrorCategory.CANCELLED for error in errors
            ):
                raise ValueError("cancelled response requires cancellation error")

        artifact_ids = tuple(artifact.artifact_id for artifact in self.artifacts)
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("output artifact identifiers must be unique")
        return self


def validate_runner_response(
    request: RunnerRequest,
    response: RunnerResponse,
) -> RunnerResponse:
    """Validate complete request/response correlation without leaking values."""

    if (
        type(request) is not RunnerRequest
        or type(response) is not RunnerResponse
    ):
        raise RunnerBoundaryValidationError() from None
    expected = request.invocation
    actual = response.invocation
    if (
        actual.invocation_id != expected.invocation_id
        or actual.run_id != expected.run_id
        or actual.runner_id != expected.runner_id
        or actual.operation != expected.operation
        or actual.step_id != expected.step_id
        or actual.attempt_number != expected.attempt_number
        or actual.retry_of_invocation_id != expected.retry_of_invocation_id
        or (
            actual.fallback_from_invocation_id
            != expected.fallback_from_invocation_id
        )
        or actual.started_at != expected.started_at
    ):
        raise RunnerBoundaryValidationError() from None
    if actual.completed_at is None or actual.completed_at < request.context.started_at:
        raise RunnerBoundaryValidationError() from None
    if response.result is not None and (
        response.result.schema_id != request.expected_result_schema_id
        or (
            response.result.result_schema_version
            != request.expected_result_schema_version
        )
    ):
        raise RunnerBoundaryValidationError() from None
    return response


__all__ = [
    "MAX_RUNNER_TIMEOUT_MS",
    "RUNNER_CONTRACT_SCHEMA_VERSION",
    "RunnerBoundaryValidationError",
    "RunnerMetadata",
    "RunnerRequest",
    "RunnerResponse",
    "validate_runner_response",
]
