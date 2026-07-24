"""Provider-neutral immutable pricing records and read-only lookup boundary."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal, Optional, Protocol, Tuple, runtime_checkable

from pydantic import field_serializer, field_validator, model_validator

from pmqa.run import validate_run_identifier
from pmqa.run.models import (
    _canonical_timestamp,
    _parse_enum,
    _serialize_timestamp,
)
from pmqa.usage.contracts import (
    EvidenceUnavailableReason,
    _UsageContract,
    _canonical_currency,
    _canonical_decimal,
    _enum_tuple,
    _serialize_decimal,
)


class PricingUnit(str, Enum):
    """Explicit denominator for one token pricing component."""

    PER_TOKEN = "per_token"
    PER_1K_TOKENS = "per_1k_tokens"
    PER_1M_TOKENS = "per_1m_tokens"


class PricingComponentKind(str, Enum):
    """Independently available model-pricing components."""

    INPUT = "input"
    OUTPUT = "output"
    CACHED_INPUT = "cached_input"


class PricingComponent(_UsageContract):
    """One non-negative price with an explicit token unit."""

    schema_version: Literal["1"]
    amount: Decimal
    unit: PricingUnit

    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, value: Any) -> Decimal:
        return _canonical_decimal(value, "amount")

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal) -> str:
        return _serialize_decimal(value)

    @field_validator("unit", mode="before")
    @classmethod
    def validate_unit(cls, value: Any) -> PricingUnit:
        return _parse_enum(value, PricingUnit, "unit")


class ModelPricing(_UsageContract):
    """Versioned immutable model pricing evidence for one effective interval."""

    schema_version: Literal["1"]
    pricing_id: str
    provider: str
    model: str
    currency: str
    pricing_source_id: str
    pricing_version: str
    effective_from: datetime
    effective_to: Optional[datetime] = None
    input_price: Optional[PricingComponent] = None
    output_price: Optional[PricingComponent] = None
    cached_input_price: Optional[PricingComponent] = None
    unavailable_components: Tuple[PricingComponentKind, ...]
    unavailable_reason: Optional[EvidenceUnavailableReason] = None

    @field_validator(
        "pricing_id",
        "provider",
        "model",
        "pricing_source_id",
        "pricing_version",
    )
    @classmethod
    def validate_identifiers(cls, value: str) -> str:
        return validate_run_identifier(value)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return _canonical_currency(value)

    @field_validator("effective_from", "effective_to", mode="before")
    @classmethod
    def validate_effective_timestamps(
        cls,
        value: Any,
        info: Any,
    ) -> Optional[datetime]:
        if value is None and info.field_name == "effective_to":
            return None
        return _canonical_timestamp(value, info.field_name)

    @field_serializer("effective_from", "effective_to")
    def serialize_effective_timestamps(
        self,
        value: Optional[datetime],
    ) -> Optional[str]:
        return None if value is None else _serialize_timestamp(value)

    @field_validator("unavailable_components", mode="before")
    @classmethod
    def validate_unavailable_components(
        cls,
        value: Any,
    ) -> Tuple[PricingComponentKind, ...]:
        return _enum_tuple(
            value,
            PricingComponentKind,
            "unavailable_components",
            maximum=len(PricingComponentKind),
        )

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

    @field_validator(
        "input_price",
        "output_price",
        "cached_input_price",
    )
    @classmethod
    def snapshot_components(
        cls,
        value: Optional[PricingComponent],
    ) -> Optional[PricingComponent]:
        if value is None:
            return None
        return PricingComponent.from_dict(value.to_dict())

    @model_validator(mode="after")
    def validate_pricing(self) -> "ModelPricing":
        if (
            self.effective_to is not None
            and self.effective_to <= self.effective_from
        ):
            raise ValueError("effective_to must follow effective_from")
        components = {
            PricingComponentKind.INPUT: self.input_price,
            PricingComponentKind.OUTPUT: self.output_price,
            PricingComponentKind.CACHED_INPUT: self.cached_input_price,
        }
        actual_missing = {
            kind for kind, component in components.items() if component is None
        }
        if actual_missing != set(self.unavailable_components):
            raise ValueError(
                "unavailable_components must identify every missing price"
            )
        if len(actual_missing) == len(components):
            raise ValueError("model pricing requires at least one component")
        if actual_missing and self.unavailable_reason is None:
            raise ValueError(
                "missing pricing components require an unavailable reason"
            )
        if not actual_missing and self.unavailable_reason is not None:
            raise ValueError(
                "complete pricing cannot have an unavailable reason"
            )
        return self


@runtime_checkable
class PricingCatalog(Protocol):
    """Read-only explicit model-pricing lookup without calculation."""

    def get_price(
        self,
        provider: str,
        model: str,
        effective_at: datetime,
    ) -> Optional[ModelPricing]:
        ...


__all__ = [
    "ModelPricing",
    "PricingCatalog",
    "PricingComponent",
    "PricingComponentKind",
    "PricingUnit",
]
