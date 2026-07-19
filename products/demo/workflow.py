"""Thin product-owned composition for the real SauceDemo PMQA workflow."""

from datetime import datetime
from typing import Callable, Optional

from pmqa.orchestration import run_pmqa_workflow
from pmqa.runtime import WorkflowRuntime
from pmqa.workflow import (
    AgentRole,
    ToolRegistry,
    WorkflowState,
    WorkflowStatus,
)
from products.demo.capture import SauceDemoCaptureRunner
from products.demo.config import DemoConfig
from products.demo.exploration_tool import SauceDemoExplorationTool
from products.demo.explorer_agent import SauceDemoExplorerAgent
from products.demo.knowledge_agent import SauceDemoKnowledgeAgent
from products.demo.validator_agent import SauceDemoValidatorAgent


SAUCEDEMO_WORKFLOW_TYPE = "saucedemo_pmqa"
_DEFAULT_RECURSION_LIMIT = 64


class SauceDemoWorkflowCompositionError(ValueError):
    """Reports invalid product composition inputs before workflow execution."""


def create_saucedemo_workflow_state(
    config: DemoConfig,
    *,
    workflow_id: str,
    product_version: str,
    goal: str,
    max_iterations: int,
    created_at: datetime,
) -> WorkflowState:
    """Create the exact empty initial state for one SauceDemo PMQA run."""

    _validate_config(config)
    _require_identifier(workflow_id, "workflow_id")
    _require_identifier(product_version, "product_version")
    if not isinstance(goal, str) or not goal.strip():
        raise SauceDemoWorkflowCompositionError("goal must be a non-empty string")
    if type(max_iterations) is not int or max_iterations < 1:
        raise SauceDemoWorkflowCompositionError(
            "max_iterations must be a positive integer"
        )
    _require_aware(created_at, "created_at")
    return WorkflowState(
        workflow_id=workflow_id,
        workflow_type=SAUCEDEMO_WORKFLOW_TYPE,
        product_id=config.product_id,
        product_version=product_version,
        goal=goal,
        status=WorkflowStatus.PENDING,
        iteration=0,
        max_iterations=max_iterations,
        created_at=created_at,
        updated_at=created_at,
    )


def run_saucedemo_workflow(
    config: DemoConfig,
    initial_state: WorkflowState,
    *,
    capture_runner: Optional[SauceDemoCaptureRunner] = None,
    clock: Optional[Callable[[], datetime]] = None,
    headless: bool = True,
    recursion_limit: int = _DEFAULT_RECURSION_LIMIT,
) -> WorkflowState:
    """Compose the real Tool and agents and return their terminal graph state."""

    _validate_config(config)
    _validate_initial_state(initial_state, config)
    if type(headless) is not bool:
        raise SauceDemoWorkflowCompositionError("headless must be a boolean")
    if type(recursion_limit) is not int or recursion_limit < 1:
        raise SauceDemoWorkflowCompositionError(
            "recursion_limit must be a positive integer"
        )

    tool = SauceDemoExplorationTool(
        config,
        capture_runner=capture_runner,
        clock=clock,
        headless=headless,
    )
    registry = ToolRegistry((tool,))
    tool_runtime = WorkflowRuntime(registry)
    agents = {
        AgentRole.EXPLORER: SauceDemoExplorerAgent(tool_runtime.invoke_tool),
        AgentRole.KNOWLEDGE: SauceDemoKnowledgeAgent(),
        AgentRole.VALIDATOR: SauceDemoValidatorAgent(),
    }
    return run_pmqa_workflow(
        initial_state,
        agents=agents,
        tool_registry=registry,
        recursion_limit=recursion_limit,
    )


def _validate_initial_state(
    state: WorkflowState, config: DemoConfig
) -> None:
    if not isinstance(state, WorkflowState):
        raise SauceDemoWorkflowCompositionError(
            "initial_state must be a WorkflowState"
        )
    if state.product_id != config.product_id:
        raise SauceDemoWorkflowCompositionError(
            "initial state product does not match DemoConfig"
        )
    if state.workflow_type != SAUCEDEMO_WORKFLOW_TYPE:
        raise SauceDemoWorkflowCompositionError(
            "initial state workflow type is unsupported"
        )
    if state.status is not WorkflowStatus.PENDING:
        raise SauceDemoWorkflowCompositionError(
            "initial state must be pending"
        )
    if state.iteration != 0:
        raise SauceDemoWorkflowCompositionError(
            "initial state iteration must be zero"
        )
    if state.created_at != state.updated_at:
        raise SauceDemoWorkflowCompositionError(
            "initial state timestamps must match"
        )
    if state.current_agent is not None or state.next_agent is not None:
        raise SauceDemoWorkflowCompositionError(
            "initial state must not contain agent routing"
        )
    if state.termination_reason is not None:
        raise SauceDemoWorkflowCompositionError(
            "initial state must not contain a termination reason"
        )
    if state.product_context:
        raise SauceDemoWorkflowCompositionError(
            "initial state product context must be empty"
        )
    if any(
        (
            state.evidence,
            state.knowledge_candidates,
            state.validation_results,
            state.reasoning_trace_ids,
            state.step_history,
            state.warnings,
            state.errors,
        )
    ):
        raise SauceDemoWorkflowCompositionError(
            "initial state append-only collections must be empty"
        )


def _validate_config(config: DemoConfig) -> None:
    if not isinstance(config, DemoConfig):
        raise SauceDemoWorkflowCompositionError("config must be a DemoConfig")
    _require_identifier(config.product_id, "config.product_id")


def _require_identifier(value: str, field_name: str) -> None:
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or any(character.isspace() for character in value)
    ):
        raise SauceDemoWorkflowCompositionError(
            f"{field_name} must be a non-empty identifier"
        )


def _require_aware(value: datetime, field_name: str) -> None:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise SauceDemoWorkflowCompositionError(
            f"{field_name} must include timezone information"
        )
