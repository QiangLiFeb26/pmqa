"""Tests for the deterministic in-process MockRunner."""

from copy import deepcopy
from datetime import datetime, timezone
from threading import Thread

import pytest
from pydantic import ValidationError

from pmqa.run import (
    PMQARunContext,
    RunReference,
    RunRequest,
    RunnerInvocationRecord,
    RunnerInvocationStatus,
)
from pmqa.runners import (
    CancellationToken,
    MockRunner,
    PMQARunner,
    RunnerBoundaryValidationError,
    RunnerControl,
    RunnerRequest,
    validate_runner_response,
)


STARTED_AT = datetime(2026, 7, 24, 12, tzinfo=timezone.utc)
COMPLETED_AT = datetime(2026, 7, 24, 12, 1, tzinfo=timezone.utc)


class SequenceClock:
    def __init__(self, *values) -> None:
        self.values = list(values)
        self.calls = 0

    def __call__(self):
        value = self.values[self.calls]
        self.calls += 1
        if isinstance(value, BaseException):
            raise value
        return value


def _request(
    invocation: RunnerInvocationRecord = None,
) -> RunnerRequest:
    reference = RunReference(reference_type="story", reference_id="12345")
    run_request = RunRequest(
        schema_version="1",
        request_id="request.1",
        session_id="session.1",
        workflow_id="workflow.generate-tests",
        workflow_version="1.0.0",
        runner_id="runner.mock",
        input_schema_id="schema.workflow-input",
        input_schema_version="1",
        inputs={"story_ids": ["12345"]},
        references=(reference,),
        requested_at=STARTED_AT,
    )
    context = PMQARunContext(
        schema_version="1",
        run_id="run.1",
        request_id="request.1",
        session_id="session.1",
        workflow_id="workflow.generate-tests",
        workflow_version="1.0.0",
        runner_id="runner.mock",
        references=(reference,),
        started_at=STARTED_AT,
    )
    pending = invocation or RunnerInvocationRecord(
        schema_version="1",
        invocation_id="invocation.1",
        run_id="run.1",
        runner_id="runner.mock",
        operation="workflow.execute",
        step_id="generate",
        status=RunnerInvocationStatus.PENDING,
        started_at=STARTED_AT,
        completed_at=None,
        duration_ms=None,
        attempt_number=1,
        retry_of_invocation_id=None,
        fallback_from_invocation_id=None,
        errors=(),
    )
    return RunnerRequest(
        schema_version="1",
        run_request=run_request,
        context=context,
        invocation=pending,
        expected_result_schema_id="schema.workflow-result",
        expected_result_schema_version="1",
        timeout_ms=30_000,
    )


def _runner(
    outcome: RunnerInvocationStatus = RunnerInvocationStatus.SUCCEEDED,
):
    wall = SequenceClock(COMPLETED_AT)
    monotonic = SequenceClock(100.0, 100.25)
    runner = MockRunner(
        outcome=outcome,
        wall_clock=wall,
        monotonic_clock=monotonic,
    )
    return runner, wall, monotonic


def test_mock_runner_satisfies_provider_neutral_protocol_shape() -> None:
    runner, _, _ = _runner()

    typed: PMQARunner = runner
    assert typed.metadata.runner_id == "runner.mock"


@pytest.mark.parametrize(
    "outcome,has_result,error_count",
    (
        (RunnerInvocationStatus.SUCCEEDED, True, 0),
        (RunnerInvocationStatus.PARTIALLY_SUCCEEDED, True, 1),
        (RunnerInvocationStatus.FAILED, False, 1),
    ),
)
def test_mock_runner_produces_configured_deterministic_outcomes(
    outcome: RunnerInvocationStatus,
    has_result: bool,
    error_count: int,
) -> None:
    runner, wall, monotonic = _runner(outcome)
    request = _request()

    response = runner.execute(request, RunnerControl())

    assert response.invocation.status is outcome
    assert (response.result is not None) is has_result
    assert len(response.invocation.errors) == error_count
    assert response.invocation.invocation_id == request.invocation.invocation_id
    assert response.invocation.completed_at == COMPLETED_AT
    assert response.invocation.duration_ms == 250
    assert wall.calls == 1
    assert monotonic.calls == 2
    assert validate_runner_response(request, response) == response


