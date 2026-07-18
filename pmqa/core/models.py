"""Minimal runtime models for framework orchestration."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class RunContext:
    """Identifies one framework run and its selected product pack."""

    run_id: str
    product: str


@dataclass(frozen=True)
class Task:
    """Describes a unit of work requested from a provider."""

    task_id: str
    description: str


@dataclass(frozen=True)
class Artifact:
    """Carries a named, JSON-compatible output produced during a run."""

    artifact_id: str
    data: Dict[str, Any]


@dataclass(frozen=True)
class ExecutionResult:
    """Records whether provider execution succeeded and its optional output."""

    succeeded: bool
    artifact: Optional[Artifact] = None


@dataclass
class PMQAState:
    """Holds the runtime values passed between workflow nodes."""

    context: RunContext
    tasks: List[Task] = field(default_factory=list)
    artifacts: List[Artifact] = field(default_factory=list)
    results: List[ExecutionResult] = field(default_factory=list)
