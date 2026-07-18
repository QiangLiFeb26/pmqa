"""Offline integration tests for the completed Task 3 reasoning flow."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from pmqa.cli import main
from pmqa.reasoning import (
    DeterministicReasoningProvider,
    ManualCopilotReasoningProvider,
    PreparedManualReasoning,
    ReasoningDecision,
    ReasoningExecutionError,
    ReasoningExecutionResult,
    ReasoningExecutionService,
    ReasoningProvider,
    ReasoningRequest,
    ReasoningResponse,
    ReasoningStatus,
    ReasoningValidationError,
    ScrubInput,
)
from pmqa.trace import SQLiteTraceStore, TraceStore


class FakeProvider(ReasoningProvider):
    """Returns controlled canonical responses without external access."""

    provider_name = "fake-provider"

    def _reason(self, request: ReasoningRequest) -> ReasoningResponse:
        return _response(request.request_id, self.provider_name)


class MismatchedRequestProvider(FakeProvider):
    """Returns an invalid request correlation for persistence tests."""

    def _reason(self, request: ReasoningRequest) -> ReasoningResponse:
        return _response("wrong-request", self.provider_name)


class MismatchedProvider(FakeProvider):
    """Returns an invalid provider identity for persistence tests."""

    def _reason(self, request: ReasoningRequest) -> ReasoningResponse:
        return _response(request.request_id, "another-provider")


class MalformedProvider(FakeProvider):
    """Returns a malformed response object for validation tests."""

    def _reason(self, request: ReasoningRequest):
        return {"request_id": request.request_id}


class RecordingTraceStore(TraceStore):
    """Records persistence calls without introducing database behavior."""

    def __init__(self) -> None:
        self.saved = []

    def save_trace(self, trace) -> None:
        self.saved.append(trace)

    def get_trace(self, trace_id):
        raise NotImplementedError

    def find_by_request(self, request_id):
        return []

    def list_recent(self, limit=20):
        return list(reversed(self.saved[-limit:]))


def test_automated_execution_scrubs_builds_and_persists(tmp_path: Path) -> None:
    with SQLiteTraceStore(tmp_path / "traces.sqlite3") as store:
        result = _service(store).execute(
            scrub_input=_unsafe_input(), provider=FakeProvider()
        )
        saved = store.list_recent()

    assert isinstance(result, ReasoningExecutionResult)
    assert result.request.metadata == {
        "note": "Bearer [REDACTED]",
        "safe": "retained",
    }
    serialized_package = result.prompt_package.model_dump_json()
    assert "private-token" not in serialized_package
    assert "secret-password" not in serialized_package
    assert result.response.provider == "fake-provider"
    assert saved == [result.trace]
    assert result.trace.metadata["package_id"] == result.prompt_package.package_id
    assert result.trace.metadata["prompt_hash"] == result.prompt_package.prompt_hash


def test_manual_prepare_complete_uses_same_package_and_saves_once(
    tmp_path: Path,
) -> None:
    provider = ManualCopilotReasoningProvider()
    with SQLiteTraceStore(tmp_path / "traces.sqlite3") as store:
        service = _service(store)
        prepared = service.prepare_manual(
            scrub_input=_unsafe_input(), provider=provider
        )
        assert isinstance(prepared, PreparedManualReasoning)
        assert store.list_recent() == []

        raw_response = _response(
            prepared.request.request_id, "github-copilot-manual"
        ).model_dump_json()
        result = service.complete_manual(
            prepared=prepared,
            raw_response=raw_response,
            provider=provider,
        )
        saved = store.list_recent()

    assert result.prompt_package is prepared.prompt_package
    assert result.trace.metadata["execution_mode"] == "manual"
    assert saved == [result.trace]


@pytest.mark.parametrize(
    ("provider", "error_type", "message"),
    [
        (MismatchedRequestProvider(), ReasoningValidationError, "must match"),
        (MismatchedProvider(), ReasoningExecutionError, "provider"),
        (MalformedProvider(), ReasoningValidationError, "Invalid reasoning response"),
    ],
)
def test_invalid_automated_response_is_not_persisted(
    provider, error_type, message
) -> None:
    store = RecordingTraceStore()

    with pytest.raises(error_type, match=message):
        _service(store).execute(scrub_input=_unsafe_input(), provider=provider)

    assert store.saved == []


def test_manual_malformed_response_is_not_persisted() -> None:
    store = RecordingTraceStore()
    provider = ManualCopilotReasoningProvider()
    service = _service(store)
    prepared = service.prepare_manual(scrub_input=_unsafe_input(), provider=provider)

    with pytest.raises(ValueError, match="invalid JSON"):
        service.complete_manual(
            prepared=prepared,
            raw_response="{not-json",
            provider=provider,
        )

    assert store.saved == []


def test_deterministic_provider_executes_without_copilot_or_terminal() -> None:
    store = RecordingTraceStore()

    result = _service(store).execute(
        scrub_input=_unsafe_input(),
        provider=DeterministicReasoningProvider(),
    )

    assert result.response.provider == "deterministic"
    assert len(store.saved) == 1


def test_task3_demo_runs_complete_offline_flow(
    tmp_path: Path, capsys
) -> None:
    database = tmp_path / "task3.sqlite3"

    assert main(["task3-demo", "--database", str(database)]) == 0

    output = capsys.readouterr().out
    assert "package_id=" in output
    assert "provider=deterministic status=completed" in output
    with SQLiteTraceStore(database) as store:
        assert len(store.list_recent()) == 1


def _service(store: TraceStore) -> ReasoningExecutionService:
    return ReasoningExecutionService(
        trace_store=store,
        clock=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc),
        trace_id_factory=lambda: "trace-1",
    )


def _unsafe_input() -> ScrubInput:
    return ScrubInput(
        request_id="request-1",
        workflow_id="workflow-1",
        task_type="offline-test",
        provider_hint=None,
        product_id="demo",
        artifact_version="1",
        constraints={"offline": True, "password": "secret-password"},
        metadata={
            "safe": "retained",
            "token": "private-token",
            "note": "Bearer private-token",
        },
    )


def _response(request_id: str, provider: str) -> ReasoningResponse:
    return ReasoningResponse(
        request_id=request_id,
        provider=provider,
        model="fake-v1",
        status=ReasoningStatus.COMPLETED,
        decisions=[
            ReasoningDecision(
                decision_type="acknowledge",
                value={"safe": True},
                confidence=1.0,
            )
        ],
    )
