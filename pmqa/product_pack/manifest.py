"""Experimental, product-neutral Product Pack manifest contracts."""

import re
from enum import Enum
from typing import Any, Dict, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


PRODUCT_PACK_IDENTIFIER_PATTERN = r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$"
_IDENTIFIER_PATTERN = re.compile(
    PRODUCT_PACK_IDENTIFIER_PATTERN,
    flags=re.ASCII,
)
_SEMANTIC_VERSION_PATTERN = re.compile(
    r"^(0|[1-9][0-9]*)\."
    r"(0|[1-9][0-9]*)\."
    r"(0|[1-9][0-9]*)"
    r"(?:-((?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$",
    flags=re.ASCII,
)
PRODUCT_PACK_IDENTIFIER_MAX_LENGTH = 64
_MAX_SEMANTIC_VERSION_LENGTH = 128
_MAX_DISPLAY_NAME_LENGTH = 120
_INVALID_MANIFEST_MESSAGE = "invalid Product Pack manifest"


class ProductPackManifestValidationError(ValueError):
    """Reports a safe, bounded external manifest validation failure."""

    def __init__(self) -> None:
        super().__init__(_INVALID_MANIFEST_MESSAGE)


class ProductPackCapability(str, Enum):
    """Declares one bounded capability provided by a Product Pack."""

    EXPLORATION_CAPTURE = "exploration_capture"
    KNOWLEDGE_MAPPING = "knowledge_mapping"
    KNOWLEDGE_VALIDATION = "knowledge_validation"
    TEST_GENERATION = "test_generation"
    TEST_INVENTORY = "test_inventory"


_CAPABILITY_ORDER = {
    capability: index for index, capability in enumerate(ProductPackCapability)
}


class ProductPackManifest(BaseModel):
    """Immutable, declarative identity and capabilities for a Product Pack."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        strict=True,
    )

    schema_version: Literal["1"]
    product_pack_api_version: Literal["1"]
    pack_id: str = Field(
        min_length=1,
        max_length=PRODUCT_PACK_IDENTIFIER_MAX_LENGTH,
        pattern=PRODUCT_PACK_IDENTIFIER_PATTERN,
    )
    pack_version: str = Field(
        min_length=1,
        max_length=_MAX_SEMANTIC_VERSION_LENGTH,
    )
    product_id: str = Field(
        min_length=1,
        max_length=PRODUCT_PACK_IDENTIFIER_MAX_LENGTH,
        pattern=PRODUCT_PACK_IDENTIFIER_PATTERN,
    )
    display_name: str = Field(
        min_length=1,
        max_length=_MAX_DISPLAY_NAME_LENGTH,
    )
    capabilities: Tuple[ProductPackCapability, ...]

    @field_validator("pack_id", "product_id")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        """Require a canonical, cross-platform lowercase ASCII identifier."""

        return validate_product_pack_identifier(value)

    @field_validator("pack_version")
    @classmethod
    def validate_pack_version(cls, value: str) -> str:
        """Require a canonical Semantic Versioning 2.0.0 value."""

        if _SEMANTIC_VERSION_PATTERN.fullmatch(value) is None:
            raise ValueError("pack_version must be canonical semantic version")
        return value

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        """Require bounded printable text without ambiguous outer whitespace."""

        if value.strip() != value or not value or not value.isprintable():
            raise ValueError("display_name must be bounded printable text")
        return value

    @field_validator("capabilities", mode="before")
    @classmethod
    def normalize_capabilities(
        cls,
        value: Any,
    ) -> Tuple[ProductPackCapability, ...]:
        """Validate and normalize capabilities into one canonical order."""

        if not isinstance(value, (list, tuple)):
            raise ValueError("capabilities must be a JSON array")

        parsed = []
        for item in value:
            if isinstance(item, ProductPackCapability):
                capability = item
            elif type(item) is str:
                try:
                    capability = ProductPackCapability(item)
                except ValueError as error:
                    raise ValueError("unsupported Product Pack capability") from error
            else:
                raise ValueError("capabilities must contain stable strings")
            parsed.append(capability)

        if len(set(parsed)) != len(parsed):
            raise ValueError("duplicate Product Pack capabilities are not allowed")
        return tuple(sorted(parsed, key=_CAPABILITY_ORDER.__getitem__))

    def to_dict(self) -> Dict[str, Any]:
        """Return deterministic data accepted by standard JSON encoders."""

        return {
            "schema_version": self.schema_version,
            "product_pack_api_version": self.product_pack_api_version,
            "pack_id": self.pack_id,
            "pack_version": self.pack_version,
            "product_id": self.product_id,
            "display_name": self.display_name,
            "capabilities": [
                capability.value for capability in self.capabilities
            ],
        }

    @classmethod
    def from_dict(cls, value: Any) -> "ProductPackManifest":
        """Safely validate an untrusted JSON-decoded manifest object."""

        try:
            return cls.model_validate(value)
        except ValidationError:
            pass
        raise ProductPackManifestValidationError() from None

    def model_copy(
        self,
        *,
        update: Optional[Dict[str, Any]] = None,
        deep: bool = False,
    ) -> "ProductPackManifest":
        """Return a revalidated copy so updates cannot bypass the contract."""

        _ = deep
        values = self.to_dict()
        values.update(update or {})
        return type(self).model_validate(values)


def validate_product_pack_identifier(value: str) -> str:
    """Apply the shared canonical identifier policy used at pack boundaries."""

    if _IDENTIFIER_PATTERN.fullmatch(value) is None:
        raise ValueError("identifier must use canonical lowercase ASCII")
    return value
