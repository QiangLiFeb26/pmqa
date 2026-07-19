"""Immutable, runtime-free contracts for structured exploration evidence."""

from datetime import datetime
from typing import Any, Dict, Iterable, Mapping, Optional, Set, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _EvidenceContract(BaseModel):
    """Base contract with validated copying and immutable typed fields."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
    )

    def model_copy(
        self,
        *,
        update: Optional[Dict[str, Any]] = None,
        deep: bool = False,
    ) -> "_EvidenceContract":
        """Return a revalidated copy so updates cannot bypass the contract."""

        _ = deep
        values = self.model_dump(mode="python")
        values.update(update or {})
        return type(self).model_validate(values)


class ExplorationSource(_EvidenceContract):
    """Attributes an evidence batch to one capture tool invocation."""

    source_type: str = Field(min_length=1)
    tool_id: str = Field(min_length=1)
    capture_id: str = Field(min_length=1)


class ObservedPage(_EvidenceContract):
    """Records stable, runtime-free facts observed about one page."""

    page_id: str = Field(min_length=1)
    url: str = Field(min_length=1)
    title: str = Field(min_length=1)
    structural_fingerprint: str = Field(min_length=1)


class ObservedAttribute(_EvidenceContract):
    """Records one safe element attribute without an unrestricted mapping."""

    name: str = Field(min_length=1)
    value: str


class ObservedElement(_EvidenceContract):
    """Records accessible, serializable facts observed about one element."""

    element_id: str = Field(min_length=1)
    page_id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    accessible_name: str = Field(min_length=1)
    visible_text: Optional[str] = None
    attributes: Tuple[ObservedAttribute, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_unique_attribute_names(self) -> "ObservedElement":
        """Reject ambiguous duplicate attribute observations."""

        _require_unique(
            (attribute.name for attribute in self.attributes),
            "attribute names",
        )
        return self


class LocatorCandidateObservation(_EvidenceContract):
    """Records a serializable strategy candidate for an observed element."""

    locator_candidate_id: str = Field(min_length=1)
    element_id: str = Field(min_length=1)
    strategy: str = Field(min_length=1)
    value: str = Field(min_length=1)
    priority: int = Field(ge=1)


class InteractionObservation(_EvidenceContract):
    """Records one action and its observed outcome without runtime handles."""

    interaction_id: str = Field(min_length=1)
    source_page_id: str = Field(min_length=1)
    target_element_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    outcome_type: str = Field(min_length=1)
    outcome_value: str = Field(min_length=1)


class ExplorationEvidence(_EvidenceContract):
    """Aggregates one correlated batch of structured exploration evidence."""

    schema_version: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    source: ExplorationSource
    captured_at: datetime
    pages: Tuple[ObservedPage, ...] = Field(default_factory=tuple)
    elements: Tuple[ObservedElement, ...] = Field(default_factory=tuple)
    locator_candidates: Tuple[LocatorCandidateObservation, ...] = Field(
        default_factory=tuple
    )
    interactions: Tuple[InteractionObservation, ...] = Field(default_factory=tuple)

    @field_validator("captured_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        """Require an unambiguous capture time."""

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("captured_at must include timezone information")
        return value

    @model_validator(mode="after")
    def validate_relationships(self) -> "ExplorationEvidence":
        """Reject duplicate IDs and references outside this evidence batch."""

        page_ids = _unique_ids(
            (page.page_id for page in self.pages), "page IDs"
        )
        element_ids = _unique_ids(
            (element.element_id for element in self.elements), "element IDs"
        )
        _require_unique(
            (
                candidate.locator_candidate_id
                for candidate in self.locator_candidates
            ),
            "locator candidate IDs",
        )
        _require_unique(
            (interaction.interaction_id for interaction in self.interactions),
            "interaction IDs",
        )

        for element in self.elements:
            if element.page_id not in page_ids:
                raise ValueError(
                    f"element {element.element_id!r} references missing page "
                    f"{element.page_id!r}"
                )
        for candidate in self.locator_candidates:
            if candidate.element_id not in element_ids:
                raise ValueError(
                    f"locator candidate {candidate.locator_candidate_id!r} "
                    f"references missing element {candidate.element_id!r}"
                )
        for interaction in self.interactions:
            if interaction.source_page_id not in page_ids:
                raise ValueError(
                    f"interaction {interaction.interaction_id!r} references "
                    f"missing page {interaction.source_page_id!r}"
                )
            if interaction.target_element_id not in element_ids:
                raise ValueError(
                    f"interaction {interaction.interaction_id!r} references "
                    f"missing element {interaction.target_element_id!r}"
                )
        return self

    def to_workflow_payload(self) -> Dict[str, Any]:
        """Return deterministic JSON-compatible data for WorkflowState evidence."""

        return self.model_dump(mode="json")

    @classmethod
    def from_workflow_payload(
        cls, payload: Mapping[str, Any]
    ) -> "ExplorationEvidence":
        """Validate and reconstruct evidence from JSON-decoded workflow data."""

        return cls.model_validate(payload)


def _unique_ids(values: Iterable[str], label: str) -> Set[str]:
    items = tuple(values)
    _require_unique(items, label)
    return set(items)


def _require_unique(values: Iterable[str], label: str) -> None:
    items = tuple(values)
    if len(set(items)) != len(items):
        raise ValueError(f"duplicate {label} are not allowed")
