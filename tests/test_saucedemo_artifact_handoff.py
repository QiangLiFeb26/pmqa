"""Focused tests for the strict SauceDemo verified-artifact handoff."""

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pmqa.models import (
    ArtifactStatus,
    ExplorationEvidence,
    ExplorationSource,
    InteractionObservation,
    KnowledgeArtifact,
    LocatorCandidateObservation,
    ObservedAttribute,
    ObservedElement,
    ObservedPage,
)
from pmqa.providers import StorageProvider
from pmqa.security.boundary_policy import (
    WORKFLOW_STATE_PROHIBITED_KEYS,
    is_prohibited_key,
)
from pmqa.storage import JsonFileStorage
from pmqa.workflow import (
    AgentInvocation,
    AgentInvocationStatus,
    AgentRole,
    TerminationReason,
    WorkflowState,
    WorkflowStatus,
)
from products.demo import artifact_handoff as handoff_module
from products.demo.artifact_handoff import (
    KNOWLEDGE_STORAGE_KEY,
    SauceDemoArtifactHandoffError,
    extract_verified_knowledge,
    generate_tests_from_verified_workflow,
    persist_verified_knowledge,
)
from products.demo.capture import SauceDemoCaptureResult
from products.demo.config import DemoConfig
from products.demo.knowledge_mapping import (
    SauceDemoKnowledgeCandidate,
    build_knowledge_candidate,
)
from products.demo.validation import (
    SauceDemoValidationResult,
    build_validation_result,
)
from products.demo.workflow import (
    create_saucedemo_workflow_state,
    run_saucedemo_workflow,
)


@pytest.fixture
def completed_workflow():
    return _completed_workflow()


def test_real_offline_workflow_extracts_independent_verified_knowledge(
    completed_workflow,
) -> None:
    before = completed_workflow.model_dump_json()
    candidate_before = json.loads(
        json.dumps(completed_workflow.knowledge_candidates[0])
    )

    knowledge = extract_verified_knowledge(completed_workflow, _config())

    assert isinstance(knowledge, KnowledgeArtifact)
    assert knowledge.pages
    assert knowledge.elements
    assert knowledge.locators
    assert knowledge.interactions
    validation = SauceDemoValidationResult.from_workflow_payload(
        completed_workflow.validation_results[-1]
    )
    assert all(
        item.lifecycle.state is ArtifactStatus.VERIFIED
        and item.lifecycle.last_verified == validation.validated_at
        for item in _knowledge_items(knowledge)
    )
    candidate = SauceDemoKnowledgeCandidate.from_workflow_payload(
        completed_workflow.knowledge_candidates[-1]
    )
    assert all(
        item.lifecycle.state is ArtifactStatus.NEW
        and item.lifecycle.last_verified is None
        for item in _knowledge_items(candidate.knowledge)
    )
    knowledge.elements[0].attributes["data-test"] = "changed-after-extraction"
    restored = extract_verified_knowledge(completed_workflow, _config())
    assert restored.elements[0].attributes["data-test"] == "username"
    assert completed_workflow.model_dump_json() == before
    assert (
        json.loads(json.dumps(completed_workflow.knowledge_candidates[0]))
        == candidate_before
    )


def test_persistence_saves_exact_verified_payload_once(completed_workflow) -> None:
    storage = _RecordingStorage()
    expected = extract_verified_knowledge(completed_workflow, _config())

    artifact = persist_verified_knowledge(
        completed_workflow, _config(), storage
    )

    assert len(storage.saved) == 1
    assert artifact is storage.saved[0]
    assert artifact.artifact_id == KNOWLEDGE_STORAGE_KEY == "knowledge"
    assert artifact.data == expected.to_dict()
    assert artifact.data["artifact_id"] == expected.artifact_id
    assert "candidate_id" not in artifact.data
    assert "validation_id" not in artifact.data
    assert "step_history" not in artifact.data


def test_json_file_storage_round_trips_only_verified_knowledge(
    completed_workflow, tmp_path
) -> None:
    expected = extract_verified_knowledge(completed_workflow, _config())
    storage = JsonFileStorage(tmp_path)

    persist_verified_knowledge(completed_workflow, _config(), storage)

    path = tmp_path / "knowledge.json"
    assert path.exists()
    decoded = json.loads(path.read_text(encoding="utf-8"))
    loaded = storage.load("knowledge")
    assert loaded is not None
    assert loaded.artifact_id == "knowledge"
    assert loaded.data == expected.to_dict() == decoded
    serialized = path.read_text(encoding="utf-8")
    _assert_safe_keys(decoded)
    for forbidden in (
        "candidate_id",
        "validation_id",
        "source_evidence_id",
        "step_history",
        "runtime-username-marker",
        "runtime-password-marker",
        "Browser",
        "Playwright",
    ):
        assert forbidden not in serialized


