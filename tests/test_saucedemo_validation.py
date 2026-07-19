"""Tests for strict deterministic SauceDemo validation-result contracts."""

import json
from datetime import datetime, timedelta, timezone

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
from pmqa.workflow import WorkflowState
from products.demo.knowledge_mapping import build_knowledge_candidate
from products.demo.validation import (
    CANDIDATE_MATCH_CHECK,
    VALIDATION_SCHEMA_VERSION,
    SauceDemoValidationResult,
    ValidationResultError,
    build_validation_result,
)


def test_validation_result_round_trips_with_exact_envelope_fields() -> None:
    result = _result()
    payload = result.to_workflow_payload()

    restored = SauceDemoValidationResult.from_workflow_payload(
        json.loads(json.dumps(payload))
    )

    assert set(payload) == {
        "schema_version",
        "validation_id",
        "workflow_id",
        "product_id",
        "candidate_id",
        "source_evidence_id",
        "status",
        "validated_at",
        "checks",
        "verified_knowledge",
    }
    assert restored.to_workflow_payload() == payload
    assert restored.schema_version == VALIDATION_SCHEMA_VERSION
    assert restored.checks[0].code == CANDIDATE_MATCH_CHECK
    assert isinstance(restored.verified_knowledge, KnowledgeArtifact)


def test_validation_ids_are_deterministic_and_candidate_correlated() -> None:
    first = _result()
    second = _result()
    evidence = _evidence(evidence_id="evidence-2")
    different = build_validation_result(
        build_knowledge_candidate(evidence), evidence, _timestamp(1)
    )

    assert first == second
    assert first.validation_id == second.validation_id
    assert first.validation_id != different.validation_id
    assert "Login" not in first.validation_id
    assert "https" not in first.validation_id


def test_passed_snapshot_reuses_models_and_does_not_mutate_new_candidate() -> None:
    candidate = build_knowledge_candidate(_evidence())
    before = candidate.to_workflow_payload()

    result = build_validation_result(candidate, _evidence(), _timestamp(1))

    assert result.status == "passed"
    assert isinstance(result.verified_knowledge, KnowledgeArtifact)
    items = _items(result.verified_knowledge)
    assert items
    assert all(item.lifecycle.state is ArtifactStatus.VERIFIED for item in items)
    assert all(
        item.lifecycle.last_verified == _timestamp(1).isoformat()
        for item in items
    )
    assert all(
        item.lifecycle.state is ArtifactStatus.NEW
        and item.lifecycle.last_verified is None
        for item in _items(candidate.knowledge)
    )
    assert candidate.to_workflow_payload() == before


def test_structurally_valid_content_mismatch_is_failed_without_snapshot() -> None:
    evidence = _evidence()
    payload = build_knowledge_candidate(evidence).to_workflow_payload()
    payload["knowledge"]["pages"][0]["title"] = "Safely changed title"
    candidate = _candidate(payload)

    result = build_validation_result(candidate, evidence, _timestamp(1))

    assert result.status == "failed"
    assert result.checks[0].status == "failed"
    assert result.verified_knowledge is None
    assert SauceDemoValidationResult.from_workflow_payload(
        result.to_workflow_payload()
    ) == result


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.update({"unexpected": True}),
        lambda payload: payload.pop("checks"),
        lambda payload: payload.update({"schema_version": "2"}),
        lambda payload: payload.update({"validation_id": "validation.wrong"}),
        lambda payload: payload.update({"status": "pending"}),
        lambda payload: payload.update({"validated_at": "2026-07-19T15:00:01"}),
        lambda payload: payload.update({"validated_at": "not-a-time"}),
        lambda payload: payload.update({"checks": []}),
        lambda payload: payload["checks"][0].update({"code": "raw_diff"}),
        lambda payload: payload["checks"][0].update({"status": "unknown"}),
        lambda payload: payload["checks"].append(dict(payload["checks"][0])),
        lambda payload: payload.update({"verified_knowledge": None}),
        lambda payload: payload["verified_knowledge"]["pages"][0][
            "lifecycle"
        ].update({"state": "new", "last_verified": None}),
        lambda payload: payload["verified_knowledge"]["elements"][0][
            "attributes"
        ].update({"browser_context": "safe-marker"}),
    ],
)
def test_parser_rejects_noncanonical_or_invalid_passed_results(mutation) -> None:
    payload = _result().to_workflow_payload()
    mutation(payload)

    with pytest.raises(ValidationResultError):
        SauceDemoValidationResult.from_workflow_payload(payload)


