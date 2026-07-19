"""Tests for deterministic single-agent runtime coordination."""

import subprocess
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest
from pydantic import ValidationError

from pmqa.runtime import WorkflowRuntime
from pmqa.workflow import (
    AGENT_UPDATE_POLICY,
    AgentCapabilities,
    AgentContractValidationError,
    AgentExecutionStatus,
    AgentRequest,
    AgentResult,
    AgentRole,
    ToolCategory,
    ToolContractValidationError,
    ToolExecutionStatus,
    ToolMetadata,
    ToolRegistry,
    ToolRequest,
    ToolResult,
    WorkflowReducerError,
    WorkflowState,
    WorkflowStatePatch,
)


def test_runtime_executes_one_agent_tool_and_reducer_pipeline() -> None:
    tool = _FakeNavigateTool()
    runtime = WorkflowRuntime(ToolRegistry([tool]))
    agent = _FakeAgent(runtime)
    state = _state()
    original_json = state.model_dump_json()

    reduced = runtime.execute_agent(
        state,
        agent,
        invocation_id="invocation-1",
        requested_at=_timestamp(),
    )

    assert agent.invocation_count == 1
    assert tool.invocation_count == 1
    assert reduced.evidence == (
        {"evidence_id": "page-1", "url_ref": "product.start_url"},
    )
    assert reduced is not state
    assert state.model_dump_json() == original_json
    assert agent.last_request is not None
    assert agent.last_request.state is state


def test_tool_dispatch_rejects_unknown_identifier() -> None:
    runtime = WorkflowRuntime(ToolRegistry())
    request = _tool_request(tool_id="utility.missing", category=ToolCategory.UTILITY)

    with pytest.raises(ToolContractValidationError, match="not registered"):
        runtime.invoke_tool(request)


def test_tool_dispatch_rejects_metadata_category_mismatch() -> None:
    tool = _FakeNavigateTool()
    runtime = WorkflowRuntime(ToolRegistry([tool]))
    values = _tool_request().model_dump(mode="python")
    values["category"] = ToolCategory.REASONING
    mismatched = ToolRequest.model_construct(**values)

    with pytest.raises(ToolContractValidationError, match="category"):
        runtime.invoke_tool(mismatched)
    assert tool.invocation_count == 0


def test_runtime_rejects_invalid_tool_result_correlation() -> None:
    tool = _FakeNavigateTool(result_tool_id="playwright.click")
    runtime = WorkflowRuntime(ToolRegistry([tool]))
    agent = _FakeAgent(runtime)

    with pytest.raises(ToolContractValidationError, match="tool_id"):
        runtime.execute_agent(
            _state(),
            agent,
            invocation_id="invocation-1",
            requested_at=_timestamp(),
        )


def test_runtime_revalidates_tool_result_schema() -> None:
    tool = _FakeNavigateTool(construct_invalid_result=True)
    runtime = WorkflowRuntime(ToolRegistry([tool]))

    with pytest.raises(ValidationError, match="status"):
        runtime.invoke_tool(_tool_request())


def test_runtime_rejects_agent_result_workflow_mismatch() -> None:
    runtime = WorkflowRuntime(ToolRegistry([_FakeNavigateTool()]))
    agent = _FakeAgent(runtime, result_workflow_id="workflow-2")

    with pytest.raises(AgentContractValidationError, match="workflow_id"):
        runtime.execute_agent(
            _state(),
            agent,
            invocation_id="invocation-1",
            requested_at=_timestamp(),
        )


def test_runtime_revalidates_agent_result_capabilities() -> None:
    runtime = WorkflowRuntime(ToolRegistry())
    agent = _FakeAgent(
        runtime,
        patch=WorkflowStatePatch(next_agent=AgentRole.VALIDATOR),
        construct_invalid_result=True,
        use_tool=False,
    )

    with pytest.raises(ValidationError, match="next_agent"):
        runtime.execute_agent(
            _state(),
            agent,
            invocation_id="invocation-1",
            requested_at=_timestamp(),
        )


