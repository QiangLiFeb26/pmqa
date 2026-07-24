"""Canonical provider-neutral AI invocation usage and cost contracts."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
import re
from typing import Any, Literal, Optional, Tuple, TypeVar

from pydantic import Field, field_serializer, field_validator, model_validator

from pmqa.run import (
    RunErrorCategory,
    RunContractValidationError,
    validate_run_identifier,
)
from pmqa.run.models import (
    _RunContract,
    _canonical_timestamp,
    _parse_enum,
    _serialize_timestamp,
)


USAGE_CONTRACT_SCHEMA_VERSION = "1"
MAX_USAGE_INTEGER = 9_223_372_036_854_775_807
_INVALID_USAGE_CONTRACT_MESSAGE = "invalid PMQA usage contract"
_MAX_DECIMAL_LENGTH = 128
_CANONICAL_DECIMAL_PATTERN = re.compile(
    r"^(?:0|[1-9][0-9]*)(?:\.[0-9]*[1-9])?$",
    flags=re.ASCII,
)
_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$", flags=re.ASCII)
_TOKEN_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cached_input_tokens",
    "total_tokens",
)
_RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS = (
    MemoryError,
    KeyboardInterrupt,
    SystemExit,
    GeneratorExit,
)

_UsageContractT = TypeVar("_UsageContractT", bound="_UsageContract")


class UsageContractValidationError(ValueError):
    """Fixed safe failure for persisted usage-contract reconstruction."""

    def __init__(self) -> None:
        super().__init__(_INVALID_USAGE_CONTRACT_MESSAGE)


class _UsageContract(_RunContract):
    """Reuse canonical Run persistence bounds with a usage-owned error."""

    @classmethod
    def from_dict(
        cls: type[_UsageContractT],
        value: Any,
    ) -> _UsageContractT:
        failed = False
        result = None
        try:
            result = super().from_dict(value)
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except RunContractValidationError:
            failed = True
        if failed or result is None:
            raise UsageContractValidationError() from None
        return result


class UsageSource(str, Enum):
    """Origin of token-usage evidence."""

    PROVIDER_REPORTED = "provider_reported"
    PARSED_FROM_CLI = "parsed_from_cli"
    ESTIMATED = "estimated"
    UNAVAILABLE = "unavailable"


class CostType(str, Enum):
    """Meaning and provenance of cost evidence."""

    PROVIDER_REPORTED = "provider_reported"
    ESTIMATED = "estimated"
    SUBSCRIPTION_INCLUDED = "subscription_included"
    UNAVAILABLE = "unavailable"


class EvidenceUnavailableReason(str, Enum):
    """Bounded reasons for absent usage, cost, model, or price evidence."""

    NOT_REPORTED = "not_reported"
    NOT_SUPPORTED = "not_supported"
    PARSING_FAILED = "parsing_failed"
    NOT_COLLECTED = "not_collected"


class TokenField(str, Enum):
    """Token fields whose absence is represented explicitly."""

    INPUT_TOKENS = "input_tokens"
    OUTPUT_TOKENS = "output_tokens"
    CACHED_INPUT_TOKENS = "cached_input_tokens"
    TOTAL_TOKENS = "total_tokens"


class TokenFieldAbsence(_UsageContract):
    """One explicitly unavailable token field and its bounded reason."""

    field: TokenField
    reason: EvidenceUnavailableReason

    @field_validator("field", mode="before")
    @classmethod
    def validate_field(cls, value: Any) -> TokenField:
        return _parse_enum(value, TokenField, "field")

    @field_validator("reason", mode="before")
    @classmethod
    def validate_reason(cls, value: Any) -> EvidenceUnavailableReason:
        return _parse_enum(value, EvidenceUnavailableReason, "reason")


class AIInvocationStatus(str, Enum):
    """Terminal lifecycle of one AI/model invocation."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


