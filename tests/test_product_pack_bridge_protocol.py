"""Tests for language-neutral Product Pack Bridge Protocol v1 contracts."""

import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import traceback

import pytest
from pydantic import ValidationError

from pmqa.models import (
    ExplorationEvidence,
    ExplorationSource,
    InteractionObservation,
    LocatorCandidateObservation,
    ObservedAttribute,
    ObservedElement,
    ObservedPage,
)
from pmqa.product_pack import (
    BRIDGE_PROTOCOL_VERSION,
    MAX_BRIDGE_ACTION_COUNT,
    ProductPackBridgeFailureCode,
    ProductPackBridgeOperation,
    ProductPackBridgeProtocolError,
    ProductPackBridgeProtocolErrorCode,
    ProductPackBridgeRequest,
    ProductPackBridgeResponse,
    ProductPackBridgeStatus,
    bridge_protocol_v1_schema,
    validate_product_pack_bridge_response,
)


SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "pmqa/product_pack/schemas/bridge_protocol_v1.schema.json"
)


class RuntimeObject:
    def __repr__(self) -> str:
        return "RuntimeObject(runtime-secret-marker)"


def _time(minutes: int = 0) -> datetime:
    return datetime(2026, 7, 20, 12, tzinfo=timezone.utc) + timedelta(
        minutes=minutes
    )


def _request(**updates) -> ProductPackBridgeRequest:
    values = {
        "protocol_version": BRIDGE_PROTOCOL_VERSION,
        "request_id": "request.1",
        "workflow_id": "workflow.1",
        "product_id": "demo",
        "pack_id": "external-demo",
        "tool_id": "exploration.capture",
        "operation": ProductPackBridgeOperation.EXPLORATION_CAPTURE,
        "requested_at": _time(),
        "action_plan": ("inspect", "fill", "click"),
    }
    values.update(updates)
    return ProductPackBridgeRequest(**values)


def _evidence(**updates) -> ExplorationEvidence:
    values = {
        "schema_version": "1",
        "evidence_id": "evidence.1",
        "workflow_id": "workflow.1",
        "product_id": "demo",
        "source": ExplorationSource(
            source_type="typescript",
            tool_id="exploration.capture",
            capture_id="capture.1",
        ),
        "captured_at": _time(1),
        "pages": (
            ObservedPage(
                page_id="page.login",
                url="https://example.invalid/login",
                title="Login",
                structural_fingerprint="sha256:page-login",
            ),
        ),
        "elements": (
            ObservedElement(
                element_id="element.login",
                page_id="page.login",
                role="button",
                accessible_name="Login",
                attributes=(
                    ObservedAttribute(name="data-test", value="login-button"),
                    ObservedAttribute(name="type", value="password"),
                ),
            ),
        ),
        "locator_candidates": (
            LocatorCandidateObservation(
                locator_candidate_id="candidate.login",
                element_id="element.login",
                strategy="data-test",
                value="login-button",
                priority=1,
            ),
        ),
        "interactions": (
            InteractionObservation(
                interaction_id="interaction.login",
                source_page_id="page.login",
                target_element_id="element.login",
                action="click",
                outcome_type="navigation",
                outcome_value="inventory",
            ),
        ),
    }
    values.update(updates)
    return ExplorationEvidence(**values)


def _response(**updates) -> ProductPackBridgeResponse:
    values = {
        "protocol_version": BRIDGE_PROTOCOL_VERSION,
        "request_id": "request.1",
        "workflow_id": "workflow.1",
        "product_id": "demo",
        "pack_id": "external-demo",
        "tool_id": "exploration.capture",
        "operation": ProductPackBridgeOperation.EXPLORATION_CAPTURE,
        "status": ProductPackBridgeStatus.SUCCEEDED,
        "completed_at": _time(2),
        "evidence": _evidence(),
        "failure_code": None,
    }
    values.update(updates)
    return ProductPackBridgeResponse(**values)


