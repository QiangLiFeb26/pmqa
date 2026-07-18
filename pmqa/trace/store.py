"""Abstract persistence contract for reasoning traces."""

from abc import ABC, abstractmethod
from typing import List

from pmqa.trace.models import TraceRecord


class TraceStoreError(RuntimeError):
    """Reports a trace persistence or decoding failure."""


class TraceDuplicateError(TraceStoreError):
    """Reports an attempt to save an existing trace identifier."""


class TraceNotFoundError(TraceStoreError):
    """Reports that a requested trace does not exist."""


class TraceDataError(TraceStoreError):
    """Reports malformed or inconsistent persisted trace data."""


class TraceStore(ABC):
    """Defines storage operations for immutable reasoning history."""

    @abstractmethod
    def save_trace(self, trace: TraceRecord) -> None:
        """Persist a trace without replacing an existing record."""

    @abstractmethod
    def get_trace(self, trace_id: str) -> TraceRecord:
        """Return one trace or raise when it is missing."""

    @abstractmethod
    def find_by_request(self, request_id: str) -> List[TraceRecord]:
        """Return traces for a request, newest first."""

    @abstractmethod
    def list_recent(self, limit: int = 20) -> List[TraceRecord]:
        """Return the most recently created traces."""
