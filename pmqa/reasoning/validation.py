"""Validation helpers for reasoning requests, responses, and exchanges."""

import json
from typing import Any, Mapping, Optional, Union

from pydantic import ValidationError
from pydantic_core import PydanticSerializationError

from pmqa.reasoning.boundary_policy import is_prohibited_reasoning_key
from pmqa.reasoning.models import ReasoningRequest, ReasoningResponse


class ReasoningValidationError(ValueError):
    """Reports a malformed or inconsistent reasoning contract value."""


RequestInput = Union[ReasoningRequest, Mapping[str, Any]]
ResponseInput = Union[ReasoningResponse, Mapping[str, Any]]

def validate_reasoning_request(value: RequestInput) -> ReasoningRequest:
    """Validate and normalize a reasoning request or raise a meaningful error."""

    request = _validate_model(ReasoningRequest, value, "request")
    payload = _dump_json(request, "request")
    _require_json(payload, "request")
    _reject_prohibited_keys(payload, "request")
    return request


def validate_reasoning_response(
    value: ResponseInput,
    expected_request_id: Optional[str] = None,
) -> ReasoningResponse:
    """Validate a response and optionally enforce its request identifier."""

    response = _validate_model(ReasoningResponse, value, "response")
    payload = _dump_json(response, "response")
    _require_json(payload, "response")
    if expected_request_id is not None and response.request_id != expected_request_id:
        raise ReasoningValidationError(
            "response.request_id must match request.request_id: "
            f"expected {expected_request_id!r}, received {response.request_id!r}"
        )
    return response


def validate_reasoning_exchange(
    request: RequestInput,
    response: ResponseInput,
) -> tuple[ReasoningRequest, ReasoningResponse]:
    """Validate both sides of an exchange and their identifier consistency."""

    valid_request = validate_reasoning_request(request)
    valid_response = validate_reasoning_response(response, valid_request.request_id)
    return valid_request, valid_response


def _validate_model(model_type, value: Any, label: str):
    try:
        return model_type.model_validate(value)
    except ValidationError as error:
        details = "; ".join(
            f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
            for item in error.errors()
        )
        raise ReasoningValidationError(f"Invalid reasoning {label}: {details}") from error


def _require_json(value: Any, label: str) -> None:
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ReasoningValidationError(
            f"Reasoning {label} must contain only JSON-compatible values: {error}"
        ) from error


def _dump_json(model: Any, label: str) -> Any:
    try:
        return model.model_dump(mode="json")
    except (PydanticSerializationError, TypeError, ValueError) as error:
        raise ReasoningValidationError(
            f"Reasoning {label} must contain only JSON-compatible values: {error}"
        ) from error


def _reject_prohibited_keys(value: Any, path: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{path}.{key}"
            if is_prohibited_reasoning_key(key):
                raise ReasoningValidationError(
                    "Reasoning request contains prohibited runtime or sensitive "
                    f"field: {child_path}"
                )
            _reject_prohibited_keys(item, child_path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_prohibited_keys(item, f"{path}[{index}]")