def _failed_response(**updates) -> ProductPackBridgeResponse:
    values = {
        "status": ProductPackBridgeStatus.FAILED,
        "evidence": None,
        "failure_code": ProductPackBridgeFailureCode.EXPLORATION_FAILED,
    }
    values.update(updates)
    return _response(**values)


def test_valid_request_is_exact_frozen_ordered_and_deeply_immutable() -> None:
    actions = ["inspect", "fill", "click"]
    request = _request(action_plan=actions)
    actions.clear()

    assert tuple(ProductPackBridgeRequest.model_fields) == (
        "protocol_version",
        "request_id",
        "workflow_id",
        "product_id",
        "pack_id",
        "tool_id",
        "operation",
        "requested_at",
        "action_plan",
    )
    assert request.action_plan == ("inspect", "fill", "click")
    assert request.requested_at == _time()
    with pytest.raises(ValidationError, match="frozen"):
        request.request_id = "changed"
    with pytest.raises(AttributeError):
        request.action_plan.append("stop")


def test_valid_succeeded_response_retains_structured_locator_evidence() -> None:
    evidence = _evidence()
    response = _response(evidence=evidence)

    assert tuple(ProductPackBridgeResponse.model_fields) == (
        "protocol_version",
        "request_id",
        "workflow_id",
        "product_id",
        "pack_id",
        "tool_id",
        "operation",
        "status",
        "completed_at",
        "evidence",
        "failure_code",
    )
    assert response.evidence is not evidence
    assert response.evidence == evidence
    assert response.evidence.locator_candidates[0].strategy == "data-test"
    assert response.evidence.elements[0].attributes[1].value == "password"
    assert response.failure_code is None


def test_valid_failed_response_uses_only_bounded_failure_code() -> None:
    response = _failed_response()

    assert response.status is ProductPackBridgeStatus.FAILED
    assert response.evidence is None
    assert (
        response.failure_code
        is ProductPackBridgeFailureCode.EXPLORATION_FAILED
    )


@pytest.mark.parametrize("contract", [_request(), _response(), _failed_response()])
def test_request_and_response_round_trip_through_standard_json(contract) -> None:
    payload = contract.to_dict()
    decoded = json.loads(json.dumps(payload))
    restored = type(contract).from_dict(decoded)

    assert restored == contract
    assert restored.to_dict() == payload
    assert json.dumps(payload) == json.dumps(contract.to_dict())
    if isinstance(restored, ProductPackBridgeResponse) and restored.evidence:
        assert restored.evidence is not contract.evidence


@pytest.mark.parametrize("contract", [_request(), _response()])
def test_unknown_fields_are_rejected_safely(contract) -> None:
    payload = contract.to_dict()
    payload["credentials"] = "runtime-secret-marker"

    with pytest.raises(ProductPackBridgeProtocolError) as captured:
        type(contract).from_dict(payload)

    assert "runtime-secret-marker" not in str(captured.value)


@pytest.mark.parametrize(
    ("contract_type", "updates"),
    [
        (ProductPackBridgeRequest, {"protocol_version": "2"}),
        (ProductPackBridgeRequest, {"operation": "generate"}),
        (ProductPackBridgeResponse, {"protocol_version": "2"}),
        (ProductPackBridgeResponse, {"operation": "generate"}),
        (ProductPackBridgeResponse, {"status": "partial"}),
    ],
)
def test_unsupported_protocol_vocabulary_is_rejected(
    contract_type,
    updates,
) -> None:
    payload = (
        _request().to_dict()
        if contract_type is ProductPackBridgeRequest
        else _response().to_dict()
    )
    payload.update(updates)

    with pytest.raises(ProductPackBridgeProtocolError):
        contract_type.from_dict(payload)


