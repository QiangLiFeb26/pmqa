"""JSON-compatible models for captured product knowledge."""

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ArtifactStatus(str, Enum):
    """Describes the verification state of a knowledge item."""

    NEW = "new"
    VERIFIED = "verified"
    STALE = "stale"


@dataclass(frozen=True)
class Lifecycle:
    """Composes verification metadata into each knowledge item."""

    state: ArtifactStatus = ArtifactStatus.NEW
    last_verified: Optional[str] = None


@dataclass(frozen=True)
class Page:
    """Captures identity and comparison evidence for a product page."""

    id: str
    lifecycle: Lifecycle
    url: str
    title: str
    structural_fingerprint: str


@dataclass(frozen=True)
class Element:
    """Captures safe accessible evidence for an element on a page."""

    id: str
    lifecycle: Lifecycle
    page_id: str
    role: str
    accessible_name: str
    visible_text: Optional[str] = None
    attributes: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Locator:
    """Captures a prioritized strategy for locating a known element."""

    id: str
    lifecycle: Lifecycle
    element_id: str
    strategy: str
    value: str
    priority: int


@dataclass(frozen=True)
class Interaction:
    """Captures a replayable action and its structured expected outcome."""

    id: str
    lifecycle: Lifecycle
    source_page_id: str
    target_element_id: str
    action: str
    expected_outcome_type: str
    expected_outcome_value: str


@dataclass(frozen=True)
class KnowledgeArtifact:
    """Contains normalized product knowledge and decision provenance."""

    artifact_id: str
    product_id: str
    reasoning_provenance: str
    pages: List[Page] = field(default_factory=list)
    elements: List[Element] = field(default_factory=list)
    locators: List[Locator] = field(default_factory=list)
    interactions: List[Interaction] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Return a representation accepted by standard JSON encoders."""

        return _encode(asdict(self))

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "KnowledgeArtifact":
        """Rebuild an artifact from its JSON-decoded representation."""

        def lifecycle(item: Dict[str, Any]) -> Lifecycle:
            raw = item["lifecycle"]
            return Lifecycle(ArtifactStatus(raw["state"]), raw["last_verified"])

        return cls(
            artifact_id=value["artifact_id"],
            product_id=value["product_id"],
            reasoning_provenance=value["reasoning_provenance"],
            pages=[Page(lifecycle=lifecycle(item), **_without_lifecycle(item)) for item in value["pages"]],
            elements=[Element(lifecycle=lifecycle(item), **_without_lifecycle(item)) for item in value["elements"]],
            locators=[Locator(lifecycle=lifecycle(item), **_without_lifecycle(item)) for item in value["locators"]],
            interactions=[Interaction(lifecycle=lifecycle(item), **_without_lifecycle(item)) for item in value["interactions"]],
        )


def _without_lifecycle(value: Dict[str, Any]) -> Dict[str, Any]:
    return {key: item for key, item in value.items() if key != "lifecycle"}


def _encode(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _encode(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_encode(item) for item in value]
    return value
