"""Tests for canonical PMQA Application Service result contracts."""

from datetime import datetime, timedelta, timezone
import json

import pytest
from pydantic import ValidationError

from pmqa.application import (
    APPLICATION_CONTRACT_SCHEMA_VERSION,
    ApplicationFailureCode,
    ApplicationRunResult,
    PMQAApplicationError,
)
from pmqa.run import (
    OutcomeMetrics,
    RunArtifact,
    RunError,
    RunErrorCategory,
    RunRecord,
    RunRequest,
    RunStatus,
    RunnerInvocationRecord,
    RunnerInvocationStatus,
    RunContractValidationError,
)
from pmqa.runners import RunnerResponse


def _time(minutes: int = 0) -> datetime:
    return datetime(2026, 7, 24, 12, tzinfo=timezone.utc) + timedelta(
        minutes=minutes
    )


def _error(index: int = 1) -> RunError:
    return RunError(
        code=f"runner.error-{index}",
        category=RunErrorCategory.EXECUTION,
        safe_message="Runner execution failed safely.",
        step_id=None,
        retryable=False,
        error_type="runner-error",
    )


def _artifact() -> RunArtifact:
    return RunArtifact(
        artifact_id="artifact.output",
        artifact_type="test-output",
        artifact_schema_version="1",
        storage_key="runs/run.1/artifacts/output",
        content_digest="a" * 64,
        created_at=_time(1),
    )


def _invocation(
    status: RunnerInvocationStatus = RunnerInvocationStatus.SUCCEEDED,
    **updates,
) -> RunnerInvocationRecord:
    errors = ()
    if status is RunnerInvocationStatus.PARTIALLY_SUCCEEDED:
        errors = (_error(),)
    elif status is RunnerInvocationStatus.FAILED:
        errors = (_error(),)
    elif status is RunnerInvocationStatus.CANCELLED:
        errors = (
            _error().model_copy(
                update={"category": RunErrorCategory.CANCELLED}
            ),
        )
    values = {
        "schema_version": "1",
        "invocation_id": "invocation.1",
        "run_id": "run.1",
        "runner_id": "runner.mock",
        "operation": "application.execute-workflow",
        "step_id": None,
        "status": status,
        "started_at": _time(),
        "completed_at": _time(1),
        "duration_ms": 250,
        "attempt_number": 1,
        "retry_of_invocation_id": None,
        "fallback_from_invocation_id": None,
        "errors": errors,
    }
    values.update(updates)
    return RunnerInvocationRecord(**values)


def _record(
    invocation: RunnerInvocationRecord = None,
    **updates,
) -> RunRecord:
    terminal = invocation or _invocation()
    result = None
    if terminal.status in {
        RunnerInvocationStatus.SUCCEEDED,
        RunnerInvocationStatus.PARTIALLY_SUCCEEDED,
    }:
        from pmqa.run import StructuredResult

        result = StructuredResult(
            schema_version="1",
            schema_id="schema.result",
            result_schema_version="1",
            data={"outcome": terminal.status.value},
        )
    values = {
        "schema_version": "1",
        "run_id": terminal.run_id,
        "request_id": "request.1",
        "session_id": "session.1",
        "workflow_id": "workflow.test",
        "workflow_version": "1",
        "runner_id": terminal.runner_id,
        "status": RunStatus(terminal.status.value),
        "references": (),
        "started_at": terminal.started_at,
        "completed_at": terminal.completed_at,
        "duration_ms": terminal.duration_ms,
        "current_step_id": None,
        "result": result,
        "artifacts": (),
        "errors": terminal.errors,
        "runner_invocation_ids": (terminal.invocation_id,),
        "outcome_metrics": None,
        "created_at": _time(-1),
        "updated_at": terminal.completed_at,
    }
    values.update(updates)
    return RunRecord(**values)


def _request(**updates) -> RunRequest:
    values = {
        "schema_version": "1",
        "request_id": "request.1",
        "session_id": "session.1",
        "workflow_id": "workflow.test",
        "workflow_version": "1",
        "runner_id": "runner.mock",
        "input_schema_id": "schema.input",
        "input_schema_version": "1",
        "inputs": {},
        "references": (),
        "requested_at": _time(-1),
    }
    values.update(updates)
    return RunRequest(**values)