def test_runtime_rejects_agent_capability_role_mismatch() -> None:
    runtime = WorkflowRuntime(ToolRegistry())
    agent = _FakeAgent(
        runtime,
        capabilities=AGENT_UPDATE_POLICY[AgentRole.VALIDATOR],
        use_tool=False,
    )

    with pytest.raises(AgentContractValidationError, match="capability role"):
        runtime.execute_agent(
            _state(),
            agent,
            invocation_id="invocation-1",
            requested_at=_timestamp(),
        )
    assert agent.invocation_count == 0


def test_runtime_rejects_patch_beyond_declared_agent_capabilities() -> None:
    runtime = WorkflowRuntime(ToolRegistry([_FakeNavigateTool()]))
    capabilities = AgentCapabilities(
        role=AgentRole.EXPLORER,
        allowed_patch_fields=frozenset(),
    )
    agent = _FakeAgent(runtime, capabilities=capabilities)

    with pytest.raises(AgentContractValidationError, match="evidence_to_add"):
        runtime.execute_agent(
            _state(),
            agent,
            invocation_id="invocation-1",
            requested_at=_timestamp(),
        )


def test_runtime_propagates_reducer_failures() -> None:
    runtime = WorkflowRuntime(ToolRegistry())
    agent = _FakeAgent(
        runtime,
        role=AgentRole.SUPERVISOR,
        patch=WorkflowStatePatch(iteration=0),
        use_tool=False,
    )

    with pytest.raises(WorkflowReducerError, match="decrease"):
        runtime.execute_agent(
            _state(iteration=1),
            agent,
            invocation_id="invocation-1",
            requested_at=_timestamp(),
        )


def test_runtime_rejects_agent_identity_and_timestamp_mismatches() -> None:
    runtime = WorkflowRuntime(ToolRegistry())
    invocation_agent = _FakeAgent(
        runtime,
        result_invocation_id="invocation-2",
        use_tool=False,
    )
    with pytest.raises(AgentContractValidationError, match="invocation_id"):
        runtime.execute_agent(
            _state(),
            invocation_agent,
            invocation_id="invocation-1",
            requested_at=_timestamp(),
        )

    early_agent = _FakeAgent(
        runtime,
        completed_at=_timestamp() - timedelta(seconds=1),
        use_tool=False,
    )
    with pytest.raises(AgentContractValidationError, match="precede"):
        runtime.execute_agent(
            _state(),
            early_agent,
            invocation_id="invocation-1",
            requested_at=_timestamp(),
        )


def test_runtime_is_deterministic_for_identical_inputs() -> None:
    state = _state()
    tool = _FakeNavigateTool()
    runtime = WorkflowRuntime(ToolRegistry([tool]))
    agent = _FakeAgent(runtime)

    first = runtime.execute_agent(
        state,
        agent,
        invocation_id="invocation-1",
        requested_at=_timestamp(),
    )
    second = runtime.execute_agent(
        state,
        agent,
        invocation_id="invocation-1",
        requested_at=_timestamp(),
    )

    assert first == second
    assert first.model_dump_json() == second.model_dump_json()


def test_runtime_import_has_no_orchestration_or_provider_dependencies() -> None:
    script = """
import sys
from pmqa.runtime import WorkflowRuntime
for prohibited in ("langgraph", "playwright", "pmqa.providers"):
    assert prohibited not in sys.modules, (prohibited, sorted(sys.modules))
assert WorkflowRuntime is not None
"""

    subprocess.run([sys.executable, "-c", script], check=True)