def test_existing_generator_produces_deterministic_two_test_file(
    completed_workflow, tmp_path
) -> None:
    first = generate_tests_from_verified_workflow(
        completed_workflow, _config(), tmp_path / "first"
    )
    second = generate_tests_from_verified_workflow(
        completed_workflow, _config(), tmp_path / "second"
    )

    first_content = first.read_text(encoding="utf-8")
    second_content = second.read_text(encoding="utf-8")
    assert first.name == second.name == "test_saucedemo_generated.py"
    assert first_content == second_content
    assert "def test_successful_login(page: Page)" in first_content
    assert "def test_inventory_page(page: Page)" in first_content


@pytest.mark.parametrize(
    "updates",
    [
        {"status": WorkflowStatus.PENDING, "termination_reason": None},
        {"status": WorkflowStatus.RUNNING, "termination_reason": None},
        {
            "status": WorkflowStatus.FAILED,
            "termination_reason": TerminationReason.ERROR,
        },
        {
            "status": WorkflowStatus.TERMINATED,
            "termination_reason": TerminationReason.MAX_ITERATIONS,
        },
        {
            "status": WorkflowStatus.COMPLETED,
            "termination_reason": TerminationReason.ERROR,
        },
        {"errors": ("fatal",)},
        {"workflow_type": "other"},
        {"product_id": "other"},
    ],
)
def test_non_successful_or_wrongly_correlated_workflow_is_rejected(
    completed_workflow, updates
) -> None:
    state = completed_workflow.model_copy(update=updates)

    with pytest.raises(SauceDemoArtifactHandoffError):
        extract_verified_knowledge(state, _config())


def test_missing_validation_is_rejected(completed_workflow) -> None:
    state = completed_workflow.model_copy(update={"validation_results": ()})

    with pytest.raises(SauceDemoArtifactHandoffError):
        extract_verified_knowledge(state, _config())


def test_latest_failed_validation_is_rejected_even_after_older_pass() -> None:
    state = _recovery_state(latest_status="failed", first_status="passed")

    with pytest.raises(
        SauceDemoArtifactHandoffError,
        match="latest knowledge validation did not pass",
    ):
        extract_verified_knowledge(state, _config())


def test_malformed_older_validation_is_not_skipped(completed_workflow) -> None:
    malformed = {
        "status": "failed",
        "unknown": "runtime-secret-marker",
    }
    state = completed_workflow.model_copy(
        update={
            "validation_results": (
                malformed,
                *completed_workflow.validation_results,
            )
        }
    )

    with pytest.raises(SauceDemoArtifactHandoffError) as captured:
        extract_verified_knowledge(state, _config())

    assert "runtime-secret-marker" not in str(captured.value)


@pytest.mark.parametrize(
    "case",
    [
        "validation_workflow",
        "validation_product",
        "validation_candidate",
        "validation_evidence",
        "missing_candidate",
        "missing_evidence",
        "duplicate_candidate",
        "duplicate_evidence",
    ],
)
def test_mismatched_missing_or_ambiguous_correlations_are_rejected(
    completed_workflow, case
) -> None:
    values = json.loads(completed_workflow.model_dump_json())
    if case.startswith("validation_"):
        payload = json.loads(json.dumps(values["validation_results"][-1]))
        field = case.removeprefix("validation_") + "_id"
        if case == "validation_product":
            field = "product_id"
        elif case == "validation_evidence":
            field = "source_evidence_id"
        payload[field] = "wrong-correlation"
        values["validation_results"][-1] = payload
    elif case == "missing_candidate":
        values["knowledge_candidates"] = []
    elif case == "missing_evidence":
        values["evidence"] = []
    elif case == "duplicate_candidate":
        values["knowledge_candidates"].append(
            values["knowledge_candidates"][0]
        )
    else:
        values["evidence"].append(values["evidence"][0])
    state = WorkflowState.model_validate(values)

    with pytest.raises(SauceDemoArtifactHandoffError):
        extract_verified_knowledge(state, _config())


def test_forged_passed_snapshot_inconsistent_with_evidence_is_rejected(
    completed_workflow,
) -> None:
    values = json.loads(completed_workflow.model_dump_json())
    result = json.loads(json.dumps(values["validation_results"][-1]))
    result["verified_knowledge"]["pages"][0]["title"] = "Forged safe title"
    values["validation_results"][-1] = result
    state = WorkflowState.model_validate(values)

    with pytest.raises(SauceDemoArtifactHandoffError):
        extract_verified_knowledge(state, _config())


def test_failed_extraction_has_no_storage_call_or_generated_output(
    completed_workflow, tmp_path
) -> None:
    invalid = completed_workflow.model_copy(update={"validation_results": ()})
    storage = _RecordingStorage()
    output = tmp_path / "generated"

    with pytest.raises(SauceDemoArtifactHandoffError):
        persist_verified_knowledge(invalid, _config(), storage)
    with pytest.raises(SauceDemoArtifactHandoffError):
        generate_tests_from_verified_workflow(invalid, _config(), output)

    assert storage.saved == []
    assert not output.exists()


