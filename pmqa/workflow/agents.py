"""Provider-independent contracts for future synchronous workflow agents."""

from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Optional, Protocol, Tuple

from pydantic import Field, model_validator

from pmqa.workflow.errors import AgentContractValidationError
from pmqa.workflow.models import (
    AgentRole,
    WorkflowState,
    _WorkflowContract,
    _freeze,
    _require_aware,
    _validate_payload,
)
from pmqa.workflow.updates import (
    AgentCapabilities,
    WorkflowStatePatch,
    validate_patch_for_role,
)


class AgentExecutionStatus(str, Enum):
    """Describes the result of one agent decision invocation."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    NO_ACTION = "no_action"


class AgentRequest(_WorkflowContract):
    """Carries immutable workflow state into one requested agent invocation."""

    workflow_id: str = Field(min_length=1)
    agent: AgentRole
    state: WorkflowState
    invocation_id: str = Field(min_length=1)
    requested_at: datetime
    instruction: Optional[str] = None
    context_refs: Tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_contract(self) -> "AgentRequest":
        """Validate workflow correlation and request timestamp."""

        _require_aware(self.requested_at, "requested_at")
        if self.workflow_id != self.state.workflow_id:
            raise ValueError("workflow_id must match state.workflow_id")
        return self


class AgentResult(_WorkflowContract):
    """Returns one agent's typed state patch without owning workflow state."""

    workflow_id: str = Field(min_length=1)
    agent: AgentRole
    invocation_id: str = Field(min_length=1)
    patch: WorkflowStatePatch
    completed_at: datetime
    outcome_status: AgentExecutionStatus
    summary: Mapping[str, Any] = Field(default_factory=dict)
    reasoning_trace_id: Optional[str] = Field(default=None, min_length=1)
    warnings: Tuple[str, ...] = Field(default_factory=tuple)
    errors: Tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_contract(self) -> "AgentResult":
        """Validate timestamp, payload safety, and role capabilities."""

        _require_aware(self.completed_at, "completed_at")
        _validate_payload(self.summary, "summary")
        validate_patch_for_role(self.agent, self.patch)
        object.__setattr__(self, "summary", _freeze(self.summary))
        return self


class PMQAAgent(Protocol):
    """Defines the synchronous decision boundary for a future PMQA agent."""

    @property
    def role(self) -> AgentRole:
        """Return the agent's declared workflow role."""

        ...

    @property
    def capabilities(self) -> AgentCapabilities:
        """Return the immutable patch operations declared by this agent."""

        ...

    def invoke(self, request: AgentRequest) -> AgentResult:
        """Return a typed decision result without mutating request state."""

        ...


def validate_agent_result(
    request: AgentRequest, result: AgentResult
) -> AgentResult:
    """Validate request/result identity and timestamp correlation without mutation."""

    if result.agent != request.agent:
        raise AgentContractValidationError(
            "Agent result role must match the requested agent role"
        )
    if result.workflow_id != request.workflow_id:
        raise AgentContractValidationError(
            "Agent result workflow_id must match the request workflow_id"
        )
    if result.invocation_id != request.invocation_id:
        raise AgentContractValidationError(
            "Agent result invocation_id must match the request invocation_id"
        )
    if result.completed_at < request.requested_at:
        raise AgentContractValidationError(
            "Agent result completed_at must not precede requested_at"
        )
    validate_patch_for_role(result.agent, result.patch)
    return result
