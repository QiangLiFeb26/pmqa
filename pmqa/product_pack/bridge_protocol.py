"""Language-neutral Product Pack Bridge Protocol v1 contracts."""

from datetime import datetime, timezone
from enum import Enum
import math
from typing import Annotated, Any, Dict, Literal, Optional, Tuple

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_serializer,
    field_validator,
    model_validator,
)

from pmqa.models.exploration import ExplorationEvidence
from pmqa.product_pack.manifest import (
    PRODUCT_PACK_IDENTIFIER_MAX_LENGTH,
    PRODUCT_PACK_IDENTIFIER_PATTERN,
    validate_product_pack_identifier,
)
from pmqa.security.boundary_policy import (
    WORKFLOW_STATE_PROHIBITED_KEYS,
    is_prohibited_key,
)


BRIDGE_PROTOCOL_VERSION = "1"
MAX_BRIDGE_ACTION_COUNT = 32
# Wire trees deeper than this are rejected before typed reconstruction.
_MAX_BRIDGE_JSON_NESTING_DEPTH = 32
_CANONICAL_TIMESTAMP_PATTERN = (
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{6})?Z$"
)
_BridgeActionIdentifier = Annotated[
    str,
    Field(
        min_length=1,
        max_length=PRODUCT_PACK_IDENTIFIER_MAX_LENGTH,
        pattern=PRODUCT_PACK_IDENTIFIER_PATTERN,
    ),
]


class ProductPackBridgeOperation(str, Enum):
    """Bounded operation vocabulary for Bridge Protocol v1."""

    EXPLORATION_CAPTURE = "exploration_capture"


