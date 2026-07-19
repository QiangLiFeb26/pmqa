"""Offline and opt-in live tests for SauceDemo workflow composition."""

import json
import os
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from pmqa.models import (
    ArtifactStatus,
    ExplorationEvidence,
    InteractionObservation,
    LocatorCandidateObservation,
    ObservedAttribute,
    ObservedElement,
    ObservedPage,
)
from pmqa.security.boundary_policy import (
    WORKFLOW_STATE_PROHIBITED_KEYS,
    is_prohibited_key,
)
from pmqa.workflow import AgentRole, TerminationReason, WorkflowStatus
from products.demo import workflow as workflow_module
from products.demo.capture import SauceDemoCaptureResult
from products.demo.config import DemoConfig, load_config
from products.demo.knowledge_mapping import SauceDemoKnowledgeCandidate
from products.demo.validation import SauceDemoValidationResult
from products.demo.workflow import (
    SAUCEDEMO_WORKFLOW_TYPE,
    SauceDemoWorkflowCompositionError,
    create_saucedemo_workflow_state,
    run_saucedemo_workflow,
)


def test_initial_state_is_exact_empty_valid_and_immutable() -> None:
    state = _initial_state()

    assert state.workflow_id == "workflow-1"
    assert state.workflow_type == SAUCEDEMO_WORKFLOW_TYPE
    assert state.product_id == _config().product_id
    assert state.product_version == "1"
    assert state.goal == "Build verified SauceDemo product memory"
    assert state.status is WorkflowStatus.PENDING
    assert state.iteration == 0
    assert state.max_iterations == 1
    assert state.created_at == state.updated_at == _timestamp()
    assert state.current_agent is None
    assert state.next_agent is None
    assert state.termination_reason is None
    assert state.product_context == {}
    assert state.evidence == ()
    assert state.knowledge_candidates == ()
    assert state.validation_results == ()
    assert state.reasoning_trace_ids == ()
    assert state.step_history == ()
    assert state.warnings == ()
    assert state.errors == ()
    with pytest.raises(ValidationError, match="frozen"):
        state.status = WorkflowStatus.RUNNING


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("workflow_id", ""),
        ("workflow_id", " workflow-1"),
        ("product_version", "bad version"),
        ("goal", "   "),
        ("max_iterations", 0),
        ("max_iterations", True),
        ("created_at", datetime(2026, 7, 19, 15)),
    ],
)
def test_initial_state_factory_rejects_malformed_inputs(field, value) -> None:
    values = _initial_values()
    values[field] = value

    with pytest.raises(SauceDemoWorkflowCompositionError):
        create_saucedemo_workflow_state(_config(), **values)


@pytest.mark.parametrize(
    "updates",
    [
        {"product_id": "other"},
        {"workflow_type": "other"},
        {"status": WorkflowStatus.RUNNING},
        {"iteration": 1},
        {"evidence": ({"safe": "value"},)},
        {"errors": ("existing-error",)},
        {"updated_at": datetime(2026, 7, 19, 15, 0, 1, tzinfo=timezone.utc)},
    ],
)
def test_invalid_initial_state_fails_before_capture(updates) -> None:
    capture = _CaptureRunner()
    state = _initial_state().model_copy(update=updates)

    with pytest.raises(SauceDemoWorkflowCompositionError):
        run_saucedemo_workflow(
            _config(), state, capture_runner=capture, clock=lambda: _timestamp(1)
        )

    assert capture.calls == []


def test_composition_wires_one_registry_to_explorer_and_graph(monkeypatch) -> None:
    observed = {}

    def inspect_wiring(initial_state, *, agents, tool_registry, recursion_limit):
        observed["registry"] = tool_registry
        observed["agents"] = agents
        observed["recursion_limit"] = recursion_limit
        dispatcher_runtime = agents[AgentRole.EXPLORER]._tool_dispatcher.__self__
        assert dispatcher_runtime.registry is tool_registry
        return initial_state

    monkeypatch.setattr(workflow_module, "run_pmqa_workflow", inspect_wiring)

    state = run_saucedemo_workflow(
        _config(),
        _initial_state(),
        capture_runner=_CaptureRunner(),
        clock=lambda: _timestamp(1),
        recursion_limit=24,
    )

    assert state == _initial_state()
    assert len(observed["registry"]) == 1
    assert observed["registry"].tool_ids == (
        "playwright.saucedemo_explore",
    )
    assert set(observed["agents"]) == {
        AgentRole.EXPLORER,
        AgentRole.KNOWLEDGE,
        AgentRole.VALIDATOR,
    }
    assert observed["recursion_limit"] == 24


