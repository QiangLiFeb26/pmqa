"""Runtime-independent state contracts for future multi-agent workflows."""

import math
import re
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Tuple

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


class _WorkflowContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
    )

    def model_copy(
        self,
        *,
        update: Optional[Dict[str, Any]] = None,
        deep: bool = False,
    ) -> "_WorkflowContract":
        """Return a fully revalidated copy so updates cannot bypass freezing."""

        _ = deep
        values = self.model_dump(mode="python")
        values.update(update or {})
        return type(self).model_validate(values)


class AgentInvocation(_WorkflowContract):
    """Records the serializable evidence for one agent invocation."""

    agent: AgentRole
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: AgentInvocationStatus
    input_summary: Mapping[str, Any] = Field(default_factory=dict)
    output_summary: Mapping[str, Any] = Field(default_factory=dict)
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
        object.__setattr__(self, "input_summary", _freeze(self.input_summary))
        object.__setattr__(self, "output_summary", _freeze(self.output_summary))
        return self


class WorkflowState(_WorkflowContract):
    """Carries checkpoint-safe shared state between future workflow agents."""

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
    product_context: Mapping[str, Any] = Field(default_factory=dict)
    evidence: Tuple[Mapping[str, Any], ...] = Field(default_factory=tuple)
    knowledge_candidates: Tuple[Mapping[str, Any], ...] = Field(default_factory=tuple)
    validation_results: Tuple[Mapping[str, Any], ...] = Field(default_factory=tuple)
    reasoning_trace_ids: Tuple[str, ...] = Field(default_factory=tuple)
    step_history: Tuple[AgentInvocation, ...] = Field(default_factory=tuple)
    warnings: Tuple[str, ...] = Field(default_factory=tuple)
    errors: Tuple[str, ...] = Field(default_factory=tuple)
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
        object.__setattr__(self, "product_context", _freeze(self.product_context))
        object.__setattr__(self, "evidence", _freeze(self.evidence))
        object.__setattr__(
            self, "knowledge_candidates", _freeze(self.knowledge_candidates)
        )
        object.__setattr__(
            self, "validation_results", _freeze(self.validation_results)
        )
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
    if isinstance(value, (list, tuple)):
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


class _FrozenDict(dict):
    """JSON-serializable mapping that rejects in-place mutation."""

    def _immutable(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("workflow mappings are immutable")

    __delitem__ = _immutable
    __ior__ = _immutable
    __setitem__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return _FrozenDict({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include timezone information")