class _FakeNavigateTool:
    def __init__(
        self,
        *,
        result_tool_id: str = "playwright.navigate",
        construct_invalid_result: bool = False,
    ) -> None:
        self._metadata = ToolMetadata(
            tool_id="playwright.navigate",
            category=ToolCategory.PLAYWRIGHT,
            description="Return deterministic page evidence",
            input_schema_version="1",
            output_schema_version="1",
        )
        self.result_tool_id = result_tool_id
        self.construct_invalid_result = construct_invalid_result
        self.invocation_count = 0

    @property
    def metadata(self) -> ToolMetadata:
        return self._metadata

    def invoke(self, request: ToolRequest) -> ToolResult:
        self.invocation_count += 1
        values = {
            "tool_id": self.result_tool_id,
            "workflow_id": request.workflow_id,
            "invocation_id": request.invocation_id,
            "completed_at": request.requested_at,
            "status": ToolExecutionStatus.SUCCEEDED,
            "output": {
                "evidence_id": "page-1",
                "url_ref": request.input["url_ref"],
            },
            "summary": {"operation": "navigate"},
        }
        if self.construct_invalid_result:
            values.pop("status")
            return ToolResult.model_construct(**values)
        return ToolResult(**values)


class _FakeAgent:
    def __init__(
        self,
        runtime: WorkflowRuntime,
        *,
        role: AgentRole = AgentRole.EXPLORER,
        capabilities: Optional[AgentCapabilities] = None,
        patch: Optional[WorkflowStatePatch] = None,
        result_workflow_id: Optional[str] = None,
        result_invocation_id: Optional[str] = None,
        completed_at: Optional[datetime] = None,
        construct_invalid_result: bool = False,
        use_tool: bool = True,
    ) -> None:
        self.runtime = runtime
        self._role = role
        self._capabilities = capabilities or AGENT_UPDATE_POLICY[role]
        self.patch = patch
        self.result_workflow_id = result_workflow_id
        self.result_invocation_id = result_invocation_id
        self.completed_at = completed_at
        self.construct_invalid_result = construct_invalid_result
        self.use_tool = use_tool
        self.invocation_count = 0
        self.last_request: Optional[AgentRequest] = None

    @property
    def role(self) -> AgentRole:
        return self._role

    @property
    def capabilities(self) -> AgentCapabilities:
        return self._capabilities

    def invoke(self, request: AgentRequest) -> AgentResult:
        self.invocation_count += 1
        self.last_request = request
        evidence = ()
        if self.use_tool:
            tool_result = self.runtime.invoke_tool(
                _tool_request(
                    workflow_id=request.workflow_id,
                    invocation_id=request.invocation_id,
                    requested_by_agent=request.agent,
                    requested_at=request.requested_at,
                )
            )
            evidence = (dict(tool_result.output),)
        patch = self.patch or WorkflowStatePatch(evidence_to_add=evidence)
        values = {
            "workflow_id": self.result_workflow_id or request.workflow_id,
            "agent": self.role,
            "invocation_id": self.result_invocation_id or request.invocation_id,
            "patch": patch,
            "completed_at": self.completed_at or request.requested_at,
            "outcome_status": AgentExecutionStatus.SUCCEEDED,
            "summary": {"tool_count": 1 if self.use_tool else 0},
        }
        if self.construct_invalid_result:
            return AgentResult.model_construct(**values)
        return AgentResult(**values)


def _tool_request(**updates) -> ToolRequest:
    values = {
        "tool_id": "playwright.navigate",
        "category": ToolCategory.PLAYWRIGHT,
        "workflow_id": "workflow-1",
        "invocation_id": "invocation-1",
        "requested_by_agent": AgentRole.EXPLORER,
        "requested_at": _timestamp(),
        "input": {"url_ref": "product.start_url"},
    }
    values.update(updates)
    return ToolRequest(**values)


def _state(**updates) -> WorkflowState:
    values = {
        "workflow_id": "workflow-1",
        "workflow_type": "single-agent",
        "product_id": "demo",
        "product_version": "1",
        "goal": "Collect one page evidence item",
        "iteration": 0,
        "max_iterations": 3,
        "created_at": _timestamp(),
        "updated_at": _timestamp(),
    }
    values.update(updates)
    return WorkflowState(**values)


def _timestamp() -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc)
