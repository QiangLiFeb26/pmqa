"""Pure deterministic policy for selecting the next workflow action."""

from typing import Mapping, Tuple

from pmqa.supervisor.contracts import (
    RoutingDecision,
    SupervisorAction,
    SupervisorReason,
)
from pmqa.supervisor.errors import SupervisorPolicyError
from pmqa.workflow.models import (
    AgentInvocation,
    AgentInvocationStatus,
    AgentRole,
    TerminationReason,
    WorkflowState,
    WorkflowStatus,
)
from pmqa.workflow.updates import WorkflowStatePatch


_TERMINAL_ACTIONS = {
    WorkflowStatus.COMPLETED: SupervisorAction.COMPLETE_WORKFLOW,
    WorkflowStatus.FAILED: SupervisorAction.FAIL_WORKFLOW,
    WorkflowStatus.TERMINATED: SupervisorAction.TERMINATE_WORKFLOW,
}


def decide_next_action(state: WorkflowState) -> RoutingDecision:
    """Return the next deterministic action without executing or applying it."""

    terminal_action = _TERMINAL_ACTIONS.get(state.status)
    if terminal_action is not None:
        return RoutingDecision(
            workflow_id=state.workflow_id,
            action=terminal_action,
            reason_code=SupervisorReason.ALREADY_TERMINAL,
            summary="Workflow is already terminal",
            patch=WorkflowStatePatch(),
        )

    _validate_non_terminal_lifecycle(state)

    if state.errors:
        return _terminal_decision(
            state,
            action=SupervisorAction.FAIL_WORKFLOW,
            reason=SupervisorReason.WORKFLOW_ERROR,
            status=WorkflowStatus.FAILED,
            termination_reason=TerminationReason.ERROR,
            summary="Workflow contains a fatal error",
        )

    if state.iteration >= state.max_iterations:
        return _terminal_decision(
            state,
            action=SupervisorAction.TERMINATE_WORKFLOW,
            reason=SupervisorReason.MAX_ITERATIONS_REACHED,
            status=WorkflowStatus.TERMINATED,
            termination_reason=TerminationReason.MAX_ITERATIONS,
            summary="Workflow reached its maximum iteration count",
        )

    _validate_artifact_dependencies(state)

    if not state.evidence:
        reason = (
            SupervisorReason.WORKFLOW_PENDING
            if state.status is WorkflowStatus.PENDING
            else SupervisorReason.EXPLORATION_REQUIRED
        )
        return _agent_decision(
            state,
            agent=AgentRole.EXPLORER,
            reason=reason,
            summary="Structured exploration evidence is required",
        )

    if not state.knowledge_candidates:
        return _agent_decision(
            state,
            agent=AgentRole.KNOWLEDGE,
            reason=SupervisorReason.KNOWLEDGE_REQUIRED,
            summary="Knowledge candidates are required",
        )

    if not state.validation_results:
        return _agent_decision(
            state,
            agent=AgentRole.VALIDATOR,
            reason=SupervisorReason.VALIDATION_REQUIRED,
            summary="Knowledge validation is required",
        )

    validation_status = _latest_validation_status(state.validation_results[-1])
    if validation_status == "passed":
        return _terminal_decision(
            state,
            action=SupervisorAction.COMPLETE_WORKFLOW,
            reason=SupervisorReason.VALIDATION_PASSED,
            status=WorkflowStatus.COMPLETED,
            termination_reason=TerminationReason.GOAL_COMPLETED,
            summary="Latest knowledge validation passed",
        )
    if validation_status == "failed":
        return _decide_failed_validation_recovery(state)
    raise SupervisorPolicyError(
        "Latest validation result has an unsupported status"
    )


def _validate_non_terminal_lifecycle(state: WorkflowState) -> None:
    if state.termination_reason is not None:
        raise SupervisorPolicyError(
            "Non-terminal workflow must not contain termination_reason"
        )
    if state.current_agent is not None and state.next_agent is not None:
        raise SupervisorPolicyError(
            "Workflow must not have current_agent and next_agent simultaneously"
        )
    if state.status is WorkflowStatus.PENDING and (
        state.current_agent is not None or state.next_agent is not None
    ):
        raise SupervisorPolicyError("Pending workflow must not contain agent routing")


def _validate_artifact_dependencies(state: WorkflowState) -> None:
    if state.knowledge_candidates and not state.evidence:
        raise SupervisorPolicyError("Knowledge candidates require evidence")
    if state.validation_results and not state.knowledge_candidates:
        raise SupervisorPolicyError(
            "Validation results require knowledge candidates"
        )


def _latest_validation_status(result: Mapping[str, object]) -> str:
    if "status" not in result:
        raise SupervisorPolicyError(
            "Latest validation result is missing required status"
        )
    status = result["status"]
    if not isinstance(status, str):
        raise SupervisorPolicyError(
            "Latest validation result status must be a string"
        )
    return status


