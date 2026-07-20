"""Tests for the experimental Product Pack manifest contract."""

import json

import pytest
from pydantic import ValidationError

from pmqa.product_pack import ProductPackCapability, ProductPackManifest


ALL_CAPABILITIES = tuple(ProductPackCapability)


def test_valid_manifest_construction_and_public_exports() -> None:
    manifest = _manifest()

    assert tuple(ProductPackManifest.model_fields) == (
        "schema_version",
        "product_pack_api_version",
        "pack_id",
        "pack_version",
        "product_id",
        "display_name",
        "capabilities",
    )
    assert manifest.schema_version == "1"
    assert manifest.product_pack_api_version == "1"
    assert manifest.pack_id == "demo-pack"
    assert manifest.product_id == "demo"
    assert manifest.capabilities == ALL_CAPABILITIES
    assert ProductPackCapability.EXPLORATION_CAPTURE.value == (
        "exploration_capture"
    )


def test_manifest_is_frozen_and_deeply_immutable() -> None:
    manifest = _manifest()

    with pytest.raises(ValidationError, match="frozen"):
        manifest.pack_id = "changed"
    with pytest.raises(AttributeError):
        manifest.capabilities.append(ProductPackCapability.TEST_INVENTORY)


def test_serialization_is_deterministic_and_json_compatible() -> None:
    manifest = _manifest(
        capabilities=[
            ProductPackCapability.TEST_INVENTORY,
            ProductPackCapability.EXPLORATION_CAPTURE,
            ProductPackCapability.KNOWLEDGE_VALIDATION,
        ]
    )
    expected = {
        "schema_version": "1",
        "product_pack_api_version": "1",
        "pack_id": "demo-pack",
        "pack_version": "1.2.3-alpha.1+build.5",
        "product_id": "demo",
        "display_name": "Demo Product Pack",
        "capabilities": [
            "exploration_capture",
            "knowledge_validation",
            "test_inventory",
        ],
    }

    assert manifest.to_dict() == expected
    assert manifest.to_dict() == manifest.to_dict()
    assert json.loads(json.dumps(manifest.to_dict())) == expected


def test_json_round_trip_restores_equal_manifest() -> None:
    original = _manifest()
    payload = json.loads(json.dumps(original.to_dict()))

    restored = ProductPackManifest.from_dict(payload)

    assert restored == original
    assert isinstance(restored.capabilities, tuple)


def test_capability_input_order_is_normalized_to_enum_order() -> None:
    forward = _manifest(capabilities=list(ALL_CAPABILITIES))
    reverse = _manifest(capabilities=list(reversed(ALL_CAPABILITIES)))

    assert reverse.capabilities == ALL_CAPABILITIES
    assert reverse.to_dict() == forward.to_dict()


def test_duplicate_capabilities_are_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate Product Pack"):
        _manifest(
            capabilities=[
                ProductPackCapability.TEST_GENERATION,
                "test_generation",
            ]
        )


def test_unsupported_capability_is_rejected() -> None:
    with pytest.raises(ValidationError, match="unsupported Product Pack"):
        _manifest(capabilities=["repository_write"])


def test_unknown_fields_are_rejected() -> None:
    payload = _manifest().to_dict()
    payload["metadata"] = {"arbitrary": True}

    with pytest.raises(ValidationError, match="metadata"):
        ProductPackManifest.from_dict(payload)


@pytest.mark.parametrize("field", ["schema_version", "product_pack_api_version"])
@pytest.mark.parametrize("invalid_version", ["0", "2", 1, None])
def test_invalid_schema_and_api_versions_are_rejected(
    field: str,
    invalid_version,
) -> None:
    with pytest.raises(ValidationError):
        _manifest(**{field: invalid_version})


@pytest.mark.parametrize(
    "invalid_version",
    [
        "1",
        "1.2",
        "v1.2.3",
        "01.2.3",
        "1.02.3",
        "1.2.03",
        "1.2.3-01",
        "1.2.3+",
        "1.2.3 alpha",
        "1.2.3/next",
        "",
    ],
)
def test_malformed_semantic_versions_are_rejected(invalid_version: str) -> None:
    with pytest.raises(ValidationError, match="pack_version"):
        _manifest(pack_version=invalid_version)


@pytest.mark.parametrize(
    "valid_version",
    ["0.0.0", "1.2.3", "1.2.3-alpha", "1.2.3-alpha.1+build.5"],
)
def test_canonical_semantic_versions_are_accepted(valid_version: str) -> None:
    assert _manifest(pack_version=valid_version).pack_version == valid_version


