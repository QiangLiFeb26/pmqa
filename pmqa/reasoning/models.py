"""Canonical request and response models shared by reasoning providers."""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from pmqa.models import Element, Interaction, Page


class ReasoningStatus(str, Enum):
    """Describes whether a reasoning provider completed its request."""

    COMPLETED = "completed"
    FAILED = "failed"


class ReasoningRequest(BaseModel):
    """Carries only structured product knowledge into a reasoning provider."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    task_type: str = Field(min_length=1)
    provider_hint: Optional[str] = None
    product_id: str = Field(min_length=1)
    artifact_version: str = Field(min_length=1)
    pages: List[Page] = Field(default_factory=list)
    elements: List[Element] = Field(default_factory=list)
    interactions: List[Interaction] = Field(default_factory=list)
    constraints: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReasoningResponse(BaseModel):
    """Returns structured decisions without assuming natural-language output."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    status: ReasoningStatus
    decisions: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