def _application_result(
    status: RunnerInvocationStatus = RunnerInvocationStatus.SUCCEEDED,
    **updates,
) -> ApplicationRunResult:
    invocation = _invocation(status)
    record = _record(invocation)
    response = RunnerResponse(
        schema_version="1",
        invocation=invocation,
        result=record.result,
        artifacts=record.artifacts,
    )
    values = {
        "schema_version": APPLICATION_CONTRACT_SCHEMA_VERSION,
        "run_request": _request(),
        "run_record": record,
        "runner_response": response,
    }
    values.update(updates)
    return ApplicationRunResult(**values)


def test_application_failure_codes_and_messages_are_stable_and_safe() -> None:
    assert {
        "workflow_not_found",
        "runner_not_found",
        "runner_boundary_failed",
        "workflow_result_invalid",
    } <= {code.value for code in ApplicationFailureCode}
    marker = "runtime-secret-marker"
    error = PMQAApplicationError(ApplicationFailureCode.WORKFLOW_NOT_FOUND)

    assert error.code is ApplicationFailureCode.WORKFLOW_NOT_FOUND
    assert marker not in str(error)


@pytest.mark.parametrize(
    "status",
    (
        RunnerInvocationStatus.SUCCEEDED,
        RunnerInvocationStatus.PARTIALLY_SUCCEEDED,
        RunnerInvocationStatus.FAILED,
        RunnerInvocationStatus.CANCELLED,
    ),
)
def test_application_result_statuses_round_trip_canonically(
    status: RunnerInvocationStatus,
) -> None:
    result = _application_result(status)
    wire = json.loads(json.dumps(result.to_dict()))

    assert ApplicationRunResult.from_dict(wire) == result
    assert result.run_record.status.value == status.value
    assert result.run_record.outcome_metrics is None


@pytest.mark.parametrize(
    "run_update",
    (
        {"run_id": "run.other"},
        {"runner_id": "runner.other"},
        {"runner_invocation_ids": ("invocation.other",)},
        {"started_at": _time(-1)},
        {"completed_at": _time(2), "updated_at": _time(2)},
        {"duration_ms": 999},
        {"errors": (_error(2),)},
        {"updated_at": _time(2)},
    ),
)
def test_application_result_rejects_correlation_mismatch(run_update) -> None:
    invocation = _invocation()
    record = _record(invocation, **run_update)

    with pytest.raises(ValidationError, match="correlation"):
        ApplicationRunResult(
            schema_version="1",
            run_request=_request(),
            run_record=record,
            runner_response=RunnerResponse(
                schema_version="1",
                invocation=invocation,
                result=record.result,
                artifacts=record.artifacts,
            ),
        )


def test_application_result_rejects_status_and_metrics_mismatch() -> None:
    invocation = _invocation(RunnerInvocationStatus.SUCCEEDED)
    with pytest.raises(ValidationError, match="status"):
        ApplicationRunResult(
            schema_version="1",
            run_request=_request(),
            run_record=_record(
                invocation,
                status=RunStatus.PARTIALLY_SUCCEEDED,
            ),
            runner_response=RunnerResponse(
                schema_version="1",
                invocation=invocation,
                result=_record(invocation).result,
                artifacts=(),
            ),
        )
    with pytest.raises(ValidationError, match="correlation"):
        ApplicationRunResult(
            schema_version="1",
            run_request=_request(),
            run_record=_record(
                invocation,
                outcome_metrics=OutcomeMetrics(tests_generated=0),
            ),
            runner_response=RunnerResponse(
                schema_version="1",
                invocation=invocation,
                result=_record(invocation).result,
                artifacts=(),
            ),
        )


@pytest.mark.parametrize(
    "request_update",
    (
        {"request_id": "request.other"},
        {"session_id": "session.other"},
        {"workflow_id": "workflow.other"},
        {"workflow_version": "2"},
        {"runner_id": "runner.other"},
        {"requested_at": _time(-2)},
    ),
)
def test_application_result_rejects_request_correlation_mismatch(
    request_update,
) -> None:
    result = _application_result()

    with pytest.raises(ValidationError, match="correlation"):
        result.model_copy(
            update={"run_request": _request(**request_update)}
        )