def test_offline_real_composition_completes_final_allowed_cycle() -> None:
    config = _config()
    config_before = deepcopy(config)
    initial = _initial_state(config=config, max_iterations=1)
    initial_before = initial.model_dump_json()
    capture = _CaptureRunner()

    final = run_saucedemo_workflow(
        config,
        initial,
        capture_runner=capture,
        clock=lambda: _timestamp(1),
        recursion_limit=24,
    )

    assert final.status is WorkflowStatus.COMPLETED
    assert final.termination_reason is TerminationReason.GOAL_COMPLETED
    assert final.iteration == 1
    assert len(final.evidence) == 1
    assert len(final.knowledge_candidates) == 1
    assert len(final.validation_results) == 1
    assert [item.agent for item in final.step_history] == [
        AgentRole.EXPLORER,
        AgentRole.KNOWLEDGE,
        AgentRole.VALIDATOR,
    ]
    assert all(
        item.status.value == "completed" for item in final.step_history
    )
    candidate = SauceDemoKnowledgeCandidate.from_workflow_payload(
        final.knowledge_candidates[0]
    )
    validation = SauceDemoValidationResult.from_workflow_payload(
        final.validation_results[0]
    )
    assert validation.status == "passed"
    assert validation.candidate_id == candidate.candidate_id
    assert validation.source_evidence_id == candidate.source_evidence_id
    assert all(
        item.lifecycle.state is ArtifactStatus.NEW
        for item in _knowledge_items(candidate.knowledge)
    )
    assert all(
        item.lifecycle.state is ArtifactStatus.VERIFIED
        for item in _knowledge_items(validation.verified_knowledge)
    )
    assert final.warnings == ()
    assert final.errors == ()
    assert capture.calls
    assert config == config_before
    assert initial.model_dump_json() == initial_before


def test_final_state_serialization_contains_only_safe_data() -> None:
    final = run_saucedemo_workflow(
        _config(),
        _initial_state(),
        capture_runner=_CaptureRunner(),
        clock=lambda: _timestamp(1),
    )

    serialized = final.model_dump_json()
    decoded = json.loads(serialized)

    _assert_safe_keys(decoded)
    assert "runtime-username-marker" not in serialized
    assert "runtime-password-marker" not in serialized
    assert "Browser" not in serialized
    assert "Playwright" not in serialized


def test_capture_failure_becomes_safe_terminal_workflow_failure() -> None:
    capture = _CaptureRunner(
        error=RuntimeError(
            "runtime-secret-marker <html>raw</html> browser-object-marker"
        )
    )
    initial = _initial_state()

    final = run_saucedemo_workflow(
        _config(),
        initial,
        capture_runner=capture,
        clock=lambda: _timestamp(1),
    )

    serialized = final.model_dump_json()
    assert final.status is WorkflowStatus.FAILED
    assert final.termination_reason is TerminationReason.ERROR
    assert final.iteration == 1
    assert final.evidence == ()
    assert final.knowledge_candidates == ()
    assert final.validation_results == ()
    assert final.errors == ("explorer_tool_failed",)
    assert len(final.step_history) == 1
    assert final.step_history[0].agent is AgentRole.EXPLORER
    assert final.step_history[0].status.value == "failed"
    assert "runtime-secret-marker" not in serialized
    assert "<html>" not in serialized
    assert "browser-object-marker" not in serialized


def test_invalid_runtime_options_fail_before_capture() -> None:
    for options in (
        {"headless": "yes"},
        {"recursion_limit": 0},
        {"recursion_limit": True},
    ):
        capture = _CaptureRunner()
        with pytest.raises(SauceDemoWorkflowCompositionError):
            run_saucedemo_workflow(
                _config(),
                _initial_state(),
                capture_runner=capture,
                clock=lambda: _timestamp(1),
                **options,
            )
        assert capture.calls == []


def test_non_callable_clock_fails_before_capture() -> None:
    capture = _CaptureRunner()

    with pytest.raises(SauceDemoWorkflowCompositionError):
        run_saucedemo_workflow(
            _config(),
            _initial_state(),
            capture_runner=capture,
            clock="not-callable",
        )

    assert capture.calls == []


@pytest.mark.parametrize(
    "invalid_value",
    [datetime(2026, 7, 19, 15), "not-a-datetime"],
)
def test_invalid_clock_sample_fails_before_capture(invalid_value) -> None:
    capture = _CaptureRunner()
    clock = _CountingClock(invalid_value)

    with pytest.raises(SauceDemoWorkflowCompositionError):
        run_saucedemo_workflow(
            _config(),
            _initial_state(),
            capture_runner=capture,
            clock=clock,
        )

    assert clock.calls == 1
    assert capture.calls == []


