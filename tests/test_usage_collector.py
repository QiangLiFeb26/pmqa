"""Focused tests for the provider-neutral AI invocation collector."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import pickle
from threading import Barrier, Lock
from typing import Any

import pytest

from pmqa.run import RunErrorCategory
from pmqa.usage import (
    AIInvocationCollectionError,
    AIInvocationCollectionErrorCode,
    AIInvocationCollector,
    AIInvocationHandle,
    AIInvocationRecord,
    AIInvocationStatus,
    CostEvidence,
    CostType,
    DefaultAIInvocationCollector,
    EvidenceUnavailableReason,
    TokenField,
    TokenFieldAbsence,
    TokenUsageEvidence,
    UsageSource,
)


STARTED_AT = datetime(2026, 7, 24, 12, tzinfo=timezone.utc)
COMPLETED_AT = STARTED_AT + timedelta(seconds=1)
RESOURCE_EXCEPTIONS = (
    MemoryError,
    KeyboardInterrupt,
    SystemExit,
    GeneratorExit,
)


class SequenceClock:
    def __init__(self, *values: object) -> None:
        self.values = values
        self.calls = 0

    def __call__(self) -> object:
        value = self.values[self.calls]
        self.calls += 1
        if isinstance(value, BaseException):
            raise value
        return value


class ThreadSafeSequenceClock(SequenceClock):
    def __init__(self, *values: object) -> None:
        super().__init__(*values)
        self._lock = Lock()

    def __call__(self) -> object:
        with self._lock:
            return super().__call__()


def _usage(**updates: Any) -> TokenUsageEvidence:
    values = {
        "schema_version": "1",
        "source": UsageSource.PROVIDER_REPORTED,
        "input_tokens": 0,
        "output_tokens": 2,
        "cached_input_tokens": 0,
        "total_tokens": 2,
        "unavailable_fields": (),
    }
    values.update(updates)
    return TokenUsageEvidence(**values)


def _unavailable_usage() -> TokenUsageEvidence:
    return TokenUsageEvidence(
        schema_version="1",
        source=UsageSource.UNAVAILABLE,
        input_tokens=None,
        output_tokens=None,
        cached_input_tokens=None,
        total_tokens=None,
        unavailable_fields=tuple(
            TokenFieldAbsence(
                field=field,
                reason=EvidenceUnavailableReason.NOT_COLLECTED,
            )
            for field in TokenField
        ),
    )


def _cost(**updates: Any) -> CostEvidence:
    values = {
        "schema_version": "1",
        "cost_type": CostType.PROVIDER_REPORTED,
        "amount": Decimal("0"),
        "currency": "USD",
        "pricing_source_id": None,
        "pricing_version": None,
        "pricing_effective_at": None,
        "unavailable_reason": None,
    }
    values.update(updates)
    return CostEvidence(**values)


def _unavailable_cost() -> CostEvidence:
    return CostEvidence(
        schema_version="1",
        cost_type=CostType.UNAVAILABLE,
        amount=None,
        currency=None,
        pricing_source_id=None,
        pricing_version=None,
        pricing_effective_at=None,
        unavailable_reason=EvidenceUnavailableReason.NOT_REPORTED,
    )


def _collector(
    *,
    wall: SequenceClock | None = None,
    monotonic: SequenceClock | None = None,
) -> tuple[DefaultAIInvocationCollector, SequenceClock, SequenceClock]:
    wall = wall or SequenceClock(STARTED_AT, COMPLETED_AT)
    monotonic = monotonic or SequenceClock(10, 11)
    return (
        DefaultAIInvocationCollector(
            wall_clock=wall,
            monotonic_clock=monotonic,
        ),
        wall,
        monotonic,
    )


def _start(
    collector: DefaultAIInvocationCollector,
    **updates: Any,
) -> AIInvocationHandle:
    values = {
        "invocation_id": "ai-invocation.1",
        "session_id": "session.1",
        "run_id": "run.1",
        "runner_invocation_id": None,
        "provider": "provider.test",
        "model": "model.test-v1",
        "model_unavailable_reason": None,
        "operation": "reasoning.generate",
        "attempt_number": 1,
        "retry_of_invocation_id": None,
        "fallback_from_invocation_id": None,
    }
    values.update(updates)
    return collector.start_invocation(**values)


def _assert_safe_error(
    captured: pytest.ExceptionInfo[AIInvocationCollectionError],
    code: AIInvocationCollectionErrorCode,
) -> None:
    assert captured.value.code is code
    assert "runtime-secret-marker" not in str(captured.value)
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None


def test_successful_lifecycle_preserves_correlation_zero_and_duration() -> None:
    collector, wall, monotonic = _collector(
        monotonic=SequenceClock(10, 10.0005)
    )
    handle = _start(
        collector,
        runner_invocation_id="runner-invocation.1",
    )

    record = collector.complete_invocation(handle, _usage(), _cost())

    assert isinstance(collector, AIInvocationCollector)
    assert record.status is AIInvocationStatus.SUCCEEDED
    assert record.invocation_id == "ai-invocation.1"
    assert record.runner_invocation_id == "runner-invocation.1"
    assert record.started_at == STARTED_AT
    assert record.completed_at == COMPLETED_AT
    assert record.duration_ms == 1  # Decimal ROUND_HALF_UP.
    assert record.usage.input_tokens == 0
    assert record.cost.amount == Decimal("0")
    assert record.error_category is None
    assert wall.calls == monotonic.calls == 2


def test_real_threads_terminalize_one_handle_exactly_once() -> None:
    wall = ThreadSafeSequenceClock(STARTED_AT, COMPLETED_AT)
    monotonic = ThreadSafeSequenceClock(10, 11)
    collector, _, _ = _collector(wall=wall, monotonic=monotonic)
    handle = _start(collector)
    competitors = 8
    barrier = Barrier(competitors)

    def complete():
        barrier.wait()
        try:
            return collector.complete_invocation(
                handle,
                _usage(),
                _cost(),
            )
        except AIInvocationCollectionError as error:
            return error

    with ThreadPoolExecutor(max_workers=competitors) as executor:
        outcomes = tuple(
            executor.map(
                lambda _index: complete(),
                range(competitors),
            )
        )

    records = tuple(
        outcome
        for outcome in outcomes
        if isinstance(outcome, AIInvocationRecord)
    )
    errors = tuple(
        outcome
        for outcome in outcomes
        if isinstance(outcome, AIInvocationCollectionError)
    )
    assert len(records) == 1
    assert records[0].status is AIInvocationStatus.SUCCEEDED
    assert len(errors) == competitors - 1
    assert all(
        error.code is AIInvocationCollectionErrorCode.INVALID_HANDLE
        for error in errors
    )
    assert wall.calls == 2
    assert monotonic.calls == 2


@pytest.mark.parametrize(
    ("method", "status", "category"),
    [
        ("fail", AIInvocationStatus.FAILED, RunErrorCategory.PROVIDER),
        ("cancel", AIInvocationStatus.CANCELLED, RunErrorCategory.CANCELLED),
    ],
)
def test_failure_and_cancellation_have_canonical_classification(
    method: str,
    status: AIInvocationStatus,
    category: RunErrorCategory,
) -> None:
    collector, _, _ = _collector()
    handle = _start(collector)

    if method == "fail":
        record = collector.fail_invocation(
            handle,
            _usage(),
            _cost(),
            RunErrorCategory.PROVIDER,
        )
    else:
        record = collector.cancel_invocation(
            handle,
            _usage(),
            _cost(),
        )

    assert record.status is status
    assert record.error_category is category


def test_unavailable_evidence_and_model_reason_are_not_fabricated() -> None:
    collector, _, _ = _collector()
    handle = _start(
        collector,
        model=None,
        model_unavailable_reason=EvidenceUnavailableReason.NOT_REPORTED,
    )

    record = collector.complete_invocation(
        handle,
        _unavailable_usage(),
        _unavailable_cost(),
    )

    assert record.model is None
    assert (
        record.model_unavailable_reason
        is EvidenceUnavailableReason.NOT_REPORTED
    )
    assert record.usage.source is UsageSource.UNAVAILABLE
    assert record.cost.cost_type is CostType.UNAVAILABLE
    assert record.usage.input_tokens is None
    assert record.cost.amount is None


@pytest.mark.parametrize(
    "metadata",
    [
        {"invocation_id": "Runtime Secret Marker"},
        {"session_id": ""},
        {"provider": "Provider Invalid"},
        {"model": None, "model_unavailable_reason": None},
        {
            "model": "model.test",
            "model_unavailable_reason": EvidenceUnavailableReason.NOT_REPORTED,
        },
        {"attempt_number": True},
        {"attempt_number": 2},
        {
            "attempt_number": 1,
            "retry_of_invocation_id": "ai-invocation.0",
        },
        {
            "attempt_number": 2,
            "retry_of_invocation_id": "ai-invocation.1",
        },
        {
            "attempt_number": 2,
            "retry_of_invocation_id": "ai-invocation.0",
            "fallback_from_invocation_id": "ai-invocation.other",
        },
    ],
)
def test_invalid_metadata_fails_before_either_clock(
    metadata: dict[str, Any],
) -> None:
    collector, wall, monotonic = _collector()

    with pytest.raises(AIInvocationCollectionError) as captured:
        _start(collector, **metadata)

    _assert_safe_error(
        captured,
        AIInvocationCollectionErrorCode.INVALID_METADATA,
    )
    assert wall.calls == monotonic.calls == 0


@pytest.mark.parametrize(
    ("updates", "expected"),
    [
        (
            {
                "attempt_number": 2,
                "retry_of_invocation_id": "ai-invocation.0",
            },
            ("ai-invocation.0", None),
        ),
        (
            {
                "attempt_number": 2,
                "fallback_from_invocation_id": "ai-invocation.other",
            },
            (None, "ai-invocation.other"),
        ),
    ],
)
def test_retry_and_fallback_metadata_are_preserved(
    updates: dict[str, Any],
    expected: tuple[str | None, str | None],
) -> None:
    collector, _, _ = _collector()
    record = collector.complete_invocation(
        _start(collector, **updates),
        _usage(),
        _cost(),
    )

    assert (
        record.retry_of_invocation_id,
        record.fallback_from_invocation_id,
    ) == expected


@pytest.mark.parametrize("clock_name", ["wall", "monotonic"])
@pytest.mark.parametrize(
    "invalid",
    [
        None,
        "runtime-secret-marker",
        True,
        float("nan"),
        float("inf"),
        datetime(2026, 7, 24, 12),
    ],
)
def test_invalid_start_clock_values_fail_safely(
    clock_name: str,
    invalid: object,
) -> None:
    wall = SequenceClock(invalid if clock_name == "wall" else STARTED_AT)
    monotonic = SequenceClock(invalid if clock_name == "monotonic" else 1)
    collector, _, _ = _collector(wall=wall, monotonic=monotonic)

    with pytest.raises(AIInvocationCollectionError) as captured:
        _start(collector)

    _assert_safe_error(
        captured,
        AIInvocationCollectionErrorCode.INVALID_CLOCK,
    )
    assert wall.calls == 1
    assert monotonic.calls == (0 if clock_name == "wall" else 1)


@pytest.mark.parametrize(
    ("clock_name", "invalid"),
    [
        ("wall", "runtime-secret-marker"),
        ("wall", datetime(2026, 7, 24, 12)),
        ("monotonic", "runtime-secret-marker"),
        ("monotonic", float("nan")),
        ("monotonic", float("inf")),
        ("monotonic", True),
    ],
)
def test_invalid_terminal_clock_consumes_handle(
    clock_name: str,
    invalid: object,
) -> None:
    wall = SequenceClock(
        STARTED_AT,
        invalid if clock_name == "wall" else COMPLETED_AT,
    )
    monotonic = SequenceClock(
        1,
        invalid if clock_name == "monotonic" else 2,
    )
    collector, _, _ = _collector(wall=wall, monotonic=monotonic)
    handle = _start(collector)

    with pytest.raises(AIInvocationCollectionError) as captured:
        collector.complete_invocation(handle, _usage(), _cost())
    _assert_safe_error(
        captured,
        AIInvocationCollectionErrorCode.INVALID_CLOCK,
    )
    with pytest.raises(AIInvocationCollectionError) as duplicate:
        collector.cancel_invocation(handle, _usage(), _cost())
    _assert_safe_error(
        duplicate,
        AIInvocationCollectionErrorCode.INVALID_HANDLE,
    )


@pytest.mark.parametrize(
    ("wall_values", "monotonic_values", "code"),
    [
        (
            (STARTED_AT, STARTED_AT - timedelta(microseconds=1)),
            (1, 2),
            AIInvocationCollectionErrorCode.INVALID_CLOCK,
        ),
        (
            (STARTED_AT, COMPLETED_AT),
            (2, 1),
            AIInvocationCollectionErrorCode.INVALID_DURATION,
        ),
        (
            (STARTED_AT, COMPLETED_AT),
            (0, 10**30),
            AIInvocationCollectionErrorCode.INVALID_DURATION,
        ),
    ],
)
def test_backwards_and_overflow_terminal_timing_fail_safely(
    wall_values: tuple[object, object],
    monotonic_values: tuple[object, object],
    code: AIInvocationCollectionErrorCode,
) -> None:
    collector, _, _ = _collector(
        wall=SequenceClock(*wall_values),
        monotonic=SequenceClock(*monotonic_values),
    )
    handle = _start(collector)

    with pytest.raises(AIInvocationCollectionError) as captured:
        collector.complete_invocation(handle, _usage(), _cost())

    _assert_safe_error(captured, code)


@pytest.mark.parametrize(
    ("elapsed", "duration_ms"),
    [(0, 0), (0.0004, 0), (0.0005, 1), (0.0015, 2)],
)
def test_duration_rounding_is_deterministic(
    elapsed: float,
    duration_ms: int,
) -> None:
    collector, _, _ = _collector(
        monotonic=SequenceClock(10.0, 10.0 + elapsed)
    )

    record = collector.complete_invocation(
        _start(collector),
        _usage(),
        _cost(),
    )

    assert record.duration_ms == duration_ms


@pytest.mark.parametrize("clock_name", ["wall", "monotonic"])
def test_ordinary_clock_exception_is_contained(clock_name: str) -> None:
    marker = RuntimeError("runtime-secret-marker")
    wall = SequenceClock(marker if clock_name == "wall" else STARTED_AT)
    monotonic = SequenceClock(marker if clock_name == "monotonic" else 1)
    collector, _, _ = _collector(wall=wall, monotonic=monotonic)

    with pytest.raises(AIInvocationCollectionError) as captured:
        _start(collector)

    _assert_safe_error(
        captured,
        AIInvocationCollectionErrorCode.INVALID_CLOCK,
    )


def test_terminal_ordinary_clock_exception_is_contained_and_consumes() -> None:
    collector, _, _ = _collector(
        wall=SequenceClock(
            STARTED_AT,
            RuntimeError("runtime-secret-marker"),
        )
    )
    handle = _start(collector)

    with pytest.raises(AIInvocationCollectionError) as captured:
        collector.complete_invocation(handle, _usage(), _cost())
    _assert_safe_error(
        captured,
        AIInvocationCollectionErrorCode.INVALID_CLOCK,
    )
    with pytest.raises(AIInvocationCollectionError) as duplicate:
        collector.complete_invocation(handle, _usage(), _cost())
    _assert_safe_error(
        duplicate,
        AIInvocationCollectionErrorCode.INVALID_HANDLE,
    )


@pytest.mark.parametrize("exception_type", RESOURCE_EXCEPTIONS)
@pytest.mark.parametrize(
    "stage",
    ["start-wall", "start-monotonic", "end-wall", "end-monotonic"],
)
def test_resource_and_control_flow_exceptions_propagate_exactly(
    exception_type: type[BaseException],
    stage: str,
) -> None:
    expected = exception_type("runtime-secret-marker")
    wall_values: list[object] = [STARTED_AT, COMPLETED_AT]
    monotonic_values: list[object] = [1, 2]
    if stage == "start-wall":
        wall_values[0] = expected
    elif stage == "start-monotonic":
        monotonic_values[0] = expected
    elif stage == "end-wall":
        wall_values[1] = expected
    else:
        monotonic_values[1] = expected
    collector, _, _ = _collector(
        wall=SequenceClock(*wall_values),
        monotonic=SequenceClock(*monotonic_values),
    )

    if stage.startswith("start"):
        with pytest.raises(exception_type) as captured:
            _start(collector)
    else:
        handle = _start(collector)
        with pytest.raises(exception_type) as captured:
            collector.complete_invocation(handle, _usage(), _cost())

    assert captured.value is expected


def test_every_terminal_combination_is_exactly_once() -> None:
    methods = ("complete", "fail", "cancel")
    for first in methods:
        for second in methods:
            collector, _, _ = _collector()
            handle = _start(collector)
            _terminal(collector, first, handle)

            with pytest.raises(AIInvocationCollectionError) as captured:
                _terminal(collector, second, handle)

            _assert_safe_error(
                captured,
                AIInvocationCollectionErrorCode.INVALID_HANDLE,
            )


def _terminal(
    collector: DefaultAIInvocationCollector,
    method: str,
    handle: AIInvocationHandle,
):
    if method == "complete":
        return collector.complete_invocation(handle, _usage(), _cost())
    if method == "fail":
        return collector.fail_invocation(
            handle,
            _usage(),
            _cost(),
            RunErrorCategory.EXECUTION,
        )
    return collector.cancel_invocation(handle, _usage(), _cost())


def test_invalid_evidence_and_failure_category_leave_handle_retryable() -> None:
    collector, wall, monotonic = _collector()
    handle = _start(collector)

    with pytest.raises(AIInvocationCollectionError) as evidence_error:
        collector.complete_invocation(
            handle,
            {"raw": True},  # type: ignore[arg-type]
            _cost(),
        )
    _assert_safe_error(
        evidence_error,
        AIInvocationCollectionErrorCode.INVALID_EVIDENCE,
    )
    with pytest.raises(AIInvocationCollectionError) as category_error:
        collector.fail_invocation(
            handle,
            _usage(),
            _cost(),
            RunErrorCategory.CANCELLED,
        )
    _assert_safe_error(
        category_error,
        AIInvocationCollectionErrorCode.INVALID_ERROR_CATEGORY,
    )
    assert wall.calls == monotonic.calls == 1

    record = collector.complete_invocation(handle, _usage(), _cost())
    assert record.status is AIInvocationStatus.SUCCEEDED
    assert wall.calls == monotonic.calls == 2


def test_mutated_evidence_is_rejected_before_clocks_and_can_be_corrected() -> None:
    collector, wall, monotonic = _collector()
    handle = _start(collector)
    usage = _usage()
    object.__setattr__(usage, "input_tokens", -1)

    with pytest.raises(AIInvocationCollectionError) as captured:
        collector.complete_invocation(handle, usage, _cost())

    _assert_safe_error(
        captured,
        AIInvocationCollectionErrorCode.INVALID_EVIDENCE,
    )
    assert wall.calls == monotonic.calls == 1
    assert collector.complete_invocation(handle, _usage(), _cost())


def test_returned_record_does_not_retain_caller_evidence() -> None:
    collector, _, _ = _collector()
    usage = _usage()
    cost = _cost()
    record = collector.complete_invocation(_start(collector), usage, cost)

    object.__setattr__(usage, "input_tokens", 999)
    object.__setattr__(cost, "amount", Decimal("99"))

    assert record.usage.input_tokens == 0
    assert record.cost.amount == Decimal("0")
    assert record.usage is not usage
    assert record.cost is not cost


def test_foreign_forged_subclassed_and_mutated_handles_are_rejected() -> None:
    owner, _, _ = _collector()
    foreign, _, _ = _collector()
    handle = _start(owner)
    forged = object.__new__(AIInvocationHandle)

    class HandleSubclass(AIInvocationHandle):
        pass

    subclassed = object.__new__(HandleSubclass)
    for collector, candidate in (
        (foreign, handle),
        (owner, forged),
        (owner, subclassed),
    ):
        with pytest.raises(AIInvocationCollectionError) as captured:
            collector.complete_invocation(candidate, _usage(), _cost())
        _assert_safe_error(
            captured,
            AIInvocationCollectionErrorCode.INVALID_HANDLE,
        )

    object.__setattr__(
        handle,
        "_AIInvocationHandle__integrity",
        object(),
    )
    with pytest.raises(AIInvocationCollectionError) as captured:
        owner.complete_invocation(handle, _usage(), _cost())
    _assert_safe_error(
        captured,
        AIInvocationCollectionErrorCode.INVALID_HANDLE,
    )


def test_handle_is_opaque_immutable_and_not_serializable() -> None:
    collector, _, _ = _collector()
    handle = _start(collector)

    assert repr(handle) == "AIInvocationHandle()"
    assert "0x" not in repr(handle)
    assert not hasattr(handle, "__dict__")
    with pytest.raises(AttributeError):
        handle.value = "runtime-secret-marker"  # type: ignore[attr-defined]
    with pytest.raises(TypeError):
        AIInvocationHandle()
    with pytest.raises(TypeError):
        pickle.dumps(handle)
    with pytest.raises(TypeError):
        json.dumps(handle)


@pytest.mark.parametrize("bad_clock", [None, "runtime-secret-marker", 7])
def test_noncallable_constructor_clocks_fail_safely(bad_clock: object) -> None:
    with pytest.raises(AIInvocationCollectionError) as captured:
        DefaultAIInvocationCollector(
            wall_clock=bad_clock,  # type: ignore[arg-type]
            monotonic_clock=lambda: 1,
        )
    _assert_safe_error(
        captured,
        AIInvocationCollectionErrorCode.INVALID_CONFIGURATION,
    )


def test_pricing_correlation_failure_after_clock_sampling_consumes_handle() -> None:
    collector, _, _ = _collector()
    handle = _start(collector)
    future_cost = CostEvidence(
        schema_version="1",
        cost_type=CostType.ESTIMATED,
        amount=Decimal("1"),
        currency="USD",
        pricing_source_id="pricing.test",
        pricing_version="1",
        pricing_effective_at=STARTED_AT + timedelta(days=1),
        unavailable_reason=None,
    )

    with pytest.raises(AIInvocationCollectionError) as captured:
        collector.complete_invocation(handle, _usage(), future_cost)
    _assert_safe_error(
        captured,
        AIInvocationCollectionErrorCode.TERMINALIZATION_FAILED,
    )
    with pytest.raises(AIInvocationCollectionError) as duplicate:
        collector.complete_invocation(handle, _usage(), _cost())
    _assert_safe_error(
        duplicate,
        AIInvocationCollectionErrorCode.INVALID_HANDLE,
    )
