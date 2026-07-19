"""Unit tests for multi-agent workflow state contracts."""

import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from pmqa.security.boundary_policy import WORKFLOW_STATE_PROHIBITED_KEY_EXTENSIONS
from pmqa.workflow import (
    AgentInvocation,
    AgentInvocationStatus,
    AgentRole,
    TerminationReason,
    WorkflowState,
    WorkflowStatus,
)


def test_workflow_state_json_round_trip_is_deterministic() -> None:
    state = _state()

    serialized = state.model_dump_json()
    restored = WorkflowState.model_validate_json(serialized)

    assert restored == state
    assert restored.model_dump_json() == serialized
    assert restored.created_at == _timestamp()
    assert restored.updated_at == _timestamp()


def test_workflow_contract_import_does_not_load_langgraph() -> None:
    statement = "\n".join(
        [
            "import sys",
            "from pmqa.workflow import WorkflowState",
            "assert WorkflowState.__name__ == 'WorkflowState'",
            "assert 'pmqa.workflow.graph' not in sys.modules",
            "assert not any(name == 'langgraph' or name.startswith('langgraph.') "
            "for name in sys.modules)",
        ]
    )
    completed = subprocess.run(
        [sys.executable, "-c", statement],
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_complete_state_supports_typed_history_and_references() -> None:
    completed_at = _timestamp() + timedelta(seconds=1)
    invocation = AgentInvocation(
        agent=AgentRole.EXPLORER,
        started_at=_timestamp(),
        completed_at=completed_at,
        status=AgentInvocationStatus.COMPLETED,
        input_summary={"page_ids": ["page.login"]},
        output_summary={"evidence_ids": ["evidence.login"]},
        reasoning_trace_id="trace-1",
    )
    state = _state().model_copy(
        update={
            "status": WorkflowStatus.RUNNING,
            "current_agent": AgentRole.EXPLORER,
            "next_agent": AgentRole.VALIDATOR,
            "iteration": 1,
            "evidence": [{"evidence_id": "evidence.login"}],
            "knowledge_candidates": [{"candidate_id": "candidate.login"}],
            "validation_results": [{"result_id": "result.login"}],
            "reasoning_trace_ids": ["trace-1"],
            "step_history": [invocation],
        }
    )

    restored = WorkflowState.model_validate_json(state.model_dump_json())

    assert restored.step_history == (invocation,)
    assert restored.next_agent is AgentRole.VALIDATOR


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("status", "unknown"),
        ("current_agent", "unknown"),
        ("termination_reason", "unknown"),
    ],
)
def test_invalid_enum_values_are_rejected(field: str, value: str) -> None:
    payload = _state().model_dump(mode="json")
    payload[field] = value

    with pytest.raises(ValidationError, match=field):
        WorkflowState.model_validate(payload)


def test_models_are_immutable() -> None:
    invocation = AgentInvocation(
        agent=AgentRole.EXPLORER,
        started_at=_timestamp(),
        status=AgentInvocationStatus.RUNNING,
    )
    for model in (_state(), invocation):
        with pytest.raises(ValidationError, match="frozen"):
            model.warnings = ["changed"]


def test_workflow_state_nested_containers_are_deeply_immutable() -> None:
    state = _state(
        product_context={"nested": {"items": ["one"]}},
        evidence=[{"details": {"ids": ["evidence-1"]}}],
        reasoning_trace_ids=["trace-1"],
    )

    with pytest.raises(TypeError, match="immutable"):
        state.product_context["api_key"] = "secret"
    with pytest.raises(TypeError, match="immutable"):
        state.product_context["nested"]["changed"] = True
    with pytest.raises(AttributeError):
        state.product_context["nested"]["items"].append("two")
    with pytest.raises(AttributeError):
        state.evidence.append({"evidence_id": "new"})
    with pytest.raises(TypeError, match="immutable"):
        state.evidence[0]["details"]["changed"] = True
    with pytest.raises(AttributeError):
        state.reasoning_trace_ids.append("trace-2")
    with pytest.raises(ValidationError, match="api_key"):
        state.model_copy(update={"product_context": {"api_key": "secret"}})


