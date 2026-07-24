"""Tests for immutable model pricing and the read-only catalog boundary."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json

import pytest
from pydantic import ValidationError

from pmqa.usage import (
    EvidenceUnavailableReason,
    ModelPricing,
    PricingCatalog,
    PricingComponent,
    PricingComponentKind,
    PricingUnit,
    UsageContractValidationError,
)


def _time(days: int = 0) -> datetime:
    return datetime(2026, 7, 1, tzinfo=timezone.utc) + timedelta(days=days)


def _component(
    amount: Decimal = Decimal("0.001"),
    unit: PricingUnit = PricingUnit.PER_1K_TOKENS,
) -> PricingComponent:
    return PricingComponent(
        schema_version="1",
        amount=amount,
        unit=unit,
    )


def _pricing(**updates) -> ModelPricing:
    values = {
        "schema_version": "1",
        "pricing_id": "pricing.test-model.2026-07",
        "provider": "provider.test",
        "model": "model.test-v1",
        "currency": "USD",
        "pricing_source_id": "pricing.public-catalog",
        "pricing_version": "2026-07-01",
        "effective_from": _time(),
        "effective_to": _time(31),
        "input_price": _component(),
        "output_price": _component(Decimal("0.002")),
        "cached_input_price": None,
        "unavailable_components": (PricingComponentKind.CACHED_INPUT,),
        "unavailable_reason": EvidenceUnavailableReason.NOT_SUPPORTED,
    }
    values.update(updates)
    return ModelPricing(**values)


class FakePricingCatalog:
    def __init__(self, pricing: ModelPricing = None) -> None:
        self.pricing = pricing
        self.calls = []

    def get_price(
        self,
        provider: str,
        model: str,
        effective_at: datetime,
    ):
        self.calls.append((provider, model, effective_at))
        if self.pricing is None:
            return None
        if (
            provider != self.pricing.provider
            or model != self.pricing.model
            or effective_at < self.pricing.effective_from
            or (
                self.pricing.effective_to is not None
                and effective_at >= self.pricing.effective_to
            )
        ):
            return None
        return self.pricing


def test_pricing_components_use_canonical_decimal_and_explicit_units() -> None:
    component = _component(Decimal("0.001000"), PricingUnit.PER_1M_TOKENS)

    assert component.to_dict() == {
        "schema_version": "1",
        "amount": "0.001",
        "unit": "per_1m_tokens",
    }
    assert PricingComponent.from_dict(component.to_dict()) == component


def test_public_pricing_contracts_have_explicit_stable_fields() -> None:
    assert tuple(PricingComponent.model_fields) == (
        "schema_version",
        "amount",
        "unit",
    )
    assert tuple(ModelPricing.model_fields) == (
        "schema_version",
        "pricing_id",
        "provider",
        "model",
        "currency",
        "pricing_source_id",
        "pricing_version",
        "effective_from",
        "effective_to",
        "input_price",
        "output_price",
        "cached_input_price",
        "unavailable_components",
        "unavailable_reason",
    )


@pytest.mark.parametrize(
    "value",
    (0.1, 1, True, "01", "1.0", "-1", Decimal("-1")),
)
def test_pricing_component_rejects_noncanonical_values(value) -> None:
    with pytest.raises(ValidationError):
        _component(value)


def test_model_pricing_supports_independently_missing_components() -> None:
    pricing = _pricing()

    assert pricing.input_price is not None
    assert pricing.output_price is not None
    assert pricing.cached_input_price is None
    assert pricing.unavailable_components == (
        PricingComponentKind.CACHED_INPUT,
    )


def test_complete_model_pricing_has_no_unavailable_reason() -> None:
    pricing = _pricing(
        cached_input_price=_component(Decimal("0.0005")),
        unavailable_components=(),
        unavailable_reason=None,
    )

    assert pricing.unavailable_components == ()
    assert pricing.unavailable_reason is None


def test_model_pricing_rejects_missing_component_contradictions() -> None:
    with pytest.raises(ValidationError, match="every missing"):
        _pricing(unavailable_components=())
    with pytest.raises(ValidationError, match="require"):
        _pricing(unavailable_reason=None)
    with pytest.raises(ValidationError, match="cannot have"):
        _pricing(
            cached_input_price=_component(),
            unavailable_components=(),
        )
    with pytest.raises(ValidationError, match="at least one"):
        _pricing(
            input_price=None,
            output_price=None,
            cached_input_price=None,
            unavailable_components=tuple(PricingComponentKind),
        )


def test_model_pricing_validates_effective_interval() -> None:
    with pytest.raises(ValidationError, match="must follow"):
        _pricing(effective_to=_time())
    with pytest.raises(ValidationError, match="must follow"):
        _pricing(effective_to=_time(-1))


def test_fake_catalog_returns_pricing_or_none_without_calculation() -> None:
    pricing = _pricing()
    catalog = FakePricingCatalog(pricing)

    assert isinstance(catalog, PricingCatalog)
    assert catalog.get_price(
        "provider.test",
        "model.test-v1",
        _time(1),
    ) is pricing
    assert catalog.get_price(
        "provider.test",
        "model.other",
        _time(1),
    ) is None
    assert catalog.get_price(
        "provider.test",
        "model.test-v1",
        _time(31),
    ) is None
    assert catalog.calls[0] == (
        "provider.test",
        "model.test-v1",
        _time(1),
    )


def test_absent_catalog_price_is_none_not_zero() -> None:
    catalog = FakePricingCatalog()
    assert catalog.get_price("provider.test", "model.test-v1", _time()) is None


def test_model_pricing_round_trip_and_revalidated_copy() -> None:
    pricing = _pricing()
    wire = json.loads(json.dumps(pricing.to_dict()))

    assert ModelPricing.from_dict(wire) == pricing
    with pytest.raises(ValidationError):
        pricing.model_copy(update={"currency": "usd"})


def test_model_pricing_retains_independent_component_snapshots() -> None:
    component = _component()
    pricing = _pricing(input_price=component)
    component.__dict__["amount"] = Decimal("999")

    assert pricing.input_price.amount == Decimal("0.001")
    assert pricing.input_price is not component


def test_model_pricing_rejects_runtime_and_unknown_wire_data_safely() -> None:
    wire = _pricing().to_dict()
    wire["pricing_table"] = {"api_key": "runtime-secret-marker"}

    with pytest.raises(UsageContractValidationError) as captured:
        ModelPricing.from_dict(wire)

    assert "runtime-secret-marker" not in str(captured.value)
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
