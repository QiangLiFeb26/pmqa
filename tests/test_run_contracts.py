"""Tests for the canonical application-level PMQA Run Contract."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from enum import Enum
import json

import pytest
from pydantic import ValidationError

from pmqa.run import (
    ApprovalMode,
    MAX_RUN_PAYLOAD_DEPTH,
    MAX_RUN_PAYLOAD_ITEMS,
    OutcomeMetrics,
    PMQARunContext,
    RUN_CONTRACT_SCHEMA_VERSION,
    RunArtifact,
    RunContractValidationError,
    RunError,
    RunErrorCategory,
    RunRecord,
    RunReference,
    RunRequest,
    RunStatus,
    RunnerInvocationRecord,
    RunnerInvocationStatus,
    StructuredResult,
    WorkflowDefinition,
    WorkflowPreviewStep,
    validate_run_identifier,
)
from pmqa.security.boundary_policy import RUN_PAYLOAD_PROHIBITED_KEYS


class DictSubclass(dict):
    pass


class ListSubclass(list):
    pass


class RuntimeObject:
    def __repr__(self) -> str:
        return "RuntimeObject(runtime-secret-marker)"


class PayloadEnum(str, Enum):
    VALUE = "value"


def _time(minutes: int = 0) -> datetime:
    return datetime(2026, 7, 24, 12, tzinfo=timezone.utc) + timedelta(
        minutes=minutes
    )


def _reference(**updates) -> RunReference:
    values = {"reference_type": "story", "reference_id": "12345"}
    values.update(updates)
    return RunReference(**values)


def _request(**updates) -> RunRequest:
    values = {
        "schema_version": RUN_CONTRACT_SCHEMA_VERSION,
        "request_id": "request.550e8400-e29b-41d4-a716-446655440000",
        "session_id": "session.1",
        "workflow_id": "workflow.generate-tests",
        "workflow_version": "1.0.0",
        "runner_id": "runner.local",
        "input_schema_id": "schema.workflow-input",
        "input_schema_version": "1",
        "inputs": {"story_ids": ["12345"], "options": {"headless": True}},
        "references": (_reference(),),
        "requested_at": _time(),
    }
    values.update(updates)
    return RunRequest(**values)


def _step(**updates) -> WorkflowPreviewStep:
    values = {
        "step_id": "explore",
        "display_name": "Explore",
        "description": "Collect safe evidence.",
    }
    values.update(updates)
    return WorkflowPreviewStep(**values)


def _definition(**updates) -> WorkflowDefinition:
    values = {
        "schema_version": "1",
        "workflow_id": "workflow.generate-tests",
        "workflow_version": "1.0.0",
        "display_name": "Generate tests",
        "description": "Explore, validate, and generate tests.",
        "input_schema_id": "schema.workflow-input",
        "input_schema_version": "1",
        "result_schema_id": "schema.workflow-result",
        "result_schema_version": "1",
        "preview_steps": (_step(),),
        "required_runner_capabilities": ("test-generation", "exploration"),
        "approval_mode": ApprovalMode.PRE_RUN,
    }
    values.update(updates)
    return WorkflowDefinition(**values)


def _context(**updates) -> PMQARunContext:
    values = {
        "schema_version": "1",
        "run_id": "run.550e8400-e29b-41d4-a716-446655440000",
        "request_id": "request.550e8400-e29b-41d4-a716-446655440000",
        "session_id": "session.1",
        "workflow_id": "workflow.generate-tests",
        "workflow_version": "1.0.0",
        "runner_id": "runner.local",
        "references": (_reference(),),
        "started_at": _time(),
    }
    values.update(updates)
    return PMQARunContext(**values)


def _result(**updates) -> StructuredResult:
    values = {
        "schema_version": "1",
        "schema_id": "schema.workflow-result",
        "result_schema_version": "1",
        "data": {"generated": 2, "files": ["test-login.spec.ts"]},
    }
    values.update(updates)
    return StructuredResult(**values)


def _artifact(**updates) -> RunArtifact:
    values = {
        "artifact_id": "artifact.generated-tests",
        "artifact_type": "playwright-tests",
        "artifact_schema_version": "1",
        "storage_key": "runs/run.1/artifacts/generated-tests",
        "content_digest": "a" * 64,
        "created_at": _time(2),
    }
    values.update(updates)
    return RunArtifact(**values)


def _error(**updates) -> RunError:
    values = {
        "code": "generation.failed",
        "category": RunErrorCategory.EXECUTION,
        "safe_message": "Test generation failed.",
        "step_id": "generate",
        "retryable": True,
        "error_type": "generation-error",
    }
    values.update(updates)
    return RunError(**values)


def _invocation(**updates) -> RunnerInvocationRecord:
    values = {
        "schema_version": "1",
        "invocation_id": "invocation.1",
        "run_id": "run.1",
        "runner_id": "runner.local",
        "operation": "workflow.execute",
        "step_id": "explore",
        "status": RunnerInvocationStatus.SUCCEEDED,
        "started_at": _time(),
        "completed_at": _time(1),
        "duration_ms": 500,
        "attempt_number": 1,
        "retry_of_invocation_id": None,
        "fallback_from_invocation_id": None,
        "errors": (),
    }
    values.update(updates)
    return RunnerInvocationRecord(**values)


def _record(**updates) -> RunRecord:
    values = {
        "schema_version": "1",
        "run_id": "run.1",
        "request_id": "request.1",
        "session_id": "session.1",
        "workflow_id": "workflow.generate-tests",
        "workflow_version": "1.0.0",
        "runner_id": "runner.local",
        "status": RunStatus.SUCCEEDED,
        "references": (_reference(),),
        "started_at": _time(),
        "completed_at": _time(3),
        "duration_ms": 1200,
        "current_step_id": "generate",
        "result": _result(),
        "artifacts": (_artifact(),),
        "errors": (),
        "runner_invocation_ids": ("invocation.1",),
        "outcome_metrics": OutcomeMetrics(tests_generated=0),
        "created_at": _time(),
        "updated_at": _time(3),
    }
    values.update(updates)
    return RunRecord(**values)


def test_public_enums_have_the_required_stable_values() -> None:
    assert tuple(item.value for item in RunStatus) == (
        "pending",
        "running",
        "awaiting_approval",
        "succeeded",
        "partially_succeeded",
        "failed",
        "cancelled",
    )
    assert tuple(item.value for item in RunnerInvocationStatus) == (
        "pending",
        "running",
        "succeeded",
        "partially_succeeded",
        "failed",
        "cancelled",
    )
    assert tuple(item.value for item in ApprovalMode) == ("none", "pre_run")
    assert tuple(item.value for item in RunErrorCategory) == (
        "validation",
        "configuration",
        "execution",
        "timeout",
        "cancelled",
        "provider",
        "internal",
    )


def test_public_models_have_the_exact_required_fields() -> None:
    assert tuple(RunReference.model_fields) == ("reference_type", "reference_id")
    assert tuple(RunRequest.model_fields) == (
        "schema_version",
        "request_id",
        "session_id",
        "workflow_id",
        "workflow_version",
        "runner_id",
        "input_schema_id",
        "input_schema_version",
        "inputs",
        "references",
        "requested_at",
    )
    assert tuple(WorkflowPreviewStep.model_fields) == (
        "step_id",
        "display_name",
        "description",
    )
    assert tuple(StructuredResult.model_fields) == (
        "schema_version",
        "schema_id",
        "result_schema_version",
        "data",
    )
    assert tuple(RunArtifact.model_fields) == (
        "artifact_id",
        "artifact_type",
        "artifact_schema_version",
        "storage_key",
        "content_digest",
        "created_at",
    )


@pytest.mark.parametrize(
    "value",
    (
        "1",
        "story.12345",
        "run.550e8400-e29b-41d4-a716-446655440000",
        "workflow_generate-tests:v1",
    ),
)
def test_neutral_run_identifier_accepts_required_forms(value: str) -> None:
    assert validate_run_identifier(value) == value


@pytest.mark.parametrize(
    "value",
    (
        "",
        ".run",
        "run.",
        "run..one",
        "run one",
        "run/one",
        r"run\one",
        "https://example.invalid/run",
        "run:$HOME",
        "run;command",
        "run\none",
        "RÜN",
        "a" * 257,
    ),
)
def test_neutral_run_identifier_rejects_unsafe_forms_without_echo(
    value: str,
) -> None:
    with pytest.raises(ValueError) as captured:
        validate_run_identifier(value)
    if value:
        assert value not in str(captured.value)


def test_run_request_is_frozen_deeply_immutable_and_detached_from_callers() -> None:
    inputs = {"nested": {"ids": ["1", "2"]}}
    references = [_reference()]
    request = _request(inputs=inputs, references=references)
    inputs["nested"]["ids"].append("3")
    references.clear()

    assert request.inputs["nested"]["ids"] == ("1", "2")
    assert request.references == (_reference(),)
    with pytest.raises(TypeError, match="immutable"):
        request.inputs["changed"] = True
    with pytest.raises(TypeError, match="immutable"):
        request.inputs["nested"]["changed"] = True
    with pytest.raises(AttributeError):
        request.inputs["nested"]["ids"].append("3")
    with pytest.raises(ValidationError, match="frozen"):
        request.run_id = "run.2"


def test_typed_session_and_run_identifiers_are_not_recursively_prohibited() -> None:
    assert _request(session_id="session.42").session_id == "session.42"
    assert _context(run_id="run.42").run_id == "run.42"
    assert _record(session_id="session.42").session_id == "session.42"


@pytest.mark.parametrize("key", sorted(RUN_PAYLOAD_PROHIBITED_KEYS))
def test_dynamic_payloads_reject_every_shared_prohibited_key(key: str) -> None:
    with pytest.raises(ValidationError):
        _request(inputs={key: "runtime-secret-marker"})
    with pytest.raises(ValidationError):
        _result(data={key: "runtime-secret-marker"})


@pytest.mark.parametrize(
    "key",
    (
        "API-Key",
        "browser context",
        "Provider-Instance",
        "prompt",
        "response",
        "command",
        "Executable Path",
        "environment",
        "authentication",
        "Page",
        "process config",
        "provider-client",
        "terminal output",
        "stdout",
        "stderr",
        "traceback",
    ),
)
def test_dynamic_payloads_reject_normalized_sensitive_and_runtime_keys(
    key: str,
) -> None:
    marker = "runtime-secret-marker"
    with pytest.raises(ValidationError) as captured:
        _request(inputs={key: marker})
    assert marker not in str(captured.value)


def test_safe_payload_values_are_not_globally_scanned() -> None:
    request = _request(
        inputs={
            "field_type": "password",
            "note": "response text and browser words are ordinary values",
        }
    )
    assert request.inputs["field_type"] == "password"


@pytest.mark.parametrize(
    "value",
    (
        b"bytes",
        bytearray(b"bytes"),
        memoryview(b"bytes"),
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        PayloadEnum.VALUE,
        RuntimeObject(),
        lambda: None,
    ),
)
def test_dynamic_payloads_reject_non_json_runtime_values(value: object) -> None:
    with pytest.raises(ValidationError) as captured:
        _request(inputs={"safe": value})
    assert "runtime-secret-marker" not in str(captured.value)


@pytest.mark.parametrize("value", (float("nan"), float("inf"), float("-inf")))
def test_dynamic_payloads_reject_non_finite_numbers(value: float) -> None:
    with pytest.raises(ValidationError, match="non-finite"):
        _request(inputs={"score": value})


def test_dynamic_payloads_reject_non_string_keys_and_container_subclasses() -> None:
    with pytest.raises(ValidationError, match="non-string"):
        _request(inputs={1: "value"})
    with pytest.raises(ValidationError):
        _request(inputs=DictSubclass({"safe": "value"}))
    with pytest.raises(ValidationError):
        _request(inputs={"items": ListSubclass(["value"])})


def test_dynamic_payloads_reject_cycles_depth_and_item_overflow() -> None:
    cyclic = {}
    cyclic["safe"] = cyclic
    with pytest.raises(ValidationError, match="cyclic"):
        _request(inputs=cyclic)

    deep: object = "value"
    for _ in range(MAX_RUN_PAYLOAD_DEPTH + 1):
        deep = {"safe": deep}
    with pytest.raises(ValidationError, match="nesting"):
        _request(inputs=deep)

    oversized = {"values": list(range(MAX_RUN_PAYLOAD_ITEMS))}
    with pytest.raises(ValidationError, match="item count"):
        _request(inputs=oversized)


def test_references_are_immutable_and_duplicate_free() -> None:
    with pytest.raises(ValidationError, match="duplicate"):
        _request(references=(_reference(), _reference()))
    with pytest.raises(ValidationError, match="duplicate"):
        _context(references=(_reference(), _reference()))
    with pytest.raises(ValidationError, match="duplicate"):
        _record(references=(_reference(), _reference()))


def test_workflow_definition_is_static_canonical_metadata() -> None:
    definition = _definition(
        required_runner_capabilities=("test-generation", "exploration")
    )
    assert definition.required_runner_capabilities == (
        "exploration",
        "test-generation",
    )
    assert definition.approval_mode is ApprovalMode.PRE_RUN
    with pytest.raises(ValidationError, match="duplicate"):
        _definition(required_runner_capabilities=("exploration", "exploration"))
    with pytest.raises(ValidationError, match="unique"):
        _definition(preview_steps=(_step(), _step()))
    with pytest.raises(ValidationError):
        _definition(factory=lambda: None)
    with pytest.raises(ValidationError):
        _definition(import_path="products.demo.workflow")


@pytest.mark.parametrize(
    "storage_key",
    (
        "/absolute/path",
        "../artifact",
        "runs/../artifact",
        r"runs\artifact",
        "c:/absolute/path",
        "file:artifact",
        "https://example.invalid/artifact",
        "runs//artifact",
        "runs/artifact;command",
    ),
)
def test_artifact_rejects_paths_urls_traversal_and_shell_syntax(
    storage_key: str,
) -> None:
    with pytest.raises(ValidationError):
        _artifact(storage_key=storage_key)


@pytest.mark.parametrize(
    "digest",
    ("", "sha256:" + "a" * 64, "A" * 64, "a" * 63, "g" * 64),
)
def test_artifact_requires_exact_lowercase_sha256_hex(digest: str) -> None:
    with pytest.raises(ValidationError, match="SHA-256"):
        _artifact(content_digest=digest)


def test_run_error_is_bounded_frozen_and_contains_no_raw_failure_fields() -> None:
    error = _error()
    assert error.retryable is True
    with pytest.raises(ValidationError, match="frozen"):
        error.retryable = False
    with pytest.raises(ValidationError):
        _error(traceback="runtime-secret-marker")
    with pytest.raises(ValidationError):
        _error(stderr="runtime-secret-marker")
    with pytest.raises(ValidationError) as captured:
        _error(safe_message="runtime-secret-marker\ntraceback")
    assert "runtime-secret-marker" not in str(captured.value)


def test_outcome_metrics_distinguish_unknown_zero_and_false() -> None:
    unknown = OutcomeMetrics()
    known = OutcomeMetrics(
        tests_generated=0,
        human_review_required=False,
    )
    assert all(value is None for value in unknown.to_dict().values())
    assert known.tests_generated == 0
    assert known.human_review_required is False
    with pytest.raises(ValidationError):
        OutcomeMetrics(tests_failed=-1)


@pytest.mark.parametrize(
    "status",
    (
        RunnerInvocationStatus.SUCCEEDED,
        RunnerInvocationStatus.PARTIALLY_SUCCEEDED,
        RunnerInvocationStatus.FAILED,
        RunnerInvocationStatus.CANCELLED,
    ),
)
def test_terminal_runner_invocations_require_completion_metadata(
    status: RunnerInvocationStatus,
) -> None:
    assert _invocation(status=status).status is status
    with pytest.raises(ValidationError, match="completion metadata"):
        _invocation(status=status, completed_at=None, duration_ms=None)


@pytest.mark.parametrize(
    "status",
    (RunnerInvocationStatus.PENDING, RunnerInvocationStatus.RUNNING),
)
def test_nonterminal_runner_invocations_forbid_completion_metadata(
    status: RunnerInvocationStatus,
) -> None:
    assert _invocation(
        status=status, completed_at=None, duration_ms=None
    ).status is status
    with pytest.raises(ValidationError, match="completion metadata"):
        _invocation(status=status)


def test_runner_invocation_time_and_retry_fallback_correlation() -> None:
    with pytest.raises(ValidationError, match="precede"):
        _invocation(completed_at=_time(-1))
    with pytest.raises(ValidationError):
        _invocation(duration_ms=-1)
    with pytest.raises(ValidationError, match="greater than 1"):
        _invocation(retry_of_invocation_id="invocation.0")
    assert _invocation(
        invocation_id="invocation.2",
        attempt_number=2,
        retry_of_invocation_id="invocation.1",
    ).retry_of_invocation_id == "invocation.1"
    with pytest.raises(ValidationError, match="itself"):
        _invocation(retry_of_invocation_id="invocation.1", attempt_number=2)
    with pytest.raises(ValidationError, match="itself"):
        _invocation(fallback_from_invocation_id="invocation.1")


@pytest.mark.parametrize(
    "status",
    (
        RunStatus.SUCCEEDED,
        RunStatus.PARTIALLY_SUCCEEDED,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
    ),
)
def test_terminal_runs_require_completion_metadata(status: RunStatus) -> None:
    values = {}
    if status in {RunStatus.FAILED, RunStatus.CANCELLED}:
        values["result"] = None
    assert _record(status=status, **values).status is status
    with pytest.raises(ValidationError, match="completion metadata"):
        _record(
            status=status,
            result=values.get("result", _result()),
            completed_at=None,
            duration_ms=None,
        )


@pytest.mark.parametrize(
    "status",
    (RunStatus.PENDING, RunStatus.RUNNING, RunStatus.AWAITING_APPROVAL),
)
def test_nonterminal_runs_forbid_completion_and_results(status: RunStatus) -> None:
    record = _record(
        status=status,
        completed_at=None,
        duration_ms=None,
        result=None,
    )
    assert record.status is status
    with pytest.raises(ValidationError, match="completion metadata"):
        _record(status=status, result=None)
    with pytest.raises(ValidationError, match="structured result"):
        _record(
            status=status,
            completed_at=None,
            duration_ms=None,
            result=_result(),
        )


def test_partially_succeeded_run_represents_partial_result_and_errors() -> None:
    record = _record(
        status=RunStatus.PARTIALLY_SUCCEEDED,
        result=_result(data={"generated": 1, "skipped": 1}),
        errors=(_error(),),
        outcome_metrics=None,
    )
    assert record.result is not None
    assert record.errors == (_error(),)
    assert record.outcome_metrics is None


def test_run_record_rejects_invalid_time_and_duplicate_correlations() -> None:
    with pytest.raises(ValidationError, match="precede"):
        _record(completed_at=_time(-1))
    with pytest.raises(ValidationError, match="updated_at"):
        _record(updated_at=_time(-1))
    with pytest.raises(ValidationError, match="artifact"):
        _record(artifacts=(_artifact(), _artifact()))
    with pytest.raises(ValidationError, match="invocation"):
        _record(runner_invocation_ids=("invocation.1", "invocation.1"))
    with pytest.raises(ValidationError, match="structured result"):
        _record(status=RunStatus.FAILED, result=_result())


def test_model_copy_revalidates_and_refreezes_updates() -> None:
    copied = _request().model_copy(
        update={"inputs": {"nested": ["safe"]}}
    )
    assert copied.inputs["nested"] == ("safe",)
    with pytest.raises(ValidationError):
        _request().model_copy(
            update={"inputs": {"password": "runtime-secret-marker"}}
        )
    with pytest.raises(ValidationError, match="present together"):
        _record().model_copy(
            update={
                "status": RunStatus.RUNNING,
                "completed_at": None,
                "duration_ms": 1,
                "result": None,
            }
        )


@pytest.mark.parametrize(
    "factory",
    (
        _reference,
        _request,
        _step,
        _definition,
        _context,
        _result,
        _artifact,
        _error,
        OutcomeMetrics,
        _invocation,
        _record,
    ),
)
def test_every_contract_has_a_canonical_plain_json_round_trip(factory) -> None:
    contract = factory()
    wire = json.loads(json.dumps(contract.to_dict()))
    restored = type(contract).from_dict(deepcopy(wire))
    assert restored == contract
    assert restored.to_dict() == wire


def test_from_dict_rejects_unknown_missing_and_noncanonical_wire_values() -> None:
    wire = _request().to_dict()
    unknown = deepcopy(wire)
    unknown["unexpected"] = True
    missing = deepcopy(wire)
    missing.pop("workflow_id")
    tuple_wire = deepcopy(wire)
    tuple_wire["references"] = tuple(tuple_wire["references"])
    datetime_wire = deepcopy(wire)
    datetime_wire["requested_at"] = _time()
    enum_wire = _definition().to_dict()
    enum_wire["approval_mode"] = ApprovalMode.PRE_RUN

    for invalid in (
        unknown,
        missing,
        tuple_wire,
        datetime_wire,
        DictSubclass(wire),
    ):
        with pytest.raises(RunContractValidationError):
            RunRequest.from_dict(invalid)
    with pytest.raises(RunContractValidationError):
        WorkflowDefinition.from_dict(enum_wire)


def test_from_dict_does_not_expose_secret_markers() -> None:
    wire = _request().to_dict()
    wire["inputs"] = {"API-Key": "runtime-secret-marker"}

    with pytest.raises(RunContractValidationError) as captured:
        RunRequest.from_dict(wire)

    assert "runtime-secret-marker" not in str(captured.value)


@pytest.mark.parametrize(
    "factory,field_name",
    (
        (_request, "requested_at"),
        (_context, "started_at"),
        (_artifact, "created_at"),
        (_invocation, "started_at"),
        (_record, "created_at"),
    ),
)
def test_naive_timestamps_are_rejected(factory, field_name: str) -> None:
    with pytest.raises(ValidationError, match="timezone"):
        factory(**{field_name: datetime(2026, 7, 24, 12)})