def test_agent_payloads_are_deeply_immutable() -> None:
    invocation = AgentInvocation(
        agent=AgentRole.EXPLORER,
        started_at=_timestamp(),
        status=AgentInvocationStatus.RUNNING,
        input_summary={"nested": {"ids": ["input-1"]}},
    )
    with pytest.raises(TypeError, match="immutable"):
        invocation.input_summary["changed"] = True
    with pytest.raises(TypeError, match="immutable"):
        invocation.input_summary["nested"]["changed"] = True
    with pytest.raises(AttributeError):
        invocation.input_summary["nested"]["ids"].append("input-2")


def test_unknown_fields_are_rejected() -> None:
    payload = _state().model_dump(mode="json")
    payload["runtime_handle"] = "not-allowed"

    with pytest.raises(ValidationError, match="runtime_handle"):
        WorkflowState.model_validate(payload)


@pytest.mark.parametrize(
    ("model_type", "payload"),
    [
        (
            AgentInvocation,
            {
                "agent": "explorer",
                "started_at": "2026-01-01T00:00:00Z",
                "status": "running",
                "unexpected": True,
            },
        ),
    ],
)
def test_agent_models_reject_unknown_fields(model_type, payload) -> None:
    with pytest.raises(ValidationError, match="unexpected"):
        model_type.model_validate(payload)


@pytest.mark.parametrize(
    "unsafe_payload",
    [
        {"metadata": {"api_key": "private"}},
        {"items": [{"cookies": ["private"]}]},
        {"browser": "live-browser"},
    ],
)
def test_sensitive_and_runtime_fields_are_rejected(unsafe_payload) -> None:
    with pytest.raises(ValidationError, match="prohibited field"):
        _state(product_context=unsafe_payload)


@pytest.mark.parametrize(
    "prohibited_key", sorted(WORKFLOW_STATE_PROHIBITED_KEY_EXTENSIONS)
)
def test_workflow_specific_fields_are_rejected(prohibited_key: str) -> None:
    with pytest.raises(ValidationError, match="prohibited field"):
        _state(product_context={"nested": {prohibited_key: "runtime-marker"}})


def test_runtime_objects_are_rejected_without_echoing_values() -> None:
    class FakeConnection:
        def __repr__(self) -> str:
            return "FakeConnection(secret=private-marker)"

    with pytest.raises(ValidationError) as captured:
        _state(product_context={"safe_name": FakeConnection()})

    assert "runtime object" in str(captured.value)
    assert "private-marker" not in str(captured.value)


def test_non_json_numbers_are_rejected() -> None:
    with pytest.raises(ValidationError, match="non-finite"):
        _state(evidence=[{"score": float("nan")}])


def test_iteration_and_timestamp_constraints_are_enforced() -> None:
    with pytest.raises(ValidationError, match="iteration"):
        _state(iteration=4, max_iterations=3)
    with pytest.raises(ValidationError, match="updated_at"):
        _state(updated_at=_timestamp() - timedelta(seconds=1))
    with pytest.raises(ValidationError, match="timezone"):
        _state(created_at=datetime(2026, 1, 1))


def test_agent_invocation_enforces_terminal_timestamp_correlation() -> None:
    with pytest.raises(ValidationError, match="completed_at"):
        AgentInvocation(
            agent=AgentRole.EXPLORER,
            started_at=_timestamp(),
            status=AgentInvocationStatus.COMPLETED,
        )


def test_agent_invocation_rejects_invalid_role_and_status() -> None:
    payload = {
        "agent": "unknown",
        "started_at": "2026-01-01T00:00:00Z",
        "status": "unknown",
    }

    with pytest.raises(ValidationError) as captured:
        AgentInvocation.model_validate(payload)

    assert "agent" in str(captured.value)
    assert "status" in str(captured.value)


def _state(**updates) -> WorkflowState:
    values = {
        "workflow_id": "workflow-1",
        "workflow_type": "product-analysis",
        "product_id": "demo",
        "product_version": "1",
        "goal": "Collect structured QA evidence",
        "max_iterations": 3,
        "product_context": {"page_ids": ["page.login"]},
        "created_at": _timestamp(),
        "updated_at": _timestamp(),
    }
    values.update(updates)
    return WorkflowState(**values)


def _timestamp() -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc)
