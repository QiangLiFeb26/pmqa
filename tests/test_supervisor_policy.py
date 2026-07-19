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
    AgentInvocation,
    AgentInvocationStatus,
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


def test_evidence_at_iteration_limit_still_routes_to_knowledge() -> None:
    state = _state(
        status=WorkflowStatus.RUNNING,
        iteration=3,
        max_iterations=3,
        evidence=({"evidence_id": "evidence-1"},),
    )

    decision = decide_next_action(state)

    _assert_agent_decision(decision, AgentRole.KNOWLEDGE)


def test_knowledge_without_validation_routes_to_validator() -> None:
    state = _knowledge_state()

    decision = decide_next_action(state)

    _assert_agent_decision(decision, AgentRole.VALIDATOR)
    assert decision.reason_code is SupervisorReason.VALIDATION_REQUIRED
    assert apply_patch(state, decision.patch).next_agent is AgentRole.VALIDATOR


def test_knowledge_at_iteration_limit_still_routes_to_validator() -> None:
    state = _knowledge_state(iteration=3, max_iterations=3)

    decision = decide_next_action(state)

    _assert_agent_decision(decision, AgentRole.VALIDATOR)


def test_latest_passed_validation_completes_workflow() -> None:
    state = _knowledge_state(
        current_agent=AgentRole.VALIDATOR,
        validation_results=({"status": "passed"},),
        step_history=(_invocation(AgentRole.VALIDATOR),),
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


def test_passed_validation_at_iteration_limit_still_completes() -> None:
    state = _knowledge_state(
        iteration=3,
        max_iterations=3,
        validation_results=({"status": "passed"},),
        step_history=(_invocation(AgentRole.VALIDATOR),),
    )

    decision = decide_next_action(state)

    assert decision.action is SupervisorAction.COMPLETE_WORKFLOW
    assert decision.reason_code is SupervisorReason.VALIDATION_PASSED


def test_latest_failed_validation_routes_to_explorer_without_deleting_history() -> None:
    state = _knowledge_state(
        validation_results=({"status": "failed", "detail": "mismatch"},),
        step_history=(_invocation(AgentRole.VALIDATOR),),
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
    ("results", "history", "expected_action", "expected_agent"),
    [
        (
            ({"status": "failed"}, {"status": "passed"}),
            (
                AgentRole.VALIDATOR,
                AgentRole.EXPLORER,
                AgentRole.KNOWLEDGE,
                AgentRole.VALIDATOR,
            ),
            SupervisorAction.COMPLETE_WORKFLOW,
            None,
        ),
        (
            ({"status": "failed"}, {"status": "failed"}),
            (
                AgentRole.VALIDATOR,
                AgentRole.EXPLORER,
                AgentRole.KNOWLEDGE,
                AgentRole.VALIDATOR,
            ),
            SupervisorAction.EXECUTE_AGENT,
            AgentRole.EXPLORER,
        ),
    ],
)
def test_only_latest_validation_result_controls_routing(
    results,
    history,
    expected_action: SupervisorAction,
    expected_agent,
) -> None:
    decision = decide_next_action(
        _knowledge_state(
            validation_results=results,
            step_history=tuple(_invocation(role) for role in history),
        )
    )

    assert decision.action is expected_action
    assert decision.selected_agent is expected_agent


def test_passed_validation_requires_completed_validator() -> None:
    state = _knowledge_state(
        validation_results=({"status": "passed"},),
        step_history=(),
    )

    with pytest.raises(SupervisorPolicyError, match="completed Validator"):
        decide_next_action(state)


def test_passed_validation_with_matching_validator_completes() -> None:
    state = _knowledge_state(
        validation_results=({"status": "passed"},),
        step_history=(_invocation(AgentRole.VALIDATOR),),
    )

    decision = decide_next_action(state)

    assert decision.action is SupervisorAction.COMPLETE_WORKFLOW
    assert apply_patch(state, decision.patch).status is WorkflowStatus.COMPLETED


def test_extra_completed_validator_without_result_is_rejected() -> None:
    state = _knowledge_state(
        validation_results=({"status": "passed"},),
        step_history=(
            _invocation(AgentRole.VALIDATOR),
            _invocation(AgentRole.VALIDATOR),
        ),
    )

    with pytest.raises(
        SupervisorPolicyError,
        match="no newly appended validation result",
    ):
        decide_next_action(state)


def test_validation_result_without_validator_is_rejected() -> None:
    state = _knowledge_state(
        validation_results=({"status": "failed"}, {"status": "passed"}),
        step_history=(_invocation(AgentRole.VALIDATOR),),
    )

    with pytest.raises(
        SupervisorPolicyError,
        match="no matching completed Validator",
    ):
        decide_next_action(state)


@pytest.mark.parametrize(
    "results",
    [
        ({"status": "passed"}, {"status": "passed"}),
        ({"status": "passed"}, {"status": "failed"}),
        (
            {"status": "failed"},
            {"status": "passed"},
            {"status": "failed"},
        ),
        (
            {"status": "failed"},
            {"status": "passed"},
            {"status": "passed"},
        ),
    ],
)
def test_validation_history_cannot_continue_after_pass(results) -> None:
    state = _knowledge_state(
        validation_results=results,
        step_history=tuple(
            _invocation(AgentRole.VALIDATOR) for _ in results
        ),
    )

    with pytest.raises(SupervisorPolicyError, match="continued after a passed"):
        decide_next_action(state)


@pytest.mark.parametrize(
    ("earlier_result", "message"),
    [
        ({"status": "skipped"}, "unsupported status"),
        ({"detail": "missing"}, "missing required status"),
        ({"status": True}, "must be a string"),
    ],
)
def test_every_validation_result_structure_is_validated(
    earlier_result,
    message: str,
) -> None:
    state = _knowledge_state(
        validation_results=(earlier_result, {"status": "passed"}),
        step_history=(
            _invocation(AgentRole.VALIDATOR),
            _invocation(AgentRole.VALIDATOR),
        ),
    )

    with pytest.raises(SupervisorPolicyError, match=message):
        decide_next_action(state)


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
                "_completed_validator": True,
            },
            "missing required status",
        ),
        (
            {
                "evidence": ({"id": "evidence-1"},),
                "knowledge_candidates": ({"id": "knowledge-1"},),
                "validation_results": ({"status": "skipped"},),
                "_completed_validator": True,
            },
            "unsupported status",
        ),
        (
            {
                "evidence": ({"id": "evidence-1"},),
                "knowledge_candidates": ({"id": "knowledge-1"},),
                "validation_results": ({"status": True},),
                "_completed_validator": True,
            },
            "must be a string",
        ),
    ],
)
def test_policy_rejects_invalid_artifact_states(updates, message: str) -> None:
    updates = dict(updates)
    if updates.pop("_completed_validator", False):
        updates["step_history"] = (_invocation(AgentRole.VALIDATOR),)
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
    state = _knowledge_state(
        validation_results=({"status": "failed"},),
        step_history=(_invocation(AgentRole.VALIDATOR),),
    )
    original = state.model_dump_json()

    first = decide_next_action(state)
    second = decide_next_action(state)

    assert first == second
    assert first.model_dump_json() == second.model_dump_json()
    assert state.model_dump_json() == original


