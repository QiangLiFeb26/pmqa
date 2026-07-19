"""Integration tests for the thin LangGraph PMQA orchestration adapter."""

import subprocess
import sys
from datetime import datetime, timezone
from typing import Callable, Mapping, Optional, Tuple

import pytest

from pmqa.orchestration import (
    PMQAGraphAssemblyError,
    build_pmqa_graph,
    run_pmqa_workflow,
)
from pmqa.runtime import WorkflowRuntime
from pmqa.supervisor import SupervisorPolicyError
from pmqa.workflow import (
    AGENT_UPDATE_POLICY,
    AgentCapabilities,
    AgentExecutionStatus,
    AgentInvocation,
    AgentInvocationStatus,
    AgentRequest,
    AgentResult,
    AgentRole,
    TerminationReason,
    ToolCategory,
    ToolContractValidationError,
    ToolExecutionStatus,
    ToolMetadata,
    ToolRegistry,
    ToolRequest,
    ToolResult,
    WorkflowState,
    WorkflowStatePatch,
    WorkflowStatus,
)


def test_graph_compiles_with_minimal_topology() -> None:
    agents, registry = _dependencies()

    graph = build_pmqa_graph(agents=agents, tool_registry=registry)
    node_names = set(graph.get_graph().nodes)

    assert "supervisor" in node_names
    assert "execute_selected_agent" in node_names


def test_happy_path_completes_through_all_agents() -> None:
    agents, registry = _dependencies()
    state = _state(max_iterations=2)
    original_json = state.model_dump_json()

    final = run_pmqa_workflow(
        state,
        agents=agents,
        tool_registry=registry,
        recursion_limit=32,
    )

    assert final.status is WorkflowStatus.COMPLETED
    assert final.termination_reason is TerminationReason.GOAL_COMPLETED
    assert final.current_agent is None
    assert final.next_agent is None
    assert [item["evidence_id"] for item in final.evidence] == ["evidence-1"]
    assert [item["knowledge_id"] for item in final.knowledge_candidates] == [
        "knowledge-1"
    ]
    assert final.validation_results == ({"status": "passed"},)
    assert [step.agent for step in final.step_history] == [
        AgentRole.EXPLORER,
        AgentRole.KNOWLEDGE,
        AgentRole.VALIDATOR,
    ]
    assert {role: agent.invocation_count for role, agent in agents.items()} == {
        AgentRole.EXPLORER: 1,
        AgentRole.KNOWLEDGE: 1,
        AgentRole.VALIDATOR: 1,
    }
    assert final.iteration == 1
    assert state.model_dump_json() == original_json


def test_failed_validation_recovery_completes_second_cycle() -> None:
    agents, registry = _dependencies(validation_outcomes=("failed", "passed"))

    final = run_pmqa_workflow(
        _state(max_iterations=3),
        agents=agents,
        tool_registry=registry,
        recursion_limit=48,
    )

    assert final.status is WorkflowStatus.COMPLETED
    assert final.iteration == 2
    assert [item["evidence_id"] for item in final.evidence] == [
        "evidence-1",
        "evidence-2",
    ]
    assert [item["knowledge_id"] for item in final.knowledge_candidates] == [
        "knowledge-1",
        "knowledge-2",
    ]
    assert final.validation_results == (
        {"status": "failed"},
        {"status": "passed"},
    )
    assert [step.agent for step in final.step_history] == [
        AgentRole.EXPLORER,
        AgentRole.KNOWLEDGE,
        AgentRole.VALIDATOR,
        AgentRole.EXPLORER,
        AgentRole.KNOWLEDGE,
        AgentRole.VALIDATOR,
    ]
    assert all(agent.invocation_count == 2 for agent in agents.values())


def test_repeated_failure_terminates_at_domain_iteration_limit() -> None:
    agents, registry = _dependencies(validation_outcomes=("failed",))

    final = run_pmqa_workflow(
        _state(max_iterations=2),
        agents=agents,
        tool_registry=registry,
        recursion_limit=48,
    )

    assert final.status is WorkflowStatus.TERMINATED
    assert final.termination_reason is TerminationReason.MAX_ITERATIONS
    assert final.iteration == 2
    assert agents[AgentRole.EXPLORER].invocation_count == 2
    assert agents[AgentRole.KNOWLEDGE].invocation_count == 1
    assert agents[AgentRole.VALIDATOR].invocation_count == 1


