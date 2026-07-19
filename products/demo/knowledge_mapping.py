"""Deterministic SauceDemo evidence-to-knowledge candidate mapping."""

import hashlib
import json
from dataclasses import dataclass, fields
from typing import Any, Dict, Iterable, Mapping, Set, Type

from pmqa.models import (
    ArtifactStatus,
    Element,
    ExplorationEvidence,
    Interaction,
    KnowledgeArtifact,
    Lifecycle,
    Locator,
    Page,
)
from pmqa.security.boundary_policy import (
    WORKFLOW_STATE_PROHIBITED_KEYS,
    is_prohibited_key,
    normalize_boundary_key,
)


CANDIDATE_SCHEMA_VERSION = "1"
MAPPING_PROVENANCE = "deterministic-evidence-mapping-v1"


class KnowledgeCandidateError(ValueError):
    """Reports invalid evidence mapping or candidate envelope data."""


@dataclass(frozen=True)
class SauceDemoKnowledgeCandidate:
    """Correlates one existing KnowledgeArtifact candidate to its evidence."""

    schema_version: str
    candidate_id: str
    workflow_id: str
    product_id: str
    source_evidence_id: str
    knowledge: KnowledgeArtifact

    def to_workflow_payload(self) -> Dict[str, Any]:
        """Return fresh JSON-compatible candidate data for WorkflowState."""

        return {
            "schema_version": self.schema_version,
            "candidate_id": self.candidate_id,
            "workflow_id": self.workflow_id,
            "product_id": self.product_id,
            "source_evidence_id": self.source_evidence_id,
            "knowledge": self.knowledge.to_dict(),
        }

    @classmethod
    def from_workflow_payload(
        cls, payload: Mapping[str, Any]
    ) -> "SauceDemoKnowledgeCandidate":
        """Strictly validate and reconstruct a candidate and its knowledge."""

        try:
            cloned = json.loads(json.dumps(payload, allow_nan=False))
        except (TypeError, ValueError) as error:
            raise KnowledgeCandidateError("candidate payload must be JSON data") from error
        if not isinstance(cloned, dict):
            raise KnowledgeCandidateError("candidate payload must be an object")
        _require_exact_keys(cloned, SauceDemoKnowledgeCandidate)
        for field_name in (
            "schema_version",
            "candidate_id",
            "workflow_id",
            "product_id",
            "source_evidence_id",
        ):
            _require_nonempty_string(cloned[field_name], field_name)
        if cloned["schema_version"] != CANDIDATE_SCHEMA_VERSION:
            raise KnowledgeCandidateError("candidate schema version is unsupported")
        knowledge_payload = cloned["knowledge"]
        _validate_knowledge_payload_shape(knowledge_payload)
        try:
            knowledge = KnowledgeArtifact.from_dict(knowledge_payload)
        except (KeyError, TypeError, ValueError) as error:
            raise KnowledgeCandidateError("candidate knowledge is malformed") from error
        _validate_knowledge(knowledge)
        candidate = cls(
            schema_version=cloned["schema_version"],
            candidate_id=cloned["candidate_id"],
            workflow_id=cloned["workflow_id"],
            product_id=cloned["product_id"],
            source_evidence_id=cloned["source_evidence_id"],
            knowledge=knowledge,
        )
        _validate_candidate_correlation(candidate)
        if candidate.to_workflow_payload() != cloned:
            raise KnowledgeCandidateError("candidate payload is not canonical")
        return candidate


