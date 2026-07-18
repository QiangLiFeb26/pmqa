"""Offline tests for the human-mediated GitHub Copilot provider."""

import json

import pytest

from pmqa.reasoning import (
    DeterministicReasoningScrubber,
    ManualCopilotReasoningProvider,
    ManualPromptPackage,
    ManualReasoningChannel,
    ManualReasoningError,
    ReasoningDecision,
    ReasoningResponse,
    ReasoningStatus,
    ReasoningValidationError,
    ScrubInput,
)


class FakeManualChannel(ManualReasoningChannel):
    """Captures a package and returns a predefined response without a terminal."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.package = None

    def present_prompt(self, package: ManualPromptPackage) -> None:
        self.package = package

    def receive_response(self) -> str:
        return self.response


def test_same_request_produces_same_prompt_package() -> None:
    provider = ManualCopilotReasoningProvider()
    request = _safe_request()

    assert provider.prepare(request) == provider.prepare(request)


def test_prompt_package_contains_only_scrubbed_request_content() -> None:
    fake_secret = "fake-password-value"
    scrubbed = DeterministicReasoningScrubber().scrub(
        _scrub_input(metadata={"password": fake_secret, "note": "safe-context"})
    )

    package = ManualCopilotReasoningProvider().prepare(scrubbed.request)
    package_json = package.model_dump_json()

    assert "safe-context" in package.request_json
    assert fake_secret not in package_json
    assert json.loads(package.request_json) == scrubbed.request.model_dump(mode="json")


def test_response_schema_is_derived_from_canonical_model() -> None:
    package = ManualCopilotReasoningProvider().prepare(_safe_request())

    assert json.loads(package.response_schema_json) == ReasoningResponse.model_json_schema()
    schema_text = package.response_schema_json
    assert "ReasoningDecision" in schema_text
    assert "evidence_ids" in schema_text


def test_valid_json_response_returns_typed_response() -> None:
    request = _safe_request()

    response = ManualCopilotReasoningProvider().complete(request, _response_json())

    assert isinstance(response, ReasoningResponse)
    assert isinstance(response.decisions[0], ReasoningDecision)
    assert response.provider == "github-copilot-manual"


def test_single_json_markdown_fence_is_accepted() -> None:
    pasted = f"```json\n{_response_json()}\n```"

    response = ManualCopilotReasoningProvider().complete(_safe_request(), pasted)

    assert response.request_id == "request-1"


@pytest.mark.parametrize(
    ("scenario", "message"),
    [
        ("empty", "empty"),
        ("malformed", "exactly one JSON object"),
        ("prose_before", "exactly one JSON object"),
        ("prose_after", "exactly one JSON object"),
        ("multiple", "exactly one JSON object"),
    ],
)
def test_invalid_manual_response_text_is_rejected(scenario: str, message: str) -> None:
    valid = _response_json()
    pasted = {
        "empty": "",
        "malformed": "{not-json}",
        "prose_before": "Here is JSON: " + valid,
        "prose_after": valid + " trailing prose",
        "multiple": valid + valid,
    }[scenario]
    with pytest.raises(ManualReasoningError, match=message):
        ManualCopilotReasoningProvider().complete(_safe_request(), pasted)


def test_request_id_mismatch_is_rejected() -> None:
    response = _response_payload()
    response["request_id"] = "wrong-request"

    with pytest.raises(ReasoningValidationError, match="must match"):
        ManualCopilotReasoningProvider().complete(_safe_request(), json.dumps(response))


def test_provider_mismatch_is_rejected() -> None:
    response = _response_payload()
    response["provider"] = "deterministic"

    with pytest.raises(ManualReasoningError, match="github-copilot-manual"):
        ManualCopilotReasoningProvider().complete(_safe_request(), json.dumps(response))


def test_invalid_status_is_rejected() -> None:
    response = _response_payload()
    response["status"] = "pending"

    with pytest.raises(ReasoningValidationError, match="status"):
        ManualCopilotReasoningProvider().complete(_safe_request(), json.dumps(response))


def test_invalid_decision_structure_is_rejected() -> None:
    response = _response_payload()
    response["decisions"] = [{"value": {"action": "inspect"}}]

    with pytest.raises(ReasoningValidationError, match="decision_type"):
        ManualCopilotReasoningProvider().complete(_safe_request(), json.dumps(response))


def test_fake_manual_channel_can_be_injected() -> None:
    channel = FakeManualChannel(_response_json())
    provider = ManualCopilotReasoningProvider(channel)

    response = provider.reason(_safe_request())

    assert response.request_id == "request-1"
    assert isinstance(channel.package, ManualPromptPackage)
    assert channel.package.request_id == "request-1"


def test_provider_without_channel_requires_two_phase_api() -> None:
    with pytest.raises(ManualReasoningError, match="prepare.*complete"):
        ManualCopilotReasoningProvider().reason(_safe_request())


def _safe_request():
    return DeterministicReasoningScrubber().scrub(_scrub_input()).request


def _scrub_input(metadata=None) -> ScrubInput:
    return ScrubInput(
        request_id="request-1",
        workflow_id="workflow-1",
        task_type="analyze",
        provider_hint="github-copilot-manual",
        product_id="demo",
        artifact_version="1",
        constraints={"return_json_only": True},
        metadata=metadata or {"source": "unit-test"},
    )


def _response_payload():
    return {
        "request_id": "request-1",
        "provider": "github-copilot-manual",
        "model": "copilot-model-selected-by-human",
        "status": ReasoningStatus.COMPLETED.value,
        "decisions": [
            {
                "decision_type": "recommendation",
                "value": {"action": "inspect"},
                "reason_summary": "Evidence supports inspection",
                "evidence_ids": [],
                "confidence": 0.8,
            }
        ],
        "confidence": 0.8,
        "warnings": [],
        "metadata": {"transport": "manual"},
    }


def _response_json() -> str:
    return json.dumps(_response_payload(), sort_keys=True)
