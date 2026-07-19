"""Tests for deterministic SauceDemo knowledge-candidate mapping."""

import json
from datetime import datetime, timezone

import pytest

from pmqa.models import (
    ArtifactStatus,
    Element,
    ExplorationEvidence,
    ExplorationSource,
    Interaction,
    InteractionObservation,
    Locator,
    LocatorCandidateObservation,
    ObservedAttribute,
    ObservedElement,
    ObservedPage,
    Page,
)
from pmqa.workflow import WorkflowState
from products.demo.knowledge_mapping import (
    CANDIDATE_SCHEMA_VERSION,
    MAPPING_PROVENANCE,
    KnowledgeCandidateError,
    SauceDemoKnowledgeCandidate,
    build_knowledge_candidate,
)


def test_observations_map_to_existing_knowledge_models() -> None:
    evidence = _evidence()

    candidate = build_knowledge_candidate(evidence)
    knowledge = candidate.knowledge

    assert isinstance(knowledge.pages[0], Page)
    assert knowledge.pages[0].id == evidence.pages[0].page_id
    assert knowledge.pages[0].url == evidence.pages[0].url
    assert knowledge.pages[0].title == evidence.pages[0].title
    assert (
        knowledge.pages[0].structural_fingerprint
        == evidence.pages[0].structural_fingerprint
    )
    assert isinstance(knowledge.elements[0], Element)
    assert knowledge.elements[0].id == evidence.elements[0].element_id
    assert knowledge.elements[0].page_id == evidence.elements[0].page_id
    assert knowledge.elements[0].attributes == {
        "data-test": "login-button",
        "type": "submit",
    }
    assert isinstance(knowledge.locators[0], Locator)
    assert knowledge.locators[0].id == (
        evidence.locator_candidates[0].locator_candidate_id
    )
    assert knowledge.locators[0].strategy == "data-test"
    assert isinstance(knowledge.interactions[0], Interaction)
    assert knowledge.interactions[0].expected_outcome_type == "navigation"
    assert knowledge.interactions[0].expected_outcome_value == "/inventory.html"
    assert knowledge.reasoning_provenance == MAPPING_PROVENANCE


def test_all_candidate_lifecycles_are_new_and_unverified() -> None:
    knowledge = build_knowledge_candidate(_evidence()).knowledge

    items = [
        *knowledge.pages,
        *knowledge.elements,
        *knowledge.locators,
        *knowledge.interactions,
    ]
    assert items
    assert all(item.lifecycle.state is ArtifactStatus.NEW for item in items)
    assert all(item.lifecycle.last_verified is None for item in items)


def test_attribute_mapping_does_not_retain_or_mutate_source() -> None:
    evidence = _evidence()
    original_json = evidence.model_dump_json()

    candidate = build_knowledge_candidate(evidence)
    candidate.knowledge.elements[0].attributes["data-test"] = "changed"

    assert evidence.elements[0].attributes[0].value == "login-button"
    assert evidence.model_dump_json() == original_json


def test_ambiguous_attribute_names_are_rejected_without_overwrite() -> None:
    original = _evidence()
    element = original.elements[0].model_copy(
        update={
            "attributes": (
                ObservedAttribute(name="data-test", value="one"),
                ObservedAttribute(name="data_test", value="two"),
            )
        }
    )
    evidence = _evidence(elements=(element, original.elements[1]))

    with pytest.raises(KnowledgeCandidateError, match="ambiguous"):
        build_knowledge_candidate(evidence)


def test_candidate_round_trips_through_standard_json_and_existing_artifact() -> None:
    candidate = build_knowledge_candidate(_evidence())
    payload = candidate.to_workflow_payload()
    decoded = json.loads(json.dumps(payload))

    restored = SauceDemoKnowledgeCandidate.from_workflow_payload(decoded)

    assert restored == candidate
    assert type(restored.knowledge) is type(candidate.knowledge)
    assert restored.knowledge.to_dict() == candidate.knowledge.to_dict()
    assert restored.schema_version == CANDIDATE_SCHEMA_VERSION


def test_candidate_parser_does_not_retain_mutable_payload_references() -> None:
    payload = build_knowledge_candidate(_evidence()).to_workflow_payload()
    restored = SauceDemoKnowledgeCandidate.from_workflow_payload(payload)

    payload["knowledge"]["pages"][0]["title"] = "Changed"
    payload["knowledge"]["elements"][0]["attributes"]["data-test"] = "changed"

    assert restored.knowledge.pages[0].title == "Login"
    assert restored.knowledge.elements[0].attributes["data-test"] == "login-button"


def test_candidate_and_artifact_ids_are_deterministic_and_correlated() -> None:
    first = build_knowledge_candidate(_evidence())
    second = build_knowledge_candidate(_evidence())
    different = build_knowledge_candidate(_evidence(evidence_id="evidence-2"))

    assert first.candidate_id == second.candidate_id
    assert first.knowledge.artifact_id == second.knowledge.artifact_id
    assert first.to_workflow_payload() == second.to_workflow_payload()
    assert first.candidate_id != different.candidate_id
    assert first.knowledge.artifact_id != different.knowledge.artifact_id
    assert "https" not in first.candidate_id
    assert "Login" not in first.candidate_id


def test_candidate_payload_is_accepted_and_deeply_frozen_by_workflow_state() -> None:
    candidate = build_knowledge_candidate(_evidence())
    state = _state(knowledge_candidates=[candidate.to_workflow_payload()])

    restored = SauceDemoKnowledgeCandidate.from_workflow_payload(
        state.knowledge_candidates[0]
    )

    assert restored == candidate
    with pytest.raises(TypeError, match="immutable"):
        state.knowledge_candidates[0]["candidate_id"] = "changed"
    with pytest.raises(TypeError, match="immutable"):
        state.knowledge_candidates[0]["knowledge"]["pages"][0]["title"] = "changed"
    with pytest.raises(AttributeError):
        state.knowledge_candidates[0]["knowledge"]["pages"].append({})


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.update({"unexpected": True}),
        lambda payload: payload.update({"schema_version": "2"}),
        lambda payload: payload.update({"candidate_id": "candidate.wrong"}),
        lambda payload: payload["knowledge"].update({"artifact_id": "knowledge.wrong"}),
        lambda payload: payload["knowledge"].update({"product_id": "other"}),
        lambda payload: payload["knowledge"]["pages"][0]["lifecycle"].update(
            {"state": "verified", "last_verified": "2026-01-01T00:00:00Z"}
        ),
        lambda payload: payload["knowledge"]["pages"][0].update(
            {"unexpected": True}
        ),
    ],
)
def test_candidate_parser_rejects_noncanonical_payloads(mutation) -> None:
    payload = build_knowledge_candidate(_evidence()).to_workflow_payload()
    mutation(payload)

    with pytest.raises(KnowledgeCandidateError):
        SauceDemoKnowledgeCandidate.from_workflow_payload(payload)


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
        "captured_at": datetime(2026, 7, 19, 15, tzinfo=timezone.utc),
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
                attributes=(
                    ObservedAttribute(name="data-test", value="login-button"),
                    ObservedAttribute(name="type", value="submit"),
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


def _state(**updates) -> WorkflowState:
    values = {
        "workflow_id": "workflow-1",
        "workflow_type": "exploration",
        "product_id": "demo",
        "product_version": "1",
        "goal": "Build candidate knowledge",
        "max_iterations": 3,
        "evidence": [_evidence().to_workflow_payload()],
        "created_at": datetime(2026, 7, 19, 15, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 7, 19, 15, tzinfo=timezone.utc),
    }
    values.update(updates)
    return WorkflowState(**values)