def test_full_failed_validation_recovery_cycle_reaches_completion() -> None:
    state = _knowledge_state(
        validation_results=({"status": "failed"},),
        step_history=(_invocation(AgentRole.VALIDATOR),),
        warnings=("preserve-warning",),
    )

    explorer_decision = decide_next_action(state)
    _assert_agent_decision(explorer_decision, AgentRole.EXPLORER)
    state = apply_patch(state, explorer_decision.patch)
    state = apply_patch(
        state,
        WorkflowStatePatch(
            evidence_to_add=({"id": "evidence-2"},),
            step_history_to_add=(_invocation(AgentRole.EXPLORER),),
        ),
    )

    knowledge_decision = decide_next_action(state)
    _assert_agent_decision(knowledge_decision, AgentRole.KNOWLEDGE)
    assert knowledge_decision.reason_code is SupervisorReason.KNOWLEDGE_REQUIRED
    state = apply_patch(state, knowledge_decision.patch)
    state = apply_patch(
        state,
        WorkflowStatePatch(
            knowledge_candidates_to_add=({"id": "knowledge-2"},),
            step_history_to_add=(_invocation(AgentRole.KNOWLEDGE),),
        ),
    )

    validator_decision = decide_next_action(state)
    _assert_agent_decision(validator_decision, AgentRole.VALIDATOR)
    assert validator_decision.reason_code is SupervisorReason.VALIDATION_REQUIRED
    state = apply_patch(state, validator_decision.patch)
    state = apply_patch(
        state,
        WorkflowStatePatch(
            validation_results_to_add=({"status": "passed"},),
            step_history_to_add=(_invocation(AgentRole.VALIDATOR),),
        ),
    )

    completion = decide_next_action(state)
    assert completion.action is SupervisorAction.COMPLETE_WORKFLOW
    assert completion.reason_code is SupervisorReason.VALIDATION_PASSED
    completed_state = apply_patch(state, completion.patch)
    assert completed_state.status is WorkflowStatus.COMPLETED
    assert len(completed_state.evidence) == 2
    assert len(completed_state.knowledge_candidates) == 2
    assert len(completed_state.validation_results) == 2
    assert len(completed_state.step_history) == 4
    assert completed_state.warnings == ("preserve-warning",)


