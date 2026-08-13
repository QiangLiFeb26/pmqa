"""Provider-neutral lifecycle collection for canonical AI invocations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from enum import Enum
import math
from threading import Lock
import time
from typing import Callable, Optional, Protocol, runtime_checkable

from pmqa.run import RunErrorCategory
from pmqa.usage.contracts import (
    MAX_USAGE_INTEGER,
    USAGE_CONTRACT_SCHEMA_VERSION,
    AIInvocationRecord,
    AIInvocationStatus,
    CostEvidence,
    EvidenceUnavailableReason,
    TokenUsageEvidence,
    _validate_ai_invocation_metadata_values,
)


_RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS = (
    MemoryError,
    KeyboardInterrupt,
    SystemExit,
    GeneratorExit,
)
_HANDLE_FACTORY_KEY = object()


def _default_wall_clock() -> datetime:
    return datetime.now(timezone.utc)


def _default_monotonic_clock() -> float:
    return time.monotonic()


class AIInvocationCollectionErrorCode(str, Enum):
    """Fixed failure vocabulary for the runtime collector boundary."""

    INVALID_CONFIGURATION = "invalid_configuration"
    INVALID_METADATA = "invalid_metadata"
    INVALID_HANDLE = "invalid_handle"
    INVALID_EVIDENCE = "invalid_evidence"
    INVALID_ERROR_CATEGORY = "invalid_error_category"
    INVALID_CLOCK = "invalid_clock"
    INVALID_DURATION = "invalid_duration"
    TERMINALIZATION_FAILED = "terminalization_failed"


_ERROR_MESSAGES = {
    AIInvocationCollectionErrorCode.INVALID_CONFIGURATION: (
        "Invalid AI invocation collector configuration."
    ),
    AIInvocationCollectionErrorCode.INVALID_METADATA: (
        "Invalid AI invocation metadata."
    ),
    AIInvocationCollectionErrorCode.INVALID_HANDLE: (
        "Invalid or finalized AI invocation handle."
    ),
    AIInvocationCollectionErrorCode.INVALID_EVIDENCE: (
        "Invalid AI invocation evidence."
    ),
    AIInvocationCollectionErrorCode.INVALID_ERROR_CATEGORY: (
        "Invalid AI invocation error category."
    ),
    AIInvocationCollectionErrorCode.INVALID_CLOCK: (
        "Invalid AI invocation clock evidence."
    ),
    AIInvocationCollectionErrorCode.INVALID_DURATION: (
        "Invalid AI invocation duration."
    ),
    AIInvocationCollectionErrorCode.TERMINALIZATION_FAILED: (
        "AI invocation terminalization failed."
    ),
}


class AIInvocationCollectionError(ValueError):
    """Safe, bounded lifecycle-collection failure."""

    def __init__(self, code: AIInvocationCollectionErrorCode) -> None:
        self.code = code
        super().__init__(_ERROR_MESSAGES[code])


class AIInvocationHandle:
    """Opaque immutable runtime ownership handle; never persisted."""

    __slots__ = ("__owner", "__integrity")

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("AIInvocationHandle values are collector-created")

    @classmethod
    def _create(
        cls,
        factory_key: object,
        owner: object,
        integrity: object,
    ) -> "AIInvocationHandle":
        if factory_key is not _HANDLE_FACTORY_KEY or cls is not AIInvocationHandle:
            raise TypeError("AIInvocationHandle values are collector-created")
        handle = object.__new__(cls)
        object.__setattr__(handle, "_AIInvocationHandle__owner", owner)
        object.__setattr__(handle, "_AIInvocationHandle__integrity", integrity)
        return handle

    def __setattr__(self, _name: str, _value: object) -> None:
        raise AttributeError("AIInvocationHandle is immutable")

    def __repr__(self) -> str:
        return "AIInvocationHandle()"

    def __reduce__(self) -> object:
        raise TypeError("AIInvocationHandle is runtime-only")


@dataclass(frozen=True)
class _InvocationMetadata:
    invocation_id: str
    session_id: str
    run_id: str
    runner_invocation_id: Optional[str]
    provider: str
    model: Optional[str]
    model_unavailable_reason: Optional[EvidenceUnavailableReason]
    operation: str
    attempt_number: int
    retry_of_invocation_id: Optional[str]
    fallback_from_invocation_id: Optional[str]


@dataclass(frozen=True)
class _ActiveInvocation:
    integrity: object
    metadata: _InvocationMetadata
    started_at: datetime
    started_monotonic: Decimal


@runtime_checkable
class AIInvocationCollector(Protocol):
    """Provider-neutral synchronous invocation lifecycle boundary."""

    def start_invocation(
        self,
        *,
        invocation_id: str,
        session_id: str,
        run_id: str,
        provider: str,
        model: Optional[str],
        model_unavailable_reason: Optional[EvidenceUnavailableReason],
        operation: str,
        attempt_number: int,
        runner_invocation_id: Optional[str] = None,
        retry_of_invocation_id: Optional[str] = None,
        fallback_from_invocation_id: Optional[str] = None,
    ) -> AIInvocationHandle:
        """Start one invocation after validating canonical correlation."""

    def complete_invocation(
        self,
        handle: AIInvocationHandle,
        usage: TokenUsageEvidence,
        cost: CostEvidence,
    ) -> AIInvocationRecord:
        """Terminalize one invocation successfully."""

    def fail_invocation(
        self,
        handle: AIInvocationHandle,
        usage: TokenUsageEvidence,
        cost: CostEvidence,
        error_category: RunErrorCategory,
    ) -> AIInvocationRecord:
        """Terminalize one invocation with a safe failure category."""

    def cancel_invocation(
        self,
        handle: AIInvocationHandle,
        usage: TokenUsageEvidence,
        cost: CostEvidence,
    ) -> AIInvocationRecord:
        """Terminalize one invocation as cancelled."""


class DefaultAIInvocationCollector:
    """Deterministic, in-memory, exactly-once lifecycle collector."""

    def __init__(
        self,
        *,
        wall_clock: Callable[[], datetime] = _default_wall_clock,
        monotonic_clock: Callable[[], float] = _default_monotonic_clock,
    ) -> None:
        if not callable(wall_clock) or not callable(monotonic_clock):
            raise AIInvocationCollectionError(
                AIInvocationCollectionErrorCode.INVALID_CONFIGURATION
            ) from None
        self._wall_clock = wall_clock
        self._monotonic_clock = monotonic_clock
        self._owner = object()
        self._active: dict[AIInvocationHandle, _ActiveInvocation] = {}
        self._lock = Lock()

    def start_invocation(
        self,
        *,
        invocation_id: str,
        session_id: str,
        run_id: str,
        provider: str,
        model: Optional[str],
        model_unavailable_reason: Optional[EvidenceUnavailableReason],
        operation: str,
        attempt_number: int,
        runner_invocation_id: Optional[str] = None,
        retry_of_invocation_id: Optional[str] = None,
        fallback_from_invocation_id: Optional[str] = None,
    ) -> AIInvocationHandle:
        metadata = self._validate_metadata(
            invocation_id=invocation_id,
            session_id=session_id,
            run_id=run_id,
            runner_invocation_id=runner_invocation_id,
            provider=provider,
            model=model,
            model_unavailable_reason=model_unavailable_reason,
            operation=operation,
            attempt_number=attempt_number,
            retry_of_invocation_id=retry_of_invocation_id,
            fallback_from_invocation_id=fallback_from_invocation_id,
        )
        started_at = self._sample_wall_clock()
        started_monotonic = self._sample_monotonic_clock()
        integrity = object()
        handle = AIInvocationHandle._create(
            _HANDLE_FACTORY_KEY,
            self._owner,
            integrity,
        )
        active = _ActiveInvocation(
            integrity=integrity,
            metadata=metadata,
            started_at=started_at,
            started_monotonic=started_monotonic,
        )
        with self._lock:
            self._active[handle] = active
        return handle

    def complete_invocation(
        self,
        handle: AIInvocationHandle,
        usage: TokenUsageEvidence,
        cost: CostEvidence,
    ) -> AIInvocationRecord:
        return self._terminalize(
            handle,
            usage,
            cost,
            status=AIInvocationStatus.SUCCEEDED,
            error_category=None,
        )

    def fail_invocation(
        self,
        handle: AIInvocationHandle,
        usage: TokenUsageEvidence,
        cost: CostEvidence,
        error_category: RunErrorCategory,
    ) -> AIInvocationRecord:
        if (
            type(error_category) is not RunErrorCategory
            or error_category is RunErrorCategory.CANCELLED
        ):
            raise AIInvocationCollectionError(
                AIInvocationCollectionErrorCode.INVALID_ERROR_CATEGORY
            ) from None
        return self._terminalize(
            handle,
            usage,
            cost,
            status=AIInvocationStatus.FAILED,
            error_category=error_category,
        )

    def cancel_invocation(
        self,
        handle: AIInvocationHandle,
        usage: TokenUsageEvidence,
        cost: CostEvidence,
    ) -> AIInvocationRecord:
        return self._terminalize(
            handle,
            usage,
            cost,
            status=AIInvocationStatus.CANCELLED,
            error_category=RunErrorCategory.CANCELLED,
        )

    @staticmethod
    def _validate_metadata(
        *,
        invocation_id: str,
        session_id: str,
        run_id: str,
        runner_invocation_id: Optional[str],
        provider: str,
        model: Optional[str],
        model_unavailable_reason: Optional[EvidenceUnavailableReason],
        operation: str,
        attempt_number: int,
        retry_of_invocation_id: Optional[str],
        fallback_from_invocation_id: Optional[str],
    ) -> _InvocationMetadata:
        failed = False
        canonical: Optional[_InvocationMetadata] = None
        try:
            required = tuple(
                AIInvocationRecord.validate_identifiers(value)
                for value in (
                    invocation_id,
                    session_id,
                    run_id,
                    provider,
                    operation,
                )
            )
            optional = tuple(
                AIInvocationRecord.validate_optional_identifiers(value)
                for value in (
                    runner_invocation_id,
                    model,
                    retry_of_invocation_id,
                    fallback_from_invocation_id,
                )
            )
            reason = AIInvocationRecord.validate_model_unavailable_reason(
                model_unavailable_reason
            )
            if (
                type(attempt_number) is not int
                or attempt_number < 1
                or attempt_number > MAX_USAGE_INTEGER
            ):
                raise ValueError
            _validate_ai_invocation_metadata_values(
                invocation_id=required[0],
                model=optional[1],
                model_unavailable_reason=reason,
                attempt_number=attempt_number,
                retry_of_invocation_id=optional[2],
                fallback_from_invocation_id=optional[3],
            )
            canonical = _InvocationMetadata(
                invocation_id=required[0],
                session_id=required[1],
                run_id=required[2],
                runner_invocation_id=optional[0],
                provider=required[3],
                model=optional[1],
                model_unavailable_reason=reason,
                operation=required[4],
                attempt_number=attempt_number,
                retry_of_invocation_id=optional[2],
                fallback_from_invocation_id=optional[3],
            )
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except Exception:
            failed = True
        if failed or canonical is None:
            raise AIInvocationCollectionError(
                AIInvocationCollectionErrorCode.INVALID_METADATA
            ) from None
        return canonical

    def _terminalize(
        self,
        handle: AIInvocationHandle,
        usage: TokenUsageEvidence,
        cost: CostEvidence,
        *,
        status: AIInvocationStatus,
        error_category: Optional[RunErrorCategory],
    ) -> AIInvocationRecord:
        active = self._inspect_handle(handle)
        usage_snapshot, cost_snapshot = self._snapshot_evidence(usage, cost)

        # Ownership is consumed atomically immediately before terminal clock
        # sampling. Caller-validation failures above leave the handle active.
        with self._lock:
            if self._active.get(handle) is not active:
                raise AIInvocationCollectionError(
                    AIInvocationCollectionErrorCode.INVALID_HANDLE
                ) from None
            del self._active[handle]

        completed_at = self._sample_wall_clock()
        completed_monotonic = self._sample_monotonic_clock()
        if completed_at < active.started_at:
            raise AIInvocationCollectionError(
                AIInvocationCollectionErrorCode.INVALID_CLOCK
            ) from None
        duration_ms = self._duration_milliseconds(
            active.started_monotonic,
            completed_monotonic,
        )
        metadata = active.metadata
        failed = False
        record: Optional[AIInvocationRecord] = None
        try:
            record = AIInvocationRecord(
                schema_version=USAGE_CONTRACT_SCHEMA_VERSION,
                invocation_id=metadata.invocation_id,
                session_id=metadata.session_id,
                run_id=metadata.run_id,
                runner_invocation_id=metadata.runner_invocation_id,
                provider=metadata.provider,
                model=metadata.model,
                model_unavailable_reason=metadata.model_unavailable_reason,
                operation=metadata.operation,
                status=status,
                started_at=active.started_at,
                completed_at=completed_at,
                duration_ms=duration_ms,
                attempt_number=metadata.attempt_number,
                retry_of_invocation_id=metadata.retry_of_invocation_id,
                fallback_from_invocation_id=(
                    metadata.fallback_from_invocation_id
                ),
                usage=usage_snapshot,
                cost=cost_snapshot,
                error_category=error_category,
            )
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except Exception:
            failed = True
        if failed or record is None:
            raise AIInvocationCollectionError(
                AIInvocationCollectionErrorCode.TERMINALIZATION_FAILED
            ) from None
        return AIInvocationRecord.from_dict(record.to_dict())

    def _inspect_handle(
        self,
        handle: AIInvocationHandle,
    ) -> _ActiveInvocation:
        active: Optional[_ActiveInvocation] = None
        if type(handle) is AIInvocationHandle:
            try:
                owner = object.__getattribute__(
                    handle,
                    "_AIInvocationHandle__owner",
                )
                integrity = object.__getattribute__(
                    handle,
                    "_AIInvocationHandle__integrity",
                )
            except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
                raise
            except Exception:
                owner = None
                integrity = None
            with self._lock:
                candidate = self._active.get(handle)
                if (
                    candidate is not None
                    and owner is self._owner
                    and candidate.integrity is integrity
                ):
                    active = candidate
                elif candidate is not None:
                    # The object identity proves this was our handle, but its
                    # private binding was altered. Consume the corrupted state.
                    del self._active[handle]
        if active is None:
            raise AIInvocationCollectionError(
                AIInvocationCollectionErrorCode.INVALID_HANDLE
            ) from None
        return active

    @staticmethod
    def _snapshot_evidence(
        usage: TokenUsageEvidence,
        cost: CostEvidence,
    ) -> tuple[TokenUsageEvidence, CostEvidence]:
        failed = False
        snapshots: Optional[tuple[TokenUsageEvidence, CostEvidence]] = None
        try:
            if (
                type(usage) is not TokenUsageEvidence
                or type(cost) is not CostEvidence
            ):
                raise ValueError
            snapshots = (
                TokenUsageEvidence.from_dict(usage.to_dict()),
                CostEvidence.from_dict(cost.to_dict()),
            )
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except Exception:
            failed = True
        if failed or snapshots is None:
            raise AIInvocationCollectionError(
                AIInvocationCollectionErrorCode.INVALID_EVIDENCE
            ) from None
        return snapshots

    def _sample_wall_clock(self) -> datetime:
        failed = False
        normalized: Optional[datetime] = None
        try:
            sampled = self._wall_clock()
            if (
                type(sampled) is not datetime
                or sampled.tzinfo is None
                or sampled.utcoffset() is None
            ):
                failed = True
            else:
                normalized = sampled.astimezone(timezone.utc)
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except Exception:
            failed = True
        if failed or normalized is None:
            raise AIInvocationCollectionError(
                AIInvocationCollectionErrorCode.INVALID_CLOCK
            ) from None
        return normalized

    def _sample_monotonic_clock(self) -> Decimal:
        failed = False
        normalized: Optional[Decimal] = None
        try:
            sampled = self._monotonic_clock()
            if (
                type(sampled) not in {int, float}
                or (type(sampled) is float and not math.isfinite(sampled))
            ):
                failed = True
            else:
                normalized = Decimal(
                    sampled if type(sampled) is int else str(sampled)
                )
                if not normalized.is_finite():
                    failed = True
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except Exception:
            failed = True
        if failed or normalized is None:
            raise AIInvocationCollectionError(
                AIInvocationCollectionErrorCode.INVALID_CLOCK
            ) from None
        return normalized

    @staticmethod
    def _duration_milliseconds(started: Decimal, completed: Decimal) -> int:
        failed = False
        duration_ms: Optional[int] = None
        try:
            elapsed = completed - started
            if elapsed < 0:
                failed = True
            else:
                rounded = (elapsed * Decimal(1000)).quantize(
                    Decimal(1),
                    rounding=ROUND_HALF_UP,
                )
                duration_ms = int(rounded)
                if duration_ms > MAX_USAGE_INTEGER:
                    failed = True
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except (InvalidOperation, ArithmeticError, ValueError):
            failed = True
        if failed or duration_ms is None:
            raise AIInvocationCollectionError(
                AIInvocationCollectionErrorCode.INVALID_DURATION
            ) from None
        return duration_ms


__all__ = [
    "AIInvocationCollectionError",
    "AIInvocationCollectionErrorCode",
    "AIInvocationCollector",
    "AIInvocationHandle",
    "DefaultAIInvocationCollector",
]
