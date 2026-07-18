"""Simple models for knowledge captured about a product."""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ArtifactStatus(str, Enum):
    """Describes the verification state of captured product knowledge."""

    NEW = "new"
    VERIFIED = "verified"
    STALE = "stale"


@dataclass(frozen=True)
class Locator:
    """Describes one product-owned strategy for locating an element."""

    strategy: str
    value: str


@dataclass(frozen=True)
class Element:
    """Describes a named element and the locators known for it."""

    name: str
    locators: List[Locator] = field(default_factory=list)


@dataclass(frozen=True)
class Page:
    """Describes a product page and its known elements."""

    name: str
    elements: List[Element] = field(default_factory=list)


@dataclass(frozen=True)
class Interaction:
    """Records an action performed against a named element."""

    action: str
    element: str


@dataclass(frozen=True)
class KnowledgeArtifact:
    """Wraps JSON-compatible product knowledge with verification metadata."""

    artifact_id: str
    kind: str
    content: Dict[str, Any]
    status: ArtifactStatus = ArtifactStatus.NEW
    last_verified: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Return a representation accepted by standard JSON encoders."""

        value = asdict(self)
        value["status"] = self.status.value
        value["last_verified"] = (
            self.last_verified.isoformat() if self.last_verified else None
        )
        return value
