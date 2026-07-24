"""Provider-neutral runtime-only runner and cancellation boundaries."""

from __future__ import annotations

from threading import Lock
from typing import Optional, Protocol

from pmqa.runners.contracts import RunnerMetadata, RunnerRequest, RunnerResponse


class CancellationToken:
    """Thread-safe, idempotent in-process cancellation signal."""

    __slots__ = ("_cancelled", "_lock")

    def __init__(self) -> None:
        self._cancelled = False
        self._lock = Lock()

    def cancel(self) -> None:
        """Request cancellation without exposing mutable serialized state."""

        with self._lock:
            self._cancelled = True

    @property
    def is_cancellation_requested(self) -> bool:
        """Return the current cancellation state safely."""

        with self._lock:
            return self._cancelled


class RunnerControl:
    """Runtime-only controls supplied to one runner execution."""

    __slots__ = ("_cancellation_token",)

    def __init__(
        self,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        if (
            cancellation_token is not None
            and type(cancellation_token) is not CancellationToken
        ):
            raise TypeError("cancellation_token must be a CancellationToken")
        self._cancellation_token = cancellation_token or CancellationToken()

    @property
    def cancellation_token(self) -> CancellationToken:
        return self._cancellation_token

    @property
    def is_cancellation_requested(self) -> bool:
        return self._cancellation_token.is_cancellation_requested


class PMQARunner(Protocol):
    """Synchronous provider-neutral execution boundary."""

    @property
    def metadata(self) -> RunnerMetadata:
        ...

    def execute(
        self,
        request: RunnerRequest,
        control: RunnerControl,
    ) -> RunnerResponse:
        ...


__all__ = [
    "CancellationToken",
    "PMQARunner",
    "RunnerControl",
]
