"""Runtime composition for exactly one agent invocation."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from pmqa.workflow.agents import (
    AgentRequest,
    AgentResult,
    PMQAAgent,
    validate_agent_result,
)
from pmqa.workflow.errors import (
    AgentContractValidationError,
    ToolContractValidationError,
)
from pmqa.workflow.models import WorkflowState
from pmqa.workflow.reducer import apply_patch
from pmqa.workflow.tools import (
    ToolRegistry,
    ToolRequest,
    ToolResult,
    validate_tool_result,
)


@dataclass(frozen=True)
class WorkflowRuntime:
    """Coordinates one agent and deterministic registry-backed tool dispatch."""

    registry: ToolRegistry

    def invoke_tool(self, request: ToolRequest) -> ToolResult:
        """Dispatch one tool request through the registry and validate its result."""

        tool = self.registry.get(request.tool_id)
        if tool.metadata.category is not request.category:
            raise ToolContractValidationError(
                "Tool request category must match registered tool metadata"
            )
        result = _revalidate(ToolResult, tool.invoke(request))
        return validate_tool_result(request, result)

    def execute_agent(
        self,
        state: WorkflowState,
        agent: PMQAAgent,
        *,
        invocation_id: str,
        requested_at: datetime,
    ) -> WorkflowState:
        """Execute exactly one agent and reduce its validated patch into new state."""

        if agent.capabilities.role is not agent.role:
            raise AgentContractValidationError(
                "Agent capability role must match the agent role"
            )
        request = AgentRequest(
            workflow_id=state.workflow_id,
            agent=agent.role,
            state=state,
            invocation_id=invocation_id,
            requested_at=requested_at,
        )
        result = _revalidate(AgentResult, agent.invoke(request))
        validate_agent_result(request, result)
        disallowed = result.patch.requested_fields() - (
            agent.capabilities.allowed_patch_fields
        )
        if disallowed:
            fields = ", ".join(sorted(field.value for field in disallowed))
            raise AgentContractValidationError(
                f"Agent result exceeds declared capabilities: {fields}"
            )
        return apply_patch(state, result.patch)


def _revalidate(model_type, value: Any):
    payload = value.model_dump(mode="python") if isinstance(value, BaseModel) else value
    return model_type.model_validate(payload)