def _canonical_decimal(value: Any, field_name: str) -> Decimal:
    if type(value) is Decimal:
        candidate = value
    elif (
        type(value) is str
        and len(value) <= _MAX_DECIMAL_LENGTH
        and _CANONICAL_DECIMAL_PATTERN.fullmatch(value)
    ):
        try:
            candidate = Decimal(value)
        except InvalidOperation:
            raise ValueError(
                f"{field_name} must be a canonical non-negative decimal"
            ) from None
        if _serialize_decimal(candidate) != value:
            raise ValueError(
                f"{field_name} must be a canonical non-negative decimal"
            )
    else:
        raise ValueError(
            f"{field_name} must be a canonical non-negative decimal"
        )
    if not candidate.is_finite() or candidate < 0:
        raise ValueError(
            f"{field_name} must be a canonical non-negative decimal"
        )
    if candidate != 0:
        decimal_tuple = candidate.as_tuple()
        digit_count = len(decimal_tuple.digits)
        exponent = decimal_tuple.exponent
        if exponent >= 0:
            serialized_length = digit_count + exponent
        elif -exponent >= digit_count:
            serialized_length = 2 - exponent
        else:
            serialized_length = digit_count + 1
        if serialized_length > _MAX_DECIMAL_LENGTH:
            raise ValueError(
                f"{field_name} must be a bounded canonical decimal"
            )
    return candidate


def _serialize_decimal(value: Decimal) -> str:
    if value == 0:
        return "0"
    serialized = format(value, "f")
    if "." in serialized:
        serialized = serialized.rstrip("0").rstrip(".")
    return serialized


def _canonical_currency(value: Any) -> str:
    if type(value) is not str or _CURRENCY_PATTERN.fullmatch(value) is None:
        raise ValueError("currency must be an uppercase three-letter code")
    return value


