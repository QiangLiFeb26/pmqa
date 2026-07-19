"""Immutable contracts returned by the supervisor policy."""

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pmqa.workflow.models import AgentRole, WorkflowStatus
from pmqa.workflow.updates import WorkflowStatePatch


class SupervisorAction(str, Enum):
    """Names the action a future orchestrator should perform next."""

    EXECUTE_AGENT = "execute_agent"
    COMPLETE_WORKFLOW = "complete_workflow"
    FAIL_WORKFLOW = "fail_workflow"
    TERMINATE_WORKFLOW = "terminate_workflow"


class SupervisorReason(str, Enum):
    """Provides a stable reason code for one routing decision."""

    WORKFLOW_PENDING = "workflow_pending"
    EXPLORATION_REQUIRED = "exploration_required"
    KNOWLEDGE_REQUIRED = "knowledge_required"
    VALIDATION_REQUIRED = "validation_required"
    VALIDATION_PASSED = "validation_passed"
    VALIDATION_FAILED = "validation_failed"
    MAX_ITERATIONS_REACHED = "max_iterations_reached"
    WORKFLOW_ERROR = "workflow_error"
    ALREADY_TERMINAL = "already_terminal"


class RoutingDecision(BaseModel):
    """Describes a deterministic supervisor choice without executing it."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
    )

    workflow_id: str = Field(min_length=1)
    action: SupervisorAction
    selected_agent: Optional[AgentRole] = None
    reason_code: SupervisorReason
    summary: str = Field(min_length=1)
    patch: WorkflowStatePatch

    @model_validator(mode="after")
    def validate_contract(self) -> "RoutingDecision":
        """Validate agent selection and patch correlation."""

        if self.reason_code is SupervisorReason.ALREADY_TERMINAL:
            if self.selected_agent is not None or self.patch.requested_fields():
                raise ValueError(
                    "already-terminal decision must have no agent and an empty patch"
                )
            return self

        if self.action is SupervisorAction.EXECUTE_AGENT:
            if self.selected_agent is None:
                raise ValueError("execute-agent decision requires selected_agent")
            if self.patch.status is not WorkflowStatus.RUNNING:
                raise ValueError("execute-agent patch must set running status")
            if self.patch.next_agent is not self.selected_agent:
                raise ValueError("execute-agent patch must route to selected_agent")
            if not self.patch.clear_current_agent:
                raise ValueError("execute-agent patch must clear current_agent")
            return self

        if self.selected_agent is not None:
            raise ValueError("terminal decision must not select an agent")
        expected_status = {
            SupervisorAction.COMPLETE_WORKFLOW: WorkflowStatus.COMPLETED,
            SupervisorAction.FAIL_WORKFLOW: WorkflowStatus.FAILED,
            SupervisorAction.TERMINATE_WORKFLOW: WorkflowStatus.TERMINATED,
        }[self.action]
        if self.patch.status is not expected_status:
            raise ValueError("terminal decision patch status must match action")
        if not self.patch.clear_current_agent or not self.patch.clear_next_agent:
            raise ValueError("terminal decision patch must clear agent routing")
        return self

    def model_copy(
        self,
        *,
        update: Optional[Dict[str, Any]] = None,
        deep: bool = False,
    ) -> "RoutingDecision":
        """Return a revalidated copy so updates cannot bypass the contract."""

        _ = deep
        values = self.model_dump(mode="python")
        values.update(update or {})
        return type(self).model_validate(values)