@pytest.mark.parametrize(
    "timestamp",
    [
        datetime(2026, 7, 20, 12),
        "2026-07-20T12:00:00+00:00",
        "2026-07-20T12:00:00z",
        "2026-07-20T12:00:00.1Z",
        "2026-07-20 12:00:00Z",
        "not-a-time",
        RuntimeObject(),
    ],
)
@pytest.mark.parametrize(
    ("contract_type", "field"),
    [
        (ProductPackBridgeRequest, "requested_at"),
        (ProductPackBridgeResponse, "completed_at"),
    ],
)
def test_malformed_naive_or_noncanonical_timestamps_are_rejected_safely(
    timestamp,
    contract_type,
    field: str,
) -> None:
    payload = (
        _request().to_dict()
        if contract_type is ProductPackBridgeRequest
        else _response().to_dict()
    )
    payload[field] = timestamp

    with pytest.raises(ProductPackBridgeProtocolError) as captured:
        contract_type.from_dict(payload)
    assert "runtime-secret-marker" not in str(captured.value)


@pytest.mark.parametrize(
    "action_plan",
    [
        [],
        ["inspect"] * (MAX_BRIDGE_ACTION_COUNT + 1),
        "inspect",
        [""],
        ["Inspect"],
        ["../inspect"],
        ["https://example.invalid/action"],
        ["inspect;delete"],
        ["x" * 65],
        [RuntimeObject()],
        [{"action": "inspect"}],
        [lambda: None],
    ],
)
def test_invalid_or_excessive_action_plans_are_rejected(action_plan) -> None:
    payload = _request().to_dict()
    payload["action_plan"] = action_plan

    with pytest.raises(ProductPackBridgeProtocolError) as captured:
        ProductPackBridgeRequest.from_dict(payload)
    assert "runtime-secret-marker" not in str(captured.value)


@pytest.mark.parametrize(
    "action",
    ["password", "API-Key", "browser context", "Provider-Instance", "locator"],
)
def test_action_plan_reuses_shared_prohibited_key_policy(action: str) -> None:
    payload = _request().to_dict()
    payload["action_plan"] = [action]

    with pytest.raises(ProductPackBridgeProtocolError):
        ProductPackBridgeRequest.from_dict(payload)


@pytest.mark.parametrize(
    ("status", "evidence", "failure_code"),
    [
        ("succeeded", None, None),
        ("succeeded", _evidence().to_workflow_payload(), "protocol_failure"),
        ("failed", _evidence().to_workflow_payload(), "exploration_failed"),
        ("failed", None, None),
        ("failed", None, "runtime-secret-marker"),
    ],
)
def test_inconsistent_response_payloads_are_rejected(
    status: str,
    evidence,
    failure_code,
) -> None:
    payload = _response().to_dict()
    payload.update(
        {
            "status": status,
            "evidence": evidence,
            "failure_code": failure_code,
        }
    )

    with pytest.raises(ProductPackBridgeProtocolError) as captured:
        ProductPackBridgeResponse.from_dict(payload)
    assert "runtime-secret-marker" not in str(captured.value)


@pytest.mark.parametrize(
    "evidence_update",
    [
        {"schema_version": "2"},
        {"captured_at": "not-a-time"},
        {"runtime": RuntimeObject()},
    ],
)
def test_malformed_or_noncanonical_evidence_is_rejected_safely(
    evidence_update,
) -> None:
    payload = _response().to_dict()
    payload["evidence"].update(evidence_update)

    with pytest.raises(ProductPackBridgeProtocolError) as captured:
        ProductPackBridgeResponse.from_dict(payload)
    formatted = "".join(
        traceback.format_exception(
            type(captured.value), captured.value, captured.value.__traceback__
        )
    )
    assert "runtime-secret-marker" not in formatted
    assert "RuntimeObject" not in formatted
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None