def _optional_identifier(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return validate_run_identifier(value)


def _enum_tuple(
    value: Any,
    enum_type: Any,
    field_name: str,
    *,
    maximum: int,
) -> Tuple[Any, ...]:
    if type(value) not in {list, tuple} or len(value) > maximum:
        raise ValueError(f"{field_name} must be a bounded ordered array")
    parsed = tuple(_parse_enum(item, enum_type, field_name) for item in value)
    if len(parsed) != len(set(parsed)):
        raise ValueError(f"{field_name} must be duplicate-free")
    return tuple(sorted(parsed, key=lambda item: item.value))


class TokenUsageEvidence(_UsageContract):
    """Exact, partial, estimated, parsed, or unavailable token evidence."""

    schema_version: Literal["1"]
    source: UsageSource
    input_tokens: Optional[int] = Field(
        default=None,
        ge=0,
        le=MAX_USAGE_INTEGER,
    )
    output_tokens: Optional[int] = Field(
        default=None,
        ge=0,
        le=MAX_USAGE_INTEGER,
    )
    cached_input_tokens: Optional[int] = Field(
        default=None,
        ge=0,
        le=MAX_USAGE_INTEGER,
    )
    total_tokens: Optional[int] = Field(
        default=None,
        ge=0,
        le=MAX_USAGE_INTEGER,
    )
    unavailable_fields: Tuple[TokenFieldAbsence, ...]

    @field_validator("source", mode="before")
    @classmethod
    def validate_source(cls, value: Any) -> UsageSource:
        return _parse_enum(value, UsageSource, "source")

    @field_validator("unavailable_fields", mode="before")
    @classmethod
    def validate_unavailable_fields(
        cls,
        value: Any,
    ) -> Tuple[Any, ...]:
        if type(value) not in {list, tuple} or len(value) > len(TokenField):
            raise ValueError(
                "unavailable_fields must be a bounded ordered array"
            )
        return tuple(value)

    @field_validator("unavailable_fields")
    @classmethod
    def snapshot_unavailable_fields(
        cls,
        value: Tuple[TokenFieldAbsence, ...],
    ) -> Tuple[TokenFieldAbsence, ...]:
        fields = tuple(item.field for item in value)
        if len(fields) != len(set(fields)):
            raise ValueError("unavailable token fields must be duplicate-free")
        snapshots = tuple(
            TokenFieldAbsence.from_dict(item.to_dict()) for item in value
        )
        return tuple(sorted(snapshots, key=lambda item: item.field.value))

    @model_validator(mode="after")
    def validate_evidence(self) -> "TokenUsageEvidence":
        actual_missing = {
            TokenField(field_name)
            for field_name in _TOKEN_FIELDS
            if getattr(self, field_name) is None
        }
        declared_missing = {item.field for item in self.unavailable_fields}
        if actual_missing != declared_missing:
            raise ValueError(
                "unavailable_fields must identify every missing token field"
            )
        if self.source is UsageSource.UNAVAILABLE:
            if len(actual_missing) != len(_TOKEN_FIELDS):
                raise ValueError(
                    "unavailable usage cannot contain token counts"
                )
        elif len(actual_missing) == len(_TOKEN_FIELDS):
            raise ValueError(
                "available usage source requires at least one token count"
            )
        return self


class CostEvidence(_UsageContract):
    """Reported, estimated, subscription, or unavailable cost evidence."""

    schema_version: Literal["1"]
    cost_type: CostType
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    pricing_source_id: Optional[str] = None
    pricing_version: Optional[str] = None
    pricing_effective_at: Optional[datetime] = None
    unavailable_reason: Optional[EvidenceUnavailableReason] = None

    @field_validator("cost_type", mode="before")
    @classmethod
    def validate_cost_type(cls, value: Any) -> CostType:
        return _parse_enum(value, CostType, "cost_type")

    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, value: Any) -> Optional[Decimal]:
        if value is None:
            return None
        return _canonical_decimal(value, "amount")

    @field_serializer("amount")
    def serialize_amount(self, value: Optional[Decimal]) -> Optional[str]:
        return None if value is None else _serialize_decimal(value)

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
        return _optional_identifier(value)

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

    @model_validator(mode="after")
    def validate_evidence(self) -> "CostEvidence":
        pricing_fields = (
            self.pricing_source_id,
            self.pricing_version,
            self.pricing_effective_at,
        )
        has_all_pricing = all(value is not None for value in pricing_fields)
        has_any_pricing = any(value is not None for value in pricing_fields)
        if has_any_pricing and not has_all_pricing:
            raise ValueError("pricing evidence must be complete")

        if self.cost_type in {
            CostType.PROVIDER_REPORTED,
            CostType.ESTIMATED,
        }:
            if self.amount is None or self.currency is None:
                raise ValueError("monetary cost requires amount and currency")
            if self.unavailable_reason is not None:
                raise ValueError(
                    "monetary cost cannot have an unavailable reason"
                )
            if self.cost_type is CostType.ESTIMATED and not has_all_pricing:
                raise ValueError(
                    "estimated cost requires complete pricing evidence"
                )
        else:
            if (
                self.amount is not None
                or self.currency is not None
                or has_any_pricing
            ):
                raise ValueError(
                    "non-monetary cost evidence cannot contain money or pricing"
                )
            if (
                self.cost_type is CostType.UNAVAILABLE
                and self.unavailable_reason is None
            ):
                raise ValueError(
                    "unavailable cost requires an unavailable reason"
                )
            if (
                self.cost_type is CostType.SUBSCRIPTION_INCLUDED
                and self.unavailable_reason is not None
            ):
                raise ValueError(
                    "subscription-included cost cannot be unavailable"
                )
        return self