def test_application_result_rejects_response_payload_mismatch() -> None:
    result = _application_result()
    changed_result = result.run_record.result.model_copy(
        update={"data": {"outcome": "changed"}}
    )
    changed_response = result.runner_response.model_copy(
        update={"result": changed_result}
    )

    with pytest.raises(ValidationError, match="correlation"):
        result.model_copy(update={"runner_response": changed_response})


def test_application_result_rejects_response_artifact_mismatch() -> None:
    result = _application_result()
    changed_response = result.runner_response.model_copy(
        update={"artifacts": (_artifact(),)}
    )

    with pytest.raises(ValidationError, match="correlation"):
        result.model_copy(update={"runner_response": changed_response})


def test_application_result_model_copy_fully_revalidates() -> None:
    result = _application_result()

    with pytest.raises(ValidationError, match="correlation"):
        result.model_copy(
            update={
                "runner_response": result.runner_response.model_copy(
                    update={
                        "invocation":
                            result.runner_invocation.model_copy(
                                update={"duration_ms": 999}
                            )
                    }
                )
            }
        )


@pytest.mark.parametrize(
    "invocation_update,bypass_nested_validation",
    (
        ({"operation": "application.other"}, False),
        ({"step_id": "step.other"}, False),
        ({"attempt_number": 2}, True),
        ({"retry_of_invocation_id": "invocation.previous"}, True),
        ({"fallback_from_invocation_id": "invocation.previous"}, True),
        (
            {
                "operation": "application.other",
                "step_id": "step.other",
                "attempt_number": 2,
                "fallback_from_invocation_id": "invocation.previous",
            },
            False,
        ),
    ),
    ids=(
        "operation",
        "step",
        "attempt-two",
        "retry-predecessor",
        "fallback-predecessor",
        "combined",
    ),
)
@pytest.mark.parametrize(
    "construction_path",
    ("direct", "from-dict", "model-copy"),
)
def test_application_result_enforces_single_attempt_in_every_path(
    invocation_update,
    bypass_nested_validation: bool,
    construction_path: str,
) -> None:
    result = _application_result()
    if construction_path == "from-dict":
        wire = result.to_dict()
        wire["runner_response"]["invocation"].update(invocation_update)
        with pytest.raises(RunContractValidationError):
            ApplicationRunResult.from_dict(wire)
        return

    with pytest.raises(ValidationError):
        changed_invocation = _invocation()
        if bypass_nested_validation:
            changed_invocation.__dict__.update(invocation_update)
        else:
            changed_invocation = changed_invocation.model_copy(
                update=invocation_update
            )
        changed_response = RunnerResponse(
            schema_version="1",
            invocation=changed_invocation,
            result=result.runner_response.result,
            artifacts=result.runner_response.artifacts,
        )
        if construction_path == "direct":
            ApplicationRunResult(
                schema_version="1",
                run_request=result.run_request,
                run_record=result.run_record,
                runner_response=changed_response,
            )
        else:
            result.model_copy(update={"runner_response": changed_response})


def test_application_result_enforces_complete_tree_bound() -> None:
    errors = tuple(_error(index) for index in range(300))
    invocation = _invocation(
        RunnerInvocationStatus.FAILED,
        errors=errors,
    )
    record = _record(invocation)
    response = RunnerResponse(
        schema_version="1",
        invocation=invocation,
        result=None,
        artifacts=(),
    )

    with pytest.raises(ValidationError, match="persistence boundary"):
        ApplicationRunResult(
            schema_version="1",
            run_request=_request(),
            run_record=record,
            runner_response=response,
        )


def test_application_result_rejects_runtime_or_usage_fields() -> None:
    with pytest.raises(ValidationError):
        ApplicationRunResult(
            schema_version="1",
            run_request=_request(),
            run_record=_record(),
            runner_response=_application_result().runner_response,
            provider_client=object(),
        )
