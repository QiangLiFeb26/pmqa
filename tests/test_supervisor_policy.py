"""Tests for deterministic supervisor routing policy."""

import json
import subprocess
import sys
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from pmqa.supervisor import (
    RoutingDecision,
    SupervisorAction,
    SupervisorPolicyError,
    SupervisorReason,
    decide_next_action,
)
from pmqa.workflow import (
    AgentRole,
    TerminationReason,
    WorkflowState,
    WorkflowStatePatch,
    WorkflowStatus,
    apply_patch,
)


@pytest.mark.parametrize(
    ("status", "reason", "action"),
    [
        (
            WorkflowStatus.COMPLETED,
            TerminationReason.GOAL_COMPLETED,
            SupervisorAction.COMPLETE_WORKFLOW,
        ),
        (
            WorkflowStatus.FAILED,
            TerminationReason.ERROR,
            SupervisorAction.FAIL_WORKFLOW,
        ),
        (
            WorkflowStatus.TERMINATED,
            TerminationReason.MAX_ITERATIONS,
            SupervisorAction.TERMINATE_WORKFLOW,
        ),
    ],
)
def test_terminal_states_return_idempotent_empty_decisions(
    status: WorkflowStatus,
    reason: TerminationReason,
    action: SupervisorAction,
) -> None:
    state = _state(status=status, termination_reason=reason, errors=("existing",))

    decision = decide_next_action(state)

    assert decision.action is action
    assert decision.reason_code is SupervisorReason.ALREADY_TERMINAL
    assert decision.selected_agent is None
    assert decision.patch == WorkflowStatePatch()
    assert apply_patch(state, decision.patch) == state


def test_existing_errors_fail_workflow_before_iteration_limit() -> None:
    state = _state(
        status=WorkflowStatus.RUNNING,
        errors=("fatal",),
        iteration=3,
        max_iterations=3,
        current_agent=AgentRole.EXPLORER,
    )

    decision = decide_next_action(state)
    reduced = apply_patch(state, decision.patch)

    assert decision.action is SupervisorAction.FAIL_WORKFLOW
    assert decision.reason_code is SupervisorReason.WORKFLOW_ERROR
    assert decision.selected_agent is None
    assert decision.patch.termination_reason is TerminationReason.ERROR
    assert decision.patch.clear_current_agent
    assert decision.patch.clear_next_agent
    assert not decision.patch.errors_to_add
    assert reduced.status is WorkflowStatus.FAILED
    assert reduced.errors == state.errors


def test_iteration_limit_terminates_workflow() -> None:
    state = _state(
        status=WorkflowStatus.RUNNING,
        iteration=3,
        max_iterations=3,
        next_agent=AgentRole.VALIDATOR,
    )

    decision = decide_next_action(state)
    reduced = apply_patch(state, decision.patch)

    assert decision.action is SupervisorAction.TERMINATE_WORKFLOW
    assert decision.reason_code is SupervisorReason.MAX_ITERATIONS_REACHED
    assert decision.selected_agent is None
    assert decision.patch.termination_reason is TerminationReason.MAX_ITERATIONS
    assert reduced.status is WorkflowStatus.TERMINATED
    assert reduced.current_agent is None
    assert reduced.next_agent is None


def test_pending_workflow_routes_to_explorer_without_incrementing() -> None:
    state = _state()

    decision = decide_next_action(state)
    reduced = apply_patch(state, decision.patch)

    _assert_agent_decision(decision, AgentRole.EXPLORER)
    assert decision.reason_code is SupervisorReason.WORKFLOW_PENDING
    assert decision.patch.iteration is None
    assert reduced.iteration == state.iteration
    assert reduced.status is WorkflowStatus.RUNNING
    assert reduced.current_agent is None
    assert reduced.next_agent is AgentRole.EXPLORER


def test_running_workflow_without_evidence_routes_to_explorer() -> None:
    decision = decide_next_action(_state(status=WorkflowStatus.RUNNING))

    _assert_agent_decision(decision, AgentRole.EXPLORER)
    assert decision.reason_code is SupervisorReason.EXPLORATION_REQUIRED


