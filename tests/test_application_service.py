"""Tests for the synchronous single-attempt PMQA Application Service."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from pmqa.application import (
    APPLICATION_RUN_OPERATION,
    ApplicationFailureCode,
    PMQAApplicationError,
    PMQAApplicationService,
    RunnerRegistry,
    WorkflowAdapterValidationError,
    WorkflowRegistry,
)
from pmqa.run import (
    ApprovalMode,
    RunArtifact,
    RunRequest,
    RunnerInvocationStatus,
    StructuredResult,
    WorkflowDefinition,
)
from pmqa.runners import (
    CancellationToken,
    MockRunner,
    RunnerBoundaryValidationError,
    RunnerControl,
    RunnerMetadata,
)


REQUESTED_AT = datetime(2026, 7, 24, 11, 59, tzinfo=timezone.utc)
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


class TestWorkflowAdapter:
    __test__ = False

    def __init__(
        self,
        definition: WorkflowDefinition,
        *,
        request_failure: BaseException = None,
        result_failure: BaseException = None,
    ) -> None:
        self.current_definition = definition
        self.request_failure = request_failure
        self.result_failure = result_failure
        self.request_calls = 0
        self.result_calls = 0

    @property
    def definition(self) -> WorkflowDefinition:
        return self.current_definition

    def validate_request(self, request: RunRequest) -> None:
        self.request_calls += 1
        if self.request_failure is not None:
            raise self.request_failure

    def validate_result(self, result: StructuredResult) -> None:
        self.result_calls += 1
        if self.result_failure is not None:
            raise self.result_failure


class CountingRunner:
    def __init__(self, delegate: MockRunner) -> None:
        self.delegate = delegate
        self.current_metadata = delegate.metadata
        self.calls = 0
        self.last_request = None
        self.last_control = None
        self.failure = None
        self.mutate_response = None

    @property
    def metadata(self) -> RunnerMetadata:
        return self.current_metadata

    def execute(self, request, control):
        self.calls += 1
        self.last_request = request
        self.last_control = control
        if self.failure is not None:
            raise self.failure
        response = self.delegate.execute(request, control)
        if self.mutate_response is not None:
            self.mutate_response(response)
        return response


def _definition(**updates) -> WorkflowDefinition:
    values = {
        "schema_version": "1",
        "workflow_id": "workflow.test",
        "workflow_version": "1",
        "display_name": "Test workflow",
        "description": "Deterministic application service test workflow.",
        "input_schema_id": "schema.input",
        "input_schema_version": "1",
        "result_schema_id": "schema.result",
        "result_schema_version": "1",
        "preview_steps": (),
        "required_runner_capabilities": ("deterministic-execution",),
        "approval_mode": ApprovalMode.NONE,
    }
    values.update(updates)
    return WorkflowDefinition(**values)


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
        "inputs": {"story_ids": ["12345"]},
        "references": (),
        "requested_at": REQUESTED_AT,
    }
    values.update(updates)
    return RunRequest(**values)


def _artifact() -> RunArtifact:
    return RunArtifact(
        artifact_id="artifact.output",
        artifact_type="test-output",
        artifact_schema_version="1",
        storage_key="runs/run.1/artifacts/output",
        content_digest="a" * 64,
        created_at=COMPLETED_AT,
    )


def _composition(
    *,
    outcome: RunnerInvocationStatus = RunnerInvocationStatus.SUCCEEDED,
    definition: WorkflowDefinition = None,
    adapter: TestWorkflowAdapter = None,
    output_artifacts=(),
    application_clock: SequenceClock = None,
):
    workflow_adapter = adapter or TestWorkflowAdapter(
        definition or _definition()
    )
    mock = MockRunner(
        outcome=(
            RunnerInvocationStatus.SUCCEEDED
            if outcome is RunnerInvocationStatus.CANCELLED
            else outcome
        ),
        output_artifacts=output_artifacts,
        wall_clock=SequenceClock(COMPLETED_AT),
        monotonic_clock=SequenceClock(10.0, 10.25),
    )
    runner = CountingRunner(mock)
    clock = application_clock or SequenceClock(STARTED_AT)
    service = PMQAApplicationService(
        workflow_registry=WorkflowRegistry((workflow_adapter,)),
        runner_registry=RunnerRegistry((runner,)),
        clock=clock,
    )
    return service, workflow_adapter, runner, clock


@pytest.mark.parametrize(
    "outcome",
    (
        RunnerInvocationStatus.SUCCEEDED,
        RunnerInvocationStatus.PARTIALLY_SUCCEEDED,
        RunnerInvocationStatus.FAILED,
        RunnerInvocationStatus.CANCELLED,
    ),
)
def test_application_service_executes_one_attempt_and_maps_terminal_outcome(
    outcome: RunnerInvocationStatus,
) -> None:
    service, adapter, runner, clock = _composition(
        outcome=outcome,
        output_artifacts=() if outcome is RunnerInvocationStatus.CANCELLED
        else (_artifact(),),
    )
    control = RunnerControl()
    if outcome is RunnerInvocationStatus.CANCELLED:
        control.cancellation_token.cancel()

    result = service.execute(
        _request(),
        run_id="run.1",
        invocation_id="invocation.1",
        control=control,
    )

    invocation = result.runner_invocation
    record = result.run_record
    assert runner.calls == 1
    assert adapter.request_calls == 1
    assert adapter.result_calls == (
        1 if outcome in {
            RunnerInvocationStatus.SUCCEEDED,
            RunnerInvocationStatus.PARTIALLY_SUCCEEDED,
        } else 0
    )
    assert clock.calls == 1
    assert runner.last_control is control
    assert invocation.status.value == outcome.value
    assert invocation.attempt_number == 1
    assert invocation.retry_of_invocation_id is None
    assert invocation.fallback_from_invocation_id is None
    assert invocation.operation == APPLICATION_RUN_OPERATION
    assert record.status.value == outcome.value
    assert record.result == result.runner_response.result
    assert record.artifacts == (
        () if outcome is RunnerInvocationStatus.CANCELLED else (_artifact(),)
    )
    assert record.artifacts == result.runner_response.artifacts
    assert record.errors == invocation.errors
    assert record.runner_invocation_ids == ("invocation.1",)
    assert record.started_at == invocation.started_at == STARTED_AT
    assert record.completed_at == invocation.completed_at == COMPLETED_AT
    assert record.duration_ms == invocation.duration_ms == 250
    assert record.created_at == REQUESTED_AT
    assert record.updated_at == COMPLETED_AT
    assert record.current_step_id is None
    assert record.outcome_metrics is None


def _assert_pre_execution_failure(
    expected_code: ApplicationFailureCode,
    *,
    service: PMQAApplicationService,
    runner: CountingRunner,
    request: RunRequest = None,
    run_id: str = "run.1",
    invocation_id: str = "invocation.1",
    control=None,
) -> None:
    marker = "runtime-secret-marker"
    kwargs = {}
    if control is not None:
        kwargs["control"] = control
    with pytest.raises(PMQAApplicationError) as captured:
        service.execute(
            request or _request(),
            run_id=run_id,
            invocation_id=invocation_id,
            **kwargs,
        )

    assert captured.value.code is expected_code
    assert marker not in str(captured.value)
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
    assert runner.calls == 0


def test_missing_workflow_and_version_fail_before_runner() -> None:
    adapter = TestWorkflowAdapter(
        _definition(workflow_id="workflow.other")
    )
    service, _, runner, _ = _composition(adapter=adapter)
    _assert_pre_execution_failure(
        ApplicationFailureCode.WORKFLOW_NOT_FOUND,
        service=service,
        runner=runner,
    )

    service, _, runner, _ = _composition()
    _assert_pre_execution_failure(
        ApplicationFailureCode.WORKFLOW_NOT_FOUND,
        service=service,
        runner=runner,
        request=_request(workflow_version="2"),
    )


def test_input_schema_and_workflow_validation_fail_before_runner() -> None:
    service, _, runner, _ = _composition()
    _assert_pre_execution_failure(
        ApplicationFailureCode.WORKFLOW_INPUT_SCHEMA_MISMATCH,
        service=service,
        runner=runner,
        request=_request(input_schema_version="2"),
    )

    adapter = TestWorkflowAdapter(
        _definition(),
        request_failure=WorkflowAdapterValidationError(),
    )
    service, _, runner, _ = _composition(adapter=adapter)
    _assert_pre_execution_failure(
        ApplicationFailureCode.WORKFLOW_INPUT_INVALID,
        service=service,
        runner=runner,
    )


def test_approval_runner_and_capability_failures_do_not_execute() -> None:
    service, _, runner, _ = _composition(
        definition=_definition(approval_mode=ApprovalMode.PRE_RUN)
    )
    _assert_pre_execution_failure(
        ApplicationFailureCode.APPROVAL_REQUIRED,
        service=service,
        runner=runner,
    )

    adapter = TestWorkflowAdapter(_definition())
    mock = CountingRunner(
        MockRunner(
            wall_clock=SequenceClock(COMPLETED_AT),
            monotonic_clock=SequenceClock(1.0, 2.0),
        )
    )
    service = PMQAApplicationService(
        workflow_registry=WorkflowRegistry((adapter,)),
        runner_registry=RunnerRegistry(()),
        clock=SequenceClock(STARTED_AT),
    )
    _assert_pre_execution_failure(
        ApplicationFailureCode.RUNNER_NOT_FOUND,
        service=service,
        runner=mock,
    )

    service, _, runner, _ = _composition(
        definition=_definition(
            required_runner_capabilities=("unavailable-capability",)
        )
    )
    _assert_pre_execution_failure(
        ApplicationFailureCode.RUNNER_CAPABILITY_MISMATCH,
        service=service,
        runner=runner,
    )


def test_definition_and_metadata_drift_fail_before_validation_or_runner() -> None:
    service, adapter, runner, _ = _composition()
    adapter.current_definition = adapter.definition.model_copy(
        update={"display_name": "Changed workflow"}
    )
    _assert_pre_execution_failure(
        ApplicationFailureCode.WORKFLOW_DEFINITION_CHANGED,
        service=service,
        runner=runner,
    )
    assert adapter.request_calls == 0

    service, adapter, runner, _ = _composition()
    runner.current_metadata = runner.metadata.model_copy(
        update={"display_name": "Changed runner"}
    )
    _assert_pre_execution_failure(
        ApplicationFailureCode.RUNNER_METADATA_CHANGED,
        service=service,
        runner=runner,
    )
    assert adapter.request_calls == 1


@pytest.mark.parametrize(
    "run_id,invocation_id",
    (
        ("runtime-secret-marker/path", "invocation.1"),
        ("run.1", "runtime-secret-marker/path"),
    ),
)
def test_invalid_identifiers_fail_safely_before_runner(
    run_id: str,
    invocation_id: str,
) -> None:
    service, _, runner, _ = _composition()
    _assert_pre_execution_failure(
        ApplicationFailureCode.INVALID_RUN_IDENTIFIER,
        service=service,
        runner=runner,
        run_id=run_id,
        invocation_id=invocation_id,
    )


@pytest.mark.parametrize(
    "clock_value",
    (
        datetime(2026, 7, 24, 12),
        datetime(2026, 7, 24, 11, 58, tzinfo=timezone.utc),
        "runtime-secret-marker",
        ValueError("runtime-secret-marker"),
    ),
)
def test_invalid_application_clock_fails_safely_before_runner(
    clock_value,
) -> None:
    service, _, runner, _ = _composition(
        application_clock=SequenceClock(clock_value)
    )
    _assert_pre_execution_failure(
        ApplicationFailureCode.INVALID_APPLICATION_CLOCK,
        service=service,
        runner=runner,
    )


def test_invalid_request_and_control_fail_before_runner() -> None:
    service, _, runner, _ = _composition()
    _assert_pre_execution_failure(
        ApplicationFailureCode.INVALID_APPLICATION_REQUEST,
        service=service,
        runner=runner,
        request=object(),
    )
    _assert_pre_execution_failure(
        ApplicationFailureCode.INVALID_APPLICATION_REQUEST,
        service=service,
        runner=runner,
        control=object(),
    )


def test_service_rejects_non_callable_clock_at_composition() -> None:
    adapter = TestWorkflowAdapter(_definition())
    runner = CountingRunner(MockRunner())

    with pytest.raises(PMQAApplicationError) as captured:
        PMQAApplicationService(
            workflow_registry=WorkflowRegistry((adapter,)),
            runner_registry=RunnerRegistry((runner,)),
            clock="runtime-secret-marker",
        )

    assert (
        captured.value.code
        is ApplicationFailureCode.INVALID_APPLICATION_CLOCK
    )
    assert "runtime-secret-marker" not in str(captured.value)
    assert runner.calls == 0


def test_omitted_control_creates_one_local_runtime_control() -> None:
    service, _, runner, _ = _composition()

    service.execute(
        _request(),
        run_id="run.1",
        invocation_id="invocation.1",
    )

    assert type(runner.last_control) is RunnerControl
    assert runner.last_control.is_cancellation_requested is False


def test_runner_boundary_failure_is_safely_classified() -> None:
    service, _, runner, _ = _composition()
    runner.failure = RunnerBoundaryValidationError()

    with pytest.raises(PMQAApplicationError) as captured:
        service.execute(
            _request(),
            run_id="run.1",
            invocation_id="invocation.1",
        )

    assert (
        captured.value.code
        is ApplicationFailureCode.RUNNER_BOUNDARY_FAILED
    )
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
    assert runner.calls == 1


def test_canonical_runner_response_is_revalidated() -> None:
    service, _, runner, _ = _composition()

    def corrupt_invocation(response) -> None:
        response.invocation.__dict__["run_id"] = "run.other"

    runner.mutate_response = corrupt_invocation
    with pytest.raises(PMQAApplicationError) as captured:
        service.execute(
            _request(),
            run_id="run.1",
            invocation_id="invocation.1",
        )

    assert (
        captured.value.code
        is ApplicationFailureCode.RUNNER_BOUNDARY_FAILED
    )
    assert runner.calls == 1


def test_result_schema_mismatch_is_rejected_before_workflow_validator() -> None:
    service, adapter, runner, _ = _composition()

    def corrupt_result(response) -> None:
        response.result.__dict__["schema_id"] = "schema.other"

    runner.mutate_response = corrupt_result
    with pytest.raises(PMQAApplicationError) as captured:
        service.execute(
            _request(),
            run_id="run.1",
            invocation_id="invocation.1",
        )

    assert (
        captured.value.code
        is ApplicationFailureCode.RUNNER_BOUNDARY_FAILED
    )
    assert adapter.result_calls == 0


def test_expected_workflow_result_failure_is_safely_classified() -> None:
    adapter = TestWorkflowAdapter(
        _definition(),
        result_failure=WorkflowAdapterValidationError(),
    )
    service, _, runner, _ = _composition(adapter=adapter)

    with pytest.raises(PMQAApplicationError) as captured:
        service.execute(
            _request(),
            run_id="run.1",
            invocation_id="invocation.1",
        )

    assert (
        captured.value.code
        is ApplicationFailureCode.WORKFLOW_RESULT_INVALID
    )
    assert runner.calls == 1
    assert adapter.result_calls == 1


@pytest.mark.parametrize(
    "failure",
    (
        RuntimeError("programming-error"),
        MemoryError("resource-error"),
        KeyboardInterrupt(),
        SystemExit(),
        GeneratorExit(),
    ),
)
def test_unexpected_and_resource_runner_failures_propagate(failure) -> None:
    service, _, runner, _ = _composition()
    runner.failure = failure

    with pytest.raises(type(failure)) as captured:
        service.execute(
            _request(),
            run_id="run.1",
            invocation_id="invocation.1",
        )

    assert captured.value is failure


def test_unexpected_workflow_validator_failure_propagates() -> None:
    expected = RuntimeError("programming-error")
    adapter = TestWorkflowAdapter(
        _definition(),
        request_failure=expected,
    )
    service, _, runner, _ = _composition(adapter=adapter)

    with pytest.raises(RuntimeError) as captured:
        service.execute(
            _request(),
            run_id="run.1",
            invocation_id="invocation.1",
        )

    assert captured.value is expected
    assert runner.calls == 0


def test_unexpected_workflow_result_failure_propagates() -> None:
    expected = RuntimeError("programming-error")
    adapter = TestWorkflowAdapter(
        _definition(),
        result_failure=expected,
    )
    service, _, runner, _ = _composition(adapter=adapter)

    with pytest.raises(RuntimeError) as captured:
        service.execute(
            _request(),
            run_id="run.1",
            invocation_id="invocation.1",
        )

    assert captured.value is expected
    assert runner.calls == 1


@pytest.mark.parametrize(
    "validation_stage",
    ("request", "result"),
)
@pytest.mark.parametrize(
    "failure",
    (MemoryError(), KeyboardInterrupt(), SystemExit(), GeneratorExit()),
)
def test_resource_and_control_flow_workflow_failures_propagate(
    validation_stage: str,
    failure: BaseException,
) -> None:
    adapter = TestWorkflowAdapter(
        _definition(),
        request_failure=failure if validation_stage == "request" else None,
        result_failure=failure if validation_stage == "result" else None,
    )
    service, _, runner, _ = _composition(adapter=adapter)

    with pytest.raises(type(failure)) as captured:
        service.execute(
            _request(),
            run_id="run.1",
            invocation_id="invocation.1",
        )

    assert captured.value is failure
    assert runner.calls == (0 if validation_stage == "request" else 1)


@pytest.mark.parametrize(
    "failure",
    (MemoryError(), KeyboardInterrupt(), SystemExit(), GeneratorExit()),
)
def test_resource_and_control_flow_clock_failures_propagate(failure) -> None:
    service, _, runner, _ = _composition(
        application_clock=SequenceClock(failure)
    )

    with pytest.raises(type(failure)) as captured:
        service.execute(
            _request(),
            run_id="run.1",
            invocation_id="invocation.1",
        )

    assert captured.value is failure
    assert runner.calls == 0


def test_caller_owned_request_and_control_are_not_mutated() -> None:
    request = _request()
    control = RunnerControl()
    request_wire = deepcopy(request.to_dict())
    service, _, _, _ = _composition()

    service.execute(
        request,
        run_id="run.1",
        invocation_id="invocation.1",
        control=control,
    )

    assert request.to_dict() == request_wire
    assert control.is_cancellation_requested is False
