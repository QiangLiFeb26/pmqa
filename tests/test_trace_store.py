"""Offline tests for provider-independent SQLite reasoning traces."""

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pytest

from pmqa.cli import main
from pmqa.reasoning import (
    ReasoningDecision,
    ReasoningRequest,
    ReasoningResponse,
    ReasoningStatus,
)
from pmqa.trace import (
    SQLiteTraceStore,
    TraceDataError,
    TraceDuplicateError,
    TraceNotFoundError,
    TraceRecord,
    TraceStore,
    TraceStoreError,
)


def test_database_and_schema_are_created(tmp_path: Path) -> None:
    database = tmp_path / "traces.sqlite3"

    with SQLiteTraceStore(database):
        pass

    with sqlite3.connect(str(database)) as connection:
        columns = connection.execute("PRAGMA table_info(reasoning_traces)").fetchall()
    assert [column[1] for column in columns] == [
        "trace_id",
        "request_id",
        "provider",
        "model",
        "status",
        "request_hash",
        "request_json",
        "response_json",
        "created_at",
        "metadata_json",
    ]


def test_unavailable_database_has_focused_error(tmp_path: Path) -> None:
    database = tmp_path / "missing-parent" / "traces.sqlite3"

    with pytest.raises(TraceStoreError, match="Unable to initialize trace database"):
        SQLiteTraceStore(database)


def test_trace_round_trip_preserves_typed_exchange(tmp_path: Path) -> None:
    trace = _trace("trace-1")

    with SQLiteTraceStore(tmp_path / "traces.sqlite3") as store:
        store.save_trace(trace)
        restored = store.get_trace(trace.trace_id)

    assert restored == trace
    assert restored.reasoning_request() == _request()
    assert restored.reasoning_response() == _response()
    assert json.loads(restored.request_json)["request_id"] == "request-1"


def test_list_recent_orders_newest_first_and_honors_limit(tmp_path: Path) -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    traces = [
        _trace("trace-1", created_at=start),
        _trace("trace-2", created_at=start + timedelta(seconds=1)),
        _trace("trace-3", created_at=start + timedelta(seconds=2)),
    ]

    with SQLiteTraceStore(tmp_path / "traces.sqlite3") as store:
        for trace in traces:
            store.save_trace(trace)
        recent = store.list_recent(limit=2)

    assert [trace.trace_id for trace in recent] == ["trace-3", "trace-2"]


def test_find_by_request_filters_and_orders_traces(tmp_path: Path) -> None:
    first = _trace("trace-1")
    second = _trace("trace-2", created_at=first.created_at + timedelta(seconds=1))
    unrelated = _trace("trace-3", request=_request(request_id="another-request"))

    with SQLiteTraceStore(tmp_path / "traces.sqlite3") as store:
        for trace in (first, second, unrelated):
            store.save_trace(trace)
        found = store.find_by_request("request-1")

    assert [trace.trace_id for trace in found] == ["trace-2", "trace-1"]


def test_duplicate_trace_id_is_rejected(tmp_path: Path) -> None:
    trace = _trace("trace-1")

    with SQLiteTraceStore(tmp_path / "traces.sqlite3") as store:
        store.save_trace(trace)
        with pytest.raises(TraceDuplicateError, match="already exists"):
            store.save_trace(trace)


def test_missing_and_empty_queries_have_explicit_results(tmp_path: Path) -> None:
    with SQLiteTraceStore(tmp_path / "traces.sqlite3") as store:
        assert store.list_recent() == []
        assert store.find_by_request("missing-request") == []
        with pytest.raises(TraceNotFoundError, match="was not found"):
            store.get_trace("missing-trace")


def test_malformed_persisted_json_is_rejected(tmp_path: Path) -> None:
    database = tmp_path / "traces.sqlite3"
    store = SQLiteTraceStore(database)
    with sqlite3.connect(str(database)) as connection:
        connection.execute(
            """
            INSERT INTO reasoning_traces VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "broken-trace",
                "request-1",
                "deterministic",
                "rules-v1",
                "completed",
                "0" * 64,
                "{not-json",
                _response().model_dump_json(),
                datetime.now(timezone.utc).isoformat(),
                "{}",
            ),
        )
        connection.commit()

    with pytest.raises(TraceDataError, match="broken-trace"):
        store.get_trace("broken-trace")
    store.close()


@pytest.mark.parametrize("provider", ["deterministic", "github-copilot-manual", "future-llm"])
def test_store_is_provider_independent(tmp_path: Path, provider: str) -> None:
    response = _response(provider=provider)
    trace = _trace(f"trace-{provider}", response=response)

    with SQLiteTraceStore(tmp_path / f"{provider}.sqlite3") as store:
        assert isinstance(store, TraceStore)
        store.save_trace(trace)
        assert store.get_trace(trace.trace_id).provider == provider


def test_trace_demo_saves_and_prints_summary(tmp_path: Path, capsys) -> None:
    database = tmp_path / "demo.sqlite3"

    assert main(["trace-demo", "--database", str(database)]) == 0

    output = capsys.readouterr().out
    assert "trace_id=trace-demo-" in output
    assert "provider=trace-demo status=completed" in output
    with SQLiteTraceStore(database) as store:
        assert len(store.list_recent()) == 1


def _request(request_id: str = "request-1") -> ReasoningRequest:
    return ReasoningRequest(
        request_id=request_id,
        workflow_id="workflow-1",
        task_type="offline-test",
        provider_hint=None,
        product_id="demo",
        artifact_version="1",
        constraints={"offline": True},
        metadata={"source": "unit-test"},
    )


def _response(
    request_id: str = "request-1", provider: str = "deterministic"
) -> ReasoningResponse:
    return ReasoningResponse(
        request_id=request_id,
        provider=provider,
        model="rules-v1",
        status=ReasoningStatus.COMPLETED,
        decisions=[
            ReasoningDecision(
                decision_type="acknowledge",
                value={"workflow_id": "workflow-1"},
                confidence=1.0,
            )
        ],
    )


def _trace(
    trace_id: str,
    request: Optional[ReasoningRequest] = None,
    response: Optional[ReasoningResponse] = None,
    created_at: Optional[datetime] = None,
) -> TraceRecord:
    request = _request() if request is None else request
    response = _response(request_id=request.request_id) if response is None else response
    return TraceRecord.from_exchange(
        trace_id=trace_id,
        request=request,
        response=response,
        created_at=created_at or datetime(2026, 1, 1, tzinfo=timezone.utc),
        metadata={"run": "test"},
    )