def test_repeated_failed_validation_starts_a_new_recovery_cycle() -> None:
    state = _knowledge_state(
        evidence=({"id": "evidence-1"}, {"id": "evidence-2"}),
        knowledge_candidates=({"id": "knowledge-1"}, {"id": "knowledge-2"}),
        validation_results=({"status": "failed"}, {"status": "failed"}),
        step_history=(
            _invocation(AgentRole.VALIDATOR),
            _invocation(AgentRole.EXPLORER),
            _invocation(AgentRole.KNOWLEDGE),
            _invocation(AgentRole.VALIDATOR),
        ),
    )

    decision = decide_next_action(state)

    _assert_agent_decision(decision, AgentRole.EXPLORER)
    assert decision.reason_code is SupervisorReason.VALIDATION_FAILED
    assert apply_patch(state, decision.patch).validation_results == (
        {"status": "failed"},
        {"status": "failed"},
    )


def test_recovery_respects_error_and_iteration_precedence() -> None:
    invalid_recovery = {
        "validation_results": ({"status": "failed"},),
        "step_history": (),
    }
    failed = decide_next_action(
        _knowledge_state(errors=("fatal",), **invalid_recovery)
    )
    terminated = decide_next_action(
        _knowledge_state(
            iteration=3,
            max_iterations=3,
            validation_results=({"status": "failed"},),
            step_history=(_invocation(AgentRole.VALIDATOR),),
        )
    )

    assert failed.action is SupervisorAction.FAIL_WORKFLOW
    assert terminated.action is SupervisorAction.TERMINATE_WORKFLOW


def test_recovery_at_iteration_limit_allows_remaining_non_explorer_agents() -> None:
    base = {
        "iteration": 3,
        "max_iterations": 3,
        "validation_results": ({"status": "failed"},),
    }
    after_explorer = _knowledge_state(
        **base,
        step_history=(
            _invocation(AgentRole.VALIDATOR),
            _invocation(AgentRole.EXPLORER),
        ),
    )
    after_knowledge = _knowledge_state(
        **base,
        step_history=(
            _invocation(AgentRole.VALIDATOR),
            _invocation(AgentRole.EXPLORER),
            _invocation(AgentRole.KNOWLEDGE),
        ),
    )

    knowledge_decision = decide_next_action(after_explorer)
    validator_decision = decide_next_action(after_knowledge)

    _assert_agent_decision(knowledge_decision, AgentRole.KNOWLEDGE)
    _assert_agent_decision(validator_decision, AgentRole.VALIDATOR)


