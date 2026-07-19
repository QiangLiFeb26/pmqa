"""Tests for deterministic immutable workflow state reduction."""

import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from pmqa.workflow import (
    AgentInvocation,
    AgentInvocationStatus,
    AgentRole,
    TerminationReason,
    WorkflowReducerError,
    WorkflowState,
    WorkflowStatePatch,
    WorkflowStatus,
    apply_patch,
)


def test_empty_patch_returns_new_equivalent_state() -> None:
    state = _state()

    reduced = apply_patch(state, WorkflowStatePatch())

    assert reduced == state
    assert reduced is not state


def test_empty_patch_preserves_unchanged_payload_values() -> None:
    state = _state(
        evidence=({"evidence_id": "existing"},),
        reasoning_trace_ids=("trace-1",),
    )

    reduced = apply_patch(state, WorkflowStatePatch())

    assert reduced.evidence == state.evidence
    assert reduced.reasoning_trace_ids == state.reasoning_trace_ids
    assert reduced.product_context == state.product_context


def test_replacement_fields_are_applied_only_when_provided() -> None:
    state = _state()
    updated_at = _timestamp(2)
    patch = WorkflowStatePatch(
        status=WorkflowStatus.RUNNING,
        current_agent=AgentRole.SUPERVISOR,
        next_agent=AgentRole.EXPLORER,
        iteration=1,
        updated_at=updated_at,
    )

    reduced = apply_patch(state, patch)

    assert reduced.status is WorkflowStatus.RUNNING
    assert reduced.current_agent is AgentRole.SUPERVISOR
    assert reduced.next_agent is AgentRole.EXPLORER
    assert reduced.iteration == 1
    assert reduced.updated_at == updated_at
    assert reduced.evidence == state.evidence


def test_clear_operations_set_routing_fields_to_none() -> None:
    state = _state(
        status=WorkflowStatus.RUNNING,
        current_agent=AgentRole.SUPERVISOR,
        next_agent=AgentRole.EXPLORER,
    )

    reduced = apply_patch(
        state,
        WorkflowStatePatch(clear_current_agent=True, clear_next_agent=True),
    )

    assert reduced.current_agent is None
    assert reduced.next_agent is None


def test_clear_termination_reason_produces_valid_non_terminal_state() -> None:
    legacy_state = _state(
        status=WorkflowStatus.RUNNING,
        termination_reason=TerminationReason.AGENT_REQUESTED,
    )
    patch = WorkflowStatePatch(
        status=WorkflowStatus.RUNNING,
        clear_termination_reason=True,
    )

    reduced = apply_patch(legacy_state, patch)

    assert reduced.termination_reason is None


def test_append_operations_preserve_existing_and_requested_order() -> None:
    existing_invocation = _invocation("trace-1", _timestamp())
    added_invocation = _invocation("trace-2", _timestamp(1))
    state = _state(
        evidence=({"id": "evidence-1"},),
        knowledge_candidates=({"id": "knowledge-1"},),
        validation_results=({"id": "validation-1"},),
        reasoning_trace_ids=("trace-1",),
        step_history=(existing_invocation,),
        warnings=("warning-1",),
        errors=("error-1",),
    )
    patch = WorkflowStatePatch(
        evidence_to_add=({"id": "evidence-2"}, {"id": "evidence-3"}),
        knowledge_candidates_to_add=({"id": "knowledge-2"},),
        validation_results_to_add=({"id": "validation-2"},),
        reasoning_trace_ids_to_add=("trace-2",),
        step_history_to_add=(added_invocation,),
        warnings_to_add=("warning-2",),
        errors_to_add=("error-2",),
    )
    original_state_json = state.model_dump_json()
    original_patch_json = patch.model_dump_json()

    reduced = apply_patch(state, patch)

    assert [item["id"] for item in reduced.evidence] == [
        "evidence-1",
        "evidence-2",
        "evidence-3",
    ]
    assert [item["id"] for item in reduced.knowledge_candidates] == [
        "knowledge-1",
        "knowledge-2",
    ]
    assert [item["id"] for item in reduced.validation_results] == [
        "validation-1",
        "validation-2",
    ]
    assert reduced.reasoning_trace_ids == ("trace-1", "trace-2")
    assert reduced.step_history == (existing_invocation, added_invocation)
    assert reduced.warnings == ("warning-1", "warning-2")
    assert reduced.errors == ("error-1", "error-2")
    assert state.model_dump_json() == original_state_json
    assert patch.model_dump_json() == original_patch_json


def test_iteration_cannot_decrease_or_exceed_limit() -> None:
    state = _state(iteration=2, max_iterations=3)

    with pytest.raises(WorkflowReducerError, match="must not decrease"):
        apply_patch(state, WorkflowStatePatch(iteration=1))
    with pytest.raises(WorkflowReducerError, match="max_iterations"):
        apply_patch(state, WorkflowStatePatch(iteration=4))
    assert apply_patch(state, WorkflowStatePatch(iteration=3)).iteration == 3


def test_updated_at_cannot_move_backwards() -> None:
    state = _state(updated_at=_timestamp(2))

    with pytest.raises(WorkflowReducerError, match="updated_at"):
        apply_patch(state, WorkflowStatePatch(updated_at=_timestamp(1)))
    assert apply_patch(
        state, WorkflowStatePatch(updated_at=_timestamp(2))
    ).updated_at == _timestamp(2)