def test_evidence_without_knowledge_routes_to_knowledge() -> None:
    state = _state(
        status=WorkflowStatus.RUNNING,
        evidence=({"evidence_id": "evidence-1"},),
    )

    decision = decide_next_action(state)

    _assert_agent_decision(decision, AgentRole.KNOWLEDGE)
    assert decision.reason_code is SupervisorReason.KNOWLEDGE_REQUIRED
    assert apply_patch(state, decision.patch).next_agent is AgentRole.KNOWLEDGE


def test_knowledge_without_validation_routes_to_validator() -> None:
    state = _knowledge_state()

    decision = decide_next_action(state)

    _assert_agent_decision(decision, AgentRole.VALIDATOR)
    assert decision.reason_code is SupervisorReason.VALIDATION_REQUIRED
    assert apply_patch(state, decision.patch).next_agent is AgentRole.VALIDATOR


def test_latest_passed_validation_completes_workflow() -> None:
    state = _knowledge_state(
        current_agent=AgentRole.VALIDATOR,
        validation_results=({"status": "passed"},),
    )

    decision = decide_next_action(state)
    reduced = apply_patch(state, decision.patch)

    assert decision.action is SupervisorAction.COMPLETE_WORKFLOW
    assert decision.reason_code is SupervisorReason.VALIDATION_PASSED
    assert decision.selected_agent is None
    assert decision.patch.termination_reason is TerminationReason.GOAL_COMPLETED
    assert reduced.status is WorkflowStatus.COMPLETED
    assert reduced.current_agent is None
    assert reduced.next_agent is None


def test_latest_failed_validation_routes_to_explorer_without_deleting_history() -> None:
    state = _knowledge_state(
        validation_results=({"status": "failed", "detail": "mismatch"},),
    )

    decision = decide_next_action(state)
    reduced = apply_patch(state, decision.patch)

    _assert_agent_decision(decision, AgentRole.EXPLORER)
    assert decision.reason_code is SupervisorReason.VALIDATION_FAILED
    assert not decision.patch.evidence_to_add
    assert not decision.patch.knowledge_candidates_to_add
    assert not decision.patch.validation_results_to_add
    assert reduced.evidence == state.evidence
    assert reduced.knowledge_candidates == state.knowledge_candidates
    assert reduced.validation_results == state.validation_results


@pytest.mark.parametrize(
    ("results", "expected_action", "expected_agent"),
    [
        (
            ({"status": "failed"}, {"status": "passed"}),
            SupervisorAction.COMPLETE_WORKFLOW,
            None,
        ),
        (
            ({"status": "passed"}, {"status": "failed"}),
            SupervisorAction.EXECUTE_AGENT,
            AgentRole.EXPLORER,
        ),
    ],
)
def test_only_latest_validation_result_controls_routing(
    results,
    expected_action: SupervisorAction,
    expected_agent,
) -> None:
    decision = decide_next_action(
        _knowledge_state(validation_results=results)
    )

    assert decision.action is expected_action
    assert decision.selected_agent is expected_agent


def test_error_precedence_skips_malformed_artifact_interpretation() -> None:
    state = _state(
        status=WorkflowStatus.RUNNING,
        errors=("fatal",),
        validation_results=({"missing": "status"},),
    )

    assert decide_next_action(state).action is SupervisorAction.FAIL_WORKFLOW


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        (
            {"knowledge_candidates": ({"id": "knowledge-1"},)},
            "require evidence",
        ),
        (
            {"validation_results": ({"status": "passed"},)},
            "require knowledge",
        ),
        (
            {
                "evidence": ({"id": "evidence-1"},),
                "knowledge_candidates": ({"id": "knowledge-1"},),
                "validation_results": ({"detail": "missing"},),
            },
            "missing required status",
        ),
        (
            {
                "evidence": ({"id": "evidence-1"},),
                "knowledge_candidates": ({"id": "knowledge-1"},),
                "validation_results": ({"status": "skipped"},),
            },
            "unsupported status",
        ),
        (
            {
                "evidence": ({"id": "evidence-1"},),
                "knowledge_candidates": ({"id": "knowledge-1"},),
                "validation_results": ({"status": True},),
            },
            "must be a string",
        ),
    ],
)
def test_policy_rejects_invalid_artifact_states(updates, message: str) -> None:
    with pytest.raises(SupervisorPolicyError, match=message):
        decide_next_action(_state(status=WorkflowStatus.RUNNING, **updates))


