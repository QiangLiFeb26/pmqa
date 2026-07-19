"""Pure deterministic application of typed workflow state patches."""

from typing import Optional, Tuple, TypeVar

from pmqa.workflow.errors import WorkflowReducerError
from pmqa.workflow.models import WorkflowState, WorkflowStatus
from pmqa.workflow.updates import WorkflowStatePatch


_Item = TypeVar("_Item")
_TERMINAL_STATUSES = frozenset(
    {
        WorkflowStatus.COMPLETED,
        WorkflowStatus.FAILED,
        WorkflowStatus.TERMINATED,
    }
)


def apply_patch(
    state: WorkflowState,
    patch: WorkflowStatePatch,
) -> WorkflowState:
    """Validate and apply one patch without mutating either input contract."""

    iteration = state.iteration if patch.iteration is None else patch.iteration
    if iteration < state.iteration:
        raise WorkflowReducerError("iteration must not decrease")
    if iteration > state.max_iterations:
        raise WorkflowReducerError("iteration must not exceed max_iterations")

    updated_at = state.updated_at if patch.updated_at is None else patch.updated_at
    if updated_at < state.updated_at:
        raise WorkflowReducerError("updated_at must not precede current updated_at")

    status = state.status if patch.status is None else patch.status
    current_agent = _replacement_or_clear(
        state.current_agent,
        patch.current_agent,
        patch.clear_current_agent,
    )
    next_agent = _replacement_or_clear(
        state.next_agent,
        patch.next_agent,
        patch.clear_next_agent,
    )
    termination_reason = _replacement_or_clear(
        state.termination_reason,
        patch.termination_reason,
        patch.clear_termination_reason,
    )

    candidate = WorkflowState(
        workflow_id=state.workflow_id,
        workflow_type=state.workflow_type,
        product_id=state.product_id,
        product_version=state.product_version,
        goal=state.goal,
        status=status,
        current_agent=current_agent,
        next_agent=next_agent,
        iteration=iteration,
        max_iterations=state.max_iterations,
        product_context=state.product_context,
        evidence=_append(state.evidence, patch.evidence_to_add),
        knowledge_candidates=_append(
            state.knowledge_candidates,
            patch.knowledge_candidates_to_add,
        ),
        validation_results=_append(
            state.validation_results,
            patch.validation_results_to_add,
        ),
        reasoning_trace_ids=_append(
            state.reasoning_trace_ids,
            patch.reasoning_trace_ids_to_add,
        ),
        step_history=_append(state.step_history, patch.step_history_to_add),
        warnings=_append(state.warnings, patch.warnings_to_add),
        errors=_append(state.errors, patch.errors_to_add),
        termination_reason=termination_reason,
        created_at=state.created_at,
        updated_at=updated_at,
    )

    _validate_lifecycle(state, candidate)
    return candidate


def _replacement_or_clear(
    existing: Optional[_Item],
    replacement: Optional[_Item],
    clear: bool,
) -> Optional[_Item]:
    if clear:
        return None
    if replacement is not None:
        return replacement
    return existing


def _append(
    existing: Tuple[_Item, ...], additions: Tuple[_Item, ...]
) -> Tuple[_Item, ...]:
    if not additions:
        return existing
    return existing + additions


def _validate_lifecycle(previous: WorkflowState, candidate: WorkflowState) -> None:
    is_terminal = candidate.status in _TERMINAL_STATUSES
    if is_terminal != (candidate.termination_reason is not None):
        raise WorkflowReducerError(
            "terminal status requires termination_reason and non-terminal "
            "status forbids it"
        )
    if is_terminal and (
        candidate.current_agent is not None or candidate.next_agent is not None
    ):
        raise WorkflowReducerError("terminal workflow must clear agent routing")
    if previous.status in _TERMINAL_STATUSES and candidate != previous:
        raise WorkflowReducerError(
            "terminal workflow accepts only idempotent no-op patches"
        )
