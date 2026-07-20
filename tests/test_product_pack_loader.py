"""Security and correlation tests for explicit Product Pack loading."""

from dataclasses import FrozenInstanceError
from importlib import metadata
import sys
import traceback
import types

import pytest

from pmqa.product_pack import (
    LoadedProductPack,
    PRODUCT_PACK_ENTRY_POINT_GROUP,
    ProductPackCapability,
    ProductPackLoadError,
    ProductPackLoadFailureCode,
    ProductPackLoadRequest,
    ProductPackManifest,
    load_product_pack_manifest,
)


class FakeEntryPoint:
    def __init__(
        self,
        payload,
        *,
        group: str = PRODUCT_PACK_ENTRY_POINT_GROUP,
        name: str = "external-demo",
        error: BaseException = None,
    ) -> None:
        self.group = group
        self.name = name
        self._payload = payload
        self._error = error
        self.load_calls = 0

    def load(self):
        self.load_calls += 1
        if self._error is not None:
            raise self._error
        return self._payload


class FakeDistribution:
    def __init__(self, entry_points) -> None:
        self.entry_points = tuple(entry_points)


def _manifest(**updates) -> ProductPackManifest:
    values = {
        "schema_version": "1",
        "product_pack_api_version": "1",
        "pack_id": "external-demo",
        "pack_version": "1.2.3",
        "product_id": "demo",
        "display_name": "External Demo Pack",
        "capabilities": (
            ProductPackCapability.EXPLORATION_CAPTURE,
            ProductPackCapability.KNOWLEDGE_MAPPING,
        ),
    }
    values.update(updates)
    return ProductPackManifest(**values)


def _request(
    manifest: ProductPackManifest = None,
    distribution_name: str = "external-demo-pack",
) -> ProductPackLoadRequest:
    return ProductPackLoadRequest(
        distribution_name=distribution_name,
        expected_manifest=manifest or _manifest(),
    )


def _load_with_payload(payload, *, request=None):
    entry_point = FakeEntryPoint(payload)
    loaded = load_product_pack_manifest(
        request or _request(),
        resolver=lambda name: FakeDistribution([entry_point]),
    )
    return loaded, entry_point


def _assert_failure(
    code: ProductPackLoadFailureCode,
    *,
    request=None,
    resolver=None,
) -> ProductPackLoadError:
    with pytest.raises(ProductPackLoadError) as captured:
        load_product_pack_manifest(
            request or _request(),
            resolver=resolver,
        )
    assert captured.value.code is code
    return captured.value


def test_successful_load_is_explicit_exact_and_calls_entry_point_once() -> None:
    expected = _manifest()
    payload = expected.to_dict()

    loaded, entry_point = _load_with_payload(payload, request=_request(expected))

    assert loaded == LoadedProductPack(
        distribution_name="external-demo-pack",
        manifest=expected,
    )
    assert loaded.manifest is not expected
    assert entry_point.load_calls == 1


def test_request_and_result_are_frozen_and_deeply_immutable() -> None:
    request = _request()
    loaded, _ = _load_with_payload(request.expected_manifest.to_dict())

    with pytest.raises(FrozenInstanceError):
        request.distribution_name = "changed"
    with pytest.raises(FrozenInstanceError):
        loaded.distribution_name = "changed"
    with pytest.raises(Exception, match="frozen"):
        loaded.manifest.pack_id = "changed"
    with pytest.raises(AttributeError):
        loaded.manifest.capabilities.append(
            ProductPackCapability.TEST_INVENTORY
        )
    assert tuple(ProductPackLoadRequest.__dataclass_fields__) == (
        "distribution_name",
        "expected_manifest",
    )


@pytest.mark.parametrize(
    ("supplied", "canonical"),
    [
        ("external-demo-pack", "external-demo-pack"),
        ("External-Demo-Pack", "external-demo-pack"),
        ("external_demo.pack", "external-demo-pack"),
        ("external..demo___pack", "external-demo-pack"),
        ("external---demo-pack", "external-demo-pack"),
        ("a1", "a1"),
    ],
)
def test_distribution_name_uses_one_canonical_representation(
    supplied: str,
    canonical: str,
) -> None:
    assert _request(distribution_name=supplied).distribution_name == canonical


