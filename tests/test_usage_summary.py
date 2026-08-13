"""Tests for deterministic provider-neutral usage aggregation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
import json
import subprocess
import sys
from typing import Any

import pytest
from pydantic import ValidationError

from pmqa.run import RunErrorCategory
from pmqa.usage import (
    MAX_USAGE_AGGREGATE_INTEGER,
    MAX_USAGE_SUMMARY_RECORDS,
    USAGE_SUMMARY_SCHEMA_VERSION,
    AIInvocationRecord,
    AIInvocationStatus,
    CostEvidence,
    CostType,
    DefaultUsageAggregator,
    EvidenceUnavailableReason,
    TokenField,
    TokenFieldAbsence,
    TokenUsageEvidence,
    UsageAggregationError,
    UsageAggregationErrorCode,
    UsageAggregator,
    UsageCostBucket,
    UsageProviderModelSummary,
    UsageSource,
    UsageSummary,
    UsageSummaryScope,
    UsageSummaryValidationError,
    UsageTokenFieldSummary,
)
import pmqa.usage.summary as summary_module


STARTED_AT = datetime(2026, 7, 24, 12, tzinfo=timezone.utc)
PRICING_AT = datetime(2026, 7, 1, tzinfo=timezone.utc)


class RuntimeObject:
    def __repr__(self) -> str:
        return "RuntimeObject(runtime-secret-marker)"


class InvocationSubclass(AIInvocationRecord):
    pass


class TupleSubclass(tuple):
    pass


def _usage(**updates: Any) -> TokenUsageEvidence:
    values = {
        "schema_version": "1",
        "source": UsageSource.PROVIDER_REPORTED,
        "input_tokens": 10,
        "output_tokens": 5,
        "cached_input_tokens": 0,
        "total_tokens": 15,
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


def _reported_cost(
    amount: Decimal = Decimal("0.1"),
    *,
    currency: str = "USD",
) -> CostEvidence:
    return CostEvidence(
        schema_version="1",
        cost_type=CostType.PROVIDER_REPORTED,
        amount=amount,
        currency=currency,
        pricing_source_id=None,
        pricing_version=None,
        pricing_effective_at=None,
        unavailable_reason=None,
    )


def _estimated_cost(
    amount: Decimal = Decimal("0.2"),
    *,
    version: str = "pricing.v1",
    effective_at: datetime = PRICING_AT,
) -> CostEvidence:
    return CostEvidence(
        schema_version="1",
        cost_type=CostType.ESTIMATED,
        amount=amount,
        currency="USD",
        pricing_source_id="pricing.catalog",
        pricing_version=version,
        pricing_effective_at=effective_at,
        unavailable_reason=None,
    )


def _subscription_cost() -> CostEvidence:
    return CostEvidence(
        schema_version="1",
        cost_type=CostType.SUBSCRIPTION_INCLUDED,
        amount=None,
        currency=None,
        pricing_source_id=None,
        pricing_version=None,
        pricing_effective_at=None,
        unavailable_reason=None,
    )


def _unavailable_cost(
    reason: EvidenceUnavailableReason = EvidenceUnavailableReason.NOT_REPORTED,
) -> CostEvidence:
    return CostEvidence(
        schema_version="1",
        cost_type=CostType.UNAVAILABLE,
        amount=None,
        currency=None,
        pricing_source_id=None,
        pricing_version=None,
        pricing_effective_at=None,
        unavailable_reason=reason,
    )


def _record(index: int = 1, **updates: Any) -> AIInvocationRecord:
    values = {
        "schema_version": "1",
        "invocation_id": f"ai-invocation.{index}",
        "session_id": "session.1",
        "run_id": "run.1",
        "runner_invocation_id": f"runner-invocation.{index}",
        "provider": "provider.alpha",
        "model": "model.alpha",
        "model_unavailable_reason": None,
        "operation": "reasoning.generate",
        "status": AIInvocationStatus.SUCCEEDED,
        "started_at": STARTED_AT,
        "completed_at": STARTED_AT + timedelta(seconds=1),
        "duration_ms": 100,
        "attempt_number": 1,
        "retry_of_invocation_id": None,
        "fallback_from_invocation_id": None,
        "usage": _usage(),
        "cost": _reported_cost(),
        "error_category": None,
    }
    values.update(updates)
    return AIInvocationRecord(**values)


def _summarize(
    records: tuple[AIInvocationRecord, ...],
    *,
    scope: UsageSummaryScope = UsageSummaryScope.SESSION,
    scope_id: str = "session.1",
) -> UsageSummary:
    return DefaultUsageAggregator().summarize(
        records,
        scope=scope,
        scope_id=scope_id,
    )


def _token(summary: Any, field: TokenField) -> UsageTokenFieldSummary:
    return next(item for item in summary.token_fields if item.field is field)


def _assert_safe_error(
    captured: pytest.ExceptionInfo[UsageAggregationError],
    code: UsageAggregationErrorCode,
) -> None:
    assert captured.value.code is code
    assert str(captured.value) == {
        UsageAggregationErrorCode.INVALID_REQUEST:
            "Invalid usage aggregation request.",
        UsageAggregationErrorCode.INVALID_RECORD:
            "Invalid AI invocation record.",
        UsageAggregationErrorCode.CORRELATION_MISMATCH:
            "Usage aggregation correlation mismatch.",
        UsageAggregationErrorCode.DUPLICATE_INVOCATION:
            "Duplicate AI invocation record.",
        UsageAggregationErrorCode.AGGREGATE_OVERFLOW:
            "Usage aggregate exceeds supported bounds.",
    }[code]
    assert "runtime-secret-marker" not in str(captured.value)
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None


def _wire_token(
    metrics: dict[str, Any],
    field: TokenField,
) -> dict[str, Any]:
    return next(
        item
        for item in metrics["token_fields"]
        if item["field"] == field.value
    )


def _shared_cost_records(
    cost: CostEvidence,
) -> tuple[AIInvocationRecord, ...]:
    return (
        _record(1, provider="provider.alpha", cost=cost),
        _record(2, provider="provider.beta", cost=cost),
    )


def test_public_contract_fields_and_vocabularies_are_exact() -> None:
    assert tuple(item.value for item in UsageSummaryScope) == (
        "session",
        "run",
    )
    assert tuple(item.value for item in UsageAggregationErrorCode) == (
        "invalid_request",
        "invalid_record",
        "correlation_mismatch",
        "duplicate_invocation",
        "aggregate_overflow",
    )
    assert tuple(UsageTokenFieldSummary.model_fields) == (
        "schema_version",
        "field",
        "total",
        "observed_invocation_count",
        "unavailable_invocation_count",
    )
    assert tuple(UsageCostBucket.model_fields) == (
        "schema_version",
        "cost_type",
        "currency",
        "pricing_source_id",
        "pricing_version",
        "pricing_effective_at",
        "unavailable_reason",
        "invocation_count",
        "amount",
    )
    assert tuple(UsageProviderModelSummary.model_fields) == (
        "schema_version",
        "provider",
        "model",
        "model_unavailable_reason",
        "invocation_count",
        "succeeded_invocation_count",
        "failed_invocation_count",
        "cancelled_invocation_count",
        "retry_invocation_count",
        "fallback_invocation_count",
        "total_duration_ms",
        "token_fields",
        "cost_buckets",
    )
    assert tuple(UsageSummary.model_fields) == (
        "schema_version",
        "scope",
        "scope_id",
        "invocation_count",
        "succeeded_invocation_count",
        "failed_invocation_count",
        "cancelled_invocation_count",
        "retry_invocation_count",
        "fallback_invocation_count",
        "total_duration_ms",
        "token_fields",
        "cost_buckets",
        "provider_model_groups",
    )
    assert isinstance(DefaultUsageAggregator(), UsageAggregator)


@pytest.mark.parametrize(
    ("scope", "scope_id"),
    (
        (UsageSummaryScope.SESSION, "session.1"),
        (UsageSummaryScope.RUN, "run.1"),
    ),
)
def test_empty_summary_has_zero_counts_and_no_fabricated_unavailability(
    scope: UsageSummaryScope,
    scope_id: str,
) -> None:
    summary = _summarize((), scope=scope, scope_id=scope_id)

    assert summary.schema_version == USAGE_SUMMARY_SCHEMA_VERSION
    assert summary.scope is scope
    assert summary.scope_id == scope_id
    assert summary.invocation_count == 0
    assert summary.succeeded_invocation_count == 0
    assert summary.failed_invocation_count == 0
    assert summary.cancelled_invocation_count == 0
    assert summary.retry_invocation_count == 0
    assert summary.fallback_invocation_count == 0
    assert summary.total_duration_ms == 0
    assert tuple(item.field for item in summary.token_fields) == tuple(
        TokenField
    )
    assert all(item.total is None for item in summary.token_fields)
    assert all(
        item.observed_invocation_count == 0
        and item.unavailable_invocation_count == 0
        for item in summary.token_fields
    )
    assert summary.cost_buckets == ()
    assert summary.provider_model_groups == ()


def test_zero_and_unavailable_token_evidence_remain_distinct() -> None:
    zero = _record(
        1,
        usage=_usage(
            input_tokens=0,
            output_tokens=0,
            cached_input_tokens=0,
            total_tokens=0,
        ),
        cost=_reported_cost(Decimal("0")),
    )
    unavailable = _record(
        2,
        usage=_unavailable_usage(),
        cost=_unavailable_cost(),
    )

    summary = _summarize((zero, unavailable))

    for field in TokenField:
        item = _token(summary, field)
        assert item.total == 0
        assert item.observed_invocation_count == 1
        assert item.unavailable_invocation_count == 1
    assert summary.cost_buckets[0].amount == Decimal("0")
    assert summary.cost_buckets[0].currency == "USD"
    assert summary.cost_buckets[1].amount is None
    assert summary.cost_buckets[1].unavailable_reason is (
        EvidenceUnavailableReason.NOT_REPORTED
    )


def test_partial_token_totals_status_predecessors_and_duration_are_exact() -> None:
    partial_usage = _usage(
        cached_input_tokens=None,
        total_tokens=None,
        unavailable_fields=(
            TokenFieldAbsence(
                field=TokenField.CACHED_INPUT_TOKENS,
                reason=EvidenceUnavailableReason.NOT_REPORTED,
            ),
            TokenFieldAbsence(
                field=TokenField.TOTAL_TOKENS,
                reason=EvidenceUnavailableReason.PARSING_FAILED,
            ),
        ),
    )
    succeeded = _record(1, duration_ms=0)
    failed = _record(
        2,
        status=AIInvocationStatus.FAILED,
        error_category=RunErrorCategory.PROVIDER,
        duration_ms=250,
        attempt_number=2,
        retry_of_invocation_id="ai-invocation.1",
        usage=partial_usage,
    )
    cancelled = _record(
        3,
        status=AIInvocationStatus.CANCELLED,
        error_category=RunErrorCategory.CANCELLED,
        duration_ms=50,
        attempt_number=2,
        fallback_from_invocation_id="ai-invocation.2",
        usage=_unavailable_usage(),
    )

    summary = _summarize((cancelled, succeeded, failed))

    assert summary.invocation_count == 3
    assert summary.succeeded_invocation_count == 1
    assert summary.failed_invocation_count == 1
    assert summary.cancelled_invocation_count == 1
    assert summary.retry_invocation_count == 1
    assert summary.fallback_invocation_count == 1
    assert summary.total_duration_ms == 300
    assert _token(summary, TokenField.INPUT_TOKENS).total == 20
    assert (
        _token(summary, TokenField.INPUT_TOKENS).unavailable_invocation_count
        == 1
    )
    assert _token(summary, TokenField.CACHED_INPUT_TOKENS).total == 0
    assert (
        _token(
            summary,
            TokenField.CACHED_INPUT_TOKENS,
        ).unavailable_invocation_count
        == 2
    )


def test_cost_buckets_preserve_type_currency_provenance_and_non_money() -> None:
    records = (
        _record(1, cost=_reported_cost(Decimal("0"))),
        _record(2, cost=_reported_cost(Decimal("0.1"))),
        _record(3, cost=_reported_cost(Decimal("1"), currency="EUR")),
        _record(4, cost=_estimated_cost(Decimal("0.2"))),
        _record(
            5,
            cost=_estimated_cost(
                Decimal("0.3"),
                version="pricing.v2",
            ),
        ),
        _record(6, cost=_subscription_cost()),
        _record(7, cost=_unavailable_cost()),
        _record(
            8,
            cost=_unavailable_cost(
                EvidenceUnavailableReason.NOT_SUPPORTED
            ),
        ),
    )

    summary = _summarize(tuple(reversed(records)))
    buckets = summary.cost_buckets

    assert tuple(item.cost_type for item in buckets) == (
        CostType.PROVIDER_REPORTED,
        CostType.PROVIDER_REPORTED,
        CostType.ESTIMATED,
        CostType.ESTIMATED,
        CostType.SUBSCRIPTION_INCLUDED,
        CostType.UNAVAILABLE,
        CostType.UNAVAILABLE,
    )
    assert buckets[0].currency == "EUR"
    assert buckets[0].amount == Decimal("1")
    assert buckets[1].currency == "USD"
    assert buckets[1].amount == Decimal("0.1")
    assert buckets[1].invocation_count == 2
    assert {
        item.pricing_version for item in buckets[2:4]
    } == {"pricing.v1", "pricing.v2"}
    assert buckets[4].amount is None and buckets[4].currency is None
    assert buckets[5].amount is None and buckets[5].currency is None
    assert {
        item.unavailable_reason for item in buckets[5:]
    } == {
        EvidenceUnavailableReason.NOT_REPORTED,
        EvidenceUnavailableReason.NOT_SUPPORTED,
    }


def test_estimated_effective_timestamps_form_distinct_buckets() -> None:
    later = PRICING_AT + timedelta(days=1)
    summary = _summarize(
        (
            _record(1, cost=_estimated_cost(effective_at=PRICING_AT)),
            _record(2, cost=_estimated_cost(effective_at=later)),
        )
    )

    assert len(summary.cost_buckets) == 2
    assert {
        item.pricing_effective_at for item in summary.cost_buckets
    } == {PRICING_AT, later}


def test_decimal_summation_ignores_ambient_precision_and_never_uses_float() -> None:
    amount = Decimal("0.1234567890123456789012345678")
    with localcontext() as context:
        context.prec = 5
        summary = _summarize(
            (
                _record(1, cost=_reported_cost(amount)),
                _record(2, cost=_reported_cost(amount)),
            )
        )

    assert summary.cost_buckets[0].amount == Decimal(
        "0.2469135780246913578024691356"
    )
    assert summary.to_dict()["cost_buckets"][0]["amount"] == (
        "0.2469135780246913578024691356"
    )


def test_decimal_aggregate_bound_is_enforced() -> None:
    maximum_length_amount = Decimal("9" * 128)

    with pytest.raises(UsageAggregationError) as captured:
        _summarize(
            (
                _record(1, cost=_reported_cost(maximum_length_amount)),
                _record(2, cost=_reported_cost(maximum_length_amount)),
            )
        )

    _assert_safe_error(
        captured,
        UsageAggregationErrorCode.AGGREGATE_OVERFLOW,
    )


def test_provider_model_groups_are_separate_non_recursive_and_sorted() -> None:
    records = (
        _record(1, provider="provider.z", model="model.z"),
        _record(2, provider="provider.a", model="model.b"),
        _record(3, provider="provider.a", model="model.a"),
        _record(
            4,
            provider="provider.a",
            model=None,
            model_unavailable_reason=EvidenceUnavailableReason.NOT_REPORTED,
        ),
        _record(
            5,
            provider="provider.a",
            model=None,
            model_unavailable_reason=EvidenceUnavailableReason.NOT_SUPPORTED,
        ),
    )

    groups = _summarize(records).provider_model_groups

    assert tuple(
        (
            item.provider,
            item.model,
            item.model_unavailable_reason,
        )
        for item in groups
    ) == (
        ("provider.a", "model.a", None),
        ("provider.a", "model.b", None),
        (
            "provider.a",
            None,
            EvidenceUnavailableReason.NOT_REPORTED,
        ),
        (
            "provider.a",
            None,
            EvidenceUnavailableReason.NOT_SUPPORTED,
        ),
        ("provider.z", "model.z", None),
    )
    assert all(
        "provider_model_groups" not in item.to_dict() for item in groups
    )
    assert sum(item.invocation_count for item in groups) == len(records)


def test_input_order_cannot_change_canonical_output() -> None:
    records = (
        _record(3, provider="provider.c", cost=_subscription_cost()),
        _record(1, provider="provider.a", cost=_estimated_cost()),
        _record(2, provider="provider.b", cost=_reported_cost()),
    )
    left = _summarize(records)
    right = _summarize(tuple(reversed(records)))

    assert left == right
    assert json.dumps(
        left.to_dict(),
        sort_keys=False,
        separators=(",", ":"),
    ) == json.dumps(
        right.to_dict(),
        sort_keys=False,
        separators=(",", ":"),
    )


def test_run_scope_requires_every_record_to_match() -> None:
    summary = _summarize(
        (_record(1, session_id="session.other"),),
        scope=UsageSummaryScope.RUN,
        scope_id="run.1",
    )
    assert summary.scope is UsageSummaryScope.RUN

    with pytest.raises(UsageAggregationError) as captured:
        _summarize(
            (_record(1, run_id="run.other"),),
            scope=UsageSummaryScope.RUN,
            scope_id="run.1",
        )
    _assert_safe_error(
        captured,
        UsageAggregationErrorCode.CORRELATION_MISMATCH,
    )


def test_duplicate_and_session_mismatch_fail_without_filtering() -> None:
    record = _record()
    with pytest.raises(UsageAggregationError) as duplicate:
        _summarize((record, record))
    _assert_safe_error(
        duplicate,
        UsageAggregationErrorCode.DUPLICATE_INVOCATION,
    )

    with pytest.raises(UsageAggregationError) as mismatch:
        _summarize((_record(session_id="session.other"),))
    _assert_safe_error(
        mismatch,
        UsageAggregationErrorCode.CORRELATION_MISMATCH,
    )


@pytest.mark.parametrize(
    "records",
    (
        [],
        TupleSubclass(),
        (object(),),
    ),
)
def test_non_tuple_subclass_and_non_record_input_fail_safely(records) -> None:
    with pytest.raises(UsageAggregationError) as captured:
        DefaultUsageAggregator().summarize(
            records,
            scope=UsageSummaryScope.SESSION,
            scope_id="session.1",
        )
    _assert_safe_error(
        captured,
        UsageAggregationErrorCode.INVALID_REQUEST
        if not isinstance(records, tuple) or type(records) is not tuple
        else UsageAggregationErrorCode.INVALID_RECORD,
    )


def test_record_subclass_mutation_and_excess_input_fail_safely() -> None:
    record = _record()
    subclass = InvocationSubclass(**record.model_dump(mode="python"))
    with pytest.raises(UsageAggregationError) as subclass_error:
        _summarize((subclass,))
    _assert_safe_error(
        subclass_error,
        UsageAggregationErrorCode.INVALID_RECORD,
    )

    record.__dict__["provider"] = RuntimeObject()
    with pytest.raises(UsageAggregationError) as mutated_error:
        _summarize((record,))
    _assert_safe_error(
        mutated_error,
        UsageAggregationErrorCode.INVALID_RECORD,
    )

    excessive = tuple(
        _record(index + 1) for index in range(MAX_USAGE_SUMMARY_RECORDS + 1)
    )
    with pytest.raises(UsageAggregationError) as excessive_error:
        _summarize(excessive)
    _assert_safe_error(
        excessive_error,
        UsageAggregationErrorCode.INVALID_REQUEST,
    )


def test_maximum_cardinality_supports_distinct_groups_and_cost_buckets() -> None:
    records = tuple(
        _record(
            index + 1,
            provider=f"provider.{index + 1}",
            cost=_estimated_cost(version=f"pricing.v{index + 1}"),
        )
        for index in range(MAX_USAGE_SUMMARY_RECORDS)
    )

    summary = _summarize(records)

    assert summary.invocation_count == MAX_USAGE_SUMMARY_RECORDS
    assert len(summary.provider_model_groups) == MAX_USAGE_SUMMARY_RECORDS
    assert len(summary.cost_buckets) == MAX_USAGE_SUMMARY_RECORDS
    assert UsageSummary.from_dict(summary.to_dict()) == summary


@pytest.mark.parametrize(
    "field",
    ("duration", "input_tokens"),
)
def test_duration_and_token_overflow_fail_safely(field: str) -> None:
    first_updates = {}
    second_updates = {}
    if field == "duration":
        first_updates["duration_ms"] = MAX_USAGE_AGGREGATE_INTEGER
        second_updates["duration_ms"] = 1
    else:
        first_updates["usage"] = _usage(
            input_tokens=MAX_USAGE_AGGREGATE_INTEGER,
            total_tokens=MAX_USAGE_AGGREGATE_INTEGER,
        )
        second_updates["usage"] = _usage(input_tokens=1, total_tokens=1)

    with pytest.raises(UsageAggregationError) as captured:
        _summarize(
            (
                _record(1, **first_updates),
                _record(2, **second_updates),
            )
        )
    _assert_safe_error(
        captured,
        UsageAggregationErrorCode.AGGREGATE_OVERFLOW,
    )


def test_summary_round_trip_copy_freezing_and_independent_snapshot() -> None:
    record = _record()
    summary = _summarize((record,))
    wire = json.loads(json.dumps(summary.to_dict()))

    assert UsageSummary.from_dict(wire) == summary
    with pytest.raises(ValidationError):
        summary.model_copy(update={"invocation_count": 2})
    with pytest.raises(ValidationError):
        summary.invocation_count = 2

    record.__dict__["duration_ms"] = 999
    record.usage.__dict__["input_tokens"] = 999
    assert summary.total_duration_ms == 100
    assert _token(summary, TokenField.INPUT_TOKENS).total == 10


@pytest.mark.parametrize(
    "change",
    (
        {"password": "runtime-secret-marker"},
        {"scope": RuntimeObject()},
        {"scope_id": "Runtime Secret Marker/path"},
    ),
)
def test_summary_reconstruction_rejects_unknown_runtime_and_noncanonical_data(
    change: dict[str, Any],
) -> None:
    wire = _summarize((_record(),)).to_dict()
    wire.update(change)

    with pytest.raises(UsageSummaryValidationError) as captured:
        UsageSummary.from_dict(wire)

    assert str(captured.value) == "invalid PMQA usage summary"
    assert "runtime-secret-marker" not in str(captured.value).lower()
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None


@pytest.mark.parametrize(
    ("scope", "scope_id"),
    (
        ("session", "session.1"),
        (UsageSummaryScope.SESSION, "Runtime Secret Marker/path"),
    ),
)
def test_invalid_request_is_fixed_and_marker_safe(scope, scope_id) -> None:
    with pytest.raises(UsageAggregationError) as captured:
        DefaultUsageAggregator().summarize(
            (),
            scope=scope,
            scope_id=scope_id,
        )
    _assert_safe_error(
        captured,
        UsageAggregationErrorCode.INVALID_REQUEST,
    )


@pytest.mark.parametrize(
    "failure",
    (MemoryError(), KeyboardInterrupt(), SystemExit(), GeneratorExit()),
)
def test_resource_and_control_flow_exceptions_propagate_exactly(
    monkeypatch: pytest.MonkeyPatch,
    failure: BaseException,
) -> None:
    def fail_from_dict(_value):
        raise failure

    monkeypatch.setattr(
        summary_module.AIInvocationRecord,
        "from_dict",
        fail_from_dict,
    )

    with pytest.raises(type(failure)) as captured:
        _summarize((_record(),))

    assert captured.value is failure


@pytest.mark.parametrize(
    "group_updates",
    (
        {
            "succeeded_invocation_count": 0,
            "failed_invocation_count": 1,
        },
        {
            "succeeded_invocation_count": 0,
            "cancelled_invocation_count": 1,
        },
        {"retry_invocation_count": 1},
        {"fallback_invocation_count": 1},
    ),
    ids=("succeeded-failed", "cancelled", "retry", "fallback"),
)
def test_cross_level_lifecycle_and_predecessor_mismatch_is_rejected(
    group_updates: dict[str, int],
) -> None:
    wire = _summarize((_record(),)).to_dict()
    wire["provider_model_groups"][0].update(group_updates)

    with pytest.raises(UsageSummaryValidationError):
        UsageSummary.from_dict(wire)


def test_cross_level_invocation_count_mismatch_is_rejected() -> None:
    wire = _summarize(
        (
            _record(1, provider="provider.a"),
            _record(2, provider="provider.b"),
        )
    ).to_dict()
    group = wire["provider_model_groups"][0]
    group["invocation_count"] = 2
    group["succeeded_invocation_count"] = 2
    for token in group["token_fields"]:
        token["observed_invocation_count"] = 2
        token["total"] *= 2
    group["cost_buckets"][0]["invocation_count"] = 2
    group["cost_buckets"][0]["amount"] = "0.2"

    with pytest.raises(UsageSummaryValidationError):
        UsageSummary.from_dict(wire)


def test_cross_level_duration_mismatch_rejected_by_all_entry_points() -> None:
    summary = _summarize((_record(),))
    wire = summary.to_dict()
    wire["provider_model_groups"][0]["total_duration_ms"] = 999

    with pytest.raises(ValidationError):
        UsageSummary(**wire)
    with pytest.raises(UsageSummaryValidationError):
        UsageSummary.from_dict(wire)

    group = summary.provider_model_groups[0].model_copy(
        update={"total_duration_ms": 999}
    )
    with pytest.raises(ValidationError):
        summary.model_copy(update={"provider_model_groups": (group,)})


def test_cross_level_token_observed_and_unavailable_counts_reconcile() -> None:
    wire = _summarize(
        (
            _record(1),
            _record(
                2,
                provider="provider.beta",
                usage=_unavailable_usage(),
            ),
        )
    ).to_dict()
    unavailable_group = wire["provider_model_groups"][1]
    group_token = _wire_token(unavailable_group, TokenField.INPUT_TOKENS)
    group_token.update(
        {
            "total": 0,
            "observed_invocation_count": 1,
            "unavailable_invocation_count": 0,
        }
    )

    with pytest.raises(UsageSummaryValidationError):
        UsageSummary.from_dict(wire)

    wire = _summarize(
        (
            _record(1),
            _record(
                2,
                provider="provider.beta",
                usage=_unavailable_usage(),
            ),
        )
    ).to_dict()
    top_token = _wire_token(wire, TokenField.INPUT_TOKENS)
    top_token.update(
        {
            "observed_invocation_count": 2,
            "unavailable_invocation_count": 0,
        }
    )
    with pytest.raises(UsageSummaryValidationError):
        UsageSummary.from_dict(wire)


def test_cross_level_token_none_and_numeric_totals_reconcile() -> None:
    unavailable_wire = _summarize(
        (
            _record(
                1,
                usage=_unavailable_usage(),
                cost=_unavailable_cost(),
            ),
        )
    ).to_dict()
    group_token = _wire_token(
        unavailable_wire["provider_model_groups"][0],
        TokenField.INPUT_TOKENS,
    )
    group_token.update(
        {
            "total": 0,
            "observed_invocation_count": 1,
            "unavailable_invocation_count": 0,
        }
    )
    with pytest.raises(UsageSummaryValidationError):
        UsageSummary.from_dict(unavailable_wire)

    numeric_wire = _summarize((_record(),)).to_dict()
    _wire_token(
        numeric_wire["provider_model_groups"][0],
        TokenField.INPUT_TOKENS,
    )["total"] = 11
    with pytest.raises(UsageSummaryValidationError):
        UsageSummary.from_dict(numeric_wire)

    zero_record = _record(
        usage=_usage(
            input_tokens=0,
            output_tokens=0,
            cached_input_tokens=0,
            total_tokens=0,
        )
    )
    zero_wire = _summarize((zero_record,)).to_dict()
    _wire_token(
        zero_wire["provider_model_groups"][0],
        TokenField.INPUT_TOKENS,
    )["total"] = 1
    with pytest.raises(UsageSummaryValidationError):
        UsageSummary.from_dict(zero_wire)


def test_multiple_groups_merge_one_monetary_cost_identity_exactly() -> None:
    records = _shared_cost_records(
        _reported_cost(Decimal("0.1234567890123456789012345678"))
    )
    summary = _summarize(records)

    assert len(summary.cost_buckets) == 1
    assert summary.cost_buckets[0].invocation_count == 2
    assert summary.cost_buckets[0].amount == Decimal(
        "0.2469135780246913578024691356"
    )
    assert UsageSummary.from_dict(summary.to_dict()) == summary


def test_multiple_groups_merge_subscription_and_unavailable_buckets() -> None:
    records = (
        _record(1, provider="provider.a", cost=_subscription_cost()),
        _record(2, provider="provider.b", cost=_subscription_cost()),
        _record(3, provider="provider.c", cost=_unavailable_cost()),
        _record(4, provider="provider.d", cost=_unavailable_cost()),
    )
    summary = _summarize(records)

    assert tuple(
        (bucket.cost_type, bucket.invocation_count, bucket.amount)
        for bucket in summary.cost_buckets
    ) == (
        (CostType.SUBSCRIPTION_INCLUDED, 2, None),
        (CostType.UNAVAILABLE, 2, None),
    )
    assert UsageSummary.from_dict(summary.to_dict()) == summary


def test_currency_and_pricing_provenance_remain_separate_across_groups() -> None:
    records = (
        _record(
            1,
            provider="provider.a",
            cost=_reported_cost(currency="USD"),
        ),
        _record(
            2,
            provider="provider.b",
            cost=_reported_cost(currency="EUR"),
        ),
        _record(
            3,
            provider="provider.c",
            cost=_estimated_cost(version="pricing.v1"),
        ),
        _record(
            4,
            provider="provider.d",
            cost=_estimated_cost(version="pricing.v2"),
        ),
    )
    summary = _summarize(records)

    assert len(summary.cost_buckets) == 4
    assert UsageSummary.from_dict(summary.to_dict()) == summary


def test_missing_and_extra_top_level_cost_identities_are_rejected() -> None:
    different = _summarize(
        (
            _record(
                1,
                provider="provider.a",
                cost=_reported_cost(Decimal("0.1"), currency="USD"),
            ),
            _record(
                2,
                provider="provider.b",
                cost=_reported_cost(Decimal("1"), currency="EUR"),
            ),
        )
    ).to_dict()
    usd_bucket = next(
        bucket
        for bucket in different["cost_buckets"]
        if bucket["currency"] == "USD"
    )
    usd_bucket["invocation_count"] = 2
    usd_bucket["amount"] = "1.1"
    different["cost_buckets"] = [usd_bucket]
    with pytest.raises(UsageSummaryValidationError):
        UsageSummary.from_dict(different)

    compatible = _summarize(
        _shared_cost_records(_reported_cost(Decimal("0.1")))
    ).to_dict()
    first = dict(compatible["cost_buckets"][0])
    first.update({"invocation_count": 1, "amount": "0.1"})
    extra = dict(first)
    extra["currency"] = "EUR"
    compatible["cost_buckets"] = [first, extra]
    with pytest.raises(UsageSummaryValidationError):
        UsageSummary.from_dict(compatible)


def test_top_level_cost_amount_and_bucket_count_mismatch_are_rejected() -> None:
    amount_wire = _summarize(
        _shared_cost_records(_reported_cost(Decimal("0.1")))
    ).to_dict()
    amount_wire["cost_buckets"][0]["amount"] = "999"
    with pytest.raises(UsageSummaryValidationError):
        UsageSummary.from_dict(amount_wire)

    count_wire = _summarize(
        (
            _record(
                1,
                provider="provider.a",
                cost=_reported_cost(currency="USD"),
            ),
            _record(
                2,
                provider="provider.a",
                cost=_reported_cost(currency="USD"),
            ),
            _record(
                3,
                provider="provider.b",
                cost=_reported_cost(currency="EUR"),
            ),
        )
    ).to_dict()
    for bucket in count_wire["cost_buckets"]:
        bucket["invocation_count"] = (
            1 if bucket["currency"] == "USD" else 2
        )
    with pytest.raises(UsageSummaryValidationError):
        UsageSummary.from_dict(count_wire)


def test_cross_level_from_dict_failure_is_fixed_safe_and_marker_free() -> None:
    wire = _summarize(
        _shared_cost_records(_reported_cost(Decimal("0.1")))
    ).to_dict()
    wire["scope_id"] = "session.runtime-secret-marker"
    wire["cost_buckets"][0]["amount"] = "999"

    with pytest.raises(UsageSummaryValidationError) as captured:
        UsageSummary.from_dict(wire)

    assert str(captured.value) == "invalid PMQA usage summary"
    assert "runtime-secret-marker" not in str(captured.value)
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
    assert not isinstance(captured.value, UsageAggregationError)


def test_cross_level_decimal_is_independent_of_ambient_precision() -> None:
    summary = _summarize(
        _shared_cost_records(
            _reported_cost(Decimal("0.1234567890123456789012345678"))
        )
    )
    wire = summary.to_dict()

    with localcontext() as context:
        context.prec = 2
        reconstructed = UsageSummary.from_dict(wire)

    assert reconstructed == summary


def test_cross_level_integer_and_decimal_overflow_are_contract_failures() -> None:
    duration_wire = _summarize(
        (
            _record(1, provider="provider.a"),
            _record(2, provider="provider.b"),
        )
    ).to_dict()
    for group in duration_wire["provider_model_groups"]:
        group["total_duration_ms"] = MAX_USAGE_AGGREGATE_INTEGER
    with pytest.raises(UsageSummaryValidationError):
        UsageSummary.from_dict(duration_wire)

    decimal_wire = _summarize(
        _shared_cost_records(_reported_cost(Decimal("0.1")))
    ).to_dict()
    maximum = "9" * 128
    for group in decimal_wire["provider_model_groups"]:
        group["cost_buckets"][0]["amount"] = maximum
    with pytest.raises(UsageSummaryValidationError) as captured:
        UsageSummary.from_dict(decimal_wire)
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None


def test_monetary_invariant_failure_uses_fixed_invalid_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = _record()
    record.cost.__dict__["amount"] = None

    monkeypatch.setattr(
        DefaultUsageAggregator,
        "_snapshot_record",
        staticmethod(lambda _record: record),
    )

    with pytest.raises(UsageAggregationError) as captured:
        _summarize((record,))

    _assert_safe_error(
        captured,
        UsageAggregationErrorCode.INVALID_RECORD,
    )


def test_monetary_invariant_is_explicit_under_optimized_python() -> None:
    statement = "\n".join(
        (
            "import runpy",
            "namespace = runpy.run_path('tests/test_usage_summary.py')",
            "record = namespace['_record']()",
            "summary = namespace['_summarize']((record,))",
            "assert str(summary.cost_buckets[0].amount) == '0.1'",
            "record.cost.__dict__['amount'] = None",
            "aggregator = namespace['DefaultUsageAggregator']",
            "aggregator._snapshot_record = staticmethod(lambda _value: record)",
            "try:",
            " namespace['_summarize']((record,))",
            "except namespace['UsageAggregationError'] as error:",
            " expected = namespace['UsageAggregationErrorCode'].INVALID_RECORD",
            " assert error.code is expected",
            "else:",
            " raise AssertionError('invalid monetary evidence was accepted')",
        )
    )
    completed = subprocess.run(
        [sys.executable, "-O", "-c", statement],
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr


@pytest.mark.parametrize(
    "failure",
    (MemoryError(), KeyboardInterrupt(), SystemExit(), GeneratorExit()),
)
def test_cross_level_decimal_resource_exceptions_propagate_exactly(
    monkeypatch: pytest.MonkeyPatch,
    failure: BaseException,
) -> None:
    wire = _summarize(
        _shared_cost_records(_reported_cost(Decimal("0.1")))
    ).to_dict()

    def fail_decimal(_value, _field_name):
        raise failure

    monkeypatch.setattr(summary_module, "_canonical_decimal", fail_decimal)
    with pytest.raises(type(failure)) as captured:
        UsageSummary.from_dict(wire)

    assert captured.value is failure


@pytest.mark.parametrize(
    ("records", "expected"),
    (
        ((), (0, 0, 0)),
        ((_record(1),), (1, 0, 0)),
        (
            (
                _record(
                    1,
                    attempt_number=2,
                    retry_of_invocation_id="ai-invocation.previous",
                ),
            ),
            (1, 1, 0),
        ),
        (
            (
                _record(
                    1,
                    attempt_number=2,
                    fallback_from_invocation_id="ai-invocation.previous",
                ),
            ),
            (1, 0, 1),
        ),
        (
            (
                _record(
                    1,
                    attempt_number=2,
                    retry_of_invocation_id="ai-invocation.previous",
                ),
                _record(
                    2,
                    attempt_number=2,
                    fallback_from_invocation_id="ai-invocation.previous",
                ),
            ),
            (2, 1, 1),
        ),
        (
            (
                _record(1),
                _record(
                    2,
                    attempt_number=2,
                    retry_of_invocation_id="ai-invocation.previous",
                ),
                _record(
                    3,
                    attempt_number=2,
                    fallback_from_invocation_id="ai-invocation.previous",
                ),
            ),
            (3, 1, 1),
        ),
        (
            (
                _record(1, provider="provider.a"),
                _record(
                    2,
                    provider="provider.b",
                    attempt_number=2,
                    retry_of_invocation_id="ai-invocation.previous",
                ),
                _record(
                    3,
                    provider="provider.c",
                    attempt_number=2,
                    fallback_from_invocation_id="ai-invocation.previous",
                ),
            ),
            (3, 1, 1),
        ),
    ),
    ids=(
        "empty",
        "first-attempt",
        "one-retry",
        "one-fallback",
        "retry-and-fallback",
        "mixed-first-and-later",
        "multiple-provider-groups",
    ),
)
def test_valid_predecessor_aggregate_combinations_remain_canonical(
    records: tuple[AIInvocationRecord, ...],
    expected: tuple[int, int, int],
) -> None:
    summary = _summarize(records)

    assert (
        summary.invocation_count,
        summary.retry_invocation_count,
        summary.fallback_invocation_count,
    ) == expected
    assert UsageSummary.from_dict(summary.to_dict()).to_dict() == (
        summary.to_dict()
    )


def test_top_level_retry_fallback_overlap_is_rejected() -> None:
    summary = _summarize((_record(),))
    updates = {
        "retry_invocation_count": 1,
        "fallback_invocation_count": 1,
    }
    wire = summary.to_dict()
    wire.update(updates)

    with pytest.raises(ValidationError):
        UsageSummary(**wire)
    with pytest.raises(UsageSummaryValidationError):
        UsageSummary.from_dict(wire)
    with pytest.raises(ValidationError):
        summary.model_copy(update=updates)


def test_provider_group_retry_fallback_overlap_is_rejected() -> None:
    summary = _summarize((_record(),))
    group = summary.provider_model_groups[0]
    updates = {
        "retry_invocation_count": 1,
        "fallback_invocation_count": 1,
    }
    wire = group.to_dict()
    wire.update(updates)

    with pytest.raises(ValidationError):
        UsageProviderModelSummary(**wire)
    with pytest.raises(UsageSummaryValidationError):
        UsageProviderModelSummary.from_dict(wire)
    with pytest.raises(ValidationError):
        group.model_copy(update=updates)


@pytest.mark.parametrize(
    ("invocation_count", "retry_count", "fallback_count"),
    (
        (1, 1, 1),
        (2, 2, 1),
        (3, 2, 2),
    ),
)
def test_reconciled_top_and_group_predecessor_overlap_is_rejected_safely(
    invocation_count: int,
    retry_count: int,
    fallback_count: int,
) -> None:
    records = tuple(_record(index + 1) for index in range(invocation_count))
    wire = _summarize(records).to_dict()
    wire["scope_id"] = "session.runtime-secret-marker"
    for metrics in (wire, wire["provider_model_groups"][0]):
        metrics["retry_invocation_count"] = retry_count
        metrics["fallback_invocation_count"] = fallback_count

    with pytest.raises(UsageSummaryValidationError) as captured:
        UsageSummary.from_dict(wire)

    assert str(captured.value) == "invalid PMQA usage summary"
    assert "runtime-secret-marker" not in str(captured.value)
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