def build_knowledge_candidate(
    evidence: ExplorationEvidence,
) -> SauceDemoKnowledgeCandidate:
    """Map one validated evidence batch to existing NEW knowledge models."""

    lifecycle = Lifecycle(ArtifactStatus.NEW, None)
    pages = [
        Page(
            id=item.page_id,
            lifecycle=lifecycle,
            url=item.url,
            title=item.title,
            structural_fingerprint=item.structural_fingerprint,
        )
        for item in evidence.pages
    ]
    elements = [
        Element(
            id=item.element_id,
            lifecycle=lifecycle,
            page_id=item.page_id,
            role=item.role,
            accessible_name=item.accessible_name,
            visible_text=item.visible_text,
            attributes=_map_attributes(item.attributes),
        )
        for item in evidence.elements
    ]
    locators = [
        Locator(
            id=item.locator_candidate_id,
            lifecycle=lifecycle,
            element_id=item.element_id,
            strategy=item.strategy,
            value=item.value,
            priority=item.priority,
        )
        for item in evidence.locator_candidates
    ]
    interactions = [
        Interaction(
            id=item.interaction_id,
            lifecycle=lifecycle,
            source_page_id=item.source_page_id,
            target_element_id=item.target_element_id,
            action=item.action,
            expected_outcome_type=item.outcome_type,
            expected_outcome_value=item.outcome_value,
        )
        for item in evidence.interactions
    ]
    knowledge = KnowledgeArtifact(
        artifact_id=_artifact_id(
            evidence.workflow_id, evidence.product_id, evidence.evidence_id
        ),
        product_id=evidence.product_id,
        reasoning_provenance=MAPPING_PROVENANCE,
        pages=pages,
        elements=elements,
        locators=locators,
        interactions=interactions,
    )
    candidate = SauceDemoKnowledgeCandidate(
        schema_version=CANDIDATE_SCHEMA_VERSION,
        candidate_id=_candidate_id(
            evidence.workflow_id, evidence.product_id, evidence.evidence_id
        ),
        workflow_id=evidence.workflow_id,
        product_id=evidence.product_id,
        source_evidence_id=evidence.evidence_id,
        knowledge=knowledge,
    )
    _validate_knowledge(knowledge)
    return candidate


def _map_attributes(attributes) -> Dict[str, str]:
    mapped: Dict[str, str] = {}
    normalized: Set[str] = set()
    for attribute in attributes:
        normalized_name = normalize_boundary_key(attribute.name)
        if normalized_name in normalized:
            raise KnowledgeCandidateError("element attribute names are ambiguous")
        if is_prohibited_key(attribute.name, WORKFLOW_STATE_PROHIBITED_KEYS):
            raise KnowledgeCandidateError("element attribute name is prohibited")
        normalized.add(normalized_name)
        mapped[attribute.name] = attribute.value
    return mapped


def _validate_candidate_correlation(candidate: SauceDemoKnowledgeCandidate) -> None:
    if candidate.knowledge.product_id != candidate.product_id:
        raise KnowledgeCandidateError("candidate knowledge product is inconsistent")
    if candidate.candidate_id != _candidate_id(
        candidate.workflow_id,
        candidate.product_id,
        candidate.source_evidence_id,
    ):
        raise KnowledgeCandidateError("candidate ID is inconsistent")
    if candidate.knowledge.artifact_id != _artifact_id(
        candidate.workflow_id,
        candidate.product_id,
        candidate.source_evidence_id,
    ):
        raise KnowledgeCandidateError("knowledge artifact ID is inconsistent")


def _validate_knowledge_payload_shape(value: Any) -> None:
    if not isinstance(value, dict):
        raise KnowledgeCandidateError("candidate knowledge must be an object")
    _require_exact_keys(value, KnowledgeArtifact)
    for collection_name, model_type in (
        ("pages", Page),
        ("elements", Element),
        ("locators", Locator),
        ("interactions", Interaction),
    ):
        items = value[collection_name]
        if not isinstance(items, list):
            raise KnowledgeCandidateError("candidate knowledge collections must be lists")
        for item in items:
            if not isinstance(item, dict):
                raise KnowledgeCandidateError("candidate knowledge item must be an object")
            _require_exact_keys(item, model_type)
            lifecycle = item["lifecycle"]
            if not isinstance(lifecycle, dict):
                raise KnowledgeCandidateError("candidate lifecycle must be an object")
            _require_exact_keys(lifecycle, Lifecycle)


