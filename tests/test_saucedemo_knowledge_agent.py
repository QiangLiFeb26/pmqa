"""Focused and narrow integration tests for the SauceDemo Knowledge agent."""

import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

from pmqa.models import (
    ArtifactStatus,
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
    ToolRegistry,
    WorkflowState,
    WorkflowStatus,
    validate_agent_result,
)
from products.demo.capture import SauceDemoCaptureResult
from products.demo.config import DemoConfig
from products.demo.exploration_contracts import SAUCEDEMO_EXPLORATION_ACTIONS
from products.demo.exploration_tool import SauceDemoExplorationTool
from products.demo.explorer_agent import SauceDemoExplorerAgent
from products.demo.knowledge_agent import SauceDemoKnowledgeAgent
from products.demo.knowledge_mapping import (
    SauceDemoKnowledgeCandidate,
    build_knowledge_candidate,
)


def test_agent_identity_uses_canonical_knowledge_capabilities() -> None:
    agent = SauceDemoKnowledgeAgent()

    assert agent.role is AgentRole.KNOWLEDGE
    assert agent.capabilities is AGENT_UPDATE_POLICY[AgentRole.KNOWLEDGE]


def test_mapping_and_agent_imports_are_runtime_and_provider_free() -> None:
    statement = "\n".join(
        [
            "import sys",
            "from products.demo.knowledge_mapping import build_knowledge_candidate",
            "from products.demo.knowledge_agent import SauceDemoKnowledgeAgent",
            "assert build_knowledge_candidate and SauceDemoKnowledgeAgent",
            "for prefix in ('playwright', 'products.demo.capture', "
            "'products.demo.exploration_tool', 'pmqa.runtime', "
            "'pmqa.orchestration', 'langgraph', 'pmqa.reasoning'):",
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


def test_first_cycle_appends_one_candidate_and_completed_history() -> None:
    state = _state(evidence=[_evidence().to_workflow_payload()])
    request = _request(state=state)
    original_state_json = state.model_dump_json()

    result = SauceDemoKnowledgeAgent().invoke(request)

    assert validate_agent_result(request, result) is result
    assert result.outcome_status is AgentExecutionStatus.SUCCEEDED
    assert len(result.patch.knowledge_candidates_to_add) == 1
    candidate = SauceDemoKnowledgeCandidate.from_workflow_payload(
        result.patch.knowledge_candidates_to_add[0]
    )
    assert candidate.source_evidence_id == "evidence-1"
    assert candidate.workflow_id == state.workflow_id
    assert candidate.product_id == state.product_id
    assert len(result.patch.step_history_to_add) == 1
    history = result.patch.step_history_to_add[0]
    assert history.agent is AgentRole.KNOWLEDGE
    assert history.status is AgentInvocationStatus.COMPLETED
    assert history.started_at == history.completed_at == request.requested_at
    assert result.completed_at == request.requested_at
    assert result.patch.updated_at == request.requested_at
    assert result.patch.errors_to_add == ()
    assert result.patch.evidence_to_add == ()
    assert "knowledge" not in result.summary
    assert "pages" not in result.summary
    assert state.model_dump_json() == original_state_json


def test_runtime_applies_candidate_without_changing_unowned_state() -> None:
    state = _state(
        status=WorkflowStatus.RUNNING,
        current_agent=AgentRole.KNOWLEDGE,
        next_agent=AgentRole.VALIDATOR,
        iteration=1,
        evidence=[_evidence().to_workflow_payload()],
        validation_results=[{"status": "pending"}],
    )
    original_json = state.model_dump_json()
    runtime = WorkflowRuntime(ToolRegistry())

    reduced = runtime.execute_agent(
        state,
        SauceDemoKnowledgeAgent(),
        invocation_id="knowledge-1",
        requested_at=_timestamp(1),
    )

    assert len(reduced.knowledge_candidates) == 1
    assert reduced.evidence == state.evidence
    assert reduced.status is state.status
    assert reduced.current_agent is state.current_agent
    assert reduced.next_agent is state.next_agent
    assert reduced.iteration == state.iteration
    assert reduced.validation_results == state.validation_results
    assert reduced.termination_reason is state.termination_reason
    assert state.model_dump_json() == original_json
    with pytest.raises(TypeError, match="immutable"):
        reduced.knowledge_candidates[0]["knowledge"]["pages"][0]["title"] = "x"


def test_recovery_cycle_maps_only_second_evidence_and_preserves_first_candidate() -> None:
    first_evidence = _evidence()
    second_evidence = _evidence(
        evidence_id="evidence-2",
        source=ExplorationSource(
            source_type="browser-automation",
            tool_id="playwright.saucedemo_explore",
            capture_id="capture-2",
        ),
    )
    first_candidate = build_knowledge_candidate(first_evidence).to_workflow_payload()
    state = _state(
        evidence=[
            first_evidence.to_workflow_payload(),
            second_evidence.to_workflow_payload(),
        ],
        knowledge_candidates=[first_candidate],
    )
    runtime = WorkflowRuntime(ToolRegistry())

    reduced = runtime.execute_agent(
        state,
        SauceDemoKnowledgeAgent(),
        invocation_id="knowledge-2",
        requested_at=_timestamp(1),
    )

    assert len(reduced.knowledge_candidates) == 2
    assert reduced.knowledge_candidates[0] == state.knowledge_candidates[0]
    added = SauceDemoKnowledgeCandidate.from_workflow_payload(
        reduced.knowledge_candidates[1]
    )
    assert added.source_evidence_id == "evidence-2"
    assert added.candidate_id != first_candidate["candidate_id"]


def test_identical_inputs_produce_identical_results_and_states() -> None:
    state = _state(evidence=[_evidence().to_workflow_payload()])
    request = _request(state=state)
    agent = SauceDemoKnowledgeAgent()
    first_result = agent.invoke(request)
    second_result = agent.invoke(request)
    runtime = WorkflowRuntime(ToolRegistry())
    first_state = runtime.execute_agent(
        state, agent, invocation_id="knowledge-1", requested_at=_timestamp(1)
    )
    second_state = runtime.execute_agent(
        state, agent, invocation_id="knowledge-1", requested_at=_timestamp(1)
    )

    assert first_result == second_result
    assert first_result.model_dump_json() == second_result.model_dump_json()
    assert first_state == second_state
    assert first_state.model_dump_json() == second_state.model_dump_json()


@pytest.mark.parametrize(
    "case", ["missing", "malformed", "wrong_workflow", "wrong_product"]
)
def test_missing_malformed_or_wrongly_correlated_evidence_fails_safely(case) -> None:
    if case == "missing":
        state = _state(evidence=[])
    elif case == "malformed":
        state = _state(evidence=[{"runtime_note": "runtime-secret-marker"}])
    elif case == "wrong_workflow":
        state = _state(
            evidence=[
                _evidence(workflow_id="workflow-other").to_workflow_payload()
            ]
        )
    else:
        state = _state(
            evidence=[_evidence(product_id="other").to_workflow_payload()]
        )
    result = SauceDemoKnowledgeAgent().invoke(_request(state=state))

    _assert_safe_failure(result)
    assert "runtime-secret-marker" not in result.model_dump_json()


def test_malformed_existing_candidate_fails_safely() -> None:
    state = _state(
        evidence=[_evidence().to_workflow_payload()],
        knowledge_candidates=[{"candidate_id": "runtime-secret-marker"}],
    )

    result = SauceDemoKnowledgeAgent().invoke(_request(state=state))

    _assert_safe_failure(result)
    assert "runtime-secret-marker" not in result.model_dump_json()


def test_candidate_referencing_missing_evidence_fails_safely() -> None:
    evidence = _evidence()
    missing_candidate = build_knowledge_candidate(
        _evidence(evidence_id="evidence-missing")
    ).to_workflow_payload()
    state = _state(
        evidence=[evidence.to_workflow_payload()],
        knowledge_candidates=[missing_candidate],
    )

    result = SauceDemoKnowledgeAgent().invoke(_request(state=state))

    _assert_safe_failure(result)


@pytest.mark.parametrize("duplicate_kind", ["candidate", "source"])
def test_duplicate_candidate_or_source_correlation_fails_safely(
    duplicate_kind: str,
) -> None:
    evidence = _evidence()
    candidate = build_knowledge_candidate(evidence).to_workflow_payload()
    duplicate = json_clone(candidate)
    if duplicate_kind == "candidate":
        candidates = [candidate, duplicate]
    else:
        duplicate["candidate_id"] = candidate["candidate_id"] + ".other"
        candidates = [candidate, duplicate]
    state = _state(
        evidence=[evidence.to_workflow_payload()],
        knowledge_candidates=candidates,
    )

    result = SauceDemoKnowledgeAgent().invoke(_request(state=state))

    _assert_safe_failure(result)


def test_zero_unprocessed_evidence_fails_safely() -> None:
    evidence = _evidence()
    state = _state(
        evidence=[evidence.to_workflow_payload()],
        knowledge_candidates=[
            build_knowledge_candidate(evidence).to_workflow_payload()
        ],
    )

    _assert_safe_failure(SauceDemoKnowledgeAgent().invoke(_request(state=state)))


def test_multiple_unprocessed_evidence_batches_fail_safely() -> None:
    state = _state(
        evidence=[
            _evidence().to_workflow_payload(),
            _evidence(evidence_id="evidence-2").to_workflow_payload(),
        ]
    )

    _assert_safe_failure(SauceDemoKnowledgeAgent().invoke(_request(state=state)))


def test_runtime_applies_failed_history_and_only_stable_error() -> None:
    state = _state(evidence=[])
    runtime = WorkflowRuntime(ToolRegistry())

    reduced = runtime.execute_agent(
        state,
        SauceDemoKnowledgeAgent(),
        invocation_id="knowledge-1",
        requested_at=_timestamp(1),
    )

    assert reduced.knowledge_candidates == ()
    assert reduced.errors == ("knowledge_mapping_failed",)
    assert len(reduced.step_history) == 1
    assert reduced.step_history[0].status is AgentInvocationStatus.FAILED
    assert reduced.evidence == state.evidence


def test_real_explorer_tool_knowledge_reducer_chain_is_offline_and_deterministic() -> None:
    capture = _FakeCaptureRunner()
    tool = SauceDemoExplorationTool(
        _config(), capture_runner=capture, clock=lambda: _timestamp(1)
    )
    runtime = WorkflowRuntime(ToolRegistry([tool]))
    explorer = SauceDemoExplorerAgent(runtime.invoke_tool)
    knowledge_agent = SauceDemoKnowledgeAgent()
    initial = _state(evidence=[])
    original_json = initial.model_dump_json()

    explored = runtime.execute_agent(
        initial,
        explorer,
        invocation_id="explorer-1",
        requested_at=_timestamp(),
    )
    mapped = runtime.execute_agent(
        explored,
        knowledge_agent,
        invocation_id="knowledge-1",
        requested_at=_timestamp(1),
    )

    assert capture.calls == [SAUCEDEMO_EXPLORATION_ACTIONS]
    assert len(explored.evidence) == 1
    assert len(mapped.knowledge_candidates) == 1
    candidate = SauceDemoKnowledgeCandidate.from_workflow_payload(
        mapped.knowledge_candidates[0]
    )
    assert candidate.knowledge.pages
    items = [
        *candidate.knowledge.pages,
        *candidate.knowledge.elements,
        *candidate.knowledge.locators,
        *candidate.knowledge.interactions,
    ]
    assert all(item.lifecycle.state is ArtifactStatus.NEW for item in items)
    assert [item.agent for item in mapped.step_history] == [
        AgentRole.EXPLORER,
        AgentRole.KNOWLEDGE,
    ]
    assert initial.model_dump_json() == original_json


def _assert_safe_failure(result) -> None:
    assert result.outcome_status is AgentExecutionStatus.FAILED
    assert result.patch.knowledge_candidates_to_add == ()
    assert result.patch.errors_to_add == ("knowledge_mapping_failed",)
    assert result.errors == ("knowledge_mapping_failed",)
    assert len(result.patch.step_history_to_add) == 1
    history = result.patch.step_history_to_add[0]
    assert history.agent is AgentRole.KNOWLEDGE
    assert history.status is AgentInvocationStatus.FAILED
    assert history.completed_at == result.completed_at
    assert result.completed_at == result.patch.updated_at
    assert result.patch.evidence_to_add == ()


class _FakeCaptureRunner:
    def __init__(self) -> None:
        self.calls = []

    def capture(self, actions):
        self.calls.append(tuple(actions))
        evidence = _evidence()
        return SauceDemoCaptureResult(
            pages=evidence.pages,
            elements=evidence.elements,
            locator_candidates=evidence.locator_candidates,
            interactions=evidence.interactions,
        )


def _request(*, state, **updates) -> AgentRequest:
    values = {
        "workflow_id": state.workflow_id,
        "agent": AgentRole.KNOWLEDGE,
        "state": state,
        "invocation_id": "knowledge-1",
        "requested_at": _timestamp(1),
    }
    values.update(updates)
    return AgentRequest(**values)


def _state(**updates) -> WorkflowState:
    values = {
        "workflow_id": "workflow-1",
        "workflow_type": "exploration",
        "product_id": "demo",
        "product_version": "1",
        "goal": "Build candidate knowledge",
        "max_iterations": 3,
        "created_at": _timestamp(),
        "updated_at": _timestamp(),
    }
    values.update(updates)
    return WorkflowState(**values)


def _evidence(**updates) -> ExplorationEvidence:
    values = {
        "schema_version": "1",
        "evidence_id": "evidence-1",
        "workflow_id": "workflow-1",
        "product_id": "demo",
        "source": ExplorationSource(
            source_type="browser-automation",
            tool_id="playwright.saucedemo_explore",
            capture_id="capture-1",
        ),
        "captured_at": _timestamp(),
        "pages": (
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
        ),
        "elements": (
            ObservedElement(
                element_id="element.login",
                page_id="page.login",
                role="button",
                accessible_name="Login",
                visible_text="Login",
                attributes=(ObservedAttribute(name="data-test", value="login-button"),),
            ),
            ObservedElement(
                element_id="element.inventory_title",
                page_id="page.inventory",
                role="heading",
                accessible_name="Products",
                visible_text="Products",
                attributes=(ObservedAttribute(name="data-test", value="title"),),
            ),
        ),
        "locator_candidates": (
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
        ),
        "interactions": (
            InteractionObservation(
                interaction_id="interaction.login",
                source_page_id="page.login",
                target_element_id="element.login",
                action="click",
                outcome_type="navigation",
                outcome_value="/inventory.html",
            ),
        ),
    }
    values.update(updates)
    return ExplorationEvidence(**values)


def _timestamp(seconds=0) -> datetime:
    return datetime(2026, 7, 19, 15, tzinfo=timezone.utc) + timedelta(
        seconds=seconds
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


def json_clone(value):
    import json

    return json.loads(json.dumps(value))
