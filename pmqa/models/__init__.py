"""JSON-compatible product knowledge models."""

from pmqa.models.exploration import (
    ExplorationEvidence,
    ExplorationSource,
    InteractionObservation,
    LocatorCandidateObservation,
    ObservedAttribute,
    ObservedElement,
    ObservedPage,
)
from pmqa.models.knowledge import (
    ArtifactStatus,
    Element,
    Interaction,
    KnowledgeArtifact,
    Lifecycle,
    Locator,
    Page,
)

__all__ = [
    "ArtifactStatus",
    "Element",
    "ExplorationEvidence",
    "ExplorationSource",
    "Interaction",
    "InteractionObservation",
    "KnowledgeArtifact",
    "Lifecycle",
    "Locator",
    "LocatorCandidateObservation",
    "ObservedAttribute",
    "ObservedElement",
    "ObservedPage",
    "Page",
]
