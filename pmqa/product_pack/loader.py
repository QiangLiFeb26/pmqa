"""Explicit, distribution-scoped loading of Product Pack manifests."""

from dataclasses import dataclass
from enum import Enum
from importlib import metadata
import re
from typing import Callable, Optional, Tuple

from pmqa.product_pack.manifest import (
    ProductPackManifest,
    ProductPackManifestValidationError,
)


PRODUCT_PACK_ENTRY_POINT_GROUP = "pmqa.product_packs"
_MAX_DISTRIBUTION_NAME_LENGTH = 128
_DISTRIBUTION_NAME_PATTERN = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$",
    flags=re.ASCII,
)
_DISTRIBUTION_ALIAS_PATTERN = re.compile(r"[-_.]+", flags=re.ASCII)


class ProductPackLoadFailureCode(str, Enum):
    """Stable, product-neutral reasons an explicit manifest load can fail."""

    INVALID_LOAD_REQUEST = "invalid_load_request"
    INVALID_LOADED_PRODUCT_PACK = "invalid_loaded_product_pack"
    DISTRIBUTION_NOT_FOUND = "distribution_not_found"
    DISTRIBUTION_METADATA_INVALID = "distribution_metadata_invalid"
    MATCHING_ENTRY_POINT_MISSING = "matching_entry_point_missing"
    MATCHING_ENTRY_POINT_AMBIGUOUS = "matching_entry_point_ambiguous"
    ENTRY_POINT_LOAD_FAILED = "entry_point_load_failed"
    LOADED_OBJECT_NOT_MANIFEST_DICT = "loaded_object_not_manifest_dict"
    MANIFEST_VALIDATION_FAILED = "manifest_validation_failed"
    MANIFEST_MISMATCH = "manifest_mismatch"


_FAILURE_MESSAGES = {
    ProductPackLoadFailureCode.INVALID_LOAD_REQUEST: (
        "invalid Product Pack load request"
    ),
    ProductPackLoadFailureCode.INVALID_LOADED_PRODUCT_PACK: (
        "invalid loaded Product Pack"
    ),
    ProductPackLoadFailureCode.DISTRIBUTION_NOT_FOUND: (
        "Product Pack distribution was not found"
    ),
    ProductPackLoadFailureCode.DISTRIBUTION_METADATA_INVALID: (
        "Product Pack distribution metadata is invalid"
    ),
    ProductPackLoadFailureCode.MATCHING_ENTRY_POINT_MISSING: (
        "Product Pack manifest entry point is missing"
    ),
    ProductPackLoadFailureCode.MATCHING_ENTRY_POINT_AMBIGUOUS: (
        "Product Pack manifest entry point is ambiguous"
    ),
    ProductPackLoadFailureCode.ENTRY_POINT_LOAD_FAILED: (
        "Product Pack manifest entry point could not be loaded"
    ),
    ProductPackLoadFailureCode.LOADED_OBJECT_NOT_MANIFEST_DICT: (
        "Product Pack manifest entry point returned an invalid object"
    ),
    ProductPackLoadFailureCode.MANIFEST_VALIDATION_FAILED: (
        "Product Pack manifest validation failed"
    ),
    ProductPackLoadFailureCode.MANIFEST_MISMATCH: (
        "Product Pack manifest does not match the expected manifest"
    ),
}


class ProductPackLoadError(ValueError):
    """Expose one fixed failure code and bounded, non-sensitive message."""

    def __init__(self, code: ProductPackLoadFailureCode) -> None:
        self.code = code
        super().__init__(_FAILURE_MESSAGES[code])


def _canonical_distribution_name(
    value: object,
    failure_code: ProductPackLoadFailureCode,
) -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > _MAX_DISTRIBUTION_NAME_LENGTH
        or _DISTRIBUTION_NAME_PATTERN.fullmatch(value) is None
    ):
        raise ProductPackLoadError(failure_code) from None

    canonical = _DISTRIBUTION_ALIAS_PATTERN.sub("-", value).lower()
    if len(canonical) > _MAX_DISTRIBUTION_NAME_LENGTH:
        raise ProductPackLoadError(failure_code) from None
    return canonical


@dataclass(frozen=True)
class ProductPackLoadRequest:
    """Operator-approved distribution and complete expected manifest pin."""

    distribution_name: str
    expected_manifest: ProductPackManifest

    def __post_init__(self) -> None:
        canonical = _canonical_distribution_name(
            self.distribution_name,
            ProductPackLoadFailureCode.INVALID_LOAD_REQUEST,
        )
        if type(self.expected_manifest) is not ProductPackManifest:
            raise ProductPackLoadError(
                ProductPackLoadFailureCode.INVALID_LOAD_REQUEST
            ) from None
        object.__setattr__(self, "distribution_name", canonical)


