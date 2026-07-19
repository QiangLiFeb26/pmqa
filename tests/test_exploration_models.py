"""Tests for immutable, runtime-free exploration evidence contracts."""

import json
import subprocess
import sys
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from pmqa.models import (
    ExplorationEvidence,
    ExplorationSource,
    InteractionObservation,
    LocatorCandidateObservation,
    ObservedAttribute,
    ObservedElement,
    ObservedPage,
)
from pmqa.security.boundary_policy import WORKFLOW_STATE_PROHIBITED_KEYS
from pmqa.workflow import WorkflowState


def test_complete_evidence_round_trips_through_standard_json() -> None:
    evidence = _evidence()

    payload = evidence.to_workflow_payload()
    decoded = json.loads(json.dumps(payload))
    restored = ExplorationEvidence.from_workflow_payload(decoded)

    assert restored == evidence
    assert restored.source.tool_id == "exploration.capture"
    assert restored.captured_at == datetime(2026, 7, 19, 12, tzinfo=timezone.utc)
    assert payload == evidence.to_workflow_payload()
    assert "locator_candidates" in payload
    assert "locator" not in payload


def test_nested_contract_collections_are_deeply_immutable() -> None:
    evidence = _evidence()

    with pytest.raises(ValidationError, match="frozen"):
        evidence.evidence_id = "changed"
    with pytest.raises(AttributeError):
        evidence.pages.append(_page())
    with pytest.raises(ValidationError, match="frozen"):
        evidence.elements[0].attributes[0].value = "changed"
    with pytest.raises(ValidationError, match="duplicate page IDs"):
        evidence.model_copy(update={"pages": [*_pages(), _page()]})


def test_mutating_constructor_inputs_does_not_change_evidence() -> None:
    payload = _evidence().model_dump(mode="python")
    pages = list(payload["pages"])
    attribute = {"name": "data-test", "value": "login-button"}
    elements = [
        {
            "element_id": "element.login",
            "page_id": "page.login",
            "role": "button",
            "accessible_name": "Login",
            "visible_text": "Login",
            "attributes": [attribute],
        }
    ]
    payload.update({"pages": pages, "elements": elements})

    evidence = ExplorationEvidence.model_validate(payload)
    pages.clear()
    elements.clear()
    attribute["value"] = "changed"

    assert evidence.pages == (_page(),)
    assert evidence.elements[0].attributes[0].value == "login-button"


@pytest.mark.parametrize(
    "field", ["pages", "elements", "locator_candidates", "interactions"]
)
def test_duplicate_entity_ids_are_rejected(field: str) -> None:
    original = getattr(_evidence(), field)
    with pytest.raises(ValidationError, match="duplicate"):
        _evidence(**{field: [*original, *original]})


@pytest.mark.parametrize(
    ("updates", "expected"),
    [
        (
            {"elements": [ObservedElement(
                element_id="element.login",
                page_id="page.missing",
                role="button",
                accessible_name="Login",
            )]},
            "missing page",
        ),
        (
            {"locator_candidates": [LocatorCandidateObservation(
                locator_candidate_id="candidate.login",
                element_id="element.missing",
                strategy="data-test",
                value="login-button",
                priority=1,
            )]},
            "missing element",
        ),
        (
            {"interactions": [InteractionObservation(
                interaction_id="interaction.login",
                source_page_id="page.missing",
                target_element_id="element.login",
                action="click",
                outcome_type="navigation",
                outcome_value="/inventory.html",
            )]},
            "missing page",
        ),
        (
            {"interactions": [InteractionObservation(
                interaction_id="interaction.login",
                source_page_id="page.login",
                target_element_id="element.missing",
                action="click",
                outcome_type="navigation",
                outcome_value="/inventory.html",
            )]},
            "missing element",
        ),
    ],
)
def test_missing_relationship_references_are_rejected(updates, expected: str) -> None:
    with pytest.raises(ValidationError, match=expected):
        _evidence(**updates)


def test_unknown_fields_are_rejected_at_every_contract_level() -> None:
    payload = _evidence().to_workflow_payload()
    payload["unexpected"] = True
    payload["pages"][0]["unexpected"] = True

    with pytest.raises(ValidationError) as captured:
        ExplorationEvidence.from_workflow_payload(payload)

    assert "unexpected" in str(captured.value)


def test_invalid_priority_and_naive_timestamp_are_rejected() -> None:
    with pytest.raises(ValidationError, match="priority"):
        LocatorCandidateObservation(
            locator_candidate_id="candidate.login",
            element_id="element.login",
            strategy="data-test",
            value="login-button",
            priority=0,
        )
    with pytest.raises(ValidationError, match="timezone"):
        _evidence(captured_at=datetime(2026, 7, 19, 12))


@pytest.mark.parametrize(
    "field", ["schema_version", "evidence_id", "workflow_id", "product_id"]
)
def test_empty_required_identifiers_are_rejected(field: str) -> None:
    with pytest.raises(ValidationError, match=field):
        _evidence(**{field: ""})


def test_serialized_evidence_is_accepted_by_generic_workflow_state() -> None:
    evidence = _evidence()
    state = WorkflowState(
        workflow_id=evidence.workflow_id,
        workflow_type="exploration",
        product_id=evidence.product_id,
        product_version="1",
        goal="Collect exploration evidence",
        max_iterations=1,
        evidence=[evidence.to_workflow_payload()],
        created_at=evidence.captured_at,
        updated_at=evidence.captured_at,
    )

    restored = ExplorationEvidence.from_workflow_payload(state.evidence[0])

    assert restored == evidence


