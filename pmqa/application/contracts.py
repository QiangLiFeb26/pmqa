"""Canonical application result and safe failure contracts."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import model_validator

from pmqa.run import (
    RunRecord,
    RunRequest,
    RunStatus,
    RunnerInvocationRecord,
    RunnerInvocationStatus,
)
from pmqa.run.models import _RunContract
from pmqa.runners.contracts import RunnerResponse


APPLICATION_CONTRACT_SCHEMA_VERSION = "1"


class ApplicationFailureCode(str, Enum):
    """Small stable vocabulary for expected application-boundary failures."""

    INVALID_APPLICATION_REQUEST = "invalid_application_request"
    INVALID_WORKFLOW_REGISTRY = "invalid_workflow_registry"
    WORKFLOW_NOT_FOUND = "workflow_not_found"
    WORKFLOW_DEFINITION_CHANGED = "workflow_definition_changed"
    WORKFLOW_INPUT_SCHEMA_MISMATCH = "workflow_input_schema_mismatch"
    WORKFLOW_INPUT_INVALID = "workflow_input_invalid"
    APPROVAL_REQUIRED = "approval_required"
    INVALID_RUNNER_REGISTRY = "invalid_runner_registry"
    RUNNER_NOT_FOUND = "runner_not_found"
    RUNNER_CAPABILITY_MISMATCH = "runner_capability_mismatch"
    RUNNER_METADATA_CHANGED = "runner_metadata_changed"
    INVALID_RUN_IDENTIFIER = "invalid_run_identifier"
    INVALID_APPLICATION_CLOCK = "invalid_application_clock"
    RUNNER_BOUNDARY_FAILED = "runner_boundary_failed"
    WORKFLOW_RESULT_INVALID = "workflow_result_invalid"


_APPLICATION_FAILURE_MESSAGES = {
    ApplicationFailureCode.INVALID_APPLICATION_REQUEST:
        "invalid PMQA application request",
    ApplicationFailureCode.INVALID_WORKFLOW_REGISTRY:
        "invalid PMQA workflow registry",
    ApplicationFailureCode.WORKFLOW_NOT_FOUND:
        "PMQA workflow was not found",
    ApplicationFailureCode.WORKFLOW_DEFINITION_CHANGED:
        "PMQA workflow definition changed",
    ApplicationFailureCode.WORKFLOW_INPUT_SCHEMA_MISMATCH:
        "PMQA workflow input schema mismatch",
    ApplicationFailureCode.WORKFLOW_INPUT_INVALID:
        "PMQA workflow input is invalid",
    ApplicationFailureCode.APPROVAL_REQUIRED:
        "PMQA workflow requires approval",
    ApplicationFailureCode.INVALID_RUNNER_REGISTRY:
        "invalid PMQA runner registry",
    ApplicationFailureCode.RUNNER_NOT_FOUND:
        "PMQA runner was not found",
    ApplicationFailureCode.RUNNER_CAPABILITY_MISMATCH:
        "PMQA runner capability mismatch",
    ApplicationFailureCode.RUNNER_METADATA_CHANGED:
        "PMQA runner metadata changed",
    ApplicationFailureCode.INVALID_RUN_IDENTIFIER:
        "invalid PMQA run identifier",
    ApplicationFailureCode.INVALID_APPLICATION_CLOCK:
        "invalid PMQA application clock",
    ApplicationFailureCode.RUNNER_BOUNDARY_FAILED:
        "PMQA runner boundary failed",
    ApplicationFailureCode.WORKFLOW_RESULT_INVALID:
        "PMQA workflow result is invalid",
}

_RUN_STATUS_BY_INVOCATION_STATUS = {
    RunnerInvocationStatus.SUCCEEDED: RunStatus.SUCCEEDED,
    RunnerInvocationStatus.PARTIALLY_SUCCEEDED:
        RunStatus.PARTIALLY_SUCCEEDED,
    RunnerInvocationStatus.FAILED: RunStatus.FAILED,
    RunnerInvocationStatus.CANCELLED: RunStatus.CANCELLED,
}


class PMQAApplicationError(RuntimeError):
    """Expected safe application failure with a stable public code."""

    def __init__(self, code: ApplicationFailureCode) -> None:
        if type(code) is not ApplicationFailureCode:
            raise TypeError("code must be an ApplicationFailureCode")
        self.code = code
        super().__init__(_APPLICATION_FAILURE_MESSAGES[code])


class WorkflowAdapterValidationError(ValueError):
    """Application-owned expected signal from workflow-specific validation."""

    def __init__(self) -> None:
        super().__init__("PMQA workflow validation failed")


class ApplicationRunResult(_RunContract):
    """Canonical single-attempt application result envelope."""

    schema_version: Literal["1"]
    run_request: RunRequest
    run_record: RunRecord
    runner_response: RunnerResponse

    @property
    def runner_invocation(self) -> RunnerInvocationRecord:
        """Return the envelope's one terminal invocation."""

        return self.runner_response.invocation

    @model_validator(mode="after")
    def validate_correlations(self) -> "ApplicationRunResult":
        request = self.run_request
        run = self.run_record
        response = self.runner_response
        invocation = response.invocation
        expected_status = _RUN_STATUS_BY_INVOCATION_STATUS.get(
            invocation.status
        )
        if expected_status is None or run.status is not expected_status:
            raise ValueError("application result status correlation is invalid")
        if (
            run.run_id != invocation.run_id
            or run.request_id != request.request_id
            or run.session_id != request.session_id
            or run.workflow_id != request.workflow_id
            or run.workflow_version != request.workflow_version
            or run.runner_id != request.runner_id
            or run.references != request.references
            or run.runner_id != invocation.runner_id
            or run.runner_invocation_ids != (invocation.invocation_id,)
            or run.started_at != invocation.started_at
            or run.completed_at != invocation.completed_at
            or run.duration_ms != invocation.duration_ms
            or run.errors != invocation.errors
            or run.result != response.result
            or run.artifacts != response.artifacts
            or run.created_at != request.requested_at
            or run.updated_at != invocation.completed_at
            or run.current_step_id is not None
            or run.outcome_metrics is not None
        ):
            raise ValueError("application result correlation is invalid")
        return self


__all__ = [
    "APPLICATION_CONTRACT_SCHEMA_VERSION",
    "ApplicationFailureCode",
    "ApplicationRunResult",
    "PMQAApplicationError",
    "WorkflowAdapterValidationError",
]