@dataclass(frozen=True)
class LoadedProductPack:
    """Safe metadata retained after an explicitly selected manifest load."""

    distribution_name: str
    manifest: ProductPackManifest

    def __post_init__(self) -> None:
        canonical = _canonical_distribution_name(
            self.distribution_name,
            ProductPackLoadFailureCode.INVALID_LOADED_PRODUCT_PACK,
        )
        if type(self.manifest) is not ProductPackManifest:
            raise ProductPackLoadError(
                ProductPackLoadFailureCode.INVALID_LOADED_PRODUCT_PACK
            ) from None
        object.__setattr__(self, "distribution_name", canonical)


DistributionResolver = Callable[[str], object]
_LoadAttempt = Tuple[
    Optional[LoadedProductPack], Optional[ProductPackLoadFailureCode]
]


def _inspect_distribution_metadata(
    distribution: object,
    expected_pack_id: str,
) -> Tuple[Optional[Tuple[object, ...]], Optional[ProductPackLoadFailureCode]]:
    try:
        matching_entry_points = tuple(
            entry_point
            for entry_point in distribution.entry_points
            if entry_point.group == PRODUCT_PACK_ENTRY_POINT_GROUP
            and entry_point.name == expected_pack_id
        )
    except MemoryError:
        raise
    except Exception:
        return None, ProductPackLoadFailureCode.DISTRIBUTION_METADATA_INVALID
    return matching_entry_points, None


def _attempt_manifest_load(
    request: ProductPackLoadRequest,
    resolver: DistributionResolver,
) -> _LoadAttempt:
    try:
        distribution = resolver(request.distribution_name)
    except MemoryError:
        raise
    except (metadata.PackageNotFoundError, OSError):
        return None, ProductPackLoadFailureCode.DISTRIBUTION_NOT_FOUND

    matching_entry_points, metadata_failure = _inspect_distribution_metadata(
        distribution,
        request.expected_manifest.pack_id,
    )
    if metadata_failure is not None:
        return None, metadata_failure
    if matching_entry_points is None:  # pragma: no cover - internal invariant
        raise RuntimeError("Product Pack metadata inspection returned no result")
    if not matching_entry_points:
        return None, ProductPackLoadFailureCode.MATCHING_ENTRY_POINT_MISSING
    if len(matching_entry_points) != 1:
        return None, ProductPackLoadFailureCode.MATCHING_ENTRY_POINT_AMBIGUOUS

    entry_point = matching_entry_points[0]
    try:
        payload = entry_point.load()
    except MemoryError:
        raise
    except Exception:
        return None, ProductPackLoadFailureCode.ENTRY_POINT_LOAD_FAILED

    if type(payload) is not dict:
        return None, ProductPackLoadFailureCode.LOADED_OBJECT_NOT_MANIFEST_DICT

    try:
        manifest = ProductPackManifest.from_dict(payload)
    except ProductPackManifestValidationError:
        return None, ProductPackLoadFailureCode.MANIFEST_VALIDATION_FAILED

    if manifest != request.expected_manifest:
        return None, ProductPackLoadFailureCode.MANIFEST_MISMATCH

    return (
        LoadedProductPack(
            distribution_name=request.distribution_name,
            manifest=manifest,
        ),
        None,
    )


def load_product_pack_manifest(
    request: ProductPackLoadRequest,
    *,
    resolver: Optional[DistributionResolver] = None,
) -> LoadedProductPack:
    """Load one approved manifest from one explicitly named distribution."""

    if type(request) is not ProductPackLoadRequest:
        raise ProductPackLoadError(
            ProductPackLoadFailureCode.INVALID_LOAD_REQUEST
        ) from None

    selected_resolver = (
        metadata.distribution if resolver is None else resolver
    )
    if not callable(selected_resolver):
        raise ProductPackLoadError(
            ProductPackLoadFailureCode.INVALID_LOAD_REQUEST
        ) from None

    loaded, failure = _attempt_manifest_load(request, selected_resolver)
    if failure is not None:
        raise ProductPackLoadError(failure) from None
    if loaded is None:  # pragma: no cover - internal invariant
        raise RuntimeError("Product Pack loader returned no result")
    return loaded


__all__ = [
    "LoadedProductPack",
    "PRODUCT_PACK_ENTRY_POINT_GROUP",
    "ProductPackLoadError",
    "ProductPackLoadFailureCode",
    "ProductPackLoadRequest",
    "load_product_pack_manifest",
]
