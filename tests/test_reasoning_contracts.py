"""Tests for provider-independent reasoning contracts and validation."""

import pytest

from pmqa.models import Element, Interaction, Lifecycle, Page
from pmqa.reasoning import (
    DeterministicReasoningProvider,
    ReasoningProvider,
    ReasoningRequest,
    ReasoningResponse,
    ReasoningStatus,
    ReasoningValidationError,
    validate_reasoning_exchange,
    validate_reasoning_request,
    validate_reasoning_response,
)


def test_valid_request_passes_and_is_json_serializable() -> None:
    request = validate_reasoning_request(_request())

    assert request.request_id == "request-1"
    assert request.model_dump(mode="json")["pages"][0]["id"] == "page.login"


def test_invalid_request_fails_with_meaningful_error() -> None:
    invalid = _request().model_dump(mode="json")
    invalid["metadata"] = {"cookies": [{"name": "session", "value": "private"}]}

    with pytest.raises(ReasoningValidationError, match="request.metadata.cookies"):
        validate_reasoning_request(invalid)


def test_request_rejects_non_json_runtime_objects() -> None:
    request = _request().model_copy(update={"metadata": {"runtime": object()}})

    with pytest.raises(ReasoningValidationError, match="JSON-compatible"):
        validate_reasoning_request(request)


def test_valid_response_passes() -> None:
    response = validate_reasoning_response(_response(), expected_request_id="request-1")

    assert response.status is ReasoningStatus.COMPLETED
    assert response.decisions == [{"decision_type": "stop"}]


def test_invalid_response_fails_with_meaningful_error() -> None:
    invalid = _response().model_dump(mode="json")
    invalid["confidence"] = 1.5

    with pytest.raises(ReasoningValidationError, match="confidence"):
        validate_reasoning_response(invalid)


def test_deterministic_provider_returns_a_valid_response() -> None:
    response = DeterministicReasoningProvider().reason(_request())

    validated = validate_reasoning_response(response, expected_request_id="request-1")
    assert validated.provider == "deterministic"
    assert validated.decisions[0]["task_type"] == "explore"


def test_request_id_mismatch_is_rejected() -> None:
    mismatched = _response().model_copy(update={"request_id": "another-request"})

    with pytest.raises(ReasoningValidationError, match="must match"):
        validate_reasoning_exchange(_request(), mismatched)


def test_provider_base_rejects_a_mismatched_response() -> None:
    class MismatchedProvider(ReasoningProvider):
        def _reason(self, request: ReasoningRequest) -> ReasoningResponse:
            return _response().model_copy(update={"request_id": "wrong"})

    with pytest.raises(ReasoningValidationError, match="must match"):
        MismatchedProvider().reason(_request())


def _request() -> ReasoningRequest:
    lifecycle = Lifecycle()
    page = Page("page.login", lifecycle, "https://example.test/", "Login", "fingerprint")
    element = Element("element.login", lifecycle, page.id, "button", "Login", "Login")
    interaction = Interaction(
        "interaction.login",
        lifecycle,
        page.id,
        element.id,
        "click",
        "navigation",
        "/inventory.html",
    )
    return ReasoningRequest(
        request_id="request-1",
        workflow_id="workflow-1",
        task_type="explore",
        provider_hint=None,
        product_id="demo",
        artifact_version="1",
        pages=[page],
        elements=[element],
        interactions=[interaction],
        constraints={"maximum_steps": 4},
        metadata={"source": "unit-test"},
    )


def _response() -> ReasoningResponse:
    return ReasoningResponse(
        request_id="request-1",
        provider="deterministic",
        model="rules-v1",
        status=ReasoningStatus.COMPLETED,
        decisions=[{"decision_type": "stop"}],
        confidence=1.0,
        warnings=[],
        metadata={},
    )