@pytest.mark.parametrize(
    "invalid_name",
    [
        "",
        " external-demo",
        "external-demo ",
        "external demo",
        "../external-demo",
        "external/demo",
        "external\\demo",
        "https://example.invalid/pack",
        "external;demo",
        "external$demo",
        "-external-demo",
        "external-demo-",
        "démo",
        "x" * 129,
        None,
        7,
    ],
)
def test_invalid_distribution_name_is_rejected_before_resolution(
    invalid_name,
) -> None:
    resolver_calls = []

    with pytest.raises(ProductPackLoadError) as captured:
        request = ProductPackLoadRequest(
            distribution_name=invalid_name,
            expected_manifest=_manifest(),
        )
        load_product_pack_manifest(
            request,
            resolver=lambda name: resolver_calls.append(name),
        )

    assert captured.value.code is ProductPackLoadFailureCode.INVALID_LOAD_REQUEST
    assert resolver_calls == []


@pytest.mark.parametrize("invalid_manifest", [{}, None, "manifest", object()])
def test_request_requires_a_trusted_manifest_instance(invalid_manifest) -> None:
    with pytest.raises(ProductPackLoadError) as captured:
        ProductPackLoadRequest(
            distribution_name="external-demo-pack",
            expected_manifest=invalid_manifest,
        )
    assert captured.value.code is ProductPackLoadFailureCode.INVALID_LOAD_REQUEST


def test_loader_rejects_invalid_request_or_resolver_before_resolution() -> None:
    for request, resolver in (({}, lambda name: None), (_request(), object())):
        with pytest.raises(ProductPackLoadError) as captured:
            load_product_pack_manifest(request, resolver=resolver)
        assert (
            captured.value.code
            is ProductPackLoadFailureCode.INVALID_LOAD_REQUEST
        )


@pytest.mark.parametrize(
    "error",
    [metadata.PackageNotFoundError("runtime-secret-marker"), OSError("marker")],
)
def test_missing_or_unreadable_distribution_is_safe(error: Exception) -> None:
    def resolver(name):
        raise error

    captured = _assert_failure(
        ProductPackLoadFailureCode.DISTRIBUTION_NOT_FOUND,
        resolver=resolver,
    )
    assert "marker" not in str(captured)
    assert captured.__cause__ is None
    assert captured.__context__ is None


def test_missing_matching_entry_point_is_rejected() -> None:
    entry_points = [
        FakeEntryPoint(_manifest().to_dict(), group="another.group"),
        FakeEntryPoint(_manifest().to_dict(), name="another-pack"),
    ]
    _assert_failure(
        ProductPackLoadFailureCode.MATCHING_ENTRY_POINT_MISSING,
        resolver=lambda name: FakeDistribution(entry_points),
    )
    assert all(entry_point.load_calls == 0 for entry_point in entry_points)


def test_duplicate_matching_entry_points_are_rejected_without_loading() -> None:
    entry_points = [
        FakeEntryPoint(_manifest().to_dict()),
        FakeEntryPoint(_manifest().to_dict()),
    ]
    _assert_failure(
        ProductPackLoadFailureCode.MATCHING_ENTRY_POINT_AMBIGUOUS,
        resolver=lambda name: FakeDistribution(entry_points),
    )
    assert all(entry_point.load_calls == 0 for entry_point in entry_points)


def test_unrelated_entry_points_are_ignored() -> None:
    unrelated = FakeEntryPoint(_manifest().to_dict(), name="another-pack")
    selected = FakeEntryPoint(_manifest().to_dict())

    loaded = load_product_pack_manifest(
        _request(),
        resolver=lambda name: FakeDistribution([unrelated, selected]),
    )

    assert loaded.manifest == _manifest()
    assert unrelated.load_calls == 0
    assert selected.load_calls == 1


@pytest.mark.parametrize(
    "error",
    [ImportError("runtime-secret-marker"), RuntimeError("runtime-secret-marker")],
)
def test_entry_point_load_failure_is_safe(error: Exception) -> None:
    entry_point = FakeEntryPoint(None, error=error)
    captured = _assert_failure(
        ProductPackLoadFailureCode.ENTRY_POINT_LOAD_FAILED,
        resolver=lambda name: FakeDistribution([entry_point]),
    )

    assert entry_point.load_calls == 1
    assert "runtime-secret-marker" not in str(captured)
    assert captured.__cause__ is None
    assert captured.__context__ is None


@pytest.mark.parametrize(
    "payload",
    [
        lambda: {},
        _manifest(),
        types.SimpleNamespace(runtime="browser"),
        type("ManifestDict", (dict,), {})(_manifest().to_dict()),
    ],
)
def test_loaded_object_must_be_a_plain_dictionary(payload) -> None:
    _assert_failure(
        ProductPackLoadFailureCode.LOADED_OBJECT_NOT_MANIFEST_DICT,
        resolver=lambda name: FakeDistribution([FakeEntryPoint(payload)]),
    )


