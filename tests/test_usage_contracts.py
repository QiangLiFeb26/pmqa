"""Tests for provider-neutral AI invocation usage and cost contracts."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json

import pytest
from pydantic import ValidationError

from pmqa.run import RunErrorCategory
from pmqa.usage import (
    USAGE_CONTRACT_SCHEMA_VERSION,
    MAX_USAGE_INTEGER,
    AIInvocationRecord,
    AIInvocationStatus,
    CostEvidence,
    CostType,
    EvidenceUnavailableReason,
    TokenField,
    TokenFieldAbsence,
    TokenUsageEvidence,
    UsageContractValidationError,
    UsageSource,
)


class RuntimeObject:
    def __repr__(self) -> str:
        return "RuntimeObject(runtime-secret-marker)"


def _time(minutes: int = 0) -> datetime:
    return datetime(2026, 7, 24, 12, tzinfo=timezone.utc) + timedelta(
        minutes=minutes
    )


def _absence(
    field: TokenField,
    reason: EvidenceUnavailableReason = EvidenceUnavailableReason.NOT_REPORTED,
) -> TokenFieldAbsence:
    return TokenFieldAbsence(field=field, reason=reason)


def _complete_usage(**updates) -> TokenUsageEvidence:
    values = {
        "schema_version": "1",
        "source": UsageSource.PROVIDER_REPORTED,
        "input_tokens": 100,
        "output_tokens": 25,
        "cached_input_tokens": 0,
        "total_tokens": 125,
        "unavailable_fields": (),
    }
    values.update(updates)
    return TokenUsageEvidence(**values)


def _unavailable_usage(**updates) -> TokenUsageEvidence:
    values = {
        "schema_version": "1",
        "source": UsageSource.UNAVAILABLE,
        "input_tokens": None,
        "output_tokens": None,
        "cached_input_tokens": None,
        "total_tokens": None,
        "unavailable_fields": tuple(
            _absence(
                field,
                EvidenceUnavailableReason.NOT_COLLECTED,
            )
            for field in TokenField
        ),
    }
    values.update(updates)
    return TokenUsageEvidence(**values)


def _reported_cost(**updates) -> CostEvidence:
    values = {
        "schema_version": "1",
        "cost_type": CostType.PROVIDER_REPORTED,
        "amount": Decimal("0.0125"),
        "currency": "USD",
        "pricing_source_id": None,
        "pricing_version": None,
        "pricing_effective_at": None,
        "unavailable_reason": None,
    }
    values.update(updates)
    return CostEvidence(**values)


def _unavailable_cost(**updates) -> CostEvidence:
    values = {
        "schema_version": "1",
        "cost_type": CostType.UNAVAILABLE,
        "amount": None,
        "currency": None,
        "pricing_source_id": None,
        "pricing_version": None,
        "pricing_effective_at": None,
        "unavailable_reason": EvidenceUnavailableReason.NOT_REPORTED,
    }
    values.update(updates)
    return CostEvidence(**values)


def _invocation(**updates) -> AIInvocationRecord:
    values = {
        "schema_version": USAGE_CONTRACT_SCHEMA_VERSION,
        "invocation_id": "ai-invocation.1",
        "session_id": "session.1",
        "run_id": "run.1",
        "runner_invocation_id": "invocation.1",
        "provider": "provider.test",
        "model": "model.test-v1",
        "model_unavailable_reason": None,
        "operation": "reasoning.generate",
        "status": AIInvocationStatus.SUCCEEDED,
        "started_at": _time(),
        "completed_at": _time(1),
        "duration_ms": 250,
        "attempt_number": 1,
        "retry_of_invocation_id": None,
        "fallback_from_invocation_id": None,
        "usage": _complete_usage(),
        "cost": _reported_cost(),
        "error_category": None,
    }
    values.update(updates)
    return AIInvocationRecord(**values)


def test_public_vocabularies_have_stable_values() -> None:
    assert tuple(item.value for item in UsageSource) == (
        "provider_reported",
        "parsed_from_cli",
        "estimated",
        "unavailable",
    )
    assert tuple(item.value for item in CostType) == (
        "provider_reported",
        "estimated",
        "subscription_included",
        "unavailable",
    )
    assert tuple(item.value for item in EvidenceUnavailableReason) == (
        "not_reported",
        "not_supported",
        "parsing_failed",
        "not_collected",
    )


def test_public_usage_contracts_have_explicit_stable_fields() -> None:
    assert tuple(TokenFieldAbsence.model_fields) == ("field", "reason")
    assert tuple(TokenUsageEvidence.model_fields) == (
        "schema_version",
        "source",
        "input_tokens",
        "output_tokens",
        "cached_input_tokens",
        "total_tokens",
        "unavailable_fields",
    )
    assert tuple(CostEvidence.model_fields) == (
        "schema_version",
        "cost_type",
        "amount",
        "currency",
        "pricing_source_id",
        "pricing_version",
        "pricing_effective_at",
        "unavailable_reason",
    )
    assert tuple(AIInvocationRecord.model_fields) == (
        "schema_version",
        "invocation_id",
        "session_id",
        "run_id",
        "runner_invocation_id",
        "provider",
        "model",
        "model_unavailable_reason",
        "operation",
        "status",
        "started_at",
        "completed_at",
        "duration_ms",
        "attempt_number",
        "retry_of_invocation_id",
        "fallback_from_invocation_id",
        "usage",
        "cost",
        "error_category",
    )


def test_complete_reported_and_cli_parsed_usage_remain_distinct() -> None:
    reported = _complete_usage()
    parsed = _complete_usage(source=UsageSource.PARSED_FROM_CLI)

    assert reported.source is UsageSource.PROVIDER_REPORTED
    assert parsed.source is UsageSource.PARSED_FROM_CLI
    assert reported.to_dict()["cached_input_tokens"] == 0


def test_partial_usage_explicitly_identifies_every_missing_field() -> None:
    evidence = _complete_usage(
        source=UsageSource.PARSED_FROM_CLI,
        cached_input_tokens=None,
        total_tokens=None,
        unavailable_fields=(
            _absence(TokenField.CACHED_INPUT_TOKENS),
            _absence(TokenField.TOTAL_TOKENS),
        ),
    )

    assert evidence.input_tokens == 100
    assert evidence.output_tokens == 25
    assert evidence.unavailable_fields == (
        _absence(TokenField.CACHED_INPUT_TOKENS),
        _absence(TokenField.TOTAL_TOKENS),
    )


def test_entirely_unavailable_usage_has_no_counts() -> None:
    evidence = _unavailable_usage()

    assert evidence.source is UsageSource.UNAVAILABLE
    assert all(
        getattr(evidence, field.value) is None for field in TokenField
    )
    assert {item.field for item in evidence.unavailable_fields} == set(
        TokenField
    )


def test_present_zero_is_not_unavailable() -> None:
    evidence = _complete_usage(
        input_tokens=0,
        output_tokens=0,
        cached_input_tokens=0,
        total_tokens=0,
    )

    assert evidence.to_dict()["total_tokens"] == 0
    assert evidence.unavailable_fields == ()


def test_estimated_usage_remains_labeled_and_is_not_repaired() -> None:
    evidence = _complete_usage(
        source=UsageSource.ESTIMATED,
        input_tokens=10,
        output_tokens=7,
        cached_input_tokens=3,
        total_tokens=999,
    )

    assert evidence.source is UsageSource.ESTIMATED
    assert evidence.total_tokens == 999


@pytest.mark.parametrize(
    "field,value",
    (
        ("input_tokens", True),
        ("input_tokens", 1.0),
        ("output_tokens", "1"),
        ("cached_input_tokens", -1),
    ),
)
def test_token_counts_reject_coercion_and_negative_values(
    field: str,
    value,
) -> None:
    with pytest.raises(ValidationError):
        _complete_usage(**{field: value})


def test_usage_integers_are_bounded_for_canonical_json() -> None:
    assert _complete_usage(total_tokens=MAX_USAGE_INTEGER).total_tokens == (
        MAX_USAGE_INTEGER
    )
    with pytest.raises(ValidationError):
        _complete_usage(total_tokens=MAX_USAGE_INTEGER + 1)
    with pytest.raises(ValidationError):
        _invocation(duration_ms=MAX_USAGE_INTEGER + 1)


def test_usage_rejects_missing_field_contradictions() -> None:
    with pytest.raises(ValidationError, match="every missing"):
        _complete_usage(
            total_tokens=None,
            unavailable_fields=(),
        )
    with pytest.raises(ValidationError):
        _complete_usage(
            total_tokens=None,
            unavailable_fields=(
                {
                    "field": TokenField.TOTAL_TOKENS,
                    "reason": None,
                },
            ),
        )
    with pytest.raises(ValidationError, match="duplicate"):
        _complete_usage(
            total_tokens=None,
            unavailable_fields=(
                _absence(TokenField.TOTAL_TOKENS),
                _absence(TokenField.TOTAL_TOKENS),
            ),
        )


def test_unavailable_source_rejects_counts_and_available_source_needs_count() -> None:
    with pytest.raises(ValidationError, match="cannot contain"):
        _unavailable_usage(
            input_tokens=0,
            unavailable_fields=(
                _absence(TokenField.OUTPUT_TOKENS),
                _absence(TokenField.CACHED_INPUT_TOKENS),
                _absence(TokenField.TOTAL_TOKENS),
            ),
        )
    with pytest.raises(ValidationError, match="at least one"):
        _unavailable_usage(source=UsageSource.ESTIMATED)


def test_provider_reported_cost_uses_canonical_decimal_wire_value() -> None:
    evidence = _reported_cost(amount=Decimal("0.012500"))

    assert evidence.amount == Decimal("0.012500")
    assert evidence.to_dict()["amount"] == "0.0125"
    assert evidence.cost_type is CostType.PROVIDER_REPORTED


def test_estimated_cost_requires_complete_pricing_evidence() -> None:
    evidence = _reported_cost(
        cost_type=CostType.ESTIMATED,
        pricing_source_id="pricing.public-catalog",
        pricing_version="2026-07-01",
        pricing_effective_at=_time(),
    )
    assert evidence.cost_type is CostType.ESTIMATED
    assert evidence.pricing_effective_at == _time()

    for missing in (
        "pricing_source_id",
        "pricing_version",
        "pricing_effective_at",
    ):
        values = {
            "cost_type": CostType.ESTIMATED,
            "pricing_source_id": "pricing.public-catalog",
            "pricing_version": "2026-07-01",
            "pricing_effective_at": _time(),
            missing: None,
        }
        with pytest.raises(ValidationError, match="pricing"):
            _reported_cost(**values)


def test_invocation_rejects_future_pricing_evidence() -> None:
    cost = _reported_cost(
        cost_type=CostType.ESTIMATED,
        pricing_source_id="pricing.public-catalog",
        pricing_version="2026-07-01",
        pricing_effective_at=_time(1),
    )
    with pytest.raises(ValidationError, match="pricing"):
        _invocation(cost=cost)


def test_subscription_included_does_not_fabricate_money() -> None:
    evidence = CostEvidence(
        schema_version="1",
        cost_type=CostType.SUBSCRIPTION_INCLUDED,
        amount=None,
        currency=None,
        pricing_source_id=None,
        pricing_version=None,
        pricing_effective_at=None,
        unavailable_reason=None,
    )

    assert evidence.amount is None
    assert evidence.currency is None
    with pytest.raises(ValidationError, match="cannot contain money"):
        evidence.model_copy(update={"amount": Decimal("0")})


def test_unavailable_cost_requires_reason_and_has_no_money() -> None:
    evidence = _unavailable_cost()
    assert evidence.amount is None

    with pytest.raises(ValidationError, match="requires"):
        _unavailable_cost(unavailable_reason=None)
    with pytest.raises(ValidationError, match="cannot contain money"):
        _unavailable_cost(amount=Decimal("0"), currency="USD")


def test_real_zero_cost_differs_from_unavailable_and_subscription() -> None:
    reported = _reported_cost(amount=Decimal("0"))
    unavailable = _unavailable_cost()
    subscription = CostEvidence(
        schema_version="1",
        cost_type=CostType.SUBSCRIPTION_INCLUDED,
        amount=None,
        currency=None,
        pricing_source_id=None,
        pricing_version=None,
        pricing_effective_at=None,
        unavailable_reason=None,
    )

    assert reported.to_dict()["amount"] == "0"
    assert unavailable.amount is None
    assert subscription.amount is None
    assert len({item.cost_type for item in (reported, unavailable, subscription)}) == 3


@pytest.mark.parametrize(
    "amount",
    (0.1, 1, True, "01", "1.0", "-1", "NaN", Decimal("-1")),
)
def test_cost_rejects_floating_or_noncanonical_amount(amount) -> None:
    with pytest.raises(ValidationError):
        _reported_cost(amount=amount)


def test_cost_rejects_oversized_decimal_evidence() -> None:
    with pytest.raises(ValidationError):
        _reported_cost(amount=Decimal("1e200"))
    with pytest.raises(ValidationError):
        _reported_cost(amount="0." + "0" * 128 + "1")


@pytest.mark.parametrize("currency", ("usd", "US", "USDD", "U1D"))
def test_cost_rejects_noncanonical_currency(currency: str) -> None:
    with pytest.raises(ValidationError):
        _reported_cost(currency=currency)


@pytest.mark.parametrize(
    "status,error_category",
    (
        (AIInvocationStatus.SUCCEEDED, None),
        (AIInvocationStatus.FAILED, RunErrorCategory.PROVIDER),
        (
            AIInvocationStatus.CANCELLED,
            RunErrorCategory.CANCELLED,
        ),
    ),
)
def test_invocation_terminal_lifecycle(
    status: AIInvocationStatus,
    error_category: RunErrorCategory,
) -> None:
    record = _invocation(status=status, error_category=error_category)
    assert record.status is status


def test_invocation_lifecycle_rejects_error_contradictions() -> None:
    with pytest.raises(ValidationError, match="cannot have"):
        _invocation(error_category=RunErrorCategory.PROVIDER)
    with pytest.raises(ValidationError, match="requires"):
        _invocation(status=AIInvocationStatus.FAILED)
    with pytest.raises(ValidationError, match="cancellation"):
        _invocation(
            status=AIInvocationStatus.CANCELLED,
            error_category=RunErrorCategory.PROVIDER,
        )
    with pytest.raises(ValidationError, match="cannot use cancellation"):
        _invocation(
            status=AIInvocationStatus.FAILED,
            error_category=RunErrorCategory.CANCELLED,
        )


def test_optional_runner_and_unavailable_model_correlation() -> None:
    record = _invocation(
        runner_invocation_id=None,
        model=None,
        model_unavailable_reason=EvidenceUnavailableReason.NOT_REPORTED,
    )

    assert record.runner_invocation_id is None
    assert record.model is None
    with pytest.raises(ValidationError, match="model identity"):
        _invocation(model=None)
    with pytest.raises(ValidationError, match="model identity"):
        _invocation(
            model_unavailable_reason=EvidenceUnavailableReason.NOT_REPORTED
        )


def test_retry_and_fallback_local_invariants() -> None:
    retry = _invocation(
        invocation_id="ai-invocation.2",
        attempt_number=2,
        retry_of_invocation_id="ai-invocation.1",
    )
    fallback = _invocation(
        invocation_id="ai-invocation.2",
        attempt_number=2,
        fallback_from_invocation_id="ai-invocation.1",
    )
    assert retry.retry_of_invocation_id == "ai-invocation.1"
    assert fallback.fallback_from_invocation_id == "ai-invocation.1"

    invalid_updates = (
        {"retry_of_invocation_id": "ai-invocation.0"},
        {"attempt_number": 2},
        {
            "invocation_id": "ai-invocation.2",
            "attempt_number": 2,
            "retry_of_invocation_id": "ai-invocation.1",
            "fallback_from_invocation_id": "ai-invocation.0",
        },
        {
            "invocation_id": "ai-invocation.2",
            "attempt_number": 2,
            "retry_of_invocation_id": "ai-invocation.2",
        },
    )
    for updates in invalid_updates:
        with pytest.raises(ValidationError):
            _invocation(**updates)


def test_invocation_timestamps_normalize_to_utc_without_deriving_duration() -> None:
    eastern = timezone(timedelta(hours=-4))
    record = _invocation(
        started_at=datetime(2026, 7, 24, 8, tzinfo=eastern),
        completed_at=datetime(2026, 7, 24, 8, 1, tzinfo=eastern),
        duration_ms=7,
    )

    assert record.started_at == _time()
    assert record.completed_at == _time(1)
    assert record.duration_ms == 7
    assert record.to_dict()["started_at"].endswith("Z")


def test_invocation_rejects_bad_time_order_and_coerced_duration() -> None:
    with pytest.raises(ValidationError, match="must not precede"):
        _invocation(started_at=_time(1), completed_at=_time())
    for duration in (True, 1.0, "1", -1):
        with pytest.raises(ValidationError):
            _invocation(duration_ms=duration)


def test_contracts_round_trip_as_canonical_json() -> None:
    record = _invocation()
    wire = json.loads(json.dumps(record.to_dict()))

    assert AIInvocationRecord.from_dict(wire) == record
    assert record.model_copy() == record


def test_revalidated_copy_rejects_corruption() -> None:
    record = _invocation()

    with pytest.raises(ValidationError):
        record.model_copy(update={"attempt_number": 2})
    with pytest.raises(ValidationError):
        record.usage.model_copy(
            update={
                "total_tokens": None,
                "unavailable_fields": (),
            }
        )


def test_caller_collection_is_copied_and_frozen() -> None:
    cached_absence = _absence(
        TokenField.CACHED_INPUT_TOKENS,
        EvidenceUnavailableReason.NOT_SUPPORTED,
    )
    total_absence = _absence(
        TokenField.TOTAL_TOKENS,
        EvidenceUnavailableReason.NOT_REPORTED,
    )
    unavailable_fields = [
        cached_absence,
        total_absence,
    ]
    evidence = _complete_usage(
        cached_input_tokens=None,
        total_tokens=None,
        unavailable_fields=unavailable_fields,
    )
    unavailable_fields.clear()
    cached_absence.__dict__["reason"] = EvidenceUnavailableReason.PARSING_FAILED

    assert evidence.unavailable_fields == (
        _absence(
            TokenField.CACHED_INPUT_TOKENS,
            EvidenceUnavailableReason.NOT_SUPPORTED,
        ),
        _absence(
            TokenField.TOTAL_TOKENS,
            EvidenceUnavailableReason.NOT_REPORTED,
        ),
    )
    with pytest.raises((AttributeError, TypeError)):
        evidence.unavailable_fields.append(
            _absence(TokenField.INPUT_TOKENS)
        )


def test_invocation_retains_independent_nested_contract_snapshots() -> None:
    usage = _complete_usage()
    cost = _reported_cost()
    record = _invocation(
        status=AIInvocationStatus.FAILED,
        usage=usage,
        cost=cost,
        error_category=RunErrorCategory.PROVIDER,
    )

    usage.__dict__["total_tokens"] = 999
    cost.__dict__["amount"] = Decimal("999")

    assert record.usage.total_tokens == 125
    assert record.cost.amount == Decimal("0.0125")
    assert record.error_category is RunErrorCategory.PROVIDER
    assert record.usage is not usage
    assert record.cost is not cost


def test_unknown_prohibited_runtime_and_secret_inputs_fail_safely() -> None:
    marker = "runtime-secret-marker"
    wire = _invocation().to_dict()
    wire["prompt"] = marker

    with pytest.raises(UsageContractValidationError) as captured:
        AIInvocationRecord.from_dict(wire)

    assert marker not in str(captured.value)
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None

    invalid_identifier = marker + "/path"
    with pytest.raises(ValidationError) as identifier:
        _invocation(provider=invalid_identifier)
    assert invalid_identifier not in str(identifier.value)

    with pytest.raises(ValidationError) as runtime:
        AIInvocationRecord(
            **_invocation().model_dump(mode="python"),
            provider_client=RuntimeObject(),
        )
    assert marker not in str(runtime.value)


def test_from_dict_rejects_cycles_depth_nonfinite_and_oversized_strings() -> None:
    wire = _invocation().to_dict()
    cyclic = deepcopy(wire)
    cyclic["unexpected"] = cyclic

    excessive = deepcopy(wire)
    nested = []
    excessive["unexpected"] = nested
    for _ in range(40):
        child = []
        nested.append(child)
        nested = child

    nonfinite = deepcopy(wire)
    nonfinite["unexpected"] = float("inf")

    oversized = deepcopy(wire)
    oversized["unexpected"] = "x" * 70000

    for value in (cyclic, excessive, nonfinite, oversized):
        with pytest.raises(UsageContractValidationError):
            AIInvocationRecord.from_dict(value)


def test_from_dict_requires_exact_canonical_wire_types() -> None:
    wire = _reported_cost().to_dict()
    assert CostEvidence.from_dict(wire) == _reported_cost()

    changed = deepcopy(wire)
    changed["amount"] = Decimal("0.0125")
    with pytest.raises(UsageContractValidationError):
        CostEvidence.from_dict(changed)
