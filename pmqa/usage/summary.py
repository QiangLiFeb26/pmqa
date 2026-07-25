"""Deterministic provider-neutral summaries of canonical AI invocations."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, localcontext
from enum import Enum
from typing import Any, Dict, Literal, Optional, Protocol, Tuple
from typing import TypeVar, runtime_checkable

from pydantic import Field, field_serializer, field_validator, model_validator

from pmqa.run import RunContractValidationError, validate_run_identifier
from pmqa.run.models import (
    _RunContract,
    _canonical_timestamp,
    _parse_enum,
    _serialize_timestamp,
)
from pmqa.usage.contracts import (
    MAX_USAGE_INTEGER,
    AIInvocationRecord,
    AIInvocationStatus,
    CostEvidence,
    CostType,
    EvidenceUnavailableReason,
    TokenField,
    UsageContractValidationError,
    _canonical_currency,
    _canonical_decimal,
    _serialize_decimal,
)


USAGE_SUMMARY_SCHEMA_VERSION = "1"
MAX_USAGE_SUMMARY_RECORDS = 64
MAX_USAGE_AGGREGATE_INTEGER = MAX_USAGE_INTEGER
_INVALID_SUMMARY_MESSAGE = "invalid PMQA usage summary"
_RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS = (
    MemoryError,
    KeyboardInterrupt,
    SystemExit,
    GeneratorExit,
)
_MONETARY_COST_TYPES = frozenset(
    {
        CostType.PROVIDER_REPORTED,
        CostType.ESTIMATED,
    }
)
_COST_TYPE_ORDER = {
    cost_type: index for index, cost_type in enumerate(CostType)
}

_SummaryContractT = TypeVar(
    "_SummaryContractT",
    bound="_SummaryContract",
)


class UsageSummaryValidationError(ValueError):
    """Fixed safe failure for persisted usage-summary reconstruction."""

    def __init__(self) -> None:
        super().__init__(_INVALID_SUMMARY_MESSAGE)


class _SummaryContract(_RunContract):
    """Canonical frozen summary contract with a summary-owned safe error."""

    @classmethod
    def from_dict(
        cls: type[_SummaryContractT],
        value: Any,
    ) -> _SummaryContractT:
        failed = False
        result = None
        try:
            result = super().from_dict(value)
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except RunContractValidationError:
            failed = True
        if failed or result is None:
            raise UsageSummaryValidationError() from None
        return result


class UsageSummaryScope(str, Enum):
    """Explicit correlation scope for a pure usage summary."""

    SESSION = "session"
    RUN = "run"


class UsageAggregationErrorCode(str, Enum):
    """Fixed failure vocabulary for pure usage aggregation."""

    INVALID_REQUEST = "invalid_request"
    INVALID_RECORD = "invalid_record"
    CORRELATION_MISMATCH = "correlation_mismatch"
    DUPLICATE_INVOCATION = "duplicate_invocation"
    AGGREGATE_OVERFLOW = "aggregate_overflow"


_AGGREGATION_ERROR_MESSAGES = {
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
}


class UsageAggregationError(RuntimeError):
    """Expected fixed, marker-safe aggregation failure."""

    def __init__(self, code: UsageAggregationErrorCode) -> None:
        if type(code) is not UsageAggregationErrorCode:
            raise TypeError("code must be a UsageAggregationErrorCode")
        self.code = code
        super().__init__(_AGGREGATION_ERROR_MESSAGES[code])


class UsageTokenFieldSummary(_SummaryContract):
    """Observed and unavailable coverage for one token field."""

    schema_version: Literal["1"]
    field: TokenField
    total: Optional[int] = Field(
        default=None,
        ge=0,
        le=MAX_USAGE_AGGREGATE_INTEGER,
    )
    observed_invocation_count: int = Field(
        ge=0,
        le=MAX_USAGE_SUMMARY_RECORDS,
    )
    unavailable_invocation_count: int = Field(
        ge=0,
        le=MAX_USAGE_SUMMARY_RECORDS,
    )

    @field_validator("field", mode="before")
    @classmethod
    def validate_field(cls, value: Any) -> TokenField:
        return _parse_enum(value, TokenField, "field")

    @model_validator(mode="after")
    def validate_coverage(self) -> "UsageTokenFieldSummary":
        if (self.total is None) != (self.observed_invocation_count == 0):
            raise ValueError(
                "token total must reflect observed invocation coverage"
            )
        return self


class UsageCostBucket(_SummaryContract):
    """One exact compatible cost-evidence identity and aggregate."""

    schema_version: Literal["1"]
    cost_type: CostType
    currency: Optional[str] = None
    pricing_source_id: Optional[str] = None
    pricing_version: Optional[str] = None
    pricing_effective_at: Optional[datetime] = None
    unavailable_reason: Optional[EvidenceUnavailableReason] = None
    invocation_count: int = Field(
        ge=1,
        le=MAX_USAGE_SUMMARY_RECORDS,
    )
    amount: Optional[Decimal] = None

    @field_validator("cost_type", mode="before")
    @classmethod
    def validate_cost_type(cls, value: Any) -> CostType:
        return _parse_enum(value, CostType, "cost_type")

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _canonical_currency(value)

    @field_validator("pricing_source_id", "pricing_version")
    @classmethod
    def validate_pricing_identifiers(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is None:
            return None
        return validate_run_identifier(value)

    @field_validator("pricing_effective_at", mode="before")
    @classmethod
    def validate_pricing_effective_at(
        cls,
        value: Any,
    ) -> Optional[datetime]:
        if value is None:
            return None
        return _canonical_timestamp(value, "pricing_effective_at")

    @field_serializer("pricing_effective_at")
    def serialize_pricing_effective_at(
        self,
        value: Optional[datetime],
    ) -> Optional[str]:
        return None if value is None else _serialize_timestamp(value)

    @field_validator("unavailable_reason", mode="before")
    @classmethod
    def validate_unavailable_reason(
        cls,
        value: Any,
    ) -> Optional[EvidenceUnavailableReason]:
        if value is None:
            return None
        return _parse_enum(
            value,
            EvidenceUnavailableReason,
            "unavailable_reason",
        )

    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, value: Any) -> Optional[Decimal]:
        if value is None:
            return None
        return _canonical_decimal(value, "amount")

    @field_serializer("amount")
    def serialize_amount(self, value: Optional[Decimal]) -> Optional[str]:
        return None if value is None else _serialize_decimal(value)

    @model_validator(mode="after")
    def validate_identity(self) -> "UsageCostBucket":
        pricing_fields = (
            self.pricing_source_id,
            self.pricing_version,
            self.pricing_effective_at,
        )
        has_all_pricing = all(value is not None for value in pricing_fields)
        has_any_pricing = any(value is not None for value in pricing_fields)
        if has_any_pricing and not has_all_pricing:
            raise ValueError("pricing provenance must be complete")
        if self.cost_type in _MONETARY_COST_TYPES:
            if self.amount is None or self.currency is None:
                raise ValueError(
                    "monetary bucket requires amount and currency"
                )
            if self.unavailable_reason is not None:
                raise ValueError(
                    "monetary bucket cannot be unavailable"
                )
            if self.cost_type is CostType.ESTIMATED and not has_all_pricing:
                raise ValueError(
                    "estimated bucket requires pricing provenance"
                )
        else:
            if (
                self.amount is not None
                or self.currency is not None
                or has_any_pricing
            ):
                raise ValueError(
                    "non-monetary bucket cannot contain money or pricing"
                )
            if (
                self.cost_type is CostType.UNAVAILABLE
                and self.unavailable_reason is None
            ):
                raise ValueError(
                    "unavailable bucket requires an unavailable reason"
                )
            if (
                self.cost_type is CostType.SUBSCRIPTION_INCLUDED
                and self.unavailable_reason is not None
            ):
                raise ValueError(
                    "subscription bucket cannot be unavailable"
                )
        return self


class UsageProviderModelSummary(_SummaryContract):
    """One exact provider/model identity with non-recursive metrics."""

    schema_version: Literal["1"]
    provider: str
    model: Optional[str] = None
    model_unavailable_reason: Optional[EvidenceUnavailableReason] = None
    invocation_count: int = Field(
        ge=1,
        le=MAX_USAGE_SUMMARY_RECORDS,
    )
    succeeded_invocation_count: int = Field(
        ge=0,
        le=MAX_USAGE_SUMMARY_RECORDS,
    )
    failed_invocation_count: int = Field(
        ge=0,
        le=MAX_USAGE_SUMMARY_RECORDS,
    )
    cancelled_invocation_count: int = Field(
        ge=0,
        le=MAX_USAGE_SUMMARY_RECORDS,
    )
    retry_invocation_count: int = Field(
        ge=0,
        le=MAX_USAGE_SUMMARY_RECORDS,
    )
    fallback_invocation_count: int = Field(
        ge=0,
        le=MAX_USAGE_SUMMARY_RECORDS,
    )
    total_duration_ms: int = Field(
        ge=0,
        le=MAX_USAGE_AGGREGATE_INTEGER,
    )
    token_fields: Tuple[UsageTokenFieldSummary, ...]
    cost_buckets: Tuple[UsageCostBucket, ...]

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        return validate_run_identifier(value)

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return validate_run_identifier(value)

    @field_validator("model_unavailable_reason", mode="before")
    @classmethod
    def validate_model_unavailable_reason(
        cls,
        value: Any,
    ) -> Optional[EvidenceUnavailableReason]:
        if value is None:
            return None
        return _parse_enum(
            value,
            EvidenceUnavailableReason,
            "model_unavailable_reason",
        )

    @field_validator("token_fields", mode="before")
    @classmethod
    def validate_token_fields_input(cls, value: Any) -> Tuple[Any, ...]:
        return _bounded_array(value, len(TokenField), "token_fields")

    @field_validator("token_fields")
    @classmethod
    def snapshot_token_fields(
        cls,
        value: Tuple[UsageTokenFieldSummary, ...],
    ) -> Tuple[UsageTokenFieldSummary, ...]:
        return _snapshot_token_fields(value)

    @field_validator("cost_buckets", mode="before")
    @classmethod
    def validate_cost_buckets_input(cls, value: Any) -> Tuple[Any, ...]:
        return _bounded_array(
            value,
            MAX_USAGE_SUMMARY_RECORDS,
            "cost_buckets",
        )

    @field_validator("cost_buckets")
    @classmethod
    def snapshot_cost_buckets(
        cls,
        value: Tuple[UsageCostBucket, ...],
    ) -> Tuple[UsageCostBucket, ...]:
        return _snapshot_cost_buckets(value)

    @model_validator(mode="after")
    def validate_group(self) -> "UsageProviderModelSummary":
        if (self.model is None) == (self.model_unavailable_reason is None):
            raise ValueError(
                "model identity or unavailable reason must be present"
            )
        _validate_metrics(
            invocation_count=self.invocation_count,
            succeeded_invocation_count=self.succeeded_invocation_count,
            failed_invocation_count=self.failed_invocation_count,
            cancelled_invocation_count=self.cancelled_invocation_count,
            retry_invocation_count=self.retry_invocation_count,
            fallback_invocation_count=self.fallback_invocation_count,
            token_fields=self.token_fields,
            cost_buckets=self.cost_buckets,
        )
        return self


class UsageSummary(_SummaryContract):
    """One deterministic session- or run-scoped usage summary."""

    schema_version: Literal["1"]
    scope: UsageSummaryScope
    scope_id: str
    invocation_count: int = Field(
        ge=0,
        le=MAX_USAGE_SUMMARY_RECORDS,
    )
    succeeded_invocation_count: int = Field(
        ge=0,
        le=MAX_USAGE_SUMMARY_RECORDS,
    )
    failed_invocation_count: int = Field(
        ge=0,
        le=MAX_USAGE_SUMMARY_RECORDS,
    )
    cancelled_invocation_count: int = Field(
        ge=0,
        le=MAX_USAGE_SUMMARY_RECORDS,
    )
    retry_invocation_count: int = Field(
        ge=0,
        le=MAX_USAGE_SUMMARY_RECORDS,
    )
    fallback_invocation_count: int = Field(
        ge=0,
        le=MAX_USAGE_SUMMARY_RECORDS,
    )
    total_duration_ms: int = Field(
        ge=0,
        le=MAX_USAGE_AGGREGATE_INTEGER,
    )
    token_fields: Tuple[UsageTokenFieldSummary, ...]
    cost_buckets: Tuple[UsageCostBucket, ...]
    provider_model_groups: Tuple[UsageProviderModelSummary, ...]

    @field_validator("scope", mode="before")
    @classmethod
    def validate_scope(cls, value: Any) -> UsageSummaryScope:
        return _parse_enum(value, UsageSummaryScope, "scope")

    @field_validator("scope_id")
    @classmethod
    def validate_scope_id(cls, value: str) -> str:
        return validate_run_identifier(value)

    @field_validator("token_fields", mode="before")
    @classmethod
    def validate_token_fields_input(cls, value: Any) -> Tuple[Any, ...]:
        return _bounded_array(value, len(TokenField), "token_fields")

    @field_validator("token_fields")
    @classmethod
    def snapshot_token_fields(
        cls,
        value: Tuple[UsageTokenFieldSummary, ...],
    ) -> Tuple[UsageTokenFieldSummary, ...]:
        return _snapshot_token_fields(value)

    @field_validator("cost_buckets", mode="before")
    @classmethod
    def validate_cost_buckets_input(cls, value: Any) -> Tuple[Any, ...]:
        return _bounded_array(
            value,
            MAX_USAGE_SUMMARY_RECORDS,
            "cost_buckets",
        )

    @field_validator("cost_buckets")
    @classmethod
    def snapshot_cost_buckets(
        cls,
        value: Tuple[UsageCostBucket, ...],
    ) -> Tuple[UsageCostBucket, ...]:
        return _snapshot_cost_buckets(value)

    @field_validator("provider_model_groups", mode="before")
    @classmethod
    def validate_provider_model_groups_input(
        cls,
        value: Any,
    ) -> Tuple[Any, ...]:
        return _bounded_array(
            value,
            MAX_USAGE_SUMMARY_RECORDS,
            "provider_model_groups",
        )

    @field_validator("provider_model_groups")
    @classmethod
    def snapshot_provider_model_groups(
        cls,
        value: Tuple[UsageProviderModelSummary, ...],
    ) -> Tuple[UsageProviderModelSummary, ...]:
        snapshots = tuple(
            UsageProviderModelSummary.from_dict(item.to_dict())
            for item in value
        )
        identities = tuple(
            _provider_model_identity(item) for item in snapshots
        )
        if len(identities) != len(set(identities)):
            raise ValueError("provider/model groups must be duplicate-free")
        return tuple(sorted(snapshots, key=_provider_model_sort_key))

    @model_validator(mode="after")
    def validate_group_coverage(self) -> "UsageSummary":
        _validate_metrics(
            invocation_count=self.invocation_count,
            succeeded_invocation_count=self.succeeded_invocation_count,
            failed_invocation_count=self.failed_invocation_count,
            cancelled_invocation_count=self.cancelled_invocation_count,
            retry_invocation_count=self.retry_invocation_count,
            fallback_invocation_count=self.fallback_invocation_count,
            token_fields=self.token_fields,
            cost_buckets=self.cost_buckets,
        )
        _validate_group_rollup(self)
        return self


@runtime_checkable
class UsageAggregator(Protocol):
    """Pure deterministic aggregation of an explicit invocation selection."""

    def summarize(
        self,
        records: Tuple[AIInvocationRecord, ...],
        *,
        scope: UsageSummaryScope,
        scope_id: str,
    ) -> UsageSummary:
        """Return one canonical summary without storage or provider access."""


class DefaultUsageAggregator:
    """Default pure provider-neutral usage aggregation implementation."""

    __slots__ = ()

    def summarize(
        self,
        records: Tuple[AIInvocationRecord, ...],
        *,
        scope: UsageSummaryScope,
        scope_id: str,
    ) -> UsageSummary:
        if (
            type(records) is not tuple
            or len(records) > MAX_USAGE_SUMMARY_RECORDS
            or type(scope) is not UsageSummaryScope
        ):
            raise UsageAggregationError(
                UsageAggregationErrorCode.INVALID_REQUEST
            ) from None
        canonical_scope_id = self._canonical_scope_id(scope_id)
        snapshots = tuple(self._snapshot_record(record) for record in records)
        invocation_ids = tuple(
            record.invocation_id for record in snapshots
        )
        if len(invocation_ids) != len(set(invocation_ids)):
            raise UsageAggregationError(
                UsageAggregationErrorCode.DUPLICATE_INVOCATION
            ) from None
        correlation_field = (
            "session_id"
            if scope is UsageSummaryScope.SESSION
            else "run_id"
        )
        if any(
            getattr(record, correlation_field) != canonical_scope_id
            for record in snapshots
        ):
            raise UsageAggregationError(
                UsageAggregationErrorCode.CORRELATION_MISMATCH
            ) from None

        metrics = self._aggregate_metrics(snapshots)
        grouped_records: Dict[
            tuple[str, Optional[str], Optional[EvidenceUnavailableReason]],
            list[AIInvocationRecord],
        ] = {}
        for record in snapshots:
            key = (
                record.provider,
                record.model,
                record.model_unavailable_reason,
            )
            grouped_records.setdefault(key, []).append(record)
        groups = []
        for key, group_records in grouped_records.items():
            provider, model, unavailable_reason = key
            group_metrics = self._aggregate_metrics(tuple(group_records))
            groups.append(
                UsageProviderModelSummary(
                    schema_version=USAGE_SUMMARY_SCHEMA_VERSION,
                    provider=provider,
                    model=model,
                    model_unavailable_reason=unavailable_reason,
                    **group_metrics,
                )
            )
        summary = UsageSummary(
            schema_version=USAGE_SUMMARY_SCHEMA_VERSION,
            scope=scope,
            scope_id=canonical_scope_id,
            provider_model_groups=tuple(groups),
            **metrics,
        )
        return UsageSummary.from_dict(summary.to_dict())

    @staticmethod
    def _canonical_scope_id(value: str) -> str:
        failed = False
        canonical = None
        try:
            canonical = validate_run_identifier(value)
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except ValueError:
            failed = True
        if failed or canonical is None:
            raise UsageAggregationError(
                UsageAggregationErrorCode.INVALID_REQUEST
            ) from None
        return canonical

    @staticmethod
    def _snapshot_record(record: AIInvocationRecord) -> AIInvocationRecord:
        failed = False
        snapshot = None
        try:
            if type(record) is not AIInvocationRecord:
                raise ValueError
            snapshot = AIInvocationRecord.from_dict(record.to_dict())
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except Exception:
            failed = True
        if failed or snapshot is None:
            raise UsageAggregationError(
                UsageAggregationErrorCode.INVALID_RECORD
            ) from None
        return snapshot

    def _aggregate_metrics(
        self,
        records: Tuple[AIInvocationRecord, ...],
    ) -> Dict[str, Any]:
        duration = 0
        for record in records:
            duration = self._bounded_integer_add(
                duration,
                record.duration_ms,
            )
        token_fields = []
        for field in TokenField:
            total = 0
            observed = 0
            for record in records:
                value = getattr(record.usage, field.value)
                if value is not None:
                    observed += 1
                    total = self._bounded_integer_add(total, value)
            token_fields.append(
                UsageTokenFieldSummary(
                    schema_version=USAGE_SUMMARY_SCHEMA_VERSION,
                    field=field,
                    total=None if observed == 0 else total,
                    observed_invocation_count=observed,
                    unavailable_invocation_count=len(records) - observed,
                )
            )

        cost_groups: Dict[tuple[Any, ...], list[CostEvidence]] = {}
        for record in records:
            identity = _cost_evidence_identity(record.cost)
            cost_groups.setdefault(identity, []).append(record.cost)
        cost_buckets = []
        for costs in cost_groups.values():
            first = costs[0]
            amount = None
            if first.cost_type in _MONETARY_COST_TYPES:
                amount = Decimal(0)
                for cost in costs:
                    if cost.amount is None:
                        raise UsageAggregationError(
                            UsageAggregationErrorCode.INVALID_RECORD
                        ) from None
                    amount = self._bounded_decimal_add(amount, cost.amount)
            cost_buckets.append(
                UsageCostBucket(
                    schema_version=USAGE_SUMMARY_SCHEMA_VERSION,
                    cost_type=first.cost_type,
                    currency=first.currency,
                    pricing_source_id=first.pricing_source_id,
                    pricing_version=first.pricing_version,
                    pricing_effective_at=first.pricing_effective_at,
                    unavailable_reason=first.unavailable_reason,
                    invocation_count=len(costs),
                    amount=amount,
                )
            )

        return {
            "invocation_count": len(records),
            "succeeded_invocation_count": sum(
                record.status is AIInvocationStatus.SUCCEEDED
                for record in records
            ),
            "failed_invocation_count": sum(
                record.status is AIInvocationStatus.FAILED
                for record in records
            ),
            "cancelled_invocation_count": sum(
                record.status is AIInvocationStatus.CANCELLED
                for record in records
            ),
            "retry_invocation_count": sum(
                record.retry_of_invocation_id is not None
                for record in records
            ),
            "fallback_invocation_count": sum(
                record.fallback_from_invocation_id is not None
                for record in records
            ),
            "total_duration_ms": duration,
            "token_fields": tuple(token_fields),
            "cost_buckets": tuple(cost_buckets),
        }

    @staticmethod
    def _bounded_integer_add(left: int, right: int) -> int:
        total = left + right
        if total > MAX_USAGE_AGGREGATE_INTEGER:
            raise UsageAggregationError(
                UsageAggregationErrorCode.AGGREGATE_OVERFLOW
            ) from None
        return total

    @staticmethod
    def _bounded_decimal_add(
        left: Decimal,
        right: Decimal,
    ) -> Decimal:
        with localcontext() as context:
            context.prec = 256
            total = left + right
        failed = False
        try:
            canonical = _canonical_decimal(total, "amount")
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except ValueError:
            failed = True
            canonical = None
        if failed or canonical is None:
            raise UsageAggregationError(
                UsageAggregationErrorCode.AGGREGATE_OVERFLOW
            ) from None
        return canonical


def _snapshot_token_fields(
    value: Tuple[UsageTokenFieldSummary, ...],
) -> Tuple[UsageTokenFieldSummary, ...]:
    snapshots = tuple(
        UsageTokenFieldSummary.from_dict(item.to_dict()) for item in value
    )
    fields = tuple(item.field for item in snapshots)
    if len(fields) != len(set(fields)):
        raise ValueError("token fields must be duplicate-free")
    return tuple(
        sorted(snapshots, key=lambda item: _token_field_order(item.field))
    )


def _snapshot_cost_buckets(
    value: Tuple[UsageCostBucket, ...],
) -> Tuple[UsageCostBucket, ...]:
    snapshots = tuple(
        UsageCostBucket.from_dict(item.to_dict()) for item in value
    )
    identities = tuple(_cost_bucket_identity(item) for item in snapshots)
    if len(identities) != len(set(identities)):
        raise ValueError("cost buckets must be duplicate-free")
    return tuple(sorted(snapshots, key=_cost_bucket_sort_key))


def _validate_metrics(
    *,
    invocation_count: int,
    succeeded_invocation_count: int,
    failed_invocation_count: int,
    cancelled_invocation_count: int,
    retry_invocation_count: int,
    fallback_invocation_count: int,
    token_fields: Tuple[UsageTokenFieldSummary, ...],
    cost_buckets: Tuple[UsageCostBucket, ...],
) -> None:
    if (
        succeeded_invocation_count
        + failed_invocation_count
        + cancelled_invocation_count
        != invocation_count
    ):
        raise ValueError("status counts must cover every invocation")
    if (
        retry_invocation_count > invocation_count
        or fallback_invocation_count > invocation_count
    ):
        raise ValueError("predecessor counts cannot exceed invocation count")
    if tuple(item.field for item in token_fields) != tuple(TokenField):
        raise ValueError("every token field must appear exactly once")
    for item in token_fields:
        if (
            item.observed_invocation_count
            + item.unavailable_invocation_count
            != invocation_count
        ):
            raise ValueError("token coverage must equal invocation count")
    if (
        sum(item.invocation_count for item in cost_buckets)
        != invocation_count
    ):
        raise ValueError("cost buckets must cover every invocation")


def _validate_group_rollup(summary: UsageSummary) -> None:
    count_fields = (
        "invocation_count",
        "succeeded_invocation_count",
        "failed_invocation_count",
        "cancelled_invocation_count",
        "retry_invocation_count",
        "fallback_invocation_count",
    )
    for field_name in count_fields:
        derived = 0
        for group in summary.provider_model_groups:
            derived = _bounded_summary_integer_add(
                derived,
                getattr(group, field_name),
                MAX_USAGE_SUMMARY_RECORDS,
            )
        if derived != getattr(summary, field_name):
            raise ValueError("provider/model count roll-up is inconsistent")

    duration = 0
    for group in summary.provider_model_groups:
        duration = _bounded_summary_integer_add(
            duration,
            group.total_duration_ms,
            MAX_USAGE_AGGREGATE_INTEGER,
        )
    if duration != summary.total_duration_ms:
        raise ValueError("provider/model duration roll-up is inconsistent")

    top_tokens = {item.field: item for item in summary.token_fields}
    for field in TokenField:
        observed = 0
        unavailable = 0
        total = 0
        observed_total = False
        for group in summary.provider_model_groups:
            item = next(
                token
                for token in group.token_fields
                if token.field is field
            )
            observed = _bounded_summary_integer_add(
                observed,
                item.observed_invocation_count,
                MAX_USAGE_SUMMARY_RECORDS,
            )
            unavailable = _bounded_summary_integer_add(
                unavailable,
                item.unavailable_invocation_count,
                MAX_USAGE_SUMMARY_RECORDS,
            )
            if item.total is not None:
                observed_total = True
                total = _bounded_summary_integer_add(
                    total,
                    item.total,
                    MAX_USAGE_AGGREGATE_INTEGER,
                )
        top = top_tokens[field]
        if (
            observed != top.observed_invocation_count
            or unavailable != top.unavailable_invocation_count
        ):
            raise ValueError("provider/model token coverage is inconsistent")
        if top.total is None:
            if observed_total:
                raise ValueError("provider/model token total is inconsistent")
        elif not observed_total or total != top.total:
            raise ValueError("provider/model token total is inconsistent")

    derived_costs: Dict[
        tuple[Any, ...],
        tuple[int, Optional[Decimal]],
    ] = {}
    for group in summary.provider_model_groups:
        for bucket in group.cost_buckets:
            identity = _cost_bucket_identity(bucket)
            previous_count, previous_amount = derived_costs.get(
                identity,
                (0, None),
            )
            invocation_count = _bounded_summary_integer_add(
                previous_count,
                bucket.invocation_count,
                MAX_USAGE_SUMMARY_RECORDS,
            )
            amount = None
            if bucket.cost_type in _MONETARY_COST_TYPES:
                if bucket.amount is None:
                    raise ValueError(
                        "monetary provider/model bucket requires an amount"
                    )
                amount = _bounded_summary_decimal_add(
                    previous_amount or Decimal(0),
                    bucket.amount,
                )
            derived_costs[identity] = (invocation_count, amount)

    top_costs = {
        _cost_bucket_identity(bucket): (bucket.invocation_count, bucket.amount)
        for bucket in summary.cost_buckets
    }
    if derived_costs != top_costs:
        raise ValueError("provider/model cost roll-up is inconsistent")


def _bounded_summary_integer_add(
    left: int,
    right: int,
    maximum: int,
) -> int:
    if right > maximum - left:
        raise ValueError("provider/model integer roll-up exceeds bounds")
    return left + right


def _bounded_summary_decimal_add(
    left: Decimal,
    right: Decimal,
) -> Decimal:
    failed = False
    canonical: Optional[Decimal] = None
    try:
        with localcontext() as context:
            context.prec = 512
            total = left + right
        canonical = _canonical_decimal(total, "amount")
    except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
        raise
    except Exception:
        failed = True
    if failed or canonical is None:
        raise ValueError("provider/model cost roll-up exceeds bounds") from None
    return canonical


def _bounded_array(
    value: Any,
    maximum: int,
    field_name: str,
) -> Tuple[Any, ...]:
    if type(value) not in {list, tuple} or len(value) > maximum:
        raise ValueError(f"{field_name} must be a bounded ordered array")
    return tuple(value)


def _token_field_order(field: TokenField) -> int:
    return tuple(TokenField).index(field)


def _cost_evidence_identity(cost: CostEvidence) -> tuple[Any, ...]:
    return (
        cost.cost_type,
        cost.currency,
        cost.pricing_source_id,
        cost.pricing_version,
        cost.pricing_effective_at,
        cost.unavailable_reason,
    )


def _cost_bucket_identity(bucket: UsageCostBucket) -> tuple[Any, ...]:
    return (
        bucket.cost_type,
        bucket.currency,
        bucket.pricing_source_id,
        bucket.pricing_version,
        bucket.pricing_effective_at,
        bucket.unavailable_reason,
    )


def _cost_bucket_sort_key(bucket: UsageCostBucket) -> tuple[Any, ...]:
    return (
        _COST_TYPE_ORDER[bucket.cost_type],
        bucket.currency or "",
        bucket.pricing_source_id or "",
        bucket.pricing_version or "",
        (
            ""
            if bucket.pricing_effective_at is None
            else _serialize_timestamp(bucket.pricing_effective_at)
        ),
        (
            ""
            if bucket.unavailable_reason is None
            else bucket.unavailable_reason.value
        ),
    )


def _provider_model_identity(
    group: UsageProviderModelSummary,
) -> tuple[Any, ...]:
    return (
        group.provider,
        group.model,
        group.model_unavailable_reason,
    )


def _provider_model_sort_key(
    group: UsageProviderModelSummary,
) -> tuple[Any, ...]:
    return (
        group.provider,
        0 if group.model is not None else 1,
        group.model or "",
        (
            ""
            if group.model_unavailable_reason is None
            else group.model_unavailable_reason.value
        ),
    )


__all__ = [
    "USAGE_SUMMARY_SCHEMA_VERSION",
    "MAX_USAGE_SUMMARY_RECORDS",
    "MAX_USAGE_AGGREGATE_INTEGER",
    "DefaultUsageAggregator",
    "UsageAggregationError",
    "UsageAggregationErrorCode",
    "UsageAggregator",
    "UsageCostBucket",
    "UsageProviderModelSummary",
    "UsageSummary",
    "UsageSummaryScope",
    "UsageSummaryValidationError",
    "UsageTokenFieldSummary",
]