def test_pre_execution_cancellation_is_idempotent_and_structured() -> None:
    token = CancellationToken()
    threads = [Thread(target=token.cancel) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    runner, _, _ = _runner()

    response = runner.execute(
        _request(),
        RunnerControl(token),
    )

    assert token.is_cancellation_requested is True
    assert response.invocation.status is RunnerInvocationStatus.CANCELLED
    assert response.result is None
    assert len(response.invocation.errors) == 1
    assert response.invocation.errors[0].category.value == "cancelled"


def test_cancellation_control_is_runtime_only_and_cannot_enter_run_json() -> None:
    control = RunnerControl()

    assert not hasattr(control, "to_dict")
    assert not hasattr(control.cancellation_token, "to_dict")
    with pytest.raises(ValidationError):
        _request().run_request.model_copy(
            update={"inputs": {"control": control}}
        )


@pytest.mark.parametrize(
    "predecessor_field",
    ("retry_of_invocation_id", "fallback_from_invocation_id"),
)
def test_mock_runner_preserves_attempt_without_orchestration(
    predecessor_field: str,
) -> None:
    invocation = _request().invocation.model_copy(
        update={
            "invocation_id": "invocation.2",
            "attempt_number": 2,
            predecessor_field: "invocation.1",
        }
    )
    request = _request(invocation)
    runner, _, _ = _runner()

    response = runner.execute(request, RunnerControl())

    assert response.invocation.attempt_number == 2
    assert getattr(response.invocation, predecessor_field) == "invocation.1"
    other = (
        "fallback_from_invocation_id"
        if predecessor_field == "retry_of_invocation_id"
        else "retry_of_invocation_id"
    )
    assert getattr(response.invocation, other) is None


def test_mock_runner_does_not_mutate_caller_owned_input() -> None:
    inputs = {"story_ids": ["12345"]}
    request = _request().model_copy(
        update={
            "run_request": _request().run_request.model_copy(
                update={"inputs": inputs}
            )
        }
    )
    before = deepcopy(inputs)
    runner, _, _ = _runner()

    runner.execute(request, RunnerControl())

    assert inputs == before


def test_mock_runner_invents_no_usage_cost_or_provider_fields() -> None:
    runner, _, _ = _runner()
    wire = runner.execute(_request(), RunnerControl()).to_dict()
    serialized = str(wire)

    for excluded in (
        "usage",
        "cost",
        "price",
        "provider",
        "prompt",
        "response",
        "stdout",
        "stderr",
    ):
        assert excluded not in serialized


def test_repeated_equivalent_execution_has_equivalent_domain_output() -> None:
    first, _, _ = _runner()
    second, _, _ = _runner()

    assert first.execute(_request(), RunnerControl()) == second.execute(
        _request(), RunnerControl()
    )


@pytest.mark.parametrize(
    "wall_value",
    (
        datetime(2026, 7, 24, 12),
        "2026-07-24T12:00:00Z",
        object(),
        ValueError("runtime-secret-marker"),
    ),
)
def test_invalid_wall_clock_fails_safely(wall_value) -> None:
    wall = SequenceClock(wall_value)
    runner = MockRunner(
        wall_clock=wall,
        monotonic_clock=SequenceClock(1.0, 2.0),
    )

    with pytest.raises(RunnerBoundaryValidationError) as captured:
        runner.execute(_request(), RunnerControl())

    assert "runtime-secret-marker" not in str(captured.value)


@pytest.mark.parametrize(
    "values",
    (
        ("not-a-clock", 2.0),
        (float("nan"), 2.0),
        (2.0, 1.0),
        (ValueError("runtime-secret-marker"), 2.0),
    ),
)
def test_invalid_monotonic_clock_fails_safely(values) -> None:
    runner = MockRunner(
        wall_clock=SequenceClock(COMPLETED_AT),
        monotonic_clock=SequenceClock(*values),
    )

    with pytest.raises(RunnerBoundaryValidationError) as captured:
        runner.execute(_request(), RunnerControl())

    assert "runtime-secret-marker" not in str(captured.value)


def test_noncallable_clocks_and_unsupported_outcome_fail_safely() -> None:
    for kwargs in (
        {"wall_clock": None},
        {"monotonic_clock": None},
        {"outcome": RunnerInvocationStatus.CANCELLED},
        {"outcome": "succeeded"},
        {"metadata": object()},
    ):
        with pytest.raises(RunnerBoundaryValidationError):
            MockRunner(**kwargs)


def test_mock_runner_rejects_identity_mismatch_and_bad_control() -> None:
    request = _request().model_copy(
        update={
            "context": _request().context.model_copy(
                update={"runner_id": "runner.other"}
            ),
            "run_request": _request().run_request.model_copy(
                update={"runner_id": "runner.other"}
            ),
            "invocation": _request().invocation.model_copy(
                update={"runner_id": "runner.other"}
            ),
        }
    )
    runner, _, _ = _runner()

    with pytest.raises(RunnerBoundaryValidationError):
        runner.execute(request, RunnerControl())
    with pytest.raises(RunnerBoundaryValidationError):
        runner.execute(_request(), object())


def test_wall_clock_must_not_precede_invocation_start() -> None:
    runner = MockRunner(
        wall_clock=SequenceClock(
            datetime(2026, 7, 24, 11, tzinfo=timezone.utc)
        ),
        monotonic_clock=SequenceClock(1.0, 2.0),
    )

    with pytest.raises(RunnerBoundaryValidationError):
        runner.execute(_request(), RunnerControl())
