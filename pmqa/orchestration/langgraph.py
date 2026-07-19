"""Thin LangGraph adapter around PMQA policy, runtime, and reducer contracts."""

from types import MappingProxyType
from typing import Mapping, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from pmqa.runtime import WorkflowRuntime
from pmqa.supervisor import SupervisorAction, decide_next_action
from pmqa.workflow import (
    AgentRole,
    PMQAAgent,
    ToolRegistry,
    WorkflowState,
    WorkflowStatePatch,
    apply_patch,
)


class PMQAGraphAssemblyError(ValueError):
    """Reports invalid dependencies or routing metadata during graph assembly."""


class PMQAGraphState(TypedDict):
    """Carries domain state and minimal transient supervisor routing metadata."""

    workflow_state: WorkflowState
    next_action: Optional[SupervisorAction]
    selected_agent: Optional[AgentRole]


_EXECUTABLE_ROLES = frozenset(
    {
        AgentRole.EXPLORER,
        AgentRole.KNOWLEDGE,
        AgentRole.VALIDATOR,
    }
)
_DEFAULT_RECURSION_LIMIT = 64


def build_pmqa_graph(
    *,
    agents: Mapping[AgentRole, PMQAAgent],
    tool_registry: ToolRegistry,
):
    """Compile an invokable synchronous PMQA graph with explicit dependencies."""

    registered_agents = _validate_agents(agents)
    runtime = WorkflowRuntime(tool_registry)

    def supervisor_node(graph_state: PMQAGraphState) -> PMQAGraphState:
        workflow_state = graph_state["workflow_state"]
        decision = decide_next_action(workflow_state)
        return {
            "workflow_state": apply_patch(workflow_state, decision.patch),
            "next_action": decision.action,
            "selected_agent": decision.selected_agent,
        }

    def execute_selected_agent(graph_state: PMQAGraphState) -> PMQAGraphState:
        workflow_state = graph_state["workflow_state"]
        selected_agent = graph_state["selected_agent"]
        if selected_agent not in _EXECUTABLE_ROLES:
            raise PMQAGraphAssemblyError(
                "Agent execution requires a supported selected_agent"
            )
        iteration = (
            workflow_state.iteration + 1
            if selected_agent is AgentRole.EXPLORER
            else None
        )
        execution_state = apply_patch(
            workflow_state,
            WorkflowStatePatch(
                current_agent=selected_agent,
                clear_next_agent=True,
                iteration=iteration,
            ),
        )
        result_state = runtime.execute_agent(
            execution_state,
            registered_agents[selected_agent],
            invocation_id=(
                f"{execution_state.workflow_id}:"
                f"{execution_state.iteration}:{selected_agent.value}"
            ),
            requested_at=execution_state.updated_at,
        )
        completed_state = apply_patch(
            result_state,
            WorkflowStatePatch(clear_current_agent=True),
        )
        return {
            "workflow_state": completed_state,
            "next_action": None,
            "selected_agent": None,
        }

    def route_after_supervisor(graph_state: PMQAGraphState) -> str:
        action = graph_state["next_action"]
        selected_agent = graph_state["selected_agent"]
        if action is SupervisorAction.EXECUTE_AGENT:
            if selected_agent not in _EXECUTABLE_ROLES:
                raise PMQAGraphAssemblyError(
                    "Execute-agent routing requires a supported selected_agent"
                )
            return "execute"
        if action in {
            SupervisorAction.COMPLETE_WORKFLOW,
            SupervisorAction.FAIL_WORKFLOW,
            SupervisorAction.TERMINATE_WORKFLOW,
        }:
            if selected_agent is not None:
                raise PMQAGraphAssemblyError(
                    "Terminal routing must not select an agent"
                )
            return "end"
        raise PMQAGraphAssemblyError("Supervisor routing metadata is incomplete")

    graph = StateGraph(PMQAGraphState)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("execute_selected_agent", execute_selected_agent)
    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "execute": "execute_selected_agent",
            "end": END,
        },
    )
    graph.add_edge("execute_selected_agent", "supervisor")
    return graph.compile()


def run_pmqa_workflow(
    workflow_state: WorkflowState,
    *,
    agents: Mapping[AgentRole, PMQAAgent],
    tool_registry: ToolRegistry,
    recursion_limit: int = _DEFAULT_RECURSION_LIMIT,
) -> WorkflowState:
    """Run one synchronous workflow with an explicit graph safety limit."""

    graph = build_pmqa_graph(agents=agents, tool_registry=tool_registry)
    result = graph.invoke(
        {
            "workflow_state": workflow_state,
            "next_action": None,
            "selected_agent": None,
        },
        config={"recursion_limit": recursion_limit},
    )
    return result["workflow_state"]


def _validate_agents(
    agents: Mapping[AgentRole, PMQAAgent],
) -> Mapping[AgentRole, PMQAAgent]:
    invalid_keys = tuple(
        repr(role) for role in agents if not isinstance(role, AgentRole)
    )
    if invalid_keys:
        raise PMQAGraphAssemblyError(
            "Agent registration keys must be AgentRole values: "
            + ", ".join(invalid_keys)
        )
    registered_roles = frozenset(agents)
    missing = sorted(role.value for role in _EXECUTABLE_ROLES - registered_roles)
    if missing:
        raise PMQAGraphAssemblyError(
            "Missing required agent registrations: " + ", ".join(missing)
        )
    unsupported = sorted(role.value for role in registered_roles - _EXECUTABLE_ROLES)
    if unsupported:
        raise PMQAGraphAssemblyError(
            "Unsupported agent registrations: " + ", ".join(unsupported)
        )
    copied = {}
    for role in sorted(registered_roles, key=lambda item: item.value):
        agent = agents[role]
        if agent.role is not role:
            raise PMQAGraphAssemblyError(
                f"Agent registration key {role.value!r} does not match agent role"
            )
        copied[role] = agent
    return MappingProxyType(copied)