def _decide_failed_validation_recovery(
    state: WorkflowState,
) -> RoutingDecision:
    """Infer the recovery prefix using temporary append-order correlation."""

    completed_validators = tuple(
        (index, invocation)
        for index, invocation in enumerate(state.step_history)
        if invocation.agent is AgentRole.VALIDATOR
        and invocation.status is AgentInvocationStatus.COMPLETED
    )
    if len(completed_validators) < len(state.validation_results):
        raise SupervisorPolicyError(
            "Failed validation has no matching completed Validator invocation"
        )
    if len(completed_validators) > len(state.validation_results):
        raise SupervisorPolicyError(
            "Completed recovery Validator has no newly appended validation result"
        )

    for result_index in range(1, len(state.validation_results)):
        previous_status = _latest_validation_status(
            state.validation_results[result_index - 1]
        )
        if previous_status != "failed":
            raise SupervisorPolicyError(
                "Validation history continued after a passed result"
            )
        previous_index = completed_validators[result_index - 1][0]
        current_index = completed_validators[result_index][0]
        completed_roles = _recovery_roles(
            state.step_history[previous_index + 1 : current_index + 1]
        )
        _require_recovery_sequence(
            completed_roles,
            complete=True,
        )

    latest_validator_index = completed_validators[-1][0]
    completed_roles = _recovery_roles(
        state.step_history[latest_validator_index + 1 :]
    )
    _require_recovery_sequence(completed_roles, complete=False)

    next_agent = (
        AgentRole.EXPLORER,
        AgentRole.KNOWLEDGE,
        AgentRole.VALIDATOR,
    )[len(completed_roles)]
    reason = {
        AgentRole.EXPLORER: SupervisorReason.VALIDATION_FAILED,
        AgentRole.KNOWLEDGE: SupervisorReason.KNOWLEDGE_REQUIRED,
        AgentRole.VALIDATOR: SupervisorReason.VALIDATION_REQUIRED,
    }[next_agent]
    return _agent_decision(
        state,
        agent=next_agent,
        reason=reason,
        summary=f"Failed-validation recovery requires {next_agent.value}",
    )


def _recovery_roles(
    invocations: Tuple[AgentInvocation, ...],
) -> Tuple[AgentRole, ...]:
    roles = []
    relevant_roles = {
        AgentRole.EXPLORER,
        AgentRole.KNOWLEDGE,
        AgentRole.VALIDATOR,
    }
    for invocation in invocations:
        if invocation.agent not in relevant_roles:
            continue
        if invocation.status is AgentInvocationStatus.FAILED:
            raise SupervisorPolicyError(
                f"Failed {invocation.agent.value} invocation cannot advance recovery"
            )
        if invocation.status is not AgentInvocationStatus.COMPLETED:
            raise SupervisorPolicyError(
                f"Incomplete {invocation.agent.value} invocation is ambiguous"
            )
        roles.append(invocation.agent)
    return tuple(roles)


def _require_recovery_sequence(
    roles: Tuple[AgentRole, ...],
    *,
    complete: bool,
) -> None:
    expected = (
        AgentRole.EXPLORER,
        AgentRole.KNOWLEDGE,
        AgentRole.VALIDATOR,
    )
    if complete:
        if roles != expected:
            raise SupervisorPolicyError(
                "Completed recovery cycle must follow Explorer, Knowledge, Validator"
            )
        return
    if len(roles) >= len(expected) or roles != expected[: len(roles)]:
        raise SupervisorPolicyError(
            "Recovery sequence must follow Explorer, Knowledge, Validator"
        )


def _agent_decision(
    state: WorkflowState,
    *,
    agent: AgentRole,
    reason: SupervisorReason,
    summary: str,
) -> RoutingDecision:
    return RoutingDecision(
        workflow_id=state.workflow_id,
        action=SupervisorAction.EXECUTE_AGENT,
        selected_agent=agent,
        reason_code=reason,
        summary=summary,
        patch=WorkflowStatePatch(
            status=WorkflowStatus.RUNNING,
            clear_current_agent=True,
            next_agent=agent,
            clear_termination_reason=True,
        ),
    )


def _terminal_decision(
    state: WorkflowState,
    *,
    action: SupervisorAction,
    reason: SupervisorReason,
    status: WorkflowStatus,
    termination_reason: TerminationReason,
    summary: str,
) -> RoutingDecision:
    return RoutingDecision(
        workflow_id=state.workflow_id,
        action=action,
        reason_code=reason,
        summary=summary,
        patch=WorkflowStatePatch(
            status=status,
            clear_current_agent=True,
            clear_next_agent=True,
            termination_reason=termination_reason,
        ),
    )
