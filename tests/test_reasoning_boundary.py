"""Regression tests for the canonical reasoning trust-boundary policy."""

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from pmqa.models import Element, Lifecycle
from pmqa.reasoning import (
    CliExecutionResult,
    CopilotCliConfig,
    CopilotCliReasoningProvider,
    CopilotCliRunner,
    DeterministicReasoningScrubber,
    ManualCopilotReasoningProvider,
    ManualPromptPackage,
    ManualReasoningChannel,
    PromptPackageBuilder,
    ReasoningDecision,
    ReasoningRequest,
    ReasoningResponse,
    ReasoningStatus,
    ReasoningValidationError,
    ScrubInput,
    validate_reasoning_request,
)
from pmqa.reasoning.boundary_policy import PROHIBITED_REASONING_KEYS
from pmqa.trace import SQLiteTraceStore, TraceRecord


class RecordingManualChannel(ManualReasoningChannel):
    """Records whether an unsafe request reached manual presentation."""

    def __init__(self) -> None:
        self.presented = None

    def present_prompt(self, package: ManualPromptPackage) -> None:
        self.presented = package

    def receive_response(self) -> str:
        raise AssertionError("unsafe requests must not request terminal input")


class RecordingCliRunner(CopilotCliRunner):
    """Records whether an unsafe request reached CLI transport."""

    def __init__(self) -> None:
        self.prompt = None

    def is_available(self, executable: str) -> bool:
        return True

    def run(self, *, command, prompt, timeout_seconds) -> CliExecutionResult:
        self.prompt = prompt
        raise AssertionError("unsafe requests must not reach CLI stdin")


@pytest.mark.parametrize("prohibited_key", sorted(PROHIBITED_REASONING_KEYS))
def test_shared_policy_is_enforced_by_scrubber_and_validator(
    prohibited_key: str,
) -> None:
    scrubbed = DeterministicReasoningScrubber().scrub(
        _scrub_input(metadata={prohibited_key: "boundary-marker"})
    )

    assert prohibited_key not in scrubbed.request.metadata
    with pytest.raises(ReasoningValidationError, match=f"metadata.{prohibited_key}"):
        validate_reasoning_request(
            _request().model_copy(
                update={"metadata": {prohibited_key: "boundary-marker"}}
            )
        )


@pytest.mark.parametrize(
    ("location", "expected_path"),
    [
        ("metadata", "request.metadata.secret"),
        ("constraints", "request.constraints.secret"),
        ("nested_dict", "request.metadata.outer.secret"),
        ("nested_list", "request.constraints.items[0].secret"),
        ("element_attributes", "request.elements[0].attributes.secret"),
    ],
)
def test_prohibited_keys_are_rejected_in_every_freeform_location(
    location: str, expected_path: str
) -> None:
    with pytest.raises(ReasoningValidationError) as captured:
        validate_reasoning_request(_unsafe_request(location, "secret"))

    assert expected_path in str(captured.value)


@pytest.mark.parametrize(
    "prohibited_key",
    ["secret", "api_key", "authorization", "refresh_token"],
)
def test_previously_drifted_keys_are_rejected(prohibited_key: str) -> None:
    with pytest.raises(ReasoningValidationError, match=prohibited_key):
        validate_reasoning_request(_unsafe_request("nested_list", prohibited_key))


@pytest.mark.parametrize(
    "safe_key", ["session_label", "tokenizer", "password_hint", "runtime_note"]
)
def test_similarly_named_safe_fields_are_not_rejected(safe_key: str) -> None:
    request = _request().model_copy(update={"metadata": {safe_key: "safe"}})

    assert validate_reasoning_request(request).metadata == {safe_key: "safe"}


def test_separator_and_case_variants_use_the_same_policy() -> None:
    request = _request().model_copy(
        update={"metadata": {"ACCESS-TOKEN": "boundary-marker"}}
    )

    with pytest.raises(ReasoningValidationError, match="ACCESS-TOKEN"):
        validate_reasoning_request(request)


def test_direct_unsafe_request_cannot_build_prompt_or_reach_manual_channel() -> None:
    secret_value = "manual-boundary-secret"
    request = _request().model_copy(
        update={"metadata": {"authorization": secret_value}}
    )
    channel = RecordingManualChannel()

    with pytest.raises(ReasoningValidationError) as prompt_error:
        PromptPackageBuilder().build(request=request, provider="test")
    with pytest.raises(ReasoningValidationError) as manual_error:
        ManualCopilotReasoningProvider(channel).reason(request)

    assert channel.presented is None
    assert secret_value not in str(prompt_error.value)
    assert secret_value not in str(manual_error.value)


def test_direct_unsafe_request_cannot_reach_cli_stdin() -> None:
    runner = RecordingCliRunner()
    provider = CopilotCliReasoningProvider(
        CopilotCliConfig(executable="copilot"), runner
    )
    request = _request().model_copy(
        update={"constraints": {"refresh_token": "cli-boundary-secret"}}
    )

    with pytest.raises(ReasoningValidationError) as captured:
        provider.reason(request)

    assert runner.prompt is None
    assert "cli-boundary-secret" not in str(captured.value)


def test_direct_unsafe_request_cannot_be_persisted(tmp_path: Path) -> None:
    request = _request().model_copy(
        update={"metadata": {"api_key": "trace-boundary-secret"}}
    )
    response = _response(request.request_id)
    database = tmp_path / "traces.sqlite3"

    with SQLiteTraceStore(database) as store:
        with pytest.raises(ReasoningValidationError) as captured:
            TraceRecord.from_exchange(
                trace_id="unsafe-trace",
                request=request,
                response=response,
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        assert store.list_recent() == []

    assert "trace-boundary-secret" not in str(captured.value)


def _unsafe_request(location: str, key: str) -> ReasoningRequest:
    request = _request()
    if location == "metadata":
        return request.model_copy(update={"metadata": {key: "boundary-marker"}})
    if location == "constraints":
        return request.model_copy(update={"constraints": {key: "boundary-marker"}})
    if location == "nested_dict":
        return request.model_copy(
            update={"metadata": {"outer": {key: "boundary-marker"}}}
        )
    if location == "nested_list":
        return request.model_copy(
            update={"constraints": {"items": [{key: "boundary-marker"}]}}
        )
    element = replace(
        request.elements[0], attributes={key: "boundary-marker"}
    )
    return request.model_copy(update={"elements": [element]})


def _request() -> ReasoningRequest:
    element = Element(
        "element.login",
        Lifecycle(),
        "page.login",
        "button",
        "Login",
        attributes={"data-test": "login-button"},
    )
    return ReasoningRequest(
        request_id="request-1",
        workflow_id="workflow-1",
        task_type="offline-test",
        product_id="demo",
        artifact_version="1",
        elements=[element],
    )


def _scrub_input(metadata=None) -> ScrubInput:
    return ScrubInput(
        request_id="request-1",
        workflow_id="workflow-1",
        task_type="offline-test",
        product_id="demo",
        artifact_version="1",
        metadata=metadata or {},
    )


def _response(request_id: str) -> ReasoningResponse:
    return ReasoningResponse(
        request_id=request_id,
        provider="deterministic",
        model="rules-v1",
        status=ReasoningStatus.COMPLETED,
        decisions=[ReasoningDecision(decision_type="acknowledge")],
    )