def test_failed_result_forbids_verified_knowledge() -> None:
    evidence = _evidence()
    payload = build_knowledge_candidate(evidence).to_workflow_payload()
    payload["knowledge"]["elements"][0]["visible_text"] = "Mismatch"
    failed = build_validation_result(
        _candidate(payload), evidence, _timestamp(1)
    ).to_workflow_payload()
    failed["verified_knowledge"] = _result().verified_knowledge.to_dict()

    with pytest.raises(ValidationResultError):
        SauceDemoValidationResult.from_workflow_payload(failed)


def test_parser_does_not_retain_mutable_verified_payload_references() -> None:
    payload = _result().to_workflow_payload()
    restored = SauceDemoValidationResult.from_workflow_payload(payload)

    payload["verified_knowledge"]["pages"][0]["title"] = "Changed"
    payload["verified_knowledge"]["elements"][0]["attributes"]["data-test"] = "x"

    assert restored.verified_knowledge.pages[0].title == "Login"
    assert restored.verified_knowledge.elements[0].attributes["data-test"] == "login"


def test_result_payload_is_accepted_and_deeply_frozen_by_workflow_state() -> None:
    state = _state(validation_results=[_result().to_workflow_payload()])

    with pytest.raises(TypeError, match="immutable"):
        state.validation_results[0]["status"] = "failed"
    with pytest.raises(TypeError, match="immutable"):
        state.validation_results[0]["verified_knowledge"]["pages"][0][
            "title"
        ] = "Changed"


def test_naive_builder_timestamp_is_rejected() -> None:
    evidence = _evidence()

    with pytest.raises(ValidationResultError):
        build_validation_result(
            build_knowledge_candidate(evidence),
            evidence,
            datetime(2026, 7, 19, 15),
        )


def test_parser_rejects_runtime_objects() -> None:
    payload = _result().to_workflow_payload()
    payload["checks"][0]["runtime"] = object()

    with pytest.raises(ValidationResultError):
        SauceDemoValidationResult.from_workflow_payload(payload)


def _result():
    evidence = _evidence()
    return build_validation_result(
        build_knowledge_candidate(evidence), evidence, _timestamp(1)
    )


def _candidate(payload):
    from products.demo.knowledge_mapping import SauceDemoKnowledgeCandidate

    return SauceDemoKnowledgeCandidate.from_workflow_payload(payload)


def _items(knowledge):
    return (
        *knowledge.pages,
        *knowledge.elements,
        *knowledge.locators,
        *knowledge.interactions,
    )


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


def _state(**updates) -> WorkflowState:
    values = {
        "workflow_id": "workflow-1",
        "workflow_type": "exploration",
        "product_id": "demo",
        "product_version": "1",
        "goal": "Validate candidate knowledge",
        "max_iterations": 3,
        "evidence": [_evidence().to_workflow_payload()],
        "knowledge_candidates": [
            build_knowledge_candidate(_evidence()).to_workflow_payload()
        ],
        "created_at": _timestamp(),
        "updated_at": _timestamp(),
    }
    values.update(updates)
    return WorkflowState(**values)


def _timestamp(seconds=0) -> datetime:
    return datetime(2026, 7, 19, 15, tzinfo=timezone.utc) + timedelta(
        seconds=seconds
    )
