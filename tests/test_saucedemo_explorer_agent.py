"""Focused tests for the product-owned SauceDemo Explorer agent."""

import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

from pmqa.models import (
    ExplorationEvidence,
    ExplorationSource,
    InteractionObservation,
    LocatorCandidateObservation,
    ObservedAttribute,
    ObservedElement,
    ObservedPage,
)
from pmqa.runtime import WorkflowRuntime
from pmqa.workflow import (
    AGENT_UPDATE_POLICY,
    AgentExecutionStatus,
    AgentInvocationStatus,
    AgentRequest,
    AgentRole,
    ToolCategory,
    ToolError,
    ToolExecutionStatus,
    ToolRegistry,
    ToolResult,
    WorkflowState,
    WorkflowStatus,
    validate_agent_result,
)
from products.demo.capture import SauceDemoCaptureResult
from products.demo.config import DemoConfig
from products.demo.exploration_contracts import (
    SAUCEDEMO_EXPLORATION_ACTIONS,
    SAUCEDEMO_EXPLORATION_TOOL_ID,
)
from products.demo.exploration_tool import SauceDemoExplorationTool
from products.demo.explorer_agent import SauceDemoExplorerAgent


def test_agent_identity_uses_canonical_explorer_capabilities() -> None:
    agent = SauceDemoExplorerAgent(_Dispatcher())

    assert agent.role is AgentRole.EXPLORER
    assert agent.capabilities is AGENT_UPDATE_POLICY[AgentRole.EXPLORER]


