"""Typed, capability-bounded state patches requested by workflow agents."""

from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, FrozenSet, Mapping, Optional, Tuple

from pydantic import ConfigDict, Field, model_validator

from pmqa.workflow.errors import AgentContractValidationError
from pmqa.workflow.models import (
    AgentInvocation,
    AgentRole,
    TerminationReason,
    WorkflowStatus,
    _WorkflowContract,
    _freeze,
    _require_aware,
    _validate_payload,
)


class WorkflowPatchField(str, Enum):
    """Names one workflow state operation an agent may request."""

    STATUS = "status"
    CURRENT_AGENT = "current_agent"
    NEXT_AGENT = "next_agent"
    ITERATION = "iteration"
    EVIDENCE_TO_ADD = "evidence_to_add"
    KNOWLEDGE_CANDIDATES_TO_ADD = "knowledge_candidates_to_add"
    VALIDATION_RESULTS_TO_ADD = "validation_results_to_add"
    REASONING_TRACE_IDS_TO_ADD = "reasoning_trace_ids_to_add"
    STEP_HISTORY_TO_ADD = "step_history_to_add"
    WARNINGS_TO_ADD = "warnings_to_add"
    ERRORS_TO_ADD = "errors_to_add"
    TERMINATION_REASON = "termination_reason"
    UPDATED_AT = "updated_at"


class WorkflowStatePatch(_WorkflowContract):
    """Describes typed replacements, clears, and append-only state changes."""

    status: Optional[WorkflowStatus] = None
    current_agent: Optional[AgentRole] = None
    clear_current_agent: bool = False
    next_agent: Optional[AgentRole] = None
    clear_next_agent: bool = False
    iteration: Optional[int] = Field(default=None, ge=0)
    evidence_to_add: Tuple[Mapping[str, Any], ...] = Field(default_factory=tuple)
    knowledge_candidates_to_add: Tuple[Mapping[str, Any], ...] = Field(
        default_factory=tuple
    )
    validation_results_to_add: Tuple[Mapping[str, Any], ...] = Field(
        default_factory=tuple
    )
    reasoning_trace_ids_to_add: Tuple[str, ...] = Field(default_factory=tuple)
    step_history_to_add: Tuple[AgentInvocation, ...] = Field(default_factory=tuple)
    warnings_to_add: Tuple[str, ...] = Field(default_factory=tuple)
    errors_to_add: Tuple[str, ...] = Field(default_factory=tuple)
    termination_reason: Optional[TerminationReason] = None
    clear_termination_reason: bool = False
    updated_at: Optional[datetime] = None

    @model_validator(mode="after")
    def validate_contract(self) -> "WorkflowStatePatch":
        """Validate patch semantics before freezing append payloads."""

        if self.current_agent is not None and self.clear_current_agent:
            raise ValueError("current_agent cannot be set and cleared together")
        if self.next_agent is not None and self.clear_next_agent:
            raise ValueError("next_agent cannot be set and cleared together")
        if self.termination_reason is not None and self.clear_termination_reason:
            raise ValueError(
                "termination_reason cannot be set and cleared together"
            )
        terminal_statuses = {
            WorkflowStatus.COMPLETED,
            WorkflowStatus.FAILED,
            WorkflowStatus.TERMINATED,
        }
        if self.status in terminal_statuses and self.termination_reason is None:
            raise ValueError("terminal status requires termination_reason")
        if self.termination_reason is not None and self.status not in terminal_statuses:
            raise ValueError("termination_reason requires a terminal status")
        if self.clear_termination_reason and self.status is None:
            raise ValueError(
                "clearing termination_reason requires a non-terminal status update"
            )
        if self.clear_termination_reason and self.status in terminal_statuses:
            raise ValueError(
                "termination_reason cannot be cleared with a terminal status"
            )
        if self.updated_at is not None:
            _require_aware(self.updated_at, "updated_at")
        for field_name in (
            "evidence_to_add",
            "knowledge_candidates_to_add",
            "validation_results_to_add",
        ):
            value = getattr(self, field_name)
            _validate_payload(value, field_name)
            object.__setattr__(self, field_name, _freeze(value))
        return self

    def requested_fields(self) -> FrozenSet[WorkflowPatchField]:
        """Return the deterministic set of operations requested by this patch."""

        requested = set()
        if self.status is not None:
            requested.add(WorkflowPatchField.STATUS)
        if self.current_agent is not None or self.clear_current_agent:
            requested.add(WorkflowPatchField.CURRENT_AGENT)
        if self.next_agent is not None or self.clear_next_agent:
            requested.add(WorkflowPatchField.NEXT_AGENT)
        if self.iteration is not None:
            requested.add(WorkflowPatchField.ITERATION)
        if self.evidence_to_add:
            requested.add(WorkflowPatchField.EVIDENCE_TO_ADD)
        if self.knowledge_candidates_to_add:
            requested.add(WorkflowPatchField.KNOWLEDGE_CANDIDATES_TO_ADD)
        if self.validation_results_to_add:
            requested.add(WorkflowPatchField.VALIDATION_RESULTS_TO_ADD)
        if self.reasoning_trace_ids_to_add:
            requested.add(WorkflowPatchField.REASONING_TRACE_IDS_TO_ADD)
        if self.step_history_to_add:
            requested.add(WorkflowPatchField.STEP_HISTORY_TO_ADD)
        if self.warnings_to_add:
            requested.add(WorkflowPatchField.WARNINGS_TO_ADD)
        if self.errors_to_add:
            requested.add(WorkflowPatchField.ERRORS_TO_ADD)
        if self.termination_reason is not None or self.clear_termination_reason:
            requested.add(WorkflowPatchField.TERMINATION_REASON)
        if self.updated_at is not None:
            requested.add(WorkflowPatchField.UPDATED_AT)
        return frozenset(requested)


