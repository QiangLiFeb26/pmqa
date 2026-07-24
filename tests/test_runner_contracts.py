"""Tests for the provider-neutral PMQA runner contracts."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest
from pydantic import ValidationError

from pmqa.run import (
    PMQARunContext,
    RunArtifact,
    RunError,
    RunErrorCategory,
    RunReference,
    RunRequest,
    RunnerInvocationRecord,
    RunnerInvocationStatus,
    StructuredResult,
)
from pmqa.runners import (
    MAX_RUNNER_TIMEOUT_MS,
    RUNNER_CONTRACT_SCHEMA_VERSION,
    RunnerBoundaryValidationError,
    RunnerMetadata,
    RunnerRequest,
    RunnerResponse,
    validate_runner_response,
)


def _time(minutes: int = 0) -> datetime:
    return datetime(2026, 7, 24, 12, tzinfo=timezone.utc) + timedelta(
        minutes=minutes
    )


def _reference() -> RunReference:
    return RunReference(reference_type="story", reference_id="12345")


def _run_request(**updates) -> RunRequest:
    values = {
        "schema_version": "1",
        "request_id": "request.1",
        "session_id": "session.1",
        "workflow_id": "workflow.generate-tests",
        "workflow_version": "1.0.0",
        "runner_id": "runner.mock",
        "input_schema_id": "schema.workflow-input",
        "input_schema_version": "1",
        "inputs": {"story_ids": ["12345"]},
        "references": (_reference(),),
        "requested_at": _time(-1),
    }
    values.update(updates)
    return RunRequest(**values)


def _context(**updates) -> PMQARunContext:
    values = {
        "schema_version": "1",
        "run_id": "run.1",
        "request_id": "request.1",
        "session_id": "session.1",
        "workflow_id": "workflow.generate-tests",
        "workflow_version": "1.0.0",
        "runner_id": "runner.mock",
        "references": (_reference(),),
        "started_at": _time(),
    }
    values.update(updates)
    return PMQARunContext(**values)


def _pending_invocation(**updates) -> RunnerInvocationRecord:
    values = {
        "schema_version": "1",
        "invocation_id": "invocation.1",
        "run_id": "run.1",
        "runner_id": "runner.mock",
        "operation": "workflow.execute",
        "step_id": "generate",
        "status": RunnerInvocationStatus.PENDING,
        "started_at": _time(),
        "completed_at": None,
        "duration_ms": None,
        "attempt_number": 1,
        "retry_of_invocation_id": None,
        "fallback_from_invocation_id": None,
        "errors": (),
    }
    values.update(updates)
    return RunnerInvocationRecord(**values)


def _runner_request(**updates) -> RunnerRequest:
    values = {
        "schema_version": RUNNER_CONTRACT_SCHEMA_VERSION,
        "run_request": _run_request(),
        "context": _context(),
        "invocation": _pending_invocation(),
        "expected_result_schema_id": "schema.workflow-result",
        "expected_result_schema_version": "1",
        "timeout_ms": 30_000,
    }
    values.update(updates)
    return RunnerRequest(**values)


def _error(
    category: RunErrorCategory = RunErrorCategory.EXECUTION,
) -> RunError:
    return RunError(
        code="runner.test.error",
        category=category,
        safe_message="Runner execution did not fully succeed.",
        step_id="generate",
        retryable=False,
        error_type="runner-test-error",
    )


def _result(**updates) -> StructuredResult:
    values = {
        "schema_version": "1",
        "schema_id": "schema.workflow-result",
        "result_schema_version": "1",
        "data": {"generated": 1},
    }
    values.update(updates)
    return StructuredResult(**values)


def _artifact(index: int = 1) -> RunArtifact:
    return RunArtifact(
        artifact_id=f"artifact.{index}",
        artifact_type="playwright-tests",
        artifact_schema_version="1",
        storage_key=f"runs/run.1/artifacts/item-{index}",
        content_digest=f"{index % 10}" * 64,
        created_at=_time(1),
    )


def _terminal_invocation(
    status: RunnerInvocationStatus,
    **updates,
) -> RunnerInvocationRecord:
    errors = ()
    if status is RunnerInvocationStatus.PARTIALLY_SUCCEEDED:
        errors = (_error(),)
    elif status is RunnerInvocationStatus.FAILED:
        errors = (_error(),)
    elif status is RunnerInvocationStatus.CANCELLED:
        errors = (_error(RunErrorCategory.CANCELLED),)
    values = {
        **_pending_invocation().model_dump(mode="python"),
        "status": status,
        "completed_at": _time(1),
        "duration_ms": 250,
        "errors": errors,
    }
    values.update(updates)
    return RunnerInvocationRecord(**values)


def _response(
    status: RunnerInvocationStatus = RunnerInvocationStatus.SUCCEEDED,
    **updates,
) -> RunnerResponse:
    result = (
        _result()
        if status
        in {
            RunnerInvocationStatus.SUCCEEDED,
            RunnerInvocationStatus.PARTIALLY_SUCCEEDED,
        }
        else None
    )
    values = {
        "schema_version": "1",
        "invocation": _terminal_invocation(status),
        "result": result,
        "artifacts": (_artifact(),),
    }
    values.update(updates)
    return RunnerResponse(**values)


def test_runner_metadata_is_canonical_and_deterministically_ordered() -> None:
    metadata = RunnerMetadata(
        schema_version="1",
        runner_id="runner.mock",
        runner_version="1.0.0",
        display_name="Mock runner",
        capabilities=("test-generation", "exploration"),
    )
    wire = json.loads(json.dumps(metadata.to_dict()))

    assert metadata.capabilities == ("exploration", "test-generation")
    assert RunnerMetadata.from_dict(wire) == metadata
    assert metadata.model_copy() == metadata


def test_runner_metadata_rejects_duplicates_runtime_fields_and_bad_copy() -> None:
    with pytest.raises(ValidationError, match="duplicate"):
        RunnerMetadata(
            schema_version="1",
            runner_id="runner.mock",
            runner_version="1",
            display_name="Mock runner",
            capabilities=("exploration", "exploration"),
        )
    with pytest.raises(ValidationError):
        RunnerMetadata(
            schema_version="1",
            runner_id="runner.mock",
            runner_version="1",
            display_name="Mock runner",
            capabilities=(),
            command="runtime-secret-marker",
        )
    with pytest.raises(ValidationError):
        RunnerMetadata(
            schema_version="1",
            runner_id="runner.mock",
            runner_version="1",
            display_name="Mock runner",
            capabilities=(),
        ).model_copy(update={"runner_id": "Runner Secret Marker"})


def test_valid_runner_request_composes_canonical_contracts() -> None:
    request = _runner_request()
    wire = json.loads(json.dumps(request.to_dict()))

    assert request.invocation.status is RunnerInvocationStatus.PENDING
    assert RunnerRequest.from_dict(wire) == request
    assert request.timeout_ms == 30_000


@pytest.mark.parametrize(
    "field,replacement",
    (
        ("request_id", "request.other"),
        ("session_id", "session.other"),
        ("workflow_id", "workflow.other"),
        ("workflow_version", "2.0.0"),
        ("runner_id", "runner.other"),
        ("references", ()),
    ),
)
def test_runner_request_rejects_run_context_mismatch(
    field: str,
    replacement,
) -> None:
    with pytest.raises(ValidationError, match="correlation"):
        _runner_request(context=_context(**{field: replacement}))


@pytest.mark.parametrize(
    "field,replacement",
    (
        ("run_id", "run.other"),
        ("runner_id", "runner.other"),
        ("started_at", _time(1)),
    ),
)
def test_runner_request_rejects_invocation_context_mismatch(
    field: str,
    replacement,
) -> None:
    with pytest.raises(ValidationError, match="correlation"):
        _runner_request(invocation=_pending_invocation(**{field: replacement}))


def test_runner_request_rejects_bad_timestamp_status_timeout_and_copy() -> None:
    with pytest.raises(ValidationError, match="timestamp"):
        _runner_request(
            run_request=_run_request(requested_at=_time(1)),
        )
    with pytest.raises(ValidationError, match="pending"):
        _runner_request(
            invocation=_terminal_invocation(
                RunnerInvocationStatus.SUCCEEDED
            )
        )
    with pytest.raises(ValidationError, match="pending"):
        _runner_request(
            invocation=_pending_invocation(errors=(_error(),))
        )
    for timeout in (0, MAX_RUNNER_TIMEOUT_MS + 1):
        with pytest.raises(ValidationError):
            _runner_request(timeout_ms=timeout)
    with pytest.raises(ValidationError):
        _runner_request().model_copy(update={"timeout_ms": 0})


@pytest.mark.parametrize(
    "status",
    (
        RunnerInvocationStatus.SUCCEEDED,
        RunnerInvocationStatus.PARTIALLY_SUCCEEDED,
        RunnerInvocationStatus.FAILED,
        RunnerInvocationStatus.CANCELLED,
    ),
)
def test_valid_terminal_responses_round_trip(
    status: RunnerInvocationStatus,
) -> None:
    response = _response(status)

    assert RunnerResponse.from_dict(response.to_dict()) == response
    assert validate_runner_response(_runner_request(), response) == response


@pytest.mark.parametrize(
    "status,result,errors",
    (
        (RunnerInvocationStatus.SUCCEEDED, None, ()),
        (
            RunnerInvocationStatus.SUCCEEDED,
            _result(),
            (_error(),),
        ),
        (
            RunnerInvocationStatus.PARTIALLY_SUCCEEDED,
            _result(),
            (),
        ),
        (
            RunnerInvocationStatus.FAILED,
            _result(),
            (_error(),),
        ),
        (
            RunnerInvocationStatus.FAILED,
            None,
            (),
        ),
        (
            RunnerInvocationStatus.CANCELLED,
            None,
            (_error(),),
        ),
    ),
)
def test_runner_response_rejects_invalid_result_error_combinations(
    status: RunnerInvocationStatus,
    result,
    errors,
) -> None:
    invocation = _terminal_invocation(status, errors=errors)
    with pytest.raises(ValidationError):
        RunnerResponse(
            schema_version="1",
            invocation=invocation,
            result=result,
            artifacts=(),
        )


@pytest.mark.parametrize(
    "status",
    (RunnerInvocationStatus.PENDING, RunnerInvocationStatus.RUNNING),
)
def test_runner_response_rejects_nonterminal_invocations(
    status: RunnerInvocationStatus,
) -> None:
    invocation = _pending_invocation(status=status)
    with pytest.raises(ValidationError, match="terminal"):
        RunnerResponse(
            schema_version="1",
            invocation=invocation,
            result=None,
            artifacts=(),
        )


def test_runner_response_rejects_duplicate_artifact_ids() -> None:
    with pytest.raises(ValidationError, match="unique"):
        _response(artifacts=(_artifact(), _artifact()))


def test_authoritative_validation_rejects_result_schema_mismatch_safely() -> None:
    marker = "runtime-secret-marker"
    response = _response(
        result=_result(
            schema_id="schema.runtime-secret-marker",
            result_schema_version="2",
        )
    )

    with pytest.raises(RunnerBoundaryValidationError) as captured:
        validate_runner_response(_runner_request(), response)

    assert marker not in str(captured.value)


@pytest.mark.parametrize(
    "field,replacement",
    (
        ("invocation_id", "invocation.other"),
        ("run_id", "run.other"),
        ("runner_id", "runner.other"),
        ("operation", "workflow.other"),
        ("step_id", "other"),
        ("attempt_number", 2),
        ("started_at", _time(1)),
    ),
)
def test_authoritative_validation_rejects_unrelated_invocation(
    field: str,
    replacement,
) -> None:
    values = _terminal_invocation(
        RunnerInvocationStatus.SUCCEEDED
    ).model_dump(mode="python")
    values[field] = replacement
    if field == "attempt_number":
        values["retry_of_invocation_id"] = "invocation.0"
    response = _response(invocation=RunnerInvocationRecord(**values))

    with pytest.raises(RunnerBoundaryValidationError):
        validate_runner_response(_runner_request(), response)


def test_authoritative_validation_preserves_attempt_predecessor_correlation() -> None:
    request = _runner_request(
        invocation=_pending_invocation(
            invocation_id="invocation.2",
            attempt_number=2,
            retry_of_invocation_id="invocation.1",
        )
    )
    unrelated = _terminal_invocation(
        RunnerInvocationStatus.SUCCEEDED,
        invocation_id="invocation.2",
        attempt_number=2,
        fallback_from_invocation_id="invocation.1",
    )

    with pytest.raises(RunnerBoundaryValidationError):
        validate_runner_response(request, _response(invocation=unrelated))


def test_runner_response_preserves_zero_duration_and_missing_result() -> None:
    response = _response(
        RunnerInvocationStatus.FAILED,
        invocation=_terminal_invocation(
            RunnerInvocationStatus.FAILED,
            duration_ms=0,
        ),
    )

    assert response.invocation.duration_ms == 0
    assert response.result is None


def test_runner_contract_complete_tree_bound_and_copy_revalidation() -> None:
    artifacts = tuple(_artifact(index) for index in range(600))
    with pytest.raises(ValidationError, match="persistence boundary"):
        _response(artifacts=artifacts)
    with pytest.raises(ValidationError, match="persistence boundary"):
        _response().model_copy(update={"artifacts": artifacts})


def test_runner_contract_rejects_secret_runtime_objects_without_echo() -> None:
    marker = "runtime-secret-marker"
    with pytest.raises(ValidationError) as captured:
        _runner_request(
            run_request=_run_request(
                inputs={"provider_client": object(), "safe": marker}
            )
        )
    assert marker not in str(captured.value)


def test_runner_contract_from_dict_rejects_noncanonical_tree() -> None:
    wire = deepcopy(_runner_request().to_dict())
    wire["timeout_ms"] = 30_000.0

    with pytest.raises(ValueError):
        RunnerRequest.from_dict(wire)