def test_storage_failure_is_safely_bounded(completed_workflow) -> None:
    storage = _RecordingStorage(
        error=RuntimeError("runtime-secret-marker <html>storage</html>")
    )

    with pytest.raises(SauceDemoArtifactHandoffError) as captured:
        persist_verified_knowledge(completed_workflow, _config(), storage)

    assert len(storage.saved) == 1
    assert "runtime-secret-marker" not in str(captured.value)
    assert "<html>" not in str(captured.value)


def test_generator_failure_is_safely_bounded(
    completed_workflow, tmp_path, monkeypatch
) -> None:
    def fail_generator(knowledge, output_directory):
        raise RuntimeError("runtime-secret-marker <html>generator</html>")

    monkeypatch.setattr(handoff_module, "generate_tests", fail_generator)

    with pytest.raises(SauceDemoArtifactHandoffError) as captured:
        generate_tests_from_verified_workflow(
            completed_workflow, _config(), tmp_path / "generated"
        )

    assert "runtime-secret-marker" not in str(captured.value)
    assert "<html>" not in str(captured.value)


def test_legitimate_failed_validation_recovery_latest_pass_is_accepted() -> None:
    state = _recovery_state(latest_status="passed")

    knowledge = extract_verified_knowledge(state, _config())

    latest = SauceDemoValidationResult.from_workflow_payload(
        state.validation_results[-1]
    )
    assert latest.status == "passed"
    assert knowledge.to_dict() == latest.verified_knowledge.to_dict()
    assert len(state.evidence) == 2
    assert len(state.knowledge_candidates) == 2
    assert len(state.validation_results) == 2


def test_extra_unvalidated_candidate_and_evidence_after_pass_is_rejected(
    completed_workflow,
) -> None:
    state = _append_unvalidated_pair(completed_workflow)

    with pytest.raises(
        SauceDemoArtifactHandoffError,
        match="terminal artifact correlation is incomplete or out of order",
    ):
        extract_verified_knowledge(state, _config())


def test_extra_unprocessed_evidence_after_pass_is_rejected(
    completed_workflow,
) -> None:
    values = json.loads(completed_workflow.model_dump_json())
    values["evidence"].append(
        _evidence("evidence-extra").to_workflow_payload()
    )
    state = WorkflowState.model_validate(values)

    with pytest.raises(SauceDemoArtifactHandoffError):
        extract_verified_knowledge(state, _config())


def test_candidate_without_validation_is_rejected(completed_workflow) -> None:
    state = _append_unvalidated_pair(completed_workflow)

    with pytest.raises(SauceDemoArtifactHandoffError):
        extract_verified_knowledge(state, _config())


def test_reordered_candidate_correlation_is_rejected() -> None:
    state = _recovery_state(latest_status="passed")
    values = json.loads(state.model_dump_json())
    values["knowledge_candidates"].reverse()
    reordered = WorkflowState.model_validate(values)

    with pytest.raises(SauceDemoArtifactHandoffError):
        extract_verified_knowledge(reordered, _config())


def test_validation_order_inconsistent_with_candidate_order_is_rejected() -> None:
    state = _recovery_state(latest_status="passed")
    values = json.loads(state.model_dump_json())
    values["validation_results"].reverse()
    reordered = WorkflowState.model_validate(values)

    with pytest.raises(SauceDemoArtifactHandoffError):
        extract_verified_knowledge(reordered, _config())


def test_terminal_incomplete_state_has_no_storage_or_generation_side_effect(
    completed_workflow, tmp_path
) -> None:
    state = _append_unvalidated_pair(completed_workflow)
    storage = _RecordingStorage()
    output = tmp_path / "generated"

    with pytest.raises(SauceDemoArtifactHandoffError):
        persist_verified_knowledge(state, _config(), storage)
    with pytest.raises(SauceDemoArtifactHandoffError):
        generate_tests_from_verified_workflow(state, _config(), output)

    assert storage.saved == []
    assert not output.exists()