class AgentCapabilities(_WorkflowContract):
    """Declares the patch operations allowed for one agent role."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: AgentRole
    allowed_patch_fields: FrozenSet[WorkflowPatchField]


_COMMON_APPEND_FIELDS = frozenset(
    {
        WorkflowPatchField.REASONING_TRACE_IDS_TO_ADD,
        WorkflowPatchField.STEP_HISTORY_TO_ADD,
        WorkflowPatchField.WARNINGS_TO_ADD,
        WorkflowPatchField.ERRORS_TO_ADD,
        WorkflowPatchField.UPDATED_AT,
    }
)


AGENT_UPDATE_POLICY: Mapping[AgentRole, AgentCapabilities] = MappingProxyType(
    {
        AgentRole.SUPERVISOR: AgentCapabilities(
            role=AgentRole.SUPERVISOR,
            allowed_patch_fields={
                WorkflowPatchField.STATUS,
                WorkflowPatchField.CURRENT_AGENT,
                WorkflowPatchField.NEXT_AGENT,
                WorkflowPatchField.ITERATION,
                WorkflowPatchField.TERMINATION_REASON,
                WorkflowPatchField.STEP_HISTORY_TO_ADD,
                WorkflowPatchField.WARNINGS_TO_ADD,
                WorkflowPatchField.ERRORS_TO_ADD,
                WorkflowPatchField.UPDATED_AT,
            },
        ),
        AgentRole.EXPLORER: AgentCapabilities(
            role=AgentRole.EXPLORER,
            allowed_patch_fields=_COMMON_APPEND_FIELDS
            | {WorkflowPatchField.EVIDENCE_TO_ADD},
        ),
        AgentRole.KNOWLEDGE: AgentCapabilities(
            role=AgentRole.KNOWLEDGE,
            allowed_patch_fields=_COMMON_APPEND_FIELDS
            | {WorkflowPatchField.KNOWLEDGE_CANDIDATES_TO_ADD},
        ),
        AgentRole.VALIDATOR: AgentCapabilities(
            role=AgentRole.VALIDATOR,
            allowed_patch_fields=_COMMON_APPEND_FIELDS
            | {WorkflowPatchField.VALIDATION_RESULTS_TO_ADD},
        ),
    }
)


def validate_patch_for_role(
    role: AgentRole, patch: WorkflowStatePatch
) -> WorkflowStatePatch:
    """Reject patch operations outside the declared role capability policy."""

    requested = patch.requested_fields()
    allowed = AGENT_UPDATE_POLICY[role].allowed_patch_fields
    disallowed = sorted(field.value for field in requested - allowed)
    if disallowed:
        raise AgentContractValidationError(
            f"Agent role {role.value!r} cannot request patch fields: "
            + ", ".join(disallowed)
        )
    return patch
