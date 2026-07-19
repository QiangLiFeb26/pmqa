"""Focused and offline integration tests for the SauceDemo Validator."""

import json
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
from pmqa.orchestration import run_pmqa_workflow
from pmqa.runtime import WorkflowRuntime
from pmqa.supervisor import SupervisorAction, decide_next_action
from pmqa.workflow import (
    AGENT_UPDATE_POLICY,
    AgentExecutionStatus,
    AgentInvocation,
    AgentInvocationStatus,
    AgentRequest,
    AgentRole,
    TerminationReason,
    ToolRegistry,
    WorkflowState,
    WorkflowStatus,
    validate_agent_result,
)
from products.demo.capture import SauceDemoCaptureResult
from products.demo.config import DemoConfig
from products.demo.exploration_tool import SauceDemoExplorationTool
from products.demo.explorer_agent import SauceDemoExplorerAgent
from products.demo.knowledge_agent import SauceDemoKnowledgeAgent
from products.demo.knowledge_mapping import (
    SauceDemoKnowledgeCandidate,
    build_knowledge_candidate,
)
from products.demo.validation import (
    SauceDemoValidationResult,
    build_validation_result,
)
from products.demo.validator_agent import SauceDemoValidatorAgent


def test_agent_identity_uses_canonical_validator_capabilities() -> None:
    agent = SauceDemoValidatorAgent()

    assert agent.role is AgentRole.VALIDATOR
    assert agent.capabilities is AGENT_UPDATE_POLICY[AgentRole.VALIDATOR]