class ProductPackBridgeStatus(str, Enum):
    """Terminal response status vocabulary."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ProductPackBridgeFailureCode(str, Enum):
    """Bounded product-neutral failures returned by an external bridge."""

    EXPLORATION_FAILED = "exploration_failed"
    ACTION_PLAN_REJECTED = "action_plan_rejected"
    PROTOCOL_FAILURE = "protocol_failure"


class ProductPackBridgeProtocolErrorCode(str, Enum):
    """Stable reasons a protocol boundary rejects an exchange."""

    INVALID_REQUEST = "invalid_request"
    INVALID_RESPONSE = "invalid_response"
    CORRELATION_MISMATCH = "correlation_mismatch"


_PROTOCOL_ERROR_MESSAGES = {
    ProductPackBridgeProtocolErrorCode.INVALID_REQUEST: (
        "invalid Product Pack bridge request"
    ),
    ProductPackBridgeProtocolErrorCode.INVALID_RESPONSE: (
        "invalid Product Pack bridge response"
    ),
    ProductPackBridgeProtocolErrorCode.CORRELATION_MISMATCH: (
        "Product Pack bridge response correlation failed"
    ),
}


class ProductPackBridgeProtocolError(ValueError):
    """Expose only a fixed protocol error code and bounded safe message."""

    def __init__(self, code: ProductPackBridgeProtocolErrorCode) -> None:
        self.code = code
        super().__init__(_PROTOCOL_ERROR_MESSAGES[code])


class _BridgeProtocolContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        strict=True,
    )

    def model_copy(
        self,
        *,
        update: Optional[Dict[str, Any]] = None,
        deep: bool = False,
    ) -> "_BridgeProtocolContract":
        """Return a safely reconstructed copy so updates cannot bypass checks."""

        _ = deep
        values = self.to_dict()
        values.update(update or {})
        return type(self).from_dict(values)


class ProductPackBridgeRequest(_BridgeProtocolContract):
    """One bounded request to an explicitly selected Product Pack bridge."""

    protocol_version: Literal["1"]
    request_id: str = Field(
        min_length=1,
        max_length=PRODUCT_PACK_IDENTIFIER_MAX_LENGTH,
        pattern=PRODUCT_PACK_IDENTIFIER_PATTERN,
    )
    workflow_id: str = Field(
        min_length=1,
        max_length=PRODUCT_PACK_IDENTIFIER_MAX_LENGTH,
        pattern=PRODUCT_PACK_IDENTIFIER_PATTERN,
    )
    product_id: str = Field(
        min_length=1,
        max_length=PRODUCT_PACK_IDENTIFIER_MAX_LENGTH,
        pattern=PRODUCT_PACK_IDENTIFIER_PATTERN,
    )
    pack_id: str = Field(
        min_length=1,
        max_length=PRODUCT_PACK_IDENTIFIER_MAX_LENGTH,
        pattern=PRODUCT_PACK_IDENTIFIER_PATTERN,
    )
    tool_id: str = Field(
        min_length=1,
        max_length=PRODUCT_PACK_IDENTIFIER_MAX_LENGTH,
        pattern=PRODUCT_PACK_IDENTIFIER_PATTERN,
    )
    operation: ProductPackBridgeOperation
    requested_at: datetime = Field(
        json_schema_extra={"pattern": _CANONICAL_TIMESTAMP_PATTERN}
    )
    action_plan: Tuple[_BridgeActionIdentifier, ...] = Field(
        min_length=1,
        max_length=MAX_BRIDGE_ACTION_COUNT,
    )

    @field_validator(
        "request_id",
        "workflow_id",
        "product_id",
        "pack_id",
        "tool_id",
    )
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        return validate_product_pack_identifier(value)

    @field_validator("operation", mode="before")
    @classmethod
    def validate_operation(cls, value: Any) -> ProductPackBridgeOperation:
        if isinstance(value, ProductPackBridgeOperation):
            return value
        if type(value) is str:
            try:
                return ProductPackBridgeOperation(value)
            except ValueError:
                pass
        raise ValueError("unsupported Product Pack bridge operation")

    @field_validator("requested_at", mode="before")
    @classmethod
    def validate_requested_at(cls, value: Any) -> datetime:
        return _canonical_timestamp(value, "requested_at")

    @field_serializer("requested_at")
    def serialize_requested_at(self, value: datetime) -> str:
        return _serialize_timestamp(value)

    @field_validator("action_plan", mode="before")
    @classmethod
    def validate_action_plan(cls, value: Any) -> Tuple[str, ...]:
        if not isinstance(value, (list, tuple)):
            raise ValueError("action_plan must be an ordered JSON array")
        if not value or len(value) > MAX_BRIDGE_ACTION_COUNT:
            raise ValueError("action_plan has an invalid action count")
        actions = []
        for action in value:
            if type(action) is not str:
                raise ValueError("action_plan must contain action identifiers")
            if is_prohibited_key(action, WORKFLOW_STATE_PROHIBITED_KEYS):
                raise ValueError("action identifier is prohibited")
            actions.append(validate_product_pack_identifier(action))
        return tuple(actions)

    def to_dict(self) -> Dict[str, Any]:
        """Return deterministic JSON-compatible Bridge Protocol v1 data."""

        return {
            "protocol_version": self.protocol_version,
            "request_id": self.request_id,
            "workflow_id": self.workflow_id,
            "product_id": self.product_id,
            "pack_id": self.pack_id,
            "tool_id": self.tool_id,
            "operation": self.operation.value,
            "requested_at": _serialize_timestamp(self.requested_at),
            "action_plan": list(self.action_plan),
        }

    @classmethod
    def from_dict(cls, value: Any) -> "ProductPackBridgeRequest":
        """Safely reconstruct a request from untrusted JSON-decoded data."""

        if type(value) is not dict or not _is_plain_json(value):
            raise ProductPackBridgeProtocolError(
                ProductPackBridgeProtocolErrorCode.INVALID_REQUEST
            ) from None
        try:
            request = cls.model_validate(dict(value))
        except ValidationError:
            pass
        else:
            if _plain_json_equal(value, request.to_dict()):
                return request
        raise ProductPackBridgeProtocolError(
            ProductPackBridgeProtocolErrorCode.INVALID_REQUEST
        ) from None


class ProductPackBridgeResponse(_BridgeProtocolContract):
    """One terminal, correlated Bridge Protocol v1 response."""

    protocol_version: Literal["1"]
    request_id: str = Field(
        min_length=1,
        max_length=PRODUCT_PACK_IDENTIFIER_MAX_LENGTH,
        pattern=PRODUCT_PACK_IDENTIFIER_PATTERN,
    )
    workflow_id: str = Field(
        min_length=1,
        max_length=PRODUCT_PACK_IDENTIFIER_MAX_LENGTH,
        pattern=PRODUCT_PACK_IDENTIFIER_PATTERN,
    )
    product_id: str = Field(
        min_length=1,
        max_length=PRODUCT_PACK_IDENTIFIER_MAX_LENGTH,
        pattern=PRODUCT_PACK_IDENTIFIER_PATTERN,
    )
    pack_id: str = Field(
        min_length=1,
        max_length=PRODUCT_PACK_IDENTIFIER_MAX_LENGTH,
        pattern=PRODUCT_PACK_IDENTIFIER_PATTERN,
    )
    tool_id: str = Field(
        min_length=1,
        max_length=PRODUCT_PACK_IDENTIFIER_MAX_LENGTH,
        pattern=PRODUCT_PACK_IDENTIFIER_PATTERN,
    )
    operation: ProductPackBridgeOperation
    status: ProductPackBridgeStatus
    completed_at: datetime = Field(
        json_schema_extra={"pattern": _CANONICAL_TIMESTAMP_PATTERN}
    )
    evidence: Optional[ExplorationEvidence]
    failure_code: Optional[ProductPackBridgeFailureCode]

    @field_validator(
        "request_id",
        "workflow_id",
        "product_id",
        "pack_id",
        "tool_id",
    )
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        return validate_product_pack_identifier(value)

    @field_validator("operation", mode="before")
    @classmethod
    def validate_operation(cls, value: Any) -> ProductPackBridgeOperation:
        return ProductPackBridgeRequest.validate_operation(value)

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, value: Any) -> ProductPackBridgeStatus:
        if isinstance(value, ProductPackBridgeStatus):
            return value
        if type(value) is str:
            try:
                return ProductPackBridgeStatus(value)
            except ValueError:
                pass
        raise ValueError("unsupported Product Pack bridge status")

    @field_validator("failure_code", mode="before")
    @classmethod
    def validate_failure_code(
        cls,
        value: Any,
    ) -> Optional[ProductPackBridgeFailureCode]:
        if value is None or isinstance(value, ProductPackBridgeFailureCode):
            return value
        if type(value) is str:
            try:
                return ProductPackBridgeFailureCode(value)
            except ValueError:
                pass
        raise ValueError("unsupported Product Pack bridge failure code")

    @field_validator("completed_at", mode="before")
    @classmethod
    def validate_completed_at(cls, value: Any) -> datetime:
        return _canonical_timestamp(value, "completed_at")

    @field_serializer("completed_at")
    def serialize_completed_at(self, value: datetime) -> str:
        return _serialize_timestamp(value)

    @field_validator("evidence", mode="before")
    @classmethod
    def require_evidence_contract(
        cls,
        value: Any,
    ) -> Optional[ExplorationEvidence]:
        if value is None:
            return value
        if type(value) is ExplorationEvidence:
            return ExplorationEvidence.from_workflow_payload(
                value.to_workflow_payload()
            )
        raise ValueError("evidence must be a validated ExplorationEvidence")

    @model_validator(mode="after")
    def validate_result(self) -> "ProductPackBridgeResponse":
        if self.status is ProductPackBridgeStatus.SUCCEEDED:
            if self.evidence is None or self.failure_code is not None:
                raise ValueError("succeeded response has inconsistent payload")
            if self.evidence.schema_version != "1":
                raise ValueError("evidence schema version is unsupported")
            if self.evidence.workflow_id != self.workflow_id:
                raise ValueError("evidence workflow correlation failed")
            if self.evidence.product_id != self.product_id:
                raise ValueError("evidence product correlation failed")
            if self.evidence.source.tool_id != self.tool_id:
                raise ValueError("evidence Tool correlation failed")
            if self.evidence.captured_at > self.completed_at:
                raise ValueError("evidence timestamp correlation failed")
        elif self.evidence is not None or self.failure_code is None:
            raise ValueError("failed response has inconsistent payload")
        return self

    def to_dict(self) -> Dict[str, Any]:
        """Return deterministic JSON-compatible Bridge Protocol v1 data."""

        return {
            "protocol_version": self.protocol_version,
            "request_id": self.request_id,
            "workflow_id": self.workflow_id,
            "product_id": self.product_id,
            "pack_id": self.pack_id,
            "tool_id": self.tool_id,
            "operation": self.operation.value,
            "status": self.status.value,
            "completed_at": _serialize_timestamp(self.completed_at),
            "evidence": (
                None if self.evidence is None else self.evidence.to_workflow_payload()
            ),
            "failure_code": (
                None if self.failure_code is None else self.failure_code.value
            ),
        }

    @classmethod
    def from_dict(cls, value: Any) -> "ProductPackBridgeResponse":
        """Safely reconstruct a response from untrusted JSON-decoded data."""

        if type(value) is not dict or not _is_plain_json(value):
            raise ProductPackBridgeProtocolError(
                ProductPackBridgeProtocolErrorCode.INVALID_RESPONSE
            ) from None
        candidate = dict(value)
        raw_evidence = candidate.get("evidence")
        if raw_evidence is not None:
            if type(raw_evidence) is not dict:
                raise ProductPackBridgeProtocolError(
                    ProductPackBridgeProtocolErrorCode.INVALID_RESPONSE
                ) from None
            try:
                validated_evidence = ExplorationEvidence.from_workflow_payload(
                    raw_evidence
                )
            except ValidationError:
                pass
            else:
                candidate["evidence"] = validated_evidence
                validated_evidence = None
            if type(candidate["evidence"]) is not ExplorationEvidence:
                raise ProductPackBridgeProtocolError(
                    ProductPackBridgeProtocolErrorCode.INVALID_RESPONSE
                ) from None
        try:
            response = cls.model_validate(candidate)
        except ValidationError:
            pass
        else:
            if _plain_json_equal(value, response.to_dict()):
                return response
        raise ProductPackBridgeProtocolError(
            ProductPackBridgeProtocolErrorCode.INVALID_RESPONSE
        ) from None


def validate_product_pack_bridge_response(
    request: ProductPackBridgeRequest,
    response: ProductPackBridgeResponse,
) -> ProductPackBridgeResponse:
    """Validate a response against its originating request without mutation."""

    if (
        type(request) is not ProductPackBridgeRequest
        or type(response) is not ProductPackBridgeResponse
    ):
        raise ProductPackBridgeProtocolError(
            ProductPackBridgeProtocolErrorCode.CORRELATION_MISMATCH
        ) from None

    request_values = (
        request.protocol_version,
        request.request_id,
        request.workflow_id,
        request.product_id,
        request.pack_id,
        request.tool_id,
        request.operation,
    )
    response_values = (
        response.protocol_version,
        response.request_id,
        response.workflow_id,
        response.product_id,
        response.pack_id,
        response.tool_id,
        response.operation,
    )
    if response_values != request_values:
        raise ProductPackBridgeProtocolError(
            ProductPackBridgeProtocolErrorCode.CORRELATION_MISMATCH
        ) from None
    if response.completed_at < request.requested_at:
        raise ProductPackBridgeProtocolError(
            ProductPackBridgeProtocolErrorCode.CORRELATION_MISMATCH
        ) from None
    if (
        response.evidence is not None
        and response.evidence.captured_at < request.requested_at
    ):
        raise ProductPackBridgeProtocolError(
            ProductPackBridgeProtocolErrorCode.CORRELATION_MISMATCH
        ) from None
    return response


def bridge_protocol_v1_schema() -> Dict[str, Any]:
    """Return the canonical language-neutral schema derived from contracts."""

    request_schema = ProductPackBridgeRequest.model_json_schema()
    response_schema = ProductPackBridgeResponse.model_json_schema()
    request_schema["$id"] = "product-pack-bridge-v1-request.json"
    response_schema["$id"] = "product-pack-bridge-v1-response.json"
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://pmqa.invalid/schemas/product-pack-bridge-v1.json",
        "title": "PMQA Product Pack Bridge Protocol v1",
        "protocol_version": BRIDGE_PROTOCOL_VERSION,
        "request": request_schema,
        "response": response_schema,
    }


def _canonical_timestamp(value: Any, field_name: str) -> datetime:
    if type(value) is datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{field_name} must include timezone information")
        return value.astimezone(timezone.utc)
    if type(value) is str and value.endswith("Z"):
        try:
            parsed = datetime.fromisoformat(value[:-1] + "+00:00")
        except ValueError:
            pass
        else:
            if _serialize_timestamp(parsed) == value:
                return parsed
    raise ValueError(f"{field_name} must be a canonical UTC timestamp")


def _serialize_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_plain_json(
    value: Any,
    *,
    depth: int = 0,
    active_containers: Optional[set] = None,
) -> bool:
    """Accept only bounded trees made from exact JSON-decoder built-in types."""

    if depth > _MAX_BRIDGE_JSON_NESTING_DEPTH:
        return False
    value_type = type(value)
    if value is None or value_type in {str, bool, int}:
        return True
    if value_type is float:
        return math.isfinite(value)
    if value_type not in {dict, list}:
        return False

    active = set() if active_containers is None else active_containers
    identity = id(value)
    if identity in active:
        return False
    active.add(identity)
    try:
        if value_type is list:
            return all(
                _is_plain_json(
                    item,
                    depth=depth + 1,
                    active_containers=active,
                )
                for item in value
            )
        return all(
            type(key) is str
            and _is_plain_json(
                item,
                depth=depth + 1,
                active_containers=active,
            )
            for key, item in value.items()
        )
    finally:
        active.remove(identity)


def _plain_json_equal(submitted: Any, canonical: Any) -> bool:
    """Compare canonical wire trees without Python's cross-type equality."""

    if type(submitted) is not type(canonical):
        return False
    if type(submitted) is dict:
        if submitted.keys() != canonical.keys():
            return False
        return all(
            _plain_json_equal(submitted[key], canonical[key])
            for key in submitted
        )
    if type(submitted) is list:
        return len(submitted) == len(canonical) and all(
            _plain_json_equal(left, right)
            for left, right in zip(submitted, canonical)
        )
    return submitted == canonical


__all__ = [
    "BRIDGE_PROTOCOL_VERSION",
    "MAX_BRIDGE_ACTION_COUNT",
    "ProductPackBridgeFailureCode",
    "ProductPackBridgeOperation",
    "ProductPackBridgeProtocolError",
    "ProductPackBridgeProtocolErrorCode",
    "ProductPackBridgeRequest",
    "ProductPackBridgeResponse",
    "ProductPackBridgeStatus",
    "bridge_protocol_v1_schema",
    "validate_product_pack_bridge_response",
]