def _validate_knowledge(knowledge: KnowledgeArtifact) -> None:
    for field_name in ("artifact_id", "product_id", "reasoning_provenance"):
        _require_nonempty_string(getattr(knowledge, field_name), field_name)
    if knowledge.reasoning_provenance != MAPPING_PROVENANCE:
        raise KnowledgeCandidateError("candidate mapping provenance is invalid")
    for item in _knowledge_items(knowledge):
        if item.lifecycle != Lifecycle(ArtifactStatus.NEW, None):
            raise KnowledgeCandidateError("candidate lifecycle must be new and unverified")
    _require_unique((item.id for item in knowledge.pages), "page IDs")
    _require_unique((item.id for item in knowledge.elements), "element IDs")
    _require_unique((item.id for item in knowledge.locators), "locator IDs")
    _require_unique((item.id for item in knowledge.interactions), "interaction IDs")
    page_ids = {item.id for item in knowledge.pages}
    element_ids = {item.id for item in knowledge.elements}
    for page in knowledge.pages:
        for value in (page.id, page.url, page.title, page.structural_fingerprint):
            _require_nonempty_string(value, "page field")
    for element in knowledge.elements:
        for value in (element.id, element.page_id, element.role, element.accessible_name):
            _require_nonempty_string(value, "element field")
        if element.visible_text is not None and not isinstance(element.visible_text, str):
            raise KnowledgeCandidateError("element visible text must be a string")
        if element.page_id not in page_ids:
            raise KnowledgeCandidateError("element references missing page")
        if not isinstance(element.attributes, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in element.attributes.items()
        ):
            raise KnowledgeCandidateError("element attributes must contain strings")
        _map_attributes(
            tuple(_Attribute(name=key, value=value) for key, value in element.attributes.items())
        )
    for locator in knowledge.locators:
        for value in (locator.id, locator.element_id, locator.strategy, locator.value):
            _require_nonempty_string(value, "locator field")
        if type(locator.priority) is not int or locator.priority < 1:
            raise KnowledgeCandidateError("locator priority is invalid")
        if locator.element_id not in element_ids:
            raise KnowledgeCandidateError("locator references missing element")
    for interaction in knowledge.interactions:
        for value in (
            interaction.id,
            interaction.source_page_id,
            interaction.target_element_id,
            interaction.action,
            interaction.expected_outcome_type,
            interaction.expected_outcome_value,
        ):
            _require_nonempty_string(value, "interaction field")
        if interaction.source_page_id not in page_ids:
            raise KnowledgeCandidateError("interaction references missing page")
        if interaction.target_element_id not in element_ids:
            raise KnowledgeCandidateError("interaction references missing element")


@dataclass(frozen=True)
class _Attribute:
    name: str
    value: str


def _knowledge_items(knowledge: KnowledgeArtifact):
    return (
        *knowledge.pages,
        *knowledge.elements,
        *knowledge.locators,
        *knowledge.interactions,
    )


def _require_exact_keys(value: Mapping[str, Any], model_type: Type) -> None:
    expected = {item.name for item in fields(model_type)}
    if set(value) != expected:
        raise KnowledgeCandidateError("candidate contains unexpected or missing fields")


def _require_nonempty_string(value: Any, label: str) -> None:
    if not isinstance(value, str) or not value:
        raise KnowledgeCandidateError(f"{label} must be a non-empty string")


def _require_unique(values: Iterable[str], label: str) -> None:
    items = tuple(values)
    if len(items) != len(set(items)):
        raise KnowledgeCandidateError(f"duplicate {label} are not allowed")


def _candidate_id(workflow_id: str, product_id: str, evidence_id: str) -> str:
    return "candidate.saucedemo." + _correlation_digest(
        "candidate", workflow_id, product_id, evidence_id
    )


def _artifact_id(workflow_id: str, product_id: str, evidence_id: str) -> str:
    return "knowledge.saucedemo." + _correlation_digest(
        "knowledge", workflow_id, product_id, evidence_id
    )


def _correlation_digest(
    identity: str, workflow_id: str, product_id: str, evidence_id: str
) -> str:
    value = "\0".join(
        (
            CANDIDATE_SCHEMA_VERSION,
            identity,
            workflow_id,
            product_id,
            evidence_id,
        )
    ).encode()
    return hashlib.sha256(value).hexdigest()[:24]