def test_transition_to_terminal_requires_reason_and_cleared_routing() -> None:
    state = _state(
        status=WorkflowStatus.RUNNING,
        current_agent=AgentRole.SUPERVISOR,
        next_agent=AgentRole.VALIDATOR,
    )
    terminal_patch = WorkflowStatePatch(
        status=WorkflowStatus.COMPLETED,
        termination_reason=TerminationReason.GOAL_COMPLETED,
    )

    with pytest.raises(WorkflowReducerError, match="clear agent routing"):
        apply_patch(state, terminal_patch)

    reduced = apply_patch(
        state,
        terminal_patch.model_copy(
            update={"clear_current_agent": True, "clear_next_agent": True}
        ),
    )
    assert reduced.status is WorkflowStatus.COMPLETED
    assert reduced.termination_reason is TerminationReason.GOAL_COMPLETED
    assert reduced.current_agent is None
    assert reduced.next_agent is None


def test_non_terminal_result_cannot_retain_termination_reason() -> None:
    state = _state(
        status=WorkflowStatus.RUNNING,
        termination_reason=TerminationReason.ERROR,
    )

    with pytest.raises(WorkflowReducerError, match="non-terminal"):
        apply_patch(state, WorkflowStatePatch())


def test_terminal_state_accepts_only_idempotent_no_op_patches() -> None:
    state = _terminal_state()
    same_lifecycle = WorkflowStatePatch(
        status=WorkflowStatus.COMPLETED,
        termination_reason=TerminationReason.GOAL_COMPLETED,
        clear_current_agent=True,
        clear_next_agent=True,
        iteration=state.iteration,
        updated_at=state.updated_at,
    )

    assert apply_patch(state, WorkflowStatePatch()) == state
    assert apply_patch(state, same_lifecycle) == state
    with pytest.raises(WorkflowReducerError, match="idempotent"):
        apply_patch(state, WorkflowStatePatch(warnings_to_add=("late",)))


def test_terminal_state_cannot_return_to_running() -> None:
    state = _terminal_state()
    patch = WorkflowStatePatch(
        status=WorkflowStatus.RUNNING,
        clear_termination_reason=True,
    )

    with pytest.raises(WorkflowReducerError, match="idempotent"):
        apply_patch(state, patch)


def test_identity_fields_are_always_copied_unchanged() -> None:
    state = _state()
    reduced = apply_patch(
        state,
        WorkflowStatePatch(
            status=WorkflowStatus.RUNNING,
            iteration=1,
            warnings_to_add=("updated",),
            updated_at=_timestamp(1),
        ),
    )

    for field_name in (
        "workflow_id",
        "workflow_type",
        "product_id",
        "product_version",
        "goal",
        "created_at",
        "max_iterations",
    ):
        assert getattr(reduced, field_name) == getattr(state, field_name)


def test_reduced_state_remains_deeply_immutable() -> None:
    state = _state()
    reduced = apply_patch(
        state,
        WorkflowStatePatch(evidence_to_add=({"nested": {"ids": ["one"]}},)),
    )

    with pytest.raises(ValidationError, match="frozen"):
        reduced.status = WorkflowStatus.FAILED
    with pytest.raises(TypeError, match="immutable"):
        reduced.evidence[0]["changed"] = True
    with pytest.raises(AttributeError):
        reduced.evidence[0]["nested"]["ids"].append("two")
    with pytest.raises(ValidationError):
        reduced.model_copy(update={"product_context": {"api_key": "hidden"}})


def test_reduction_is_deterministic() -> None:
    state = _state()
    patch = WorkflowStatePatch(
        status=WorkflowStatus.RUNNING,
        iteration=1,
        evidence_to_add=({"id": "evidence-1"},),
        updated_at=_timestamp(1),
    )

    assert apply_patch(state, patch) == apply_patch(state, patch)
    assert apply_patch(state, patch).model_dump_json() == apply_patch(
        state, patch
    ).model_dump_json()


def test_reducer_import_has_no_runtime_dependencies() -> None:
    script = """
import sys
from pmqa.workflow.reducer import apply_patch
for prohibited in ("langgraph", "playwright", "pmqa.providers"):
    assert prohibited not in sys.modules, (prohibited, sorted(sys.modules))
assert apply_patch is not None
"""

    subprocess.run([sys.executable, "-c", script], check=True)


def _timestamp(hours: int = 0) -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(hours=hours)


def _invocation(trace_id: str, started_at: datetime) -> AgentInvocation:
    return AgentInvocation(
        agent=AgentRole.EXPLORER,
        started_at=started_at,
        completed_at=started_at,
        status=AgentInvocationStatus.COMPLETED,
        reasoning_trace_id=trace_id,
    )


def _state(**updates) -> WorkflowState:
    values = {
        "workflow_id": "workflow-1",
        "workflow_type": "explore",
        "product_id": "demo",
        "product_version": "1",
        "goal": "Validate product knowledge",
        "status": WorkflowStatus.PENDING,
        "current_agent": None,
        "next_agent": None,
        "iteration": 0,
        "max_iterations": 3,
        "product_context": {"environment": "test"},
        "created_at": _timestamp(),
        "updated_at": _timestamp(),
    }
    values.update(updates)
    return WorkflowState(**values)


def _terminal_state() -> WorkflowState:
    return _state(
        status=WorkflowStatus.COMPLETED,
        termination_reason=TerminationReason.GOAL_COMPLETED,
        current_agent=None,
        next_agent=None,
        iteration=1,
        updated_at=_timestamp(1),
    )
