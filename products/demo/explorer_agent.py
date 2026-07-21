"""Product-owned Explorer agent for bounded SauceDemo evidence collection."""

import hashlib
from datetime import datetime
from typing import Callable, Optional

from pydantic import ValidationError

from pmqa.models import ExplorationEvidence
from pmqa.workflow import (
    AGENT_UPDATE_POLICY,
    AgentCapabilities,
    AgentExecutionStatus,
    AgentInvocation,
    AgentInvocationStatus,
    AgentRequest,
    AgentResult,
    AgentRole,
    ToolCategory,
    ToolExecutionStatus,
    ToolRequest,
    ToolResult,
    WorkflowStatePatch,
    validate_tool_result,
)
from products.demo.exploration_contracts import (
    SAUCEDEMO_EXPLORATION_ACTIONS,
    SAUCEDEMO_EXPLORATION_TOOL_ID,
)


ToolDispatcher = Callable[[ToolRequest], ToolResult]
_FAILURE_CODE = "explorer_tool_failed"


class SauceDemoExplorerAgent:
    """Dispatch one bounded Tool request and append validated evidence by patch."""

    def __init__(self, tool_dispatcher: ToolDispatcher) -> None:
        self._tool_dispatcher = tool_dispatcher

    @property
    def role(self) -> AgentRole:
        """Declare the canonical Explorer role."""

        return AgentRole.EXPLORER

    @property
    def capabilities(self) -> AgentCapabilities:
        """Return the canonical Explorer patch capabilities."""

        return AGENT_UPDATE_POLICY[AgentRole.EXPLORER]

    def invoke(self, request: AgentRequest) -> AgentResult:
        """Collect one evidence batch without mutating workflow state."""

        tool_request = ToolRequest(
            tool_id=SAUCEDEMO_EXPLORATION_TOOL_ID,
            category=ToolCategory.PLAYWRIGHT,
            workflow_id=request.workflow_id,
            invocation_id=_tool_invocation_id(request.invocation_id),
            requested_by_agent=AgentRole.EXPLORER,
            requested_at=request.requested_at,
            input={
                "product_id": request.state.product_id,
                "actions": SAUCEDEMO_EXPLORATION_ACTIONS,
            },
        )
        tool_result: Optional[ToolResult] = None
        try:
            dispatched = self._tool_dispatcher(tool_request)
        except Exception:
            return self._failure(request, tool_result)
        try:
            if not isinstance(dispatched, ToolResult):
                raise TypeError("tool dispatcher returned an invalid result")
            tool_result = ToolResult.model_validate(
                dispatched.model_dump(mode="python")
            )
            validate_tool_result(tool_request, tool_result)
        except (AttributeError, TypeError, ValueError):
            return self._failure(request, tool_result)

        if tool_result.status is not ToolExecutionStatus.SUCCEEDED:
            return self._failure(request, tool_result)
        if set(tool_result.output) != {"evidence"}:
            return self._failure(request, tool_result)
        try:
            evidence = ExplorationEvidence.from_workflow_payload(
                tool_result.output["evidence"]
            )
        except (TypeError, ValidationError):
            return self._failure(request, tool_result)
        if not _evidence_is_correlated(evidence, request, tool_request):
            return self._failure(request, tool_result)

        completed_at = tool_result.completed_at
        payload = evidence.to_workflow_payload()
        history = AgentInvocation(
            agent=self.role,
            started_at=request.requested_at,
            completed_at=completed_at,
            status=AgentInvocationStatus.COMPLETED,
            input_summary={
                "tool_id": tool_request.tool_id,
                "action_count": len(SAUCEDEMO_EXPLORATION_ACTIONS),
            },
            output_summary=_safe_output_summary(tool_result, evidence),
        )
        summary = _safe_output_summary(tool_result, evidence)
        return AgentResult(
            workflow_id=request.workflow_id,
            agent=self.role,
            invocation_id=request.invocation_id,
            patch=WorkflowStatePatch(
                evidence_to_add=(payload,),
                step_history_to_add=(history,),
                updated_at=completed_at,
            ),
            completed_at=completed_at,
            outcome_status=AgentExecutionStatus.SUCCEEDED,
            summary=summary,
        )

    def _failure(
        self,
        request: AgentRequest,
        tool_result: Optional[ToolResult],
    ) -> AgentResult:
        completed_at = _failure_completion_time(request, tool_result)
        tool_status = (
            tool_result.status.value
            if tool_result is not None
            else "dispatch_failed"
        )
        history = AgentInvocation(
            agent=self.role,
            started_at=request.requested_at,
            completed_at=completed_at,
            status=AgentInvocationStatus.FAILED,
            input_summary={
                "tool_id": SAUCEDEMO_EXPLORATION_TOOL_ID,
                "action_count": len(SAUCEDEMO_EXPLORATION_ACTIONS),
            },
            output_summary={
                "tool_status": tool_status,
                "error_code": _FAILURE_CODE,
            },
        )
        return AgentResult(
            workflow_id=request.workflow_id,
            agent=self.role,
            invocation_id=request.invocation_id,
            patch=WorkflowStatePatch(
                step_history_to_add=(history,),
                errors_to_add=(_FAILURE_CODE,),
                updated_at=completed_at,
            ),
            completed_at=completed_at,
            outcome_status=AgentExecutionStatus.FAILED,
            summary={
                "tool_id": SAUCEDEMO_EXPLORATION_TOOL_ID,
                "tool_status": tool_status,
                "error_code": _FAILURE_CODE,
            },
            errors=(_FAILURE_CODE,),
        )


def _tool_invocation_id(agent_invocation_id: str) -> str:
    correlation = (
        agent_invocation_id + "\0" + SAUCEDEMO_EXPLORATION_TOOL_ID
    ).encode("utf-8")
    return "tool.saucedemo." + hashlib.sha256(correlation).hexdigest()[:40]


def _evidence_is_correlated(
    evidence: ExplorationEvidence,
    request: AgentRequest,
    tool_request: ToolRequest,
) -> bool:
    return (
        evidence.workflow_id == request.workflow_id
        and evidence.product_id == request.state.product_id
        and evidence.source.tool_id == SAUCEDEMO_EXPLORATION_TOOL_ID
        and evidence.source.capture_id == tool_request.invocation_id
    )


def _safe_output_summary(
    tool_result: ToolResult,
    evidence: ExplorationEvidence,
):
    return {
        "tool_id": SAUCEDEMO_EXPLORATION_TOOL_ID,
        "tool_status": tool_result.status.value,
        "evidence_id": evidence.evidence_id,
        "page_count": len(evidence.pages),
        "element_count": len(evidence.elements),
        "locator_candidate_count": len(evidence.locator_candidates),
        "interaction_count": len(evidence.interactions),
    }


def _failure_completion_time(
    request: AgentRequest,
    tool_result: Optional[ToolResult],
) -> datetime:
    if tool_result is None or tool_result.completed_at < request.requested_at:
        return request.requested_at
    return tool_result.completed_at