def test_runtime_objects_are_rejected_without_leaking_their_values() -> None:
    class FakeBrowser:
        def __repr__(self) -> str:
            return "FakeBrowser(secret=runtime-marker)"

    payload = _evidence().to_workflow_payload()
    payload["source"]["tool_id"] = FakeBrowser()

    with pytest.raises(ValidationError) as captured:
        ExplorationEvidence.from_workflow_payload(payload)

    assert "runtime-marker" not in str(captured.value)


@pytest.mark.parametrize("prohibited_name", sorted(WORKFLOW_STATE_PROHIBITED_KEYS))
def test_every_workflow_prohibited_key_is_rejected_as_attribute_name(
    prohibited_name: str,
) -> None:
    with pytest.raises(ValidationError, match="attribute name is prohibited"):
        ObservedAttribute(name=prohibited_name, value="runtime-secret-marker")


@pytest.mark.parametrize(
    "prohibited_variant", ["API-Key", "browser context", "Provider-Instance"]
)
def test_prohibited_attribute_name_variants_use_shared_normalization(
    prohibited_variant: str,
) -> None:
    with pytest.raises(ValidationError, match="attribute name is prohibited"):
        ObservedAttribute(name=prohibited_variant, value="safe-marker")


def test_prohibited_attribute_error_does_not_echo_its_value() -> None:
    with pytest.raises(ValidationError) as captured:
        ObservedAttribute(name="password", value="runtime-secret-marker")

    assert "attribute name is prohibited" in str(captured.value)
    assert "runtime-secret-marker" not in str(captured.value)


def test_safe_attribute_names_and_values_remain_valid() -> None:
    attributes = (
        ObservedAttribute(name="data-test", value="login-button"),
        ObservedAttribute(name="type", value="password"),
    )

    evidence = _evidence(
        elements=[_elements()[0].model_copy(update={"attributes": attributes})]
    )

    assert evidence.elements[0].attributes == attributes
    assert evidence.to_workflow_payload()["elements"][0]["attributes"][1] == {
        "name": "type",
        "value": "password",
    }


def test_prohibited_semantic_attribute_cannot_reach_workflow_payload() -> None:
    payload = _evidence().to_workflow_payload()
    payload["elements"][0]["attributes"].append(
        {"name": "browser_context", "value": "runtime-secret-marker"}
    )

    with pytest.raises(ValidationError) as captured:
        ExplorationEvidence.from_workflow_payload(payload)

    assert "attribute name is prohibited" in str(captured.value)
    assert "runtime-secret-marker" not in str(captured.value)


def test_prohibited_semantic_attribute_cannot_build_workflow_state_evidence() -> None:
    with pytest.raises(ValidationError, match="attribute name is prohibited"):
        element = _elements()[0].model_copy(
            update={
                "attributes": [
                    {"name": "api_key", "value": "runtime-secret-marker"}
                ]
            }
        )
        evidence = _evidence(elements=[element])
        WorkflowState(
            workflow_id=evidence.workflow_id,
            workflow_type="exploration",
            product_id=evidence.product_id,
            product_version="1",
            goal="Collect exploration evidence",
            max_iterations=1,
            evidence=[evidence.to_workflow_payload()],
            created_at=evidence.captured_at,
            updated_at=evidence.captured_at,
        )


def test_generic_evidence_import_has_no_runtime_or_product_side_effects() -> None:
    statement = "\n".join(
        [
            "import sys",
            "from pmqa.models.exploration import ExplorationEvidence",
            "assert ExplorationEvidence",
            "for prefix in ('products', 'playwright', 'langgraph', "
            "'pmqa.providers', 'pmqa.runtime', 'pmqa.orchestration'):",
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


def _evidence(**updates) -> ExplorationEvidence:
    values = {
        "schema_version": "1",
        "evidence_id": "evidence.capture-1",
        "workflow_id": "workflow-1",
        "product_id": "product-1",
        "source": ExplorationSource(
            source_type="browser-automation",
            tool_id="exploration.capture",
            capture_id="capture-1",
        ),
        "captured_at": datetime(2026, 7, 19, 12, tzinfo=timezone.utc),
        "pages": _pages(),
        "elements": _elements(),
        "locator_candidates": _locator_candidates(),
        "interactions": _interactions(),
    }
    values.update(updates)
    return ExplorationEvidence(**values)


def _page() -> ObservedPage:
    return ObservedPage(
        page_id="page.login",
        url="https://example.test/",
        title="Login",
        structural_fingerprint="sha256:abc",
    )


def _pages():
    return [_page()]


def _elements():
    return [
        ObservedElement(
            element_id="element.login",
            page_id="page.login",
            role="button",
            accessible_name="Login",
            visible_text="Login",
            attributes=(ObservedAttribute(name="data-test", value="login-button"),),
        )
    ]


def _locator_candidates():
    return [
        LocatorCandidateObservation(
            locator_candidate_id="candidate.login",
            element_id="element.login",
            strategy="data-test",
            value="login-button",
            priority=1,
        )
    ]


def _interactions():
    return [
        InteractionObservation(
            interaction_id="interaction.login",
            source_page_id="page.login",
            target_element_id="element.login",
            action="click",
            outcome_type="navigation",
            outcome_value="/inventory.html",
        )
    ]