@pytest.mark.parametrize("field", ["pack_id", "product_id"])
@pytest.mark.parametrize(
    "invalid_identifier",
    [
        "",
        "Demo",
        "demo pack",
        "demo/pack",
        "demo\\pack",
        "demo..pack",
        "demo$pack",
        "https://demo",
        "-demo",
        "demo-",
        "demo__pack",
        "démo",
    ],
)
def test_invalid_identifiers_are_rejected(
    field: str,
    invalid_identifier: str,
) -> None:
    with pytest.raises(ValidationError, match=field):
        _manifest(**{field: invalid_identifier})


@pytest.mark.parametrize(
    "valid_identifier",
    ["demo", "demo-pack", "demo_pack", "demo.pack", "product2"],
)
def test_canonical_identifiers_are_accepted(valid_identifier: str) -> None:
    assert _manifest(pack_id=valid_identifier).pack_id == valid_identifier


@pytest.mark.parametrize(
    "display_name",
    ["", "   ", " Demo", "Demo ", "Demo\nPack", "x" * 121],
)
def test_blank_oversized_or_ambiguous_display_names_are_rejected(
    display_name: str,
) -> None:
    with pytest.raises(ValidationError, match="display_name"):
        _manifest(display_name=display_name)


def test_runtime_objects_are_rejected_without_leaking_repr() -> None:
    class RuntimeObject:
        def __repr__(self) -> str:
            return "RuntimeObject(secret=runtime-secret-marker)"

    payload = _manifest().to_dict()
    payload["display_name"] = RuntimeObject()

    with pytest.raises(ValidationError) as captured:
        ProductPackManifest.from_dict(payload)

    assert "runtime-secret-marker" not in str(captured.value)


@pytest.mark.parametrize(
    "unexpected_field",
    [
        "credentials",
        "password",
        "token",
        "cookie",
        "environment",
        "base_url",
        "selectors",
        "dom",
        "html",
        "filesystem_path",
        "repository_path",
        "callable",
        "subprocess_handle",
        "browser",
        "page",
        "locator",
        "entry_point",
        "command",
        "configuration",
    ],
)
def test_sensitive_or_runtime_fields_cannot_enter_manifest(
    unexpected_field: str,
) -> None:
    payload = _manifest().to_dict()
    payload[unexpected_field] = "runtime-secret-marker"

    with pytest.raises(ValidationError) as captured:
        ProductPackManifest.from_dict(payload)

    assert "runtime-secret-marker" not in str(captured.value)


def test_validated_copy_update_cannot_bypass_validation() -> None:
    manifest = _manifest()

    with pytest.raises(ValidationError, match="pack_version"):
        manifest.model_copy(update={"pack_version": "v2"})
    with pytest.raises(ValidationError, match="credential"):
        manifest.model_copy(update={"credential": "runtime-secret-marker"})


def test_caller_owned_input_is_not_modified() -> None:
    capabilities = [
        "test_inventory",
        "exploration_capture",
        "knowledge_mapping",
    ]
    payload = _manifest().to_dict()
    payload["capabilities"] = capabilities
    original_payload = json.loads(json.dumps(payload))

    manifest = ProductPackManifest.from_dict(payload)

    assert payload == original_payload
    assert capabilities == [
        "test_inventory",
        "exploration_capture",
        "knowledge_mapping",
    ]
    assert manifest.capabilities == (
        ProductPackCapability.EXPLORATION_CAPTURE,
        ProductPackCapability.KNOWLEDGE_MAPPING,
        ProductPackCapability.TEST_INVENTORY,
    )


def test_non_array_capabilities_are_rejected_safely() -> None:
    for invalid in ("test_generation", {"test_generation"}, object()):
        with pytest.raises(ValidationError) as captured:
            _manifest(capabilities=invalid)
        assert "capabilities must be a JSON array" in str(captured.value)


def _manifest(**updates) -> ProductPackManifest:
    values = {
        "schema_version": "1",
        "product_pack_api_version": "1",
        "pack_id": "demo-pack",
        "pack_version": "1.2.3-alpha.1+build.5",
        "product_id": "demo",
        "display_name": "Demo Product Pack",
        "capabilities": list(ALL_CAPABILITIES),
    }
    values.update(updates)
    return ProductPackManifest(**values)
