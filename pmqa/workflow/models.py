"""Runtime-independent state contracts for future multi-agent workflows."""

import math
import re
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pmqa.workflow.errors import WorkflowStateValidationError


class WorkflowStatus(str, Enum):
    """Describes the lifecycle state of a workflow."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TERMINATED = "terminated"


class AgentInvocationStatus(str, Enum):
    """Describes the lifecycle state of one agent invocation record."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentRole(str, Enum):
    """Identifies a bounded responsibility in the future agent runtime."""

    SUPERVISOR = "supervisor"
    EXPLORER = "explorer"
    VALIDATOR = "validator"
    KNOWLEDGE = "knowledge"


class TerminationReason(str, Enum):
    """Describes why a workflow intentionally stopped."""

    GOAL_COMPLETED = "goal_completed"
    MAX_ITERATIONS = "max_iterations"
    AGENT_REQUESTED = "agent_requested"
    ERROR = "error"


class AgentInvocation(BaseModel):
    """Records the serializable evidence for one agent invocation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    agent: AgentRole
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: AgentInvocationStatus
    input_summary: Dict[str, Any] = Field(default_factory=dict)
    output_summary: Dict[str, Any] = Field(default_factory=dict)
    reasoning_trace_id: Optional[str] = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_contract(self) -> "AgentInvocation":
        """Validate timestamps and structured summaries."""

        _require_aware(self.started_at, "started_at")
        if self.completed_at is not None:
            _require_aware(self.completed_at, "completed_at")
            if self.completed_at < self.started_at:
                raise ValueError("completed_at must not precede started_at")
        terminal = self.status in {
            AgentInvocationStatus.COMPLETED,
            AgentInvocationStatus.FAILED,
        }
        if terminal != (self.completed_at is not None):
            raise ValueError(
                "completed_at must be present exactly when invocation status is terminal"
            )
        _validate_payload(self.input_summary, "input_summary")
        _validate_payload(self.output_summary, "output_summary")
        return self


class AgentOutcome(BaseModel):
    """Describes requested state changes returned by an agent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    next_agent: Optional[AgentRole] = None
    state_updates: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    terminate: bool = False
    termination_reason: Optional[TerminationReason] = None

    @model_validator(mode="after")
    def validate_contract(self) -> "AgentOutcome":
        """Validate safe updates and termination correlation."""

        _validate_payload(self.state_updates, "state_updates")
        if self.terminate != (self.termination_reason is not None):
            raise ValueError(
                "termination_reason must be present exactly when terminate is true"
            )
        return self


class WorkflowState(BaseModel):
    """Carries checkpoint-safe shared state between future workflow agents."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    workflow_id: str = Field(min_length=1)
    workflow_type: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    product_version: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    status: WorkflowStatus = WorkflowStatus.PENDING
    current_agent: Optional[AgentRole] = None
    next_agent: Optional[AgentRole] = None
    iteration: int = Field(default=0, ge=0)
    max_iterations: int = Field(ge=1)
    product_context: Dict[str, Any] = Field(default_factory=dict)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    knowledge_candidates: List[Dict[str, Any]] = Field(default_factory=list)
    validation_results: List[Dict[str, Any]] = Field(default_factory=list)
    reasoning_trace_ids: List[str] = Field(default_factory=list)
    step_history: List[AgentInvocation] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    termination_reason: Optional[TerminationReason] = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_contract(self) -> "WorkflowState":
        """Validate deterministic timestamps and checkpoint-safe payloads."""

        _require_aware(self.created_at, "created_at")
        _require_aware(self.updated_at, "updated_at")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")
        if self.iteration > self.max_iterations:
            raise ValueError("iteration must not exceed max_iterations")
        _validate_payload(self.product_context, "product_context")
        _validate_payload(self.evidence, "evidence")
        _validate_payload(self.knowledge_candidates, "knowledge_candidates")
        _validate_payload(self.validation_results, "validation_results")
        return self


_PROHIBITED_STATE_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "authorization",
        "browser",
        "browser_context",
        "browser_state",
        "connection",
        "cookie",
        "cookies",
        "credential",
        "credentials",
        "dom",
        "html",
        "llm_client",
        "locator",
        "passwd",
        "password",
        "playwright",
        "provider_instance",
        "raw_dom",
        "refresh_token",
        "runtime",
        "screenshot",
        "secret",
        "session",
        "session_id",
        "storage_state",
        "token",
        "tokens",
    }
)


def _validate_payload(value: Any, path: str) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise WorkflowStateValidationError(
                f"Workflow state contains a non-finite number at {path}"
            )
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_payload(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise WorkflowStateValidationError(
                    f"Workflow state contains a non-string key at {path}"
                )
            child_path = f"{path}.{key}"
            if _normalize_key(key) in _PROHIBITED_STATE_KEYS:
                raise WorkflowStateValidationError(
                    f"Workflow state contains a prohibited field at {child_path}"
                )
            _validate_payload(item, child_path)
        return
    raise WorkflowStateValidationError(
        f"Workflow state contains a runtime object at {path}"
    )


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include timezone information")