@pytest.mark.parametrize(
    "field",
    [
        "protocol_version",
        "request_id",
        "workflow_id",
        "product_id",
        "pack_id",
        "tool_id",
        "operation",
    ],
)
def test_every_request_response_identity_mismatch_is_rejected(field: str) -> None:
    response = _response()
    values = {
        name: getattr(response, name)
        for name in ProductPackBridgeResponse.model_fields
    }
    if field == "protocol_version":
        values[field] = "2"
        mismatched = ProductPackBridgeResponse.model_construct(**values)
    elif field == "operation":
        values[field] = "generate"
        mismatched = ProductPackBridgeResponse.model_construct(**values)
    elif field == "workflow_id":
        mismatched = _response(
            workflow_id="workflow.2",
            evidence=_evidence(workflow_id="workflow.2"),
        )
    elif field == "product_id":
        mismatched = _response(
            product_id="another-product",
            evidence=_evidence(product_id="another-product"),
        )
    elif field == "tool_id":
        mismatched = _response(
            tool_id="another.tool",
            evidence=_evidence(
                source=ExplorationSource(
                    source_type="typescript",
                    tool_id="another.tool",
                    capture_id="capture.1",
                )
            ),
        )
    else:
        values[field] = "another-id"
        mismatched = ProductPackBridgeResponse(**values)

    with pytest.raises(ProductPackBridgeProtocolError) as captured:
        validate_product_pack_bridge_response(_request(), mismatched)
    assert (
        captured.value.code
        is ProductPackBridgeProtocolErrorCode.CORRELATION_MISMATCH
    )


def test_timestamp_and_evidence_correlations_are_enforced() -> None:
    before_request = _time() - timedelta(minutes=1)
    responses = (
        _failed_response(completed_at=before_request),
        _response(
            evidence=_evidence(captured_at=before_request),
            completed_at=_time(2),
        ),
    )

    for response in responses:
        with pytest.raises(ProductPackBridgeProtocolError):
            validate_product_pack_bridge_response(_request(), response)


def test_valid_exchange_returns_same_immutable_response() -> None:
    request = _request()
    response = _response()

    assert validate_product_pack_bridge_response(request, response) is response


def test_caller_owned_payload_is_unchanged_and_not_retained() -> None:
    payload = _response().to_dict()
    original = copy.deepcopy(payload)

    restored = ProductPackBridgeResponse.from_dict(payload)
    payload["evidence"]["pages"].clear()
    payload["evidence"]["source"]["tool_id"] = "changed"

    assert original["evidence"]["pages"]
    assert restored.evidence.pages
    assert restored.evidence.source.tool_id == "exploration.capture"


def test_model_copy_updates_are_revalidated() -> None:
    with pytest.raises(ProductPackBridgeProtocolError):
        _request().model_copy(update={"protocol_version": "2"})
    with pytest.raises(ProductPackBridgeProtocolError):
        _response().model_copy(update={"failure_code": "protocol_failure"})


def test_safe_protocol_error_has_fixed_bounded_public_state() -> None:
    payload = _request().to_dict()
    payload["credentials"] = "runtime-secret-marker"

    with pytest.raises(ProductPackBridgeProtocolError) as captured:
        ProductPackBridgeRequest.from_dict(payload)
    error = captured.value
    formatted = "".join(
        traceback.format_exception(type(error), error, error.__traceback__)
    )

    assert error.args == ("invalid Product Pack bridge request",)
    assert vars(error) == {
        "code": ProductPackBridgeProtocolErrorCode.INVALID_REQUEST
    }
    assert error.__cause__ is None
    assert error.__context__ is None
    assert "runtime-secret-marker" not in formatted
    assert formatted.count("File ") <= 3


def test_canonical_versioned_schema_matches_python_contracts() -> None:
    stored = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    derived = bridge_protocol_v1_schema()

    assert stored == derived
    assert stored["protocol_version"] == "1"
    assert stored["request"]["properties"].keys() == set(
        ProductPackBridgeRequest.model_fields
    )
    assert stored["response"]["properties"].keys() == set(
        ProductPackBridgeResponse.model_fields
    )
    assert stored["request"]["properties"]["action_plan"]["maxItems"] == 32