def test_generic_pmqa_imports_remain_product_independent() -> None:
    statement = "\n".join(
        [
            "import sys",
            "import pmqa.core, pmqa.providers, pmqa.storage, pmqa.workflow",
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


class _RecordingStorage(StorageProvider):
    def __init__(self, *, error=None):
        self.saved = []
        self.error = error

    def save(self, artifact):
        self.saved.append(artifact)
        if self.error is not None:
            raise self.error

    def load(self, artifact_id):
        return None


class _CaptureRunner:
    def capture(self, actions):
        return _capture_result()


def _completed_workflow():
    config = _config()
    initial = create_saucedemo_workflow_state(
        config,
        workflow_id="workflow-1",
        product_version="1",
        goal="Build verified SauceDemo product memory",
        max_iterations=1,
        created_at=_timestamp(),
    )
    return run_saucedemo_workflow(
        config,
        initial,
        capture_runner=_CaptureRunner(),
        clock=lambda: _timestamp(1),
    )


def _append_unvalidated_pair(state):
    evidence = _evidence("evidence-extra")
    candidate = build_knowledge_candidate(evidence)
    values = json.loads(state.model_dump_json())
    values["evidence"].append(evidence.to_workflow_payload())
    values["knowledge_candidates"].append(candidate.to_workflow_payload())
    return WorkflowState.model_validate(values)


def _recovery_state(*, latest_status, first_status="failed"):
    first_evidence = _evidence("evidence-1")
    first_payload = build_knowledge_candidate(
        first_evidence
    ).to_workflow_payload()
    if first_status == "failed":
        first_payload["knowledge"]["pages"][0]["title"] = "First mismatch"
    first_candidate = SauceDemoKnowledgeCandidate.from_workflow_payload(
        first_payload
    )
    first_result = build_validation_result(
        first_candidate, first_evidence, _timestamp(1)
    )
    second_evidence = _evidence("evidence-2")
    second_payload = build_knowledge_candidate(
        second_evidence
    ).to_workflow_payload()
    if latest_status == "failed":
        second_payload["knowledge"]["pages"][0]["title"] = "Safe mismatch"
    second_candidate = SauceDemoKnowledgeCandidate.from_workflow_payload(
        second_payload
    )
    second_result = build_validation_result(
        second_candidate, second_evidence, _timestamp(2)
    )
    return WorkflowState(
        workflow_id="workflow-1",
        workflow_type="saucedemo_pmqa",
        product_id="demo",
        product_version="1",
        goal="Recovered verified knowledge",
        status=WorkflowStatus.COMPLETED,
        iteration=2,
        max_iterations=2,
        evidence=(
            first_evidence.to_workflow_payload(),
            second_evidence.to_workflow_payload(),
        ),
        knowledge_candidates=(
            first_candidate.to_workflow_payload(),
            second_candidate.to_workflow_payload(),
        ),
        validation_results=(
            first_result.to_workflow_payload(),
            second_result.to_workflow_payload(),
        ),
        step_history=tuple(
            AgentInvocation(
                agent=role,
                started_at=_timestamp(cycle),
                completed_at=_timestamp(cycle),
                status=AgentInvocationStatus.COMPLETED,
            )
            for cycle, role in (
                (1, AgentRole.EXPLORER),
                (1, AgentRole.KNOWLEDGE),
                (1, AgentRole.VALIDATOR),
                (2, AgentRole.EXPLORER),
                (2, AgentRole.KNOWLEDGE),
                (2, AgentRole.VALIDATOR),
            )
        ),
        termination_reason=TerminationReason.GOAL_COMPLETED,
        created_at=_timestamp(),
        updated_at=_timestamp(2),
    )


def _evidence(evidence_id):
    return ExplorationEvidence(
        schema_version="1",
        evidence_id=evidence_id,
        workflow_id="workflow-1",
        product_id="demo",
        source=ExplorationSource(
            source_type="browser-automation",
            tool_id="playwright.saucedemo_explore",
            capture_id="capture-" + evidence_id,
        ),
        captured_at=_timestamp(),
        pages=_capture_result().pages,
        elements=_capture_result().elements,
        locator_candidates=_capture_result().locator_candidates,
        interactions=_capture_result().interactions,
    )


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
                element_id="element.username",
                page_id="page.login",
                role="textbox",
                accessible_name="Username",
                visible_text=None,
                attributes=(
                    ObservedAttribute(name="data-test", value="username"),
                    ObservedAttribute(name="type", value="text"),
                ),
            ),
            ObservedElement(
                element_id="element.password",
                page_id="page.login",
                role="textbox",
                accessible_name="Password",
                visible_text=None,
                attributes=(
                    ObservedAttribute(name="data-test", value="password"),
                    ObservedAttribute(name="type", value="password"),
                ),
            ),
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
                locator_candidate_id="locator.username",
                element_id="element.username",
                strategy="data-test",
                value="username",
                priority=1,
            ),
            LocatorCandidateObservation(
                locator_candidate_id="locator.password",
                element_id="element.password",
                strategy="data-test",
                value="password",
                priority=1,
            ),
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


def _config():
    return DemoConfig(
        product_id="demo",
        base_url="https://example.test",
        start_path="/",
        maximum_exploration_steps=4,
        allowed_safe_actions=["inspect", "fill", "click", "stop"],
        blocked_destructive_actions=["checkout", "purchase", "delete"],
        artifact_output_location=Path("artifacts"),
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