def test_explorer_import_is_lightweight_and_playwright_free() -> None:
    statement = "\n".join(
        [
            "import sys",
            "from products.demo.explorer_agent import SauceDemoExplorerAgent",
            "assert SauceDemoExplorerAgent",
            "for prefix in ('playwright', 'products.demo.capture', "
            "'products.demo.exploration_tool', 'pmqa.runtime', "
            "'pmqa.orchestration', 'langgraph'):",
            "    assert not any(name == prefix or name.startswith(prefix + '.') "
            "for name in sys.modules)",
        ]
    )
    completed = subprocess.run(
        [sys.executable, "-c", statement],
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_success_dispatches_once_and_returns_correlated_patch() -> None:
    dispatcher = _Dispatcher()
    agent = SauceDemoExplorerAgent(dispatcher)
    request = _agent_request()
    original_state_json = request.state.model_dump_json()

    result = agent.invoke(request)

    assert validate_agent_result(request, result) is result
    assert result.outcome_status is AgentExecutionStatus.SUCCEEDED
    assert len(dispatcher.requests) == 1
    tool_request = dispatcher.requests[0]
    assert tool_request.tool_id == SAUCEDEMO_EXPLORATION_TOOL_ID
    assert tool_request.category is ToolCategory.PLAYWRIGHT
    assert tool_request.workflow_id == request.workflow_id
    assert tool_request.invocation_id == (
        request.invocation_id + ":" + SAUCEDEMO_EXPLORATION_TOOL_ID
    )
    assert tool_request.invocation_id != request.invocation_id
    assert tool_request.requested_by_agent is AgentRole.EXPLORER
    assert tool_request.requested_at == request.requested_at
    assert tool_request.input == {
        "product_id": request.state.product_id,
        "actions": SAUCEDEMO_EXPLORATION_ACTIONS,
    }
    assert len(result.patch.evidence_to_add) == 1
    evidence = ExplorationEvidence.from_workflow_payload(
        result.patch.evidence_to_add[0]
    )
    assert evidence.workflow_id == request.workflow_id
    assert evidence.source.capture_id == tool_request.invocation_id
    assert "evidence" not in result.patch.evidence_to_add[0]
    assert len(result.patch.step_history_to_add) == 1
    history = result.patch.step_history_to_add[0]
    assert history.agent is AgentRole.EXPLORER
    assert history.status is AgentInvocationStatus.COMPLETED
    assert history.started_at == request.requested_at
    assert history.completed_at == result.completed_at == _timestamp(1)
    assert result.patch.updated_at == result.completed_at
    assert result.patch.errors_to_add == ()
    assert "pages" not in result.summary
    assert "pages" not in history.output_summary
    assert request.state.model_dump_json() == original_state_json


def test_runtime_applies_success_patch_without_changing_unowned_state() -> None:
    state = _state(
        status=WorkflowStatus.RUNNING,
        current_agent=AgentRole.EXPLORER,
        next_agent=AgentRole.KNOWLEDGE,
        iteration=1,
        knowledge_candidates=[{"candidate_id": "existing"}],
        validation_results=[{"status": "pending"}],
    )
    runtime = WorkflowRuntime(ToolRegistry())
    agent = SauceDemoExplorerAgent(_Dispatcher())
    original_json = state.model_dump_json()

    reduced = runtime.execute_agent(
        state,
        agent,
        invocation_id="agent-1",
        requested_at=_timestamp(),
    )

    assert len(reduced.evidence) == 1
    assert len(reduced.step_history) == 1
    assert reduced.status is state.status
    assert reduced.current_agent is state.current_agent
    assert reduced.next_agent is state.next_agent
    assert reduced.iteration == state.iteration
    assert reduced.knowledge_candidates == state.knowledge_candidates
    assert reduced.validation_results == state.validation_results
    assert reduced.termination_reason is state.termination_reason
    assert state.model_dump_json() == original_json


def test_second_explorer_invocation_appends_without_replacing_evidence() -> None:
    runtime = WorkflowRuntime(ToolRegistry())
    agent = SauceDemoExplorerAgent(_Dispatcher())
    first = runtime.execute_agent(
        _state(), agent, invocation_id="agent-1", requested_at=_timestamp()
    )
    second = runtime.execute_agent(
        first,
        agent,
        invocation_id="agent-2",
        requested_at=_timestamp(1),
    )

    assert len(first.evidence) == 1
    assert len(second.evidence) == 2
    assert len(second.step_history) == 2
    assert first.evidence[0] == second.evidence[0]
    assert second.evidence[0]["evidence_id"] != second.evidence[1]["evidence_id"]


def test_identical_inputs_and_tool_results_are_deterministic() -> None:
    request = _agent_request()
    first_result = SauceDemoExplorerAgent(_Dispatcher()).invoke(request)
    second_result = SauceDemoExplorerAgent(_Dispatcher()).invoke(request)
    runtime = WorkflowRuntime(ToolRegistry())
    first_state = runtime.execute_agent(
        request.state,
        SauceDemoExplorerAgent(_Dispatcher()),
        invocation_id=request.invocation_id,
        requested_at=request.requested_at,
    )
    second_state = runtime.execute_agent(
        request.state,
        SauceDemoExplorerAgent(_Dispatcher()),
        invocation_id=request.invocation_id,
        requested_at=request.requested_at,
    )

    assert first_result == second_result
    assert first_result.model_dump_json() == second_result.model_dump_json()
    assert first_state == second_state
    assert first_state.model_dump_json() == second_state.model_dump_json()


@pytest.mark.parametrize(
    "status",
    [
        ToolExecutionStatus.FAILED,
        ToolExecutionStatus.PARTIAL,
        ToolExecutionStatus.SKIPPED,
    ],
)
def test_non_success_tool_status_returns_safe_failure(status) -> None:
    dispatcher = _Dispatcher(status=status, tool_error_secret=True)

    result = SauceDemoExplorerAgent(dispatcher).invoke(_agent_request())

    _assert_safe_failure(result)
    assert result.completed_at == _timestamp(1)
    assert len(dispatcher.requests) == 1
    assert "runtime-secret-marker" not in result.model_dump_json()


@pytest.mark.parametrize("output", [{}, {"wrapper": {"evidence": {}}}])
def test_missing_or_wrapped_evidence_output_returns_safe_failure(output) -> None:
    result = SauceDemoExplorerAgent(_Dispatcher(output=output)).invoke(
        _agent_request()
    )

    _assert_safe_failure(result)


def test_malformed_evidence_returns_safe_failure_without_echoing_payload() -> None:
    malformed = {
        "evidence": {
            "schema_version": "runtime-secret-marker",
            "unexpected": "<html>raw</html>",
        }
    }

    result = SauceDemoExplorerAgent(_Dispatcher(output=malformed)).invoke(
        _agent_request()
    )

    _assert_safe_failure(result)
    serialized = result.model_dump_json()
    assert "runtime-secret-marker" not in serialized
    assert "<html>" not in serialized


@pytest.mark.parametrize(
    ("evidence_update", "request_update"),
    [
        ({"workflow_id": "workflow-other"}, {}),
        ({"product_id": "other"}, {}),
        ({"source_tool_id": "playwright.other"}, {}),
        ({"capture_id": "capture-other"}, {}),
    ],
)
def test_wrong_evidence_correlation_returns_safe_failure(
    evidence_update, request_update
) -> None:
    dispatcher = _Dispatcher(evidence_update=evidence_update)

    result = SauceDemoExplorerAgent(dispatcher).invoke(
        _agent_request(**request_update)
    )

    _assert_safe_failure(result)
    assert len(dispatcher.requests) == 1


def test_tool_result_correlation_failure_returns_safe_failure() -> None:
    dispatcher = _Dispatcher(result_invocation_id="tool-other")

    result = SauceDemoExplorerAgent(dispatcher).invoke(_agent_request())

    _assert_safe_failure(result)
    assert len(dispatcher.requests) == 1


def test_registry_dispatch_failure_is_safe_and_not_retried() -> None:
    missing_tool_runtime = WorkflowRuntime(ToolRegistry())
    agent = SauceDemoExplorerAgent(missing_tool_runtime.invoke_tool)

    result = agent.invoke(_agent_request())

    _assert_safe_failure(result)
    assert result.completed_at == _timestamp()


def test_dispatch_exception_text_is_not_exposed_or_retried() -> None:
    dispatcher = _Dispatcher(
        exception=RuntimeError("runtime-secret-marker <html>raw</html>")
    )

    result = SauceDemoExplorerAgent(dispatcher).invoke(_agent_request())

    _assert_safe_failure(result)
    assert len(dispatcher.requests) == 1
    serialized = result.model_dump_json()
    assert "runtime-secret-marker" not in serialized
    assert "<html>" not in serialized


def test_runtime_applies_failure_history_and_error_without_other_changes() -> None:
    state = _state(
        status=WorkflowStatus.RUNNING,
        current_agent=AgentRole.EXPLORER,
        next_agent=AgentRole.KNOWLEDGE,
        iteration=1,
        knowledge_candidates=[{"candidate_id": "existing"}],
        validation_results=[{"status": "pending"}],
    )
    runtime = WorkflowRuntime(ToolRegistry())
    agent = SauceDemoExplorerAgent(_Dispatcher(status=ToolExecutionStatus.FAILED))

    reduced = runtime.execute_agent(
        state,
        agent,
        invocation_id="agent-1",
        requested_at=_timestamp(),
    )

    assert reduced.evidence == ()
    assert reduced.errors == ("explorer_tool_failed",)
    assert len(reduced.step_history) == 1
    assert reduced.step_history[0].status is AgentInvocationStatus.FAILED
    assert reduced.status is state.status
    assert reduced.current_agent is state.current_agent
    assert reduced.next_agent is state.next_agent
    assert reduced.iteration == state.iteration
    assert reduced.knowledge_candidates == state.knowledge_candidates
    assert reduced.validation_results == state.validation_results
    assert reduced.termination_reason is state.termination_reason


def test_offline_real_runtime_tool_agent_reducer_chain() -> None:
    capture = _FakeCaptureRunner()
    tool = SauceDemoExplorationTool(
        _config(), capture_runner=capture, clock=lambda: _timestamp(1)
    )
    runtime = WorkflowRuntime(ToolRegistry([tool]))
    agent = SauceDemoExplorerAgent(runtime.invoke_tool)
    state = _state()

    reduced = runtime.execute_agent(
        state,
        agent,
        invocation_id="agent-1",
        requested_at=_timestamp(),
    )

    assert capture.calls == [SAUCEDEMO_EXPLORATION_ACTIONS]
    assert len(reduced.evidence) == 1
    evidence = ExplorationEvidence.from_workflow_payload(reduced.evidence[0])
    assert evidence.workflow_id == state.workflow_id
    assert evidence.product_id == state.product_id
    assert evidence.source.tool_id == SAUCEDEMO_EXPLORATION_TOOL_ID
    assert evidence.source.capture_id == (
        "agent-1:" + SAUCEDEMO_EXPLORATION_TOOL_ID
    )
    assert reduced.step_history[-1].status is AgentInvocationStatus.COMPLETED
    assert reduced.updated_at == _timestamp(1)


def _assert_safe_failure(result) -> None:
    assert result.outcome_status is AgentExecutionStatus.FAILED
    assert result.patch.evidence_to_add == ()
    assert result.patch.errors_to_add == ("explorer_tool_failed",)
    assert result.errors == ("explorer_tool_failed",)
    assert len(result.patch.step_history_to_add) == 1
    history = result.patch.step_history_to_add[0]
    assert history.status is AgentInvocationStatus.FAILED
    assert history.agent is AgentRole.EXPLORER
    assert history.completed_at == result.completed_at
    assert result.patch.updated_at == result.completed_at
    assert "evidence" not in result.summary
    assert "output" not in result.summary


class _Dispatcher:
    def __init__(
        self,
        *,
        status=ToolExecutionStatus.SUCCEEDED,
        output=None,
        evidence_update=None,
        result_invocation_id=None,
        exception=None,
        tool_error_secret=False,
    ) -> None:
        self.status = status
        self.output = output
        self.evidence_update = evidence_update or {}
        self.result_invocation_id = result_invocation_id
        self.exception = exception
        self.tool_error_secret = tool_error_secret
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        if self.exception is not None:
            raise self.exception
        output = self.output
        if output is None:
            output = {"evidence": _evidence(request, **self.evidence_update)}
        errors = ()
        if self.tool_error_secret:
            errors = (
                ToolError(
                    code="capture_failed",
                    message="runtime-secret-marker <html>raw</html>",
                ),
            )
        return ToolResult(
            tool_id=request.tool_id,
            workflow_id=request.workflow_id,
            invocation_id=self.result_invocation_id or request.invocation_id,
            completed_at=_timestamp(1),
            status=self.status,
            output=output,
            errors=errors,
        )


class _FakeCaptureRunner:
    def __init__(self) -> None:
        self.calls = []

    def capture(self, actions):
        self.calls.append(tuple(actions))
        return _capture_result()


def _agent_request(**updates) -> AgentRequest:
    values = {
        "workflow_id": "workflow-1",
        "agent": AgentRole.EXPLORER,
        "state": _state(),
        "invocation_id": "agent-1",
        "requested_at": _timestamp(),
    }
    values.update(updates)
    return AgentRequest(**values)


def _state(**updates) -> WorkflowState:
    values = {
        "workflow_id": "workflow-1",
        "workflow_type": "exploration",
        "product_id": "demo",
        "product_version": "1",
        "goal": "Collect bounded SauceDemo evidence",
        "max_iterations": 3,
        "created_at": _timestamp(),
        "updated_at": _timestamp(),
    }
    values.update(updates)
    return WorkflowState(**values)


def _timestamp(seconds=0) -> datetime:
    return datetime(2026, 7, 19, 15, tzinfo=timezone.utc) + timedelta(
        seconds=seconds
    )


def _evidence(request, **updates):
    source_tool_id = updates.pop("source_tool_id", request.tool_id)
    capture_id = updates.pop("capture_id", request.invocation_id)
    values = {
        "schema_version": "1",
        "evidence_id": "evidence." + request.invocation_id,
        "workflow_id": request.workflow_id,
        "product_id": request.input["product_id"],
        "source": ExplorationSource(
            source_type="browser-automation",
            tool_id=source_tool_id,
            capture_id=capture_id,
        ),
        "captured_at": _timestamp(1),
        "pages": _capture_result().pages,
        "elements": _capture_result().elements,
        "locator_candidates": _capture_result().locator_candidates,
        "interactions": _capture_result().interactions,
    }
    values.update(updates)
    return ExplorationEvidence(**values).to_workflow_payload()


def _capture_result() -> SauceDemoCaptureResult:
    pages = (
        ObservedPage(
            page_id="page.login",
            url="https://example.test/",
            title="Login",
            structural_fingerprint="login-fingerprint",
        ),
        ObservedPage(
            page_id="page.inventory",
            url="https://example.test/inventory.html",
            title="Inventory",
            structural_fingerprint="inventory-fingerprint",
        ),
    )
    elements = (
        ObservedElement(
            element_id="element.login",
            page_id="page.login",
            role="button",
            accessible_name="Login",
            visible_text="Login",
            attributes=(
                ObservedAttribute(name="data-test", value="login-button"),
            ),
        ),
        ObservedElement(
            element_id="element.inventory_title",
            page_id="page.inventory",
            role="heading",
            accessible_name="Products",
            visible_text="Products",
            attributes=(ObservedAttribute(name="data-test", value="title"),),
        ),
    )
    locator_candidates = (
        LocatorCandidateObservation(
            locator_candidate_id="locator.login",
            element_id="element.login",
            strategy="data-test",
            value="login-button",
            priority=1,
        ),
        LocatorCandidateObservation(
            locator_candidate_id="locator.inventory_title",
            element_id="element.inventory_title",
            strategy="data-test",
            value="title",
            priority=1,
        ),
    )
    interactions = (
        InteractionObservation(
            interaction_id="interaction.login",
            source_page_id="page.login",
            target_element_id="element.login",
            action="click",
            outcome_type="navigation",
            outcome_value="/inventory.html",
        ),
    )
    return SauceDemoCaptureResult(
        pages=pages,
        elements=elements,
        locator_candidates=locator_candidates,
        interactions=interactions,
    )


def _config() -> DemoConfig:
    return DemoConfig(
        product_id="demo",
        base_url="https://example.test",
        start_path="/",
        maximum_exploration_steps=4,
        allowed_safe_actions=["inspect", "fill", "click", "stop"],
        blocked_destructive_actions=["checkout", "purchase", "delete"],
        artifact_output_location=None,
        generated_test_output_location=None,
        credential_environment_variables={
            "username": "PMQA_TEST_DEMO_USERNAME",
            "password": "PMQA_TEST_DEMO_PASSWORD",
        },
        demo_only_default_credentials={
            "username": "runtime-username-marker",
            "password": "runtime-password-marker",
        },
    )