def test_malformed_manifest_payload_is_safe_and_does_not_echo_marker() -> None:
    payload = _manifest().to_dict()
    payload["credentials"] = "runtime-secret-marker"

    error = _assert_failure(
        ProductPackLoadFailureCode.MANIFEST_VALIDATION_FAILED,
        resolver=lambda name: FakeDistribution([FakeEntryPoint(payload)]),
    )
    formatted = "".join(
        traceback.format_exception(type(error), error, error.__traceback__)
    )

    assert "runtime-secret-marker" not in str(error)
    assert "runtime-secret-marker" not in formatted
    assert error.__cause__ is None
    assert error.__context__ is None


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("pack_id", "another-pack", ProductPackLoadFailureCode.MANIFEST_MISMATCH),
        ("product_id", "another", ProductPackLoadFailureCode.MANIFEST_MISMATCH),
        ("pack_version", "1.2.4", ProductPackLoadFailureCode.MANIFEST_MISMATCH),
        ("display_name", "Another Pack", ProductPackLoadFailureCode.MANIFEST_MISMATCH),
        (
            "capabilities",
            ["test_inventory"],
            ProductPackLoadFailureCode.MANIFEST_MISMATCH,
        ),
        (
            "schema_version",
            "2",
            ProductPackLoadFailureCode.MANIFEST_VALIDATION_FAILED,
        ),
        (
            "product_pack_api_version",
            "2",
            ProductPackLoadFailureCode.MANIFEST_VALIDATION_FAILED,
        ),
    ],
)
def test_every_manifest_correlation_axis_is_enforced(
    field: str,
    value,
    code: ProductPackLoadFailureCode,
) -> None:
    payload = _manifest().to_dict()
    payload[field] = value
    _assert_failure(
        code,
        resolver=lambda name: FakeDistribution([FakeEntryPoint(payload)]),
    )


def test_expected_manifest_and_source_dictionary_are_not_retained_or_mutated() -> None:
    expected = _manifest()
    expected_before = expected.to_dict()
    source = expected.to_dict()

    loaded, _ = _load_with_payload(source, request=_request(expected))
    source["display_name"] = "Mutated External Source"
    source["capabilities"].append("test_inventory")

    assert expected.to_dict() == expected_before
    assert loaded.manifest == expected
    assert loaded.manifest.to_dict() == expected_before
    assert loaded.manifest is not expected
    assert loaded.manifest.to_dict() is not source
    assert tuple(LoadedProductPack.__dataclass_fields__) == (
        "distribution_name",
        "manifest",
    )


def test_safe_error_has_only_fixed_public_state_and_bounded_traceback() -> None:
    marker = "runtime-secret-marker"
    entry_point = FakeEntryPoint(None, error=RuntimeError(marker))

    error = _assert_failure(
        ProductPackLoadFailureCode.ENTRY_POINT_LOAD_FAILED,
        resolver=lambda name: FakeDistribution([entry_point]),
    )
    formatted = "".join(
        traceback.format_exception(type(error), error, error.__traceback__)
    )

    assert error.args == (
        "Product Pack manifest entry point could not be loaded",
    )
    assert vars(error) == {
        "code": ProductPackLoadFailureCode.ENTRY_POINT_LOAD_FAILED
    }
    assert error.__cause__ is None
    assert error.__context__ is None
    assert marker not in formatted
    assert formatted.count("File ") <= 4


@pytest.mark.parametrize(
    "error_type",
    [KeyboardInterrupt, SystemExit, GeneratorExit, MemoryError],
)
@pytest.mark.parametrize("boundary", ["resolver", "entry_point"])
def test_process_control_and_memory_exceptions_propagate(
    error_type,
    boundary: str,
) -> None:
    error = error_type()
    if boundary == "resolver":
        resolver = lambda name: (_ for _ in ()).throw(error)
    else:
        resolver = lambda name: FakeDistribution(
            [FakeEntryPoint(None, error=error)]
        )

    with pytest.raises(error_type):
        load_product_pack_manifest(_request(), resolver=resolver)


def test_loader_does_not_use_global_discovery(monkeypatch) -> None:
    expected = _manifest()
    selected = FakeEntryPoint(expected.to_dict())
    calls = []
    original_sys_path = tuple(sys.path)

    monkeypatch.setattr(
        metadata,
        "entry_points",
        lambda: pytest.fail("global entry point discovery was used"),
    )
    monkeypatch.setattr(
        metadata,
        "distributions",
        lambda: pytest.fail("installed distributions were enumerated"),
    )

    loaded = load_product_pack_manifest(
        _request(expected, "external_demo.pack"),
        resolver=lambda name: (
            calls.append(name) or FakeDistribution([selected])
        ),
    )

    assert calls == ["external-demo-pack"]
    assert tuple(sys.path) == original_sys_path
    assert loaded.distribution_name == "external-demo-pack"
    assert selected.load_calls == 1