def test_policy_rejects_invalid_non_terminal_lifecycle_state() -> None:
    with pytest.raises(SupervisorPolicyError, match="termination_reason"):
        decide_next_action(
            _state(
                status=WorkflowStatus.RUNNING,
                termination_reason=TerminationReason.ERROR,
            )
        )
    with pytest.raises(SupervisorPolicyError, match="simultaneously"):
        decide_next_action(
            _state(
                status=WorkflowStatus.RUNNING,
                current_agent=AgentRole.EXPLORER,
                next_agent=AgentRole.KNOWLEDGE,
            )
        )
    with pytest.raises(SupervisorPolicyError, match="Pending"):
        decide_next_action(_state(next_agent=AgentRole.EXPLORER))


def test_routing_decision_is_strict_immutable_and_json_serializable() -> None:
    decision = decide_next_action(_state())
    restored = RoutingDecision.model_validate_json(decision.model_dump_json())

    assert restored == decision
    assert json.loads(decision.model_dump_json())["selected_agent"] == "explorer"
    with pytest.raises(ValidationError, match="frozen"):
        decision.summary = "changed"
    with pytest.raises(ValidationError, match="Extra inputs"):
        RoutingDecision.model_validate(
            {**decision.model_dump(mode="python"), "provider": "unsupported"}
        )
    with pytest.raises(ValidationError, match="selected_agent"):
        decision.model_copy(update={"selected_agent": None})
    with pytest.raises(ValidationError, match="frozen"):
        decision.patch.next_agent = AgentRole.KNOWLEDGE


def test_policy_does_not_mutate_state_and_is_deterministic() -> None:
    state = _knowledge_state(validation_results=({"status": "failed"},))
    original = state.model_dump_json()

    first = decide_next_action(state)
    second = decide_next_action(state)

    assert first == second
    assert first.model_dump_json() == second.model_dump_json()
    assert state.model_dump_json() == original


def test_supervisor_import_has_no_runtime_or_provider_dependencies() -> None:
    script = """
import sys
from pmqa.supervisor import RoutingDecision, decide_next_action
for prohibited in (
    "langgraph", "playwright", "pmqa.providers", "pmqa.runtime"
):
    assert prohibited not in sys.modules, (prohibited, sorted(sys.modules))
assert RoutingDecision is not None and decide_next_action is not None
"""

    subprocess.run([sys.executable, "-c", script], check=True)


def _assert_agent_decision(
    decision: RoutingDecision,
    agent: AgentRole,
) -> None:
    assert decision.action is SupervisorAction.EXECUTE_AGENT
    assert decision.selected_agent is agent
    assert decision.patch.status is WorkflowStatus.RUNNING
    assert decision.patch.clear_current_agent
    assert decision.patch.next_agent is agent
    assert decision.patch.clear_termination_reason


def _knowledge_state(**updates) -> WorkflowState:
    values = {
        "status": WorkflowStatus.RUNNING,
        "evidence": ({"id": "evidence-1"},),
        "knowledge_candidates": ({"id": "knowledge-1"},),
    }
    values.update(updates)
    return _state(**values)


def _state(**updates) -> WorkflowState:
    values = {
        "workflow_id": "workflow-1",
        "workflow_type": "knowledge-lifecycle",
        "product_id": "demo",
        "product_version": "1",
        "goal": "Produce validated product knowledge",
        "status": WorkflowStatus.PENDING,
        "iteration": 0,
        "max_iterations": 3,
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    values.update(updates)
    return WorkflowState(**values)