@pytest.mark.parametrize(
    ("history", "results", "message"),
    [
        ((), ({"status": "failed"},), "no matching completed Validator"),
        (
            (AgentRole.VALIDATOR, AgentRole.KNOWLEDGE),
            ({"status": "failed"},),
            "must follow Explorer",
        ),
        (
            (
                AgentRole.VALIDATOR,
                AgentRole.EXPLORER,
                AgentRole.VALIDATOR,
            ),
            ({"status": "failed"}, {"status": "failed"}),
            "must follow Explorer",
        ),
        (
            (
                AgentRole.VALIDATOR,
                AgentRole.EXPLORER,
                AgentRole.KNOWLEDGE,
                AgentRole.VALIDATOR,
            ),
            ({"status": "failed"},),
            "no newly appended validation result",
        ),
        (
            (
                AgentRole.VALIDATOR,
                AgentRole.EXPLORER,
                AgentRole.EXPLORER,
            ),
            ({"status": "failed"},),
            "must follow Explorer",
        ),
    ],
)
def test_policy_rejects_invalid_recovery_sequences(
    history,
    results,
    message: str,
) -> None:
    state = _knowledge_state(
        validation_results=results,
        step_history=tuple(_invocation(role) for role in history),
    )

    with pytest.raises(SupervisorPolicyError, match=message):
        decide_next_action(state)


def test_failed_or_incomplete_recovery_invocation_is_ambiguous() -> None:
    base_history = (_invocation(AgentRole.VALIDATOR),)
    for status, message in (
        (AgentInvocationStatus.FAILED, "cannot advance"),
        (AgentInvocationStatus.RUNNING, "ambiguous"),
    ):
        state = _knowledge_state(
            validation_results=({"status": "failed"},),
            step_history=base_history
            + (_invocation(AgentRole.EXPLORER, status),),
        )
        with pytest.raises(SupervisorPolicyError, match=message):
            decide_next_action(state)


@pytest.mark.parametrize(
    ("action", "status", "wrong_reason"),
    [
        (
            SupervisorAction.COMPLETE_WORKFLOW,
            WorkflowStatus.COMPLETED,
            TerminationReason.ERROR,
        ),
        (
            SupervisorAction.FAIL_WORKFLOW,
            WorkflowStatus.FAILED,
            TerminationReason.GOAL_COMPLETED,
        ),
        (
            SupervisorAction.TERMINATE_WORKFLOW,
            WorkflowStatus.TERMINATED,
            TerminationReason.ERROR,
        ),
    ],
)
def test_terminal_decision_rejects_mismatched_termination_reason(
    action: SupervisorAction,
    status: WorkflowStatus,
    wrong_reason: TerminationReason,
) -> None:
    with pytest.raises(ValidationError, match="termination_reason"):
        RoutingDecision(
            workflow_id="workflow-1",
            action=action,
            reason_code=SupervisorReason.WORKFLOW_ERROR,
            summary="Invalid terminal mapping",
            patch=WorkflowStatePatch(
                status=status,
                termination_reason=wrong_reason,
                clear_current_agent=True,
                clear_next_agent=True,
            ),
        )


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


def _invocation(
    agent: AgentRole,
    status: AgentInvocationStatus = AgentInvocationStatus.COMPLETED,
) -> AgentInvocation:
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    terminal = status in {
        AgentInvocationStatus.COMPLETED,
        AgentInvocationStatus.FAILED,
    }
    return AgentInvocation(
        agent=agent,
        started_at=timestamp,
        completed_at=timestamp if terminal else None,
        status=status,
    )


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