def test_valid_injected_clock_is_sampled_once_before_capture() -> None:
    capture = _CaptureRunner()
    clock = _CountingClock(_timestamp(1))

    final = run_saucedemo_workflow(
        _config(),
        _initial_state(),
        capture_runner=capture,
        clock=clock,
    )

    assert final.status is WorkflowStatus.COMPLETED
    assert final.updated_at == _timestamp(1)
    assert clock.calls == 1
    assert capture.calls


def test_prevalidated_clock_preserves_tool_timestamp_correlation() -> None:
    clock = _CountingClock(_timestamp(-1))

    final = run_saucedemo_workflow(
        _config(),
        _initial_state(),
        capture_runner=_CaptureRunner(),
        clock=clock,
    )

    assert final.updated_at == _timestamp()
    evidence = ExplorationEvidence.from_workflow_payload(final.evidence[0])
    assert evidence.captured_at == _timestamp()
    assert clock.calls == 1


def test_generic_pmqa_imports_remain_product_independent() -> None:
    statement = "\n".join(
        [
            "import sys",
            "import pmqa.models",
            "import pmqa.workflow",
            "import pmqa.runtime",
            "import pmqa.supervisor",
            "import pmqa.orchestration",
            "assert not any(name == 'products.demo' or ",
            "name.startswith('products.demo.') for name in sys.modules)",
        ]
    )
    completed = subprocess.run(
        [sys.executable, "-c", statement],
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


@pytest.mark.skipif(
    os.getenv("PMQA_RUN_LIVE_SAUCEDEMO_WORKFLOW") != "1",
    reason="set PMQA_RUN_LIVE_SAUCEDEMO_WORKFLOW=1 for live composition",
)
def test_live_saucedemo_workflow_composition() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    config = load_config(repository_root)
    created_at = datetime.now(timezone.utc)
    initial = create_saucedemo_workflow_state(
        config,
        workflow_id="live-saucedemo-workflow",
        product_version="live",
        goal="Validate the bounded live SauceDemo workflow",
        max_iterations=1,
        created_at=created_at,
    )

    final = run_saucedemo_workflow(
        config,
        initial,
        headless=True,
        recursion_limit=24,
    )

    assert final.status is WorkflowStatus.COMPLETED
    assert final.termination_reason is TerminationReason.GOAL_COMPLETED
    assert len(final.validation_results) == 1
    assert final.validation_results[0]["status"] == "passed"


class _CaptureRunner:
    def __init__(self, *, error=None):
        self.calls = []
        self.error = error

    def capture(self, actions):
        self.calls.append(tuple(actions))
        if self.error is not None:
            raise self.error
        return _capture_result()


class _CountingClock:
    def __init__(self, value):
        self.value = value
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.value


def _capture_result():
    return SauceDemoCaptureResult(
        pages=(
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
        elements=(
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
        ),
        locator_candidates=(
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
        interactions=(
            InteractionObservation(
                interaction_id="interaction.login",
                source_page_id="page.login",
                target_element_id="element.login",
                action="click",
                outcome_type="navigation",
                outcome_value="/inventory.html",
            ),
        ),
    )


def _initial_state(*, config=None, max_iterations=1):
    return create_saucedemo_workflow_state(
        config or _config(),
        **{**_initial_values(), "max_iterations": max_iterations},
    )


def _initial_values():
    return {
        "workflow_id": "workflow-1",
        "product_version": "1",
        "goal": "Build verified SauceDemo product memory",
        "max_iterations": 1,
        "created_at": _timestamp(),
    }


def _config():
    return DemoConfig(
        product_id="demo",
        base_url="https://example.test",
        start_path="/",
        maximum_exploration_steps=4,
        allowed_safe_actions=["inspect", "fill", "click", "stop"],
        blocked_destructive_actions=["checkout", "purchase", "delete"],
        artifact_output_location=Path("artifacts/knowledge.json"),
        generated_test_output_location=Path("generated_tests"),
        credential_environment_variables={
            "username": "PMQA_TEST_DEMO_USERNAME",
            "password": "PMQA_TEST_DEMO_PASSWORD",
        },
        demo_only_default_credentials={
            "username": "runtime-username-marker",
            "password": "runtime-password-marker",
        },
    )


def _knowledge_items(knowledge):
    return (
        *knowledge.pages,
        *knowledge.elements,
        *knowledge.locators,
        *knowledge.interactions,
    )


def _assert_safe_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            assert not is_prohibited_key(key, WORKFLOW_STATE_PROHIBITED_KEYS)
            _assert_safe_keys(item)
    elif isinstance(value, list):
        for item in value:
            _assert_safe_keys(item)


def _timestamp(seconds=0):
    return datetime(2026, 7, 19, 15, tzinfo=timezone.utc) + timedelta(
        seconds=seconds
    )
