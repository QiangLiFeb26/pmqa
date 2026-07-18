"""Provider contracts at the framework's integration boundary."""

from abc import ABC, abstractmethod
from typing import Optional

from pmqa.core.models import Artifact, ExecutionResult, RunContext, Task


class ExecutionProvider(ABC):
    """Executes one task against an external system."""

    @abstractmethod
    def execute(self, task: Task, context: RunContext) -> ExecutionResult:
        """Execute the task and return its result."""


class StorageProvider(ABC):
    """Persists and retrieves framework artifacts."""

    @abstractmethod
    def save(self, artifact: Artifact) -> None:
        """Persist an artifact."""

    @abstractmethod
    def load(self, artifact_id: str) -> Optional[Artifact]:
        """Retrieve an artifact when it exists."""
