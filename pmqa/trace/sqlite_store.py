"""SQLite implementation of the provider-independent trace store."""

import json
import sqlite3
from pathlib import Path
from typing import Any, List, Mapping, Union

from pydantic import ValidationError

from pmqa.reasoning.validation import (
    ReasoningValidationError,
    validate_reasoning_exchange,
)
from pmqa.trace.models import TraceRecord
from pmqa.trace.store import (
    TraceDataError,
    TraceDuplicateError,
    TraceNotFoundError,
    TraceStore,
    TraceStoreError,
)
from pmqa.utils.hashing import canonical_json, canonical_json_sha256


class SQLiteTraceStore(TraceStore):
    """Persists reasoning traces through one built-in SQLite connection."""

    def __init__(self, database: Union[str, Path]) -> None:
        self._database = str(database)
        try:
            self._connection = sqlite3.connect(self._database)
            self._connection.row_factory = sqlite3.Row
            self._create_schema()
        except sqlite3.Error as error:
            raise TraceStoreError(
                f"Unable to initialize trace database {self._database!r}: {error}"
            ) from error

    def close(self) -> None:
        """Close the underlying SQLite connection."""

        self._connection.close()

    def __enter__(self) -> "SQLiteTraceStore":
        """Return this store for context-managed use."""

        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        """Close the store when leaving a context manager."""

        self.close()

    def save_trace(self, trace: TraceRecord) -> None:
        """Persist a validated trace without overwriting duplicates."""

        validated = self._validate_record(trace)
        try:
            with self._connection:
                self._connection.execute(
                    """
                    INSERT INTO reasoning_traces (
                        trace_id, request_id, provider, model, status,
                        request_hash, request_json, response_json,
                        created_at, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        validated.trace_id,
                        validated.request_id,
                        validated.provider,
                        validated.model,
                        validated.status.value,
                        validated.request_hash,
                        validated.request_json,
                        validated.response_json,
                        validated.created_at.isoformat(),
                        canonical_json(validated.metadata),
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise TraceDuplicateError(
                f"Trace {trace.trace_id!r} already exists"
            ) from error
        except sqlite3.Error as error:
            raise TraceStoreError(
                f"Unable to save trace {trace.trace_id!r}: {error}"
            ) from error

    def get_trace(self, trace_id: str) -> TraceRecord:
        """Return one trace or raise a focused missing-record error."""

        row = self._query_one(
            "SELECT * FROM reasoning_traces WHERE trace_id = ?", (trace_id,)
        )
        if row is None:
            raise TraceNotFoundError(f"Trace {trace_id!r} was not found")
        return self._row_to_record(row)

    def find_by_request(self, request_id: str) -> List[TraceRecord]:
        """Return traces for a request in deterministic newest-first order."""

        return self._query_many(
            """
            SELECT * FROM reasoning_traces
            WHERE request_id = ?
            ORDER BY created_at DESC, trace_id DESC
            """,
            (request_id,),
        )

    def list_recent(self, limit: int = 20) -> List[TraceRecord]:
        """Return at most ``limit`` traces in newest-first order."""

        if limit < 1:
            raise ValueError("limit must be at least 1")
        return self._query_many(
            """
            SELECT * FROM reasoning_traces
            ORDER BY created_at DESC, trace_id DESC
            LIMIT ?
            """,
            (limit,),
        )

    def _create_schema(self) -> None:
        with self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS reasoning_traces (
                    trace_id TEXT PRIMARY KEY NOT NULL,
                    request_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    status TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                )
                """
            )

    def _query_one(self, sql: str, parameters: tuple) -> Any:
        try:
            return self._connection.execute(sql, parameters).fetchone()
        except sqlite3.Error as error:
            raise TraceStoreError(f"Unable to read trace database: {error}") from error

    def _query_many(self, sql: str, parameters: tuple) -> List[TraceRecord]:
        try:
            rows = self._connection.execute(sql, parameters).fetchall()
        except sqlite3.Error as error:
            raise TraceStoreError(f"Unable to read trace database: {error}") from error
        return [self._row_to_record(row) for row in rows]

    def _row_to_record(self, row: Mapping[str, Any]) -> TraceRecord:
        trace_id = row["trace_id"]
        try:
            metadata = json.loads(row["metadata_json"])
            if not isinstance(metadata, dict):
                raise ValueError("metadata_json must decode to an object")
            record = TraceRecord(
                trace_id=trace_id,
                request_id=row["request_id"],
                provider=row["provider"],
                model=row["model"],
                status=row["status"],
                request_hash=row["request_hash"],
                request_json=row["request_json"],
                response_json=row["response_json"],
                created_at=row["created_at"],
                metadata=metadata,
            )
            return self._validate_record(record)
        except (
            json.JSONDecodeError,
            ReasoningValidationError,
            ValidationError,
            ValueError,
        ) as error:
            raise TraceDataError(
                f"Trace {trace_id!r} contains malformed or inconsistent data: {error}"
            ) from error

    @staticmethod
    def _validate_record(trace: TraceRecord) -> TraceRecord:
        try:
            request_data = json.loads(trace.request_json)
            response_data = json.loads(trace.response_json)
            request, response = validate_reasoning_exchange(request_data, response_data)
            if trace.request_json != canonical_json(request_data):
                raise ValueError("request_json is not canonical JSON")
            if trace.response_json != canonical_json(response_data):
                raise ValueError("response_json is not canonical JSON")
            if trace.request_id != request.request_id:
                raise ValueError("request_id does not match request_json")
            if trace.provider != response.provider:
                raise ValueError("provider does not match response_json")
            if trace.model != response.model:
                raise ValueError("model does not match response_json")
            if trace.status != response.status:
                raise ValueError("status does not match response_json")
            if trace.request_hash != canonical_json_sha256(request_data):
                raise ValueError("request_hash does not match request_json")
            canonical_json(trace.metadata)
            return trace
        except (json.JSONDecodeError, ReasoningValidationError, TypeError, ValueError) as error:
            raise TraceDataError(
                f"Trace {trace.trace_id!r} is invalid: {error}"
            ) from error