class AIInvocationRecord(_UsageContract):
    """One terminal AI/model call correlated to a PMQA run."""

    schema_version: Literal["1"]
    invocation_id: str
    session_id: str
    run_id: str
    runner_invocation_id: Optional[str] = None
    provider: str
    model: Optional[str] = None
    model_unavailable_reason: Optional[EvidenceUnavailableReason] = None
    operation: str
    status: AIInvocationStatus
    started_at: datetime
    completed_at: datetime
    duration_ms: int = Field(ge=0, le=MAX_USAGE_INTEGER)
    attempt_number: int = Field(ge=1, le=MAX_USAGE_INTEGER)
    retry_of_invocation_id: Optional[str] = None
    fallback_from_invocation_id: Optional[str] = None
    usage: TokenUsageEvidence
    cost: CostEvidence
    error_category: Optional[RunErrorCategory] = None

    @field_validator(
        "invocation_id",
        "session_id",
        "run_id",
        "provider",
        "operation",
    )
    @classmethod
    def validate_identifiers(cls, value: str) -> str:
        return validate_run_identifier(value)

    @field_validator(
        "runner_invocation_id",
        "model",
        "retry_of_invocation_id",
        "fallback_from_invocation_id",
    )
    @classmethod
    def validate_optional_identifiers(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        return _optional_identifier(value)

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

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, value: Any) -> AIInvocationStatus:
        return _parse_enum(value, AIInvocationStatus, "status")

    @field_validator("error_category", mode="before")
    @classmethod
    def validate_error_category(
        cls,
        value: Any,
    ) -> Optional[RunErrorCategory]:
        if value is None:
            return None
        return _parse_enum(value, RunErrorCategory, "error_category")

    @field_validator("usage")
    @classmethod
    def snapshot_usage(cls, value: TokenUsageEvidence) -> TokenUsageEvidence:
        return TokenUsageEvidence.from_dict(value.to_dict())

    @field_validator("cost")
    @classmethod
    def snapshot_cost(cls, value: CostEvidence) -> CostEvidence:
        return CostEvidence.from_dict(value.to_dict())

    @field_validator("started_at", "completed_at", mode="before")
    @classmethod
    def validate_timestamps(cls, value: Any, info: Any) -> datetime:
        return _canonical_timestamp(value, info.field_name)

    @field_serializer("started_at", "completed_at")
    def serialize_timestamps(self, value: datetime) -> str:
        return _serialize_timestamp(value)

    @model_validator(mode="after")
    def validate_lifecycle(self) -> "AIInvocationRecord":
        if self.completed_at < self.started_at:
            raise ValueError("completed_at must not precede started_at")
        if (
            self.cost.pricing_effective_at is not None
            and self.cost.pricing_effective_at > self.started_at
        ):
            raise ValueError(
                "pricing evidence cannot take effect after invocation start"
            )
        if (self.model is None) == (self.model_unavailable_reason is None):
            raise ValueError(
                "model identity or unavailable reason must be present"
            )
        if self.retry_of_invocation_id == self.invocation_id:
            raise ValueError("retry cannot reference the invocation itself")
        if self.fallback_from_invocation_id == self.invocation_id:
            raise ValueError("fallback cannot reference the invocation itself")
        predecessor_count = sum(
            value is not None
            for value in (
                self.retry_of_invocation_id,
                self.fallback_from_invocation_id,
            )
        )
        if self.attempt_number == 1 and predecessor_count != 0:
            raise ValueError("first attempt must not declare a predecessor")
        if self.attempt_number > 1 and predecessor_count != 1:
            raise ValueError(
                "later attempt must declare exactly one predecessor"
            )
        if self.status is AIInvocationStatus.SUCCEEDED:
            if self.error_category is not None:
                raise ValueError("successful invocation cannot have an error")
        elif self.error_category is None:
            raise ValueError("failed or cancelled invocation requires an error")
        elif (
            self.status is AIInvocationStatus.CANCELLED
            and self.error_category is not RunErrorCategory.CANCELLED
        ):
            raise ValueError(
                "cancelled invocation requires cancellation classification"
            )
        elif (
            self.status is AIInvocationStatus.FAILED
            and self.error_category is RunErrorCategory.CANCELLED
        ):
            raise ValueError(
                "failed invocation cannot use cancellation classification"
            )
        return self


__all__ = [
    "MAX_USAGE_INTEGER",
    "USAGE_CONTRACT_SCHEMA_VERSION",
    "AIInvocationRecord",
    "AIInvocationStatus",
    "CostEvidence",
    "CostType",
    "EvidenceUnavailableReason",
    "TokenField",
    "TokenFieldAbsence",
    "TokenUsageEvidence",
    "UsageContractValidationError",
    "UsageSource",
]