def test_validator_imports_are_runtime_tool_graph_and_provider_free() -> None:
    statement = "\n".join(
        [
            "import sys",
            "from products.demo.validation import SauceDemoValidationResult",
            "from products.demo.validator_agent import SauceDemoValidatorAgent",
            "assert SauceDemoValidationResult and SauceDemoValidatorAgent",
            "for prefix in ('playwright', 'products.demo.capture', ",
            "'products.demo.exploration_tool', 'pmqa.runtime', ",
            "'pmqa.orchestration', 'langgraph', 'pmqa.reasoning'):",
            "    assert not any(name == prefix or name.startswith(prefix + '.') ",
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


def test_first_cycle_passes_with_completed_history_and_bounded_patch() -> None:
    state = _state()
    request = _request(state)
    original = state.model_dump_json()

    result = SauceDemoValidatorAgent().invoke(request)

    assert validate_agent_result(request, result) is result
    assert result.outcome_status is AgentExecutionStatus.SUCCEEDED
    assert len(result.patch.validation_results_to_add) == 1
    validation = SauceDemoValidationResult.from_workflow_payload(
        result.patch.validation_results_to_add[0]
    )
    assert validation.status == "passed"
    assert validation.verified_knowledge is not None
    assert result.patch.errors_to_add == ()
    assert result.patch.evidence_to_add == ()
    assert result.patch.knowledge_candidates_to_add == ()
    assert result.patch.status is None
    assert result.patch.current_agent is None
    assert result.patch.next_agent is None
    assert result.patch.iteration is None
    assert result.patch.termination_reason is None
    history = result.patch.step_history_to_add[0]
    assert history.agent is AgentRole.VALIDATOR
    assert history.status is AgentInvocationStatus.COMPLETED
    assert history.started_at == history.completed_at == request.requested_at
    assert state.model_dump_json() == original


def test_runtime_applies_passed_result_without_mutating_candidate_or_state() -> None:
    state = _state(status=WorkflowStatus.RUNNING, iteration=1)
    original = state.model_dump_json()

    reduced = WorkflowRuntime(ToolRegistry()).execute_agent(
        state,
        SauceDemoValidatorAgent(),
        invocation_id="validator-1",
        requested_at=_timestamp(2),
    )

    assert len(reduced.validation_results) == 1
    assert reduced.evidence == state.evidence
    assert reduced.knowledge_candidates == state.knowledge_candidates
    assert reduced.status is state.status
    assert reduced.iteration == state.iteration
    candidate = SauceDemoKnowledgeCandidate.from_workflow_payload(
        reduced.knowledge_candidates[0]
    )
    validation = SauceDemoValidationResult.from_workflow_payload(
        reduced.validation_results[0]
    )
    assert all(
        item.lifecycle.state is ArtifactStatus.NEW
        for item in _items(candidate.knowledge)
    )
    assert all(
        item.lifecycle.state is ArtifactStatus.VERIFIED
        for item in _items(validation.verified_knowledge)
    )
    assert state.model_dump_json() == original


def test_domain_mismatch_succeeds_with_failed_result_and_no_fatal_error() -> None:
    evidence = _evidence()
    candidate = build_knowledge_candidate(evidence).to_workflow_payload()
    candidate["knowledge"]["locators"][0]["value"] = "safe-mismatch"
    state = _state(knowledge_candidates=[candidate])
    request = _request(state)

    result = SauceDemoValidatorAgent().invoke(request)

    assert validate_agent_result(request, result) is result
    assert result.outcome_status is AgentExecutionStatus.SUCCEEDED
    validation = SauceDemoValidationResult.from_workflow_payload(
        result.patch.validation_results_to_add[0]
    )
    assert validation.status == "failed"
    assert validation.verified_knowledge is None
    assert result.patch.errors_to_add == ()
    assert result.errors == ()
    assert result.patch.step_history_to_add[0].status is AgentInvocationStatus.COMPLETED
    assert "safe-mismatch" not in result.model_dump_json()


def test_recovery_cycle_validates_only_second_candidate() -> None:
    first_evidence = _evidence()
    first_payload = build_knowledge_candidate(first_evidence).to_workflow_payload()
    first_payload["knowledge"]["pages"][0]["title"] = "Mismatch"
    first_candidate = SauceDemoKnowledgeCandidate.from_workflow_payload(first_payload)
    first_result = build_validation_result(
        first_candidate, first_evidence, _timestamp(1)
    )
    second_evidence = _evidence(
        evidence_id="evidence-2",
        source=ExplorationSource(
            source_type="browser-automation",
            tool_id="playwright.saucedemo_explore",
            capture_id="capture-2",
        ),
    )
    second_candidate = build_knowledge_candidate(second_evidence)
    state = _state(
        evidence=[
            first_evidence.to_workflow_payload(),
            second_evidence.to_workflow_payload(),
        ],
        knowledge_candidates=[
            first_candidate.to_workflow_payload(),
            second_candidate.to_workflow_payload(),
        ],
        validation_results=[first_result.to_workflow_payload()],
    )

    result = SauceDemoValidatorAgent().invoke(_request(state))
    validation = SauceDemoValidationResult.from_workflow_payload(
        result.patch.validation_results_to_add[0]
    )

    assert validation.candidate_id == second_candidate.candidate_id
    assert validation.source_evidence_id == "evidence-2"
    assert validation.status == "passed"
    assert SauceDemoValidationResult.from_workflow_payload(
        state.validation_results[0]
    ) == first_result


@pytest.mark.parametrize(
    "case",
    [
        "no_evidence",
        "no_candidate",
        "malformed_evidence",
        "malformed_candidate",
        "wrong_evidence_workflow",
        "candidate_missing_evidence",
        "multiple_unvalidated",
    ],
)
def test_malformed_or_ambiguous_state_returns_safe_execution_failure(case) -> None:
    evidence = _evidence()
    if case == "no_evidence":
        state = _state(evidence=[])
    elif case == "no_candidate":
        state = _state(knowledge_candidates=[])
    elif case == "malformed_evidence":
        state = _state(evidence=[{"note": "runtime-secret-marker"}])
    elif case == "malformed_candidate":
        state = _state(knowledge_candidates=[{"note": "runtime-secret-marker"}])
    elif case == "wrong_evidence_workflow":
        wrong = _evidence(workflow_id="workflow-other")
        state = _state(
            evidence=[wrong.to_workflow_payload()],
            knowledge_candidates=[
                build_knowledge_candidate(wrong).to_workflow_payload()
            ],
        )
    elif case == "candidate_missing_evidence":
        missing = _evidence(evidence_id="evidence-missing")
        state = _state(
            knowledge_candidates=[
                build_knowledge_candidate(missing).to_workflow_payload()
            ]
        )
    else:
        second = _evidence(evidence_id="evidence-2")
        state = _state(
            evidence=[evidence.to_workflow_payload(), second.to_workflow_payload()],
            knowledge_candidates=[
                build_knowledge_candidate(evidence).to_workflow_payload(),
                build_knowledge_candidate(second).to_workflow_payload(),
            ],
        )

    result = SauceDemoValidatorAgent().invoke(_request(state))

    _assert_execution_failure(result)
    assert "runtime-secret-marker" not in result.model_dump_json()


def test_zero_unvalidated_candidate_returns_execution_failure() -> None:
    evidence = _evidence()
    candidate = build_knowledge_candidate(evidence)
    existing = build_validation_result(candidate, evidence, _timestamp(1))
    state = _state(validation_results=[existing.to_workflow_payload()])

    _assert_execution_failure(SauceDemoValidatorAgent().invoke(_request(state)))


@pytest.mark.parametrize("case", ["malformed", "missing_candidate", "duplicate"])
def test_existing_result_correlation_and_duplicates_fail_safely(case) -> None:
    evidence = _evidence()
    candidate = build_knowledge_candidate(evidence)
    result = build_validation_result(
        candidate, evidence, _timestamp(1)
    ).to_workflow_payload()
    if case == "malformed":
        results = [{"status": "passed", "note": "runtime-secret-marker"}]
    elif case == "missing_candidate":
        other_evidence = _evidence(evidence_id="evidence-other")
        other_candidate = build_knowledge_candidate(other_evidence)
        results = [
            build_validation_result(
                other_candidate, other_evidence, _timestamp(1)
            ).to_workflow_payload()
        ]
    else:
        results = [result, json.loads(json.dumps(result))]
    state = _state(validation_results=results)

    agent_result = SauceDemoValidatorAgent().invoke(_request(state))

    _assert_execution_failure(agent_result)
    assert "runtime-secret-marker" not in agent_result.model_dump_json()


def test_identical_inputs_produce_identical_results_and_reduced_states() -> None:
    state = _state()
    request = _request(state)
    agent = SauceDemoValidatorAgent()
    runtime = WorkflowRuntime(ToolRegistry())

    assert agent.invoke(request) == agent.invoke(request)
    first = runtime.execute_agent(
        state, agent, invocation_id="validator-1", requested_at=_timestamp(2)
    )
    second = runtime.execute_agent(
        state, agent, invocation_id="validator-1", requested_at=_timestamp(2)
    )
    assert first == second
    assert first.model_dump_json() == second.model_dump_json()


def test_supervisor_completes_after_real_passed_validation() -> None:
    reduced = _execute_validator(_state(status=WorkflowStatus.RUNNING, iteration=1))

    decision = decide_next_action(reduced)

    assert decision.action is SupervisorAction.COMPLETE_WORKFLOW


def test_supervisor_recovers_to_explorer_after_real_domain_failure() -> None:
    candidate = build_knowledge_candidate(_evidence()).to_workflow_payload()
    candidate["knowledge"]["interactions"][0][
        "expected_outcome_value"
    ] = "/safe-mismatch"
    reduced = _execute_validator(
        _state(
            status=WorkflowStatus.RUNNING,
            iteration=1,
            knowledge_candidates=[candidate],
        )
    )

    decision = decide_next_action(reduced)

    assert reduced.errors == ()
    assert reduced.validation_results[0]["status"] == "failed"
    assert reduced.step_history[-1].status is AgentInvocationStatus.COMPLETED
    assert decision.action is SupervisorAction.EXECUTE_AGENT
    assert decision.selected_agent is AgentRole.EXPLORER


def test_supervisor_fails_after_validator_execution_failure() -> None:
    reduced = _execute_validator(
        _state(status=WorkflowStatus.RUNNING, iteration=1, evidence=[])
    )

    decision = decide_next_action(reduced)

    assert reduced.validation_results == ()
    assert reduced.errors == ("validator_execution_failed",)
    assert reduced.step_history[-1].status is AgentInvocationStatus.FAILED
    assert decision.action is SupervisorAction.FAIL_WORKFLOW


def test_full_real_agent_offline_graph_completes() -> None:
    capture = _FakeCaptureRunner()
    tool = SauceDemoExplorationTool(
        _config(), capture_runner=capture, clock=lambda: _timestamp(1)
    )
    registry = ToolRegistry([tool])
    initial = _state(evidence=[], knowledge_candidates=[])
    original = initial.model_dump_json()

    final = run_pmqa_workflow(
        initial,
        agents={
            AgentRole.EXPLORER: SauceDemoExplorerAgent(
                WorkflowRuntime(registry).invoke_tool
            ),
            AgentRole.KNOWLEDGE: SauceDemoKnowledgeAgent(),
            AgentRole.VALIDATOR: SauceDemoValidatorAgent(),
        },
        tool_registry=registry,
    )

    assert final.status is WorkflowStatus.COMPLETED
    assert final.termination_reason is TerminationReason.GOAL_COMPLETED
    assert final.iteration == 1
    assert len(final.evidence) == 1
    assert len(final.knowledge_candidates) == 1
    assert len(final.validation_results) == 1
    candidate = SauceDemoKnowledgeCandidate.from_workflow_payload(
        final.knowledge_candidates[0]
    )
    validation = SauceDemoValidationResult.from_workflow_payload(
        final.validation_results[0]
    )
    assert validation.status == "passed"
    assert validation.verified_knowledge is not None
    assert all(
        item.lifecycle.state is ArtifactStatus.NEW
        for item in _items(candidate.knowledge)
    )
    assert all(
        item.lifecycle.state is ArtifactStatus.VERIFIED
        for item in _items(validation.verified_knowledge)
    )
    assert [item.agent for item in final.step_history] == [
        AgentRole.EXPLORER,
        AgentRole.KNOWLEDGE,
        AgentRole.VALIDATOR,
    ]
    assert initial.model_dump_json() == original
    assert capture.calls


def test_generic_minimal_task4_validation_result_remains_supported() -> None:
    state = _state(
        status=WorkflowStatus.RUNNING,
        iteration=1,
        validation_results=[{"status": "passed"}],
        step_history=[
            AgentInvocation(
                agent=AgentRole.VALIDATOR,
                started_at=_timestamp(1),
                completed_at=_timestamp(1),
                status=AgentInvocationStatus.COMPLETED,
            )
        ],
    )

    decision = decide_next_action(state)

    assert decision.action is SupervisorAction.COMPLETE_WORKFLOW


def _execute_validator(state):
    return WorkflowRuntime(ToolRegistry()).execute_agent(
        state,
        SauceDemoValidatorAgent(),
        invocation_id="validator-1",
        requested_at=_timestamp(2),
    )


def _assert_execution_failure(result) -> None:
    assert result.outcome_status is AgentExecutionStatus.FAILED
    assert result.patch.validation_results_to_add == ()
    assert result.patch.errors_to_add == ("validator_execution_failed",)
    assert result.errors == ("validator_execution_failed",)
    assert len(result.patch.step_history_to_add) == 1
    assert result.patch.step_history_to_add[0].status is AgentInvocationStatus.FAILED


class _FakeCaptureRunner:
    def __init__(self):
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


def _request(state):
    return AgentRequest(
        workflow_id=state.workflow_id,
        agent=AgentRole.VALIDATOR,
        state=state,
        invocation_id="validator-1",
        requested_at=_timestamp(2),
    )


def _state(**updates):
    evidence = _evidence()
    values = {
        "workflow_id": "workflow-1",
        "workflow_type": "exploration",
        "product_id": "demo",
        "product_version": "1",
        "goal": "Validate candidate knowledge",
        "max_iterations": 3,
        "evidence": [evidence.to_workflow_payload()],
        "knowledge_candidates": [
            build_knowledge_candidate(evidence).to_workflow_payload()
        ],
        "created_at": _timestamp(),
        "updated_at": _timestamp(),
    }
    values.update(updates)
    return WorkflowState(**values)


def _evidence(**updates):
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
        ),
        "elements": (
            ObservedElement(
                element_id="element.login",
                page_id="page.login",
                role="button",
                accessible_name="Login",
                visible_text="Login",
                attributes=(ObservedAttribute(name="data-test", value="login"),),
            ),
        ),
        "locator_candidates": (
            LocatorCandidateObservation(
                locator_candidate_id="locator.login",
                element_id="element.login",
                strategy="data-test",
                value="login",
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


def _items(knowledge):
    return (
        *knowledge.pages,
        *knowledge.elements,
        *knowledge.locators,
        *knowledge.interactions,
    )


def _timestamp(seconds=0):
    return datetime(2026, 7, 19, 15, tzinfo=timezone.utc) + timedelta(
        seconds=seconds
    )


def _config():
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