def test_agent_appended_error_causes_supervisor_failure() -> None:
    agents, registry = _dependencies(fatal_role=AgentRole.EXPLORER)

    final = run_pmqa_workflow(
        _state(max_iterations=2),
        agents=agents,
        tool_registry=registry,
        recursion_limit=16,
    )

    assert final.status is WorkflowStatus.FAILED
    assert final.termination_reason is TerminationReason.ERROR
    assert final.errors == ("explorer failed",)
    assert agents[AgentRole.EXPLORER].invocation_count == 1
    assert agents[AgentRole.KNOWLEDGE].invocation_count == 0
    assert agents[AgentRole.VALIDATOR].invocation_count == 0


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        (WorkflowStatus.COMPLETED, TerminationReason.GOAL_COMPLETED),
        (WorkflowStatus.FAILED, TerminationReason.ERROR),
        (WorkflowStatus.TERMINATED, TerminationReason.MAX_ITERATIONS),
    ],
)
def test_already_terminal_input_is_idempotent(
    status: WorkflowStatus,
    reason: TerminationReason,
) -> None:
    agents, registry = _dependencies()
    state = _state(status=status, termination_reason=reason)

    final = run_pmqa_workflow(
        state,
        agents=agents,
        tool_registry=registry,
        recursion_limit=4,
    )

    assert final == state
    assert final is not state
    assert all(agent.invocation_count == 0 for agent in agents.values())


@pytest.mark.parametrize(
    "missing_role",
    [AgentRole.EXPLORER, AgentRole.KNOWLEDGE, AgentRole.VALIDATOR],
)
def test_missing_agent_registration_fails_during_assembly(
    missing_role: AgentRole,
) -> None:
    agents, registry = _dependencies()
    incomplete = {
        role: agent
        for role, agent in agents.items()
        if role is not missing_role
    }

    with pytest.raises(PMQAGraphAssemblyError, match=missing_role.value):
        build_pmqa_graph(agents=incomplete, tool_registry=registry)


def test_unsupported_and_mismatched_agent_registration_is_rejected() -> None:
    agents, registry = _dependencies()
    with_supervisor = {**agents, AgentRole.SUPERVISOR: agents[AgentRole.EXPLORER]}
    with pytest.raises(PMQAGraphAssemblyError, match="Unsupported"):
        build_pmqa_graph(agents=with_supervisor, tool_registry=registry)

    mismatched = dict(agents)
    mismatched[AgentRole.EXPLORER] = agents[AgentRole.KNOWLEDGE]
    with pytest.raises(PMQAGraphAssemblyError, match="does not match"):
        build_pmqa_graph(agents=mismatched, tool_registry=registry)

    invalid_key = {**agents, "invalid": agents[AgentRole.EXPLORER]}
    with pytest.raises(PMQAGraphAssemblyError, match="AgentRole"):
        build_pmqa_graph(agents=invalid_key, tool_registry=registry)


def test_supervisor_policy_error_propagates_from_graph() -> None:
    agents, registry = _dependencies()
    inconsistent = _state(
        status=WorkflowStatus.RUNNING,
        termination_reason=TerminationReason.ERROR,
    )

    with pytest.raises(SupervisorPolicyError, match="termination_reason"):
        run_pmqa_workflow(
            inconsistent,
            agents=agents,
            tool_registry=registry,
            recursion_limit=8,
        )


def test_runtime_tool_error_propagates_from_graph() -> None:
    agents, registry = _dependencies(invalid_tool_result=True)

    with pytest.raises(ToolContractValidationError, match="workflow_id"):
        run_pmqa_workflow(
            _state(max_iterations=2),
            agents=agents,
            tool_registry=registry,
            recursion_limit=8,
        )


def test_independently_assembled_graphs_are_deterministic() -> None:
    first_agents, first_registry = _dependencies(
        validation_outcomes=("failed", "passed")
    )
    second_agents, second_registry = _dependencies(
        validation_outcomes=("failed", "passed")
    )
    initial = _state(max_iterations=3)

    first = run_pmqa_workflow(
        initial,
        agents=first_agents,
        tool_registry=first_registry,
        recursion_limit=48,
    )
    second = run_pmqa_workflow(
        initial,
        agents=second_agents,
        tool_registry=second_registry,
        recursion_limit=48,
    )

    assert first == second
    assert first.model_dump_json() == second.model_dump_json()


def test_core_imports_do_not_load_langgraph() -> None:
    for module_name in ("pmqa.workflow", "pmqa.runtime", "pmqa.supervisor"):
        script = f"""
import sys
import {module_name}
assert not any(
    name == "langgraph" or name.startswith("langgraph.")
    for name in sys.modules
), sorted(sys.modules)
"""
        subprocess.run([sys.executable, "-c", script], check=True)


def test_graph_state_does_not_serialize_runtime_dependencies() -> None:
    agents, registry = _dependencies()

    final = run_pmqa_workflow(
        _state(max_iterations=2),
        agents=agents,
        tool_registry=registry,
        recursion_limit=32,
    )
    payload = final.model_dump_json()

    for forbidden in ("_FakeAgent", "_FakeTool", "ToolRegistry", "langgraph"):
        assert forbidden not in payload
    assert "registry" not in WorkflowState.model_fields
    assert "agents" not in WorkflowState.model_fields


