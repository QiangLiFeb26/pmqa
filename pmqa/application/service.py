"""Synchronous single-attempt PMQA Application Service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional

from pmqa.application.contracts import (
    APPLICATION_CONTRACT_SCHEMA_VERSION,
    ApplicationFailureCode,
    ApplicationRunResult,
    PMQAApplicationError,
    WorkflowAdapterValidationError,
)
from pmqa.application.registry import RunnerRegistry, WorkflowRegistry
from pmqa.run import (
    ApprovalMode,
    PMQARunContext,
    RunRecord,
    RunRequest,
    RunStatus,
    RunnerInvocationRecord,
    RunnerInvocationStatus,
    validate_run_identifier,
)
from pmqa.runners.base import RunnerControl
from pmqa.runners.contracts import (
    MAX_RUNNER_TIMEOUT_MS,
    RUNNER_CONTRACT_SCHEMA_VERSION,
    RunnerBoundaryValidationError,
    RunnerRequest,
    RunnerResponse,
    validate_runner_response,
)


APPLICATION_RUN_OPERATION = "application.execute-workflow"
_DEFAULT_RUNNER_TIMEOUT_MS = 30_000
_RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS = (
    MemoryError,
    KeyboardInterrupt,
    SystemExit,
    GeneratorExit,
)
_RUN_STATUS_BY_INVOCATION_STATUS = {
    RunnerInvocationStatus.SUCCEEDED: RunStatus.SUCCEEDED,
    RunnerInvocationStatus.PARTIALLY_SUCCEEDED:
        RunStatus.PARTIALLY_SUCCEEDED,
    RunnerInvocationStatus.FAILED: RunStatus.FAILED,
    RunnerInvocationStatus.CANCELLED: RunStatus.CANCELLED,
}


class PMQAApplicationService:
    """Explicitly select and execute one workflow/runner attempt."""

    __slots__ = (
        "_clock",
        "_runner_registry",
        "_runner_timeout_ms",
        "_workflow_registry",
    )

    def __init__(
        self,
        *,
        workflow_registry: WorkflowRegistry,
        runner_registry: RunnerRegistry,
        clock: Callable[[], datetime],
        runner_timeout_ms: int = _DEFAULT_RUNNER_TIMEOUT_MS,
    ) -> None:
        if (
            type(workflow_registry) is not WorkflowRegistry
            or type(runner_registry) is not RunnerRegistry
            or type(runner_timeout_ms) is not int
            or not 1 <= runner_timeout_ms <= MAX_RUNNER_TIMEOUT_MS
        ):
            raise PMQAApplicationError(
                ApplicationFailureCode.INVALID_APPLICATION_REQUEST
            ) from None
        if not callable(clock):
            raise PMQAApplicationError(
                ApplicationFailureCode.INVALID_APPLICATION_CLOCK
            ) from None
        self._workflow_registry = workflow_registry
        self._runner_registry = runner_registry
        self._clock = clock
        self._runner_timeout_ms = runner_timeout_ms

    def execute(
        self,
        request: RunRequest,
        *,
        run_id: str,
        invocation_id: str,
        control: Optional[RunnerControl] = None,
    ) -> ApplicationRunResult:
        canonical_request = self._canonical_request(request)
        workflow = self._workflow_registry.resolve(
            canonical_request.workflow_id,
            canonical_request.workflow_version,
        )
        definition = workflow.definition
        if (
            canonical_request.input_schema_id != definition.input_schema_id
            or canonical_request.input_schema_version
            != definition.input_schema_version
        ):
            raise PMQAApplicationError(
                ApplicationFailureCode.WORKFLOW_INPUT_SCHEMA_MISMATCH
            ) from None
        self._validate_live_workflow_definition(workflow)
        self._validate_workflow_request(workflow.adapter, canonical_request)

        runner_registration = self._runner_registry.resolve(
            canonical_request.runner_id
        )
        if not set(definition.required_runner_capabilities).issubset(
            runner_registration.metadata.capabilities
        ):
            raise PMQAApplicationError(
                ApplicationFailureCode.RUNNER_CAPABILITY_MISMATCH
            ) from None
        self._validate_live_runner_metadata(runner_registration)
        if definition.approval_mode is not ApprovalMode.NONE:
            raise PMQAApplicationError(
                ApplicationFailureCode.APPROVAL_REQUIRED
            ) from None

        canonical_run_id = self._canonical_identifier(run_id)
        canonical_invocation_id = self._canonical_identifier(invocation_id)
        runtime_control = self._control(control)
        started_at = self._sample_clock()
        if started_at < canonical_request.requested_at:
            raise PMQAApplicationError(
                ApplicationFailureCode.INVALID_APPLICATION_CLOCK
            ) from None

        context = PMQARunContext(
            schema_version="1",
            run_id=canonical_run_id,
            request_id=canonical_request.request_id,
            session_id=canonical_request.session_id,
            workflow_id=canonical_request.workflow_id,
            workflow_version=canonical_request.workflow_version,
            runner_id=canonical_request.runner_id,
            references=canonical_request.references,
            started_at=started_at,
        )
        pending_invocation = RunnerInvocationRecord(
            schema_version="1",
            invocation_id=canonical_invocation_id,
            run_id=canonical_run_id,
            runner_id=canonical_request.runner_id,
            operation=APPLICATION_RUN_OPERATION,
            step_id=None,
            status=RunnerInvocationStatus.PENDING,
            started_at=started_at,
            completed_at=None,
            duration_ms=None,
            attempt_number=1,
            retry_of_invocation_id=None,
            fallback_from_invocation_id=None,
            errors=(),
        )
        runner_request = RunnerRequest(
            schema_version=RUNNER_CONTRACT_SCHEMA_VERSION,
            run_request=canonical_request,
            context=context,
            invocation=pending_invocation,
            expected_result_schema_id=definition.result_schema_id,
            expected_result_schema_version=definition.result_schema_version,
            timeout_ms=self._runner_timeout_ms,
        )

        response = self._execute_runner(
            runner_registration.runner,
            runner_request,
            runtime_control,
        )
        if response.result is not None:
            self._validate_workflow_result(
                workflow.adapter,
                response.result,
            )
        return self._assemble_result(
            canonical_request,
            response,
        )

    @staticmethod
    def _canonical_request(request: RunRequest) -> RunRequest:
        if type(request) is not RunRequest:
            raise PMQAApplicationError(
                ApplicationFailureCode.INVALID_APPLICATION_REQUEST
            ) from None
        failed = False
        canonical = None
        try:
            canonical = RunRequest.from_dict(request.to_dict())
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except Exception:
            failed = True
        if failed or canonical is None:
            raise PMQAApplicationError(
                ApplicationFailureCode.INVALID_APPLICATION_REQUEST
            ) from None
        return canonical

    @staticmethod
    def _validate_live_workflow_definition(workflow) -> None:
        failed = False
        live_definition = None
        try:
            live_definition = workflow.adapter.definition
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except Exception:
            failed = True
        if (
            failed
            or type(live_definition) is not type(workflow.definition)
            or live_definition != workflow.definition
        ):
            raise PMQAApplicationError(
                ApplicationFailureCode.WORKFLOW_DEFINITION_CHANGED
            ) from None

    @staticmethod
    def _validate_workflow_request(adapter, request: RunRequest) -> None:
        failed = False
        try:
            adapter.validate_request(request)
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except WorkflowAdapterValidationError:
            failed = True
        if failed:
            raise PMQAApplicationError(
                ApplicationFailureCode.WORKFLOW_INPUT_INVALID
            ) from None

    @staticmethod
    def _validate_live_runner_metadata(registration) -> None:
        failed = False
        live_metadata = None
        try:
            live_metadata = registration.runner.metadata
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except Exception:
            failed = True
        if (
            failed
            or type(live_metadata) is not type(registration.metadata)
            or live_metadata != registration.metadata
        ):
            raise PMQAApplicationError(
                ApplicationFailureCode.RUNNER_METADATA_CHANGED
            ) from None

    @staticmethod
    def _canonical_identifier(value: str) -> str:
        failed = False
        canonical = None
        try:
            canonical = validate_run_identifier(value)
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except ValueError:
            failed = True
        if failed or canonical is None:
            raise PMQAApplicationError(
                ApplicationFailureCode.INVALID_RUN_IDENTIFIER
            ) from None
        return canonical

    @staticmethod
    def _control(control: Optional[RunnerControl]) -> RunnerControl:
        if control is None:
            return RunnerControl()
        if type(control) is not RunnerControl:
            raise PMQAApplicationError(
                ApplicationFailureCode.INVALID_APPLICATION_REQUEST
            ) from None
        return control

    def _sample_clock(self) -> datetime:
        failed = False
        normalized = None
        try:
            sampled = self._clock()
            if (
                type(sampled) is not datetime
                or sampled.tzinfo is None
                or sampled.utcoffset() is None
            ):
                failed = True
            else:
                normalized = sampled.astimezone(timezone.utc)
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except Exception:
            failed = True
        if failed or normalized is None:
            raise PMQAApplicationError(
                ApplicationFailureCode.INVALID_APPLICATION_CLOCK
            ) from None
        return normalized

    @staticmethod
    def _execute_runner(
        runner,
        request: RunnerRequest,
        control: RunnerControl,
    ) -> RunnerResponse:
        try:
            response = runner.execute(request, control)
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except RunnerBoundaryValidationError:
            response = None
        if response is None or type(response) is not RunnerResponse:
            raise PMQAApplicationError(
                ApplicationFailureCode.RUNNER_BOUNDARY_FAILED
            ) from None

        reconstruction_failed = False
        canonical_response = None
        try:
            canonical_response = RunnerResponse.from_dict(response.to_dict())
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except Exception:
            reconstruction_failed = True
        if reconstruction_failed or canonical_response is None:
            raise PMQAApplicationError(
                ApplicationFailureCode.RUNNER_BOUNDARY_FAILED
            ) from None

        validation_failed = False
        try:
            canonical_response = validate_runner_response(
                request,
                canonical_response,
            )
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except RunnerBoundaryValidationError:
            validation_failed = True
        if validation_failed:
            raise PMQAApplicationError(
                ApplicationFailureCode.RUNNER_BOUNDARY_FAILED
            ) from None
        return canonical_response

    @staticmethod
    def _validate_workflow_result(adapter, result) -> None:
        failed = False
        try:
            adapter.validate_result(result)
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except WorkflowAdapterValidationError:
            failed = True
        if failed:
            raise PMQAApplicationError(
                ApplicationFailureCode.WORKFLOW_RESULT_INVALID
            ) from None

    @staticmethod
    def _assemble_result(
        request: RunRequest,
        response: RunnerResponse,
    ) -> ApplicationRunResult:
        invocation = response.invocation
        run_record = RunRecord(
            schema_version="1",
            run_id=invocation.run_id,
            request_id=request.request_id,
            session_id=request.session_id,
            workflow_id=request.workflow_id,
            workflow_version=request.workflow_version,
            runner_id=request.runner_id,
            status=_RUN_STATUS_BY_INVOCATION_STATUS[invocation.status],
            references=request.references,
            started_at=invocation.started_at,
            completed_at=invocation.completed_at,
            duration_ms=invocation.duration_ms,
            current_step_id=None,
            result=response.result,
            artifacts=response.artifacts,
            errors=invocation.errors,
            runner_invocation_ids=(invocation.invocation_id,),
            outcome_metrics=None,
            created_at=request.requested_at,
            updated_at=invocation.completed_at,
        )
        return ApplicationRunResult(
            schema_version=APPLICATION_CONTRACT_SCHEMA_VERSION,
            run_request=request,
            run_record=run_record,
            runner_response=response,
        )


__all__ = [
    "APPLICATION_RUN_OPERATION",
    "PMQAApplicationService",
]