class _FakeTool:
    def __init__(self, *, invalid_result: bool = False) -> None:
        self._metadata = ToolMetadata(
            tool_id="utility.emit",
            category=ToolCategory.UTILITY,
            description="Return deterministic fake execution evidence",
            input_schema_version="1",
            output_schema_version="1",
        )
        self.invalid_result = invalid_result
        self.invocation_count = 0

    @property
    def metadata(self) -> ToolMetadata:
        return self._metadata

    def invoke(self, request: ToolRequest) -> ToolResult:
        self.invocation_count += 1
        return ToolResult(
            tool_id=request.tool_id,
            workflow_id=(
                "wrong-workflow"
                if self.invalid_result
                else request.workflow_id
            ),
            invocation_id=request.invocation_id,
            completed_at=request.requested_at,
            status=ToolExecutionStatus.SUCCEEDED,
            output=dict(request.input),
            summary={"operation": "emit"},
        )


class _FakeAgent:
    def __init__(
        self,
        role: AgentRole,
        dispatch_tool: Callable[[ToolRequest], ToolResult],
        *,
        validation_outcomes: Tuple[str, ...] = ("passed",),
        fatal: bool = False,
    ) -> None:
        self._role = role
        self._dispatch_tool = dispatch_tool
        self.validation_outcomes = validation_outcomes
        self.fatal = fatal
        self.invocation_count = 0

    @property
    def role(self) -> AgentRole:
        return self._role

    @property
    def capabilities(self) -> AgentCapabilities:
        return AGENT_UPDATE_POLICY[self.role]

    def invoke(self, request: AgentRequest) -> AgentResult:
        self.invocation_count += 1
        call_number = self.invocation_count
        tool_result = self._dispatch_tool(
            ToolRequest(
                tool_id="utility.emit",
                category=ToolCategory.UTILITY,
                workflow_id=request.workflow_id,
                invocation_id=request.invocation_id,
                requested_by_agent=request.agent,
                requested_at=request.requested_at,
                input={"role": self.role.value, "call": call_number},
            )
        )
        invocation = AgentInvocation(
            agent=self.role,
            started_at=request.requested_at,
            completed_at=request.requested_at,
            status=AgentInvocationStatus.COMPLETED,
        )
        patch_values = {"step_history_to_add": (invocation,)}
        if self.fatal:
            patch_values["errors_to_add"] = (f"{self.role.value} failed",)
        elif self.role is AgentRole.EXPLORER:
            patch_values["evidence_to_add"] = (
                {"evidence_id": f"evidence-{tool_result.output['call']}"},
            )
        elif self.role is AgentRole.KNOWLEDGE:
            patch_values["knowledge_candidates_to_add"] = (
                {"knowledge_id": f"knowledge-{tool_result.output['call']}"},
            )
        else:
            outcome_index = min(call_number - 1, len(self.validation_outcomes) - 1)
            patch_values["validation_results_to_add"] = (
                {"status": self.validation_outcomes[outcome_index]},
            )
        return AgentResult(
            workflow_id=request.workflow_id,
            agent=self.role,
            invocation_id=request.invocation_id,
            patch=WorkflowStatePatch(**patch_values),
            completed_at=request.requested_at,
            outcome_status=AgentExecutionStatus.SUCCEEDED,
            summary={"tool_id": tool_result.tool_id},
        )


def _dependencies(
    *,
    validation_outcomes: Tuple[str, ...] = ("passed",),
    fatal_role: Optional[AgentRole] = None,
    invalid_tool_result: bool = False,
) -> Tuple[Mapping[AgentRole, _FakeAgent], ToolRegistry]:
    tool = _FakeTool(invalid_result=invalid_tool_result)
    registry = ToolRegistry([tool])
    dispatch_tool = WorkflowRuntime(registry).invoke_tool
    agents = {
        role: _FakeAgent(
            role,
            dispatch_tool,
            validation_outcomes=validation_outcomes,
            fatal=role is fatal_role,
        )
        for role in (
            AgentRole.EXPLORER,
            AgentRole.KNOWLEDGE,
            AgentRole.VALIDATOR,
        )
    }
    return agents, registry


def _state(**updates) -> WorkflowState:
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    values = {
        "workflow_id": "workflow-1",
        "workflow_type": "graph-assembly",
        "product_id": "demo",
        "product_version": "1",
        "goal": "Produce validated knowledge",
        "max_iterations": 2,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    values.update(updates)
    return WorkflowState(**values)
