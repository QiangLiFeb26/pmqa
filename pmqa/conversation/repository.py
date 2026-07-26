"""Provider-neutral conversation repositories with deterministic transitions."""

from __future__ import annotations

from enum import Enum
from functools import wraps
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any, Dict, Optional, Protocol, Tuple, runtime_checkable

from pmqa.conversation.contracts import (
    DEFAULT_CONVERSATION_LIST_LIMIT,
    MAX_CONVERSATION_LIST_LIMIT,
    ConversationContractValidationError,
    ConversationRetentionPolicy,
    ConversationSession,
    ConversationSessionStatus,
    ConversationTurn,
    ConversationTurnStatus,
    validate_conversation_list_limit,
    validate_conversation_timestamp,
)
from pmqa.run import validate_run_identifier


CONVERSATION_REPOSITORY_SCHEMA_NAME = "pmqa.conversation"
CONVERSATION_REPOSITORY_SCHEMA_VERSION = 1
MAX_CONVERSATION_RECORD_BYTES = 128 * 1024

_RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS = (
    MemoryError,
    KeyboardInterrupt,
    SystemExit,
    GeneratorExit,
)


class ConversationRepositoryErrorCode(str, Enum):
    """Stable safe repository failure classifications."""

    INVALID_REQUEST = "invalid_request"
    NOT_FOUND = "not_found"
    DUPLICATE = "duplicate"
    REVISION_CONFLICT = "revision_conflict"
    STATE_CONFLICT = "state_conflict"
    CORRUPT = "corrupt"
    SCHEMA_MISMATCH = "schema_mismatch"
    UNAVAILABLE = "unavailable"


_REPOSITORY_ERROR_MESSAGES = {
    ConversationRepositoryErrorCode.INVALID_REQUEST:
        "invalid conversation repository request",
    ConversationRepositoryErrorCode.NOT_FOUND:
        "conversation record was not found",
    ConversationRepositoryErrorCode.DUPLICATE:
        "conversation record already exists",
    ConversationRepositoryErrorCode.REVISION_CONFLICT:
        "conversation session revision conflict",
    ConversationRepositoryErrorCode.STATE_CONFLICT:
        "conversation state transition conflict",
    ConversationRepositoryErrorCode.CORRUPT:
        "conversation repository is corrupt",
    ConversationRepositoryErrorCode.SCHEMA_MISMATCH:
        "conversation repository schema is incompatible",
    ConversationRepositoryErrorCode.UNAVAILABLE:
        "conversation repository is unavailable",
}


class ConversationRepositoryError(RuntimeError):
    """Expose only a fixed repository code and safe message."""

    def __init__(self, code: ConversationRepositoryErrorCode) -> None:
        if type(code) is not ConversationRepositoryErrorCode:
            raise TypeError("code must be a ConversationRepositoryErrorCode")
        self.code = code
        super().__init__(_REPOSITORY_ERROR_MESSAGES[code])


def _safe_repository_method(method):
    @wraps(method)
    def boundary(*args, **kwargs):
        failure = None
        try:
            return method(*args, **kwargs)
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except ConversationRepositoryError as error:
            failure = error.code
        if failure is not None:
            _raise_repository_error(failure)

    return boundary


def _safe_repository_class(cls):
    for name in (
        "__init__",
        "create_session",
        "get_session",
        "list_sessions",
        "get_turn",
        "list_turns",
        "append_turn",
        "replace_turn",
        "close_session",
        "delete_session",
        "purge_expired",
    ):
        if name in cls.__dict__:
            setattr(cls, name, _safe_repository_method(getattr(cls, name)))
    return cls


@runtime_checkable
class ConversationRepository(Protocol):
    """Synchronous canonical conversation persistence boundary."""

    def create_session(self, session: ConversationSession) -> None:
        ...

    def get_session(self, session_id: str) -> ConversationSession:
        ...

    def list_sessions(
        self,
        limit: int = DEFAULT_CONVERSATION_LIST_LIMIT,
    ) -> Tuple[ConversationSession, ...]:
        ...

    def get_turn(self, turn_id: str) -> ConversationTurn:
        ...

    def list_turns(
        self,
        session_id: str,
        limit: int = DEFAULT_CONVERSATION_LIST_LIMIT,
    ) -> Tuple[ConversationTurn, ...]:
        ...

    def append_turn(
        self,
        *,
        expected_revision: int,
        session: ConversationSession,
        turn: ConversationTurn,
    ) -> None:
        ...

    def replace_turn(
        self,
        *,
        expected_revision: int,
        session: ConversationSession,
        turn: ConversationTurn,
    ) -> None:
        ...

    def close_session(
        self,
        *,
        expected_revision: int,
        session: ConversationSession,
    ) -> None:
        ...

    def delete_session(self, session_id: str) -> None:
        ...

    def purge_expired(
        self,
        cutoff: Any,
        limit: int = MAX_CONVERSATION_LIST_LIMIT,
    ) -> Tuple[str, ...]:
        ...


@_safe_repository_class
class InMemoryConversationRepository:
    """Deterministic process-local canonical repository."""

    __slots__ = ("_lock", "_sessions", "_turns")

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._turns: Dict[str, Dict[str, Any]] = {}

    def create_session(self, session: ConversationSession) -> None:
        canonical = _canonical_session(session)
        if canonical.revision != 1 or canonical.turn_ids:
            _raise_repository_error(
                ConversationRepositoryErrorCode.INVALID_REQUEST
            )
        with self._lock:
            if canonical.session_id in self._sessions:
                _raise_repository_error(
                    ConversationRepositoryErrorCode.DUPLICATE
                )
            self._sessions[canonical.session_id] = canonical.to_dict()

    def get_session(self, session_id: str) -> ConversationSession:
        canonical_id = _canonical_identifier(session_id)
        with self._lock:
            wire = self._sessions.get(canonical_id)
            if wire is None:
                _raise_repository_error(
                    ConversationRepositoryErrorCode.NOT_FOUND
                )
            session = _session_from_wire(wire)
            self._validate_stored_turn_index(session)
            return session

    def list_sessions(
        self,
        limit: int = DEFAULT_CONVERSATION_LIST_LIMIT,
    ) -> Tuple[ConversationSession, ...]:
        canonical_limit = _canonical_limit(limit)
        with self._lock:
            sessions = []
            for wire in self._sessions.values():
                session = _session_from_wire(wire)
                self._validate_stored_turn_index(session)
                sessions.append(session)
            sessions = tuple(sessions)
        by_identifier = sorted(sessions, key=lambda item: item.session_id)
        return tuple(
            sorted(
                by_identifier,
                key=lambda item: item.updated_at,
                reverse=True,
            )[:canonical_limit]
        )

    def get_turn(self, turn_id: str) -> ConversationTurn:
        canonical_id = _canonical_identifier(turn_id)
        with self._lock:
            wire = self._turns.get(canonical_id)
            if wire is None:
                _raise_repository_error(
                    ConversationRepositoryErrorCode.NOT_FOUND
                )
            turn = _turn_from_wire(wire)
            session = self._stored_session(turn.session_id)
            _validate_turn_membership(session, turn)
            return turn

    def list_turns(
        self,
        session_id: str,
        limit: int = DEFAULT_CONVERSATION_LIST_LIMIT,
    ) -> Tuple[ConversationTurn, ...]:
        canonical_id = _canonical_identifier(session_id)
        canonical_limit = _canonical_limit(limit)
        with self._lock:
            session = self._stored_session(canonical_id)
            self._validate_stored_turn_index(session)
            return tuple(
                _turn_from_wire(self._turns[turn_id])
                for turn_id in session.turn_ids[:canonical_limit]
            )

    def append_turn(
        self,
        *,
        expected_revision: int,
        session: ConversationSession,
        turn: ConversationTurn,
    ) -> None:
        canonical_session = _canonical_session(session)
        canonical_turn = _canonical_turn(turn)
        canonical_revision = _canonical_revision(expected_revision)
        with self._lock:
            current = self._stored_session(canonical_session.session_id)
            if canonical_turn.turn_id in self._turns:
                _raise_repository_error(
                    ConversationRepositoryErrorCode.DUPLICATE
                )
            _validate_append_transition(
                current,
                canonical_revision,
                canonical_session,
                canonical_turn,
            )
            self._sessions[canonical_session.session_id] = (
                canonical_session.to_dict()
            )
            self._turns[canonical_turn.turn_id] = canonical_turn.to_dict()

    def replace_turn(
        self,
        *,
        expected_revision: int,
        session: ConversationSession,
        turn: ConversationTurn,
    ) -> None:
        canonical_session = _canonical_session(session)
        canonical_turn = _canonical_turn(turn)
        canonical_revision = _canonical_revision(expected_revision)
        with self._lock:
            current_session = self._stored_session(
                canonical_session.session_id
            )
            current_turn = self._stored_turn(canonical_turn.turn_id)
            _validate_replace_turn_transition(
                current_session,
                current_turn,
                canonical_revision,
                canonical_session,
                canonical_turn,
            )
            self._sessions[canonical_session.session_id] = (
                canonical_session.to_dict()
            )
            self._turns[canonical_turn.turn_id] = canonical_turn.to_dict()

    def close_session(
        self,
        *,
        expected_revision: int,
        session: ConversationSession,
    ) -> None:
        canonical_session = _canonical_session(session)
        canonical_revision = _canonical_revision(expected_revision)
        with self._lock:
            current = self._stored_session(canonical_session.session_id)
            turns = tuple(
                _turn_from_wire(self._turns[turn_id])
                for turn_id in current.turn_ids
            )
            _validate_close_transition(
                current,
                turns,
                canonical_revision,
                canonical_session,
            )
            self._sessions[canonical_session.session_id] = (
                canonical_session.to_dict()
            )

    def delete_session(self, session_id: str) -> None:
        canonical_id = _canonical_identifier(session_id)
        with self._lock:
            wire = self._sessions.get(canonical_id)
            if wire is None:
                _raise_repository_error(
                    ConversationRepositoryErrorCode.NOT_FOUND
                )
            session = _session_from_wire(wire)
            self._validate_stored_turn_index(session)
            del self._sessions[canonical_id]
            for turn_id in session.turn_ids:
                self._turns.pop(turn_id, None)

    def purge_expired(
        self,
        cutoff: Any,
        limit: int = MAX_CONVERSATION_LIST_LIMIT,
    ) -> Tuple[str, ...]:
        canonical_cutoff = _canonical_timestamp(cutoff)
        canonical_limit = _canonical_limit(limit)
        with self._lock:
            expired = sorted(
                (
                    session
                    for session in (
                        _session_from_wire(wire)
                        for wire in self._sessions.values()
                    )
                    if session.expires_at is not None
                    and session.expires_at <= canonical_cutoff
                ),
                key=lambda item: (item.expires_at, item.session_id),
            )[:canonical_limit]
            for session in expired:
                self._validate_stored_turn_index(session)
                del self._sessions[session.session_id]
                for turn_id in session.turn_ids:
                    self._turns.pop(turn_id, None)
        return tuple(session.session_id for session in expired)

    def _stored_session(self, session_id: str) -> ConversationSession:
        wire = self._sessions.get(session_id)
        if wire is None:
            _raise_repository_error(ConversationRepositoryErrorCode.NOT_FOUND)
        return _session_from_wire(wire)

    def _stored_turn(self, turn_id: str) -> ConversationTurn:
        wire = self._turns.get(turn_id)
        if wire is None:
            _raise_repository_error(ConversationRepositoryErrorCode.NOT_FOUND)
        return _turn_from_wire(wire)

    def _validate_stored_turn_index(
        self,
        session: ConversationSession,
    ) -> None:
        indexed = tuple(
            sorted(
                (
                    _turn_from_wire(wire)
                    for wire in self._turns.values()
                    if wire.get("session_id") == session.session_id
                ),
                key=lambda item: item.sequence_number,
            )
        )
        if (
            tuple(turn.turn_id for turn in indexed) != session.turn_ids
            or any(
                turn.sequence_number != index
                for index, turn in enumerate(indexed, start=1)
            )
        ):
            _raise_repository_error(
                ConversationRepositoryErrorCode.CORRUPT
            )


@_safe_repository_class
class SQLiteConversationRepository:
    """Explicit local SQLite repository for durable conversation policies."""

    __slots__ = ("_database_path", "_lock")

    def __init__(self, database_path: str) -> None:
        if (
            type(database_path) is not str
            or not database_path
            or not Path(database_path).is_absolute()
        ):
            _raise_repository_error(
                ConversationRepositoryErrorCode.INVALID_REQUEST
            )
        self._database_path = database_path
        self._lock = threading.RLock()
        self._initialize()

    def create_session(self, session: ConversationSession) -> None:
        canonical = _canonical_session(session)
        if (
            not canonical.retention_policy.durable
            or canonical.expires_at is None
            or canonical.revision != 1
            or canonical.turn_ids
        ):
            _raise_repository_error(
                ConversationRepositoryErrorCode.INVALID_REQUEST
            )
        with self._lock:
            connection = self._open()
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    INSERT INTO conversation_sessions(
                        session_id, revision, updated_at, expires_at, payload
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        canonical.session_id,
                        canonical.revision,
                        canonical.to_dict()["updated_at"],
                        canonical.to_dict()["expires_at"],
                        _encode_record(canonical.to_dict()),
                    ),
                )
                connection.commit()
            except sqlite3.IntegrityError:
                _rollback_quietly(connection)
                _raise_repository_error(
                    ConversationRepositoryErrorCode.DUPLICATE
                )
            except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
                _rollback_quietly(connection)
                raise
            except sqlite3.Error:
                _rollback_quietly(connection)
                _raise_repository_error(
                    ConversationRepositoryErrorCode.UNAVAILABLE
                )
            finally:
                _close_quietly(connection)

    def get_session(self, session_id: str) -> ConversationSession:
        canonical_id = _canonical_identifier(session_id)
        with self._lock:
            connection = self._open()
            try:
                row = connection.execute(
                    """
                    SELECT revision, updated_at, expires_at, payload
                    FROM conversation_sessions WHERE session_id = ?
                    """,
                    (canonical_id,),
                ).fetchone()
                if row is None:
                    _raise_repository_error(
                        ConversationRepositoryErrorCode.NOT_FOUND
                    )
                session = _session_from_row(canonical_id, row)
                self._validate_session_turn_index(connection, session)
                return session
            except ConversationRepositoryError:
                raise
            except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
                raise
            except sqlite3.Error:
                _raise_repository_error(
                    ConversationRepositoryErrorCode.UNAVAILABLE
                )
            finally:
                _close_quietly(connection)

    def list_sessions(
        self,
        limit: int = DEFAULT_CONVERSATION_LIST_LIMIT,
    ) -> Tuple[ConversationSession, ...]:
        canonical_limit = _canonical_limit(limit)
        with self._lock:
            connection = self._open()
            try:
                rows = connection.execute(
                    """
                    SELECT session_id, revision, updated_at, expires_at, payload
                    FROM conversation_sessions
                    ORDER BY updated_at DESC, session_id ASC
                    LIMIT ?
                    """,
                    (canonical_limit,),
                ).fetchall()
                sessions = []
                for row in rows:
                    session = _session_from_row(row[0], row[1:])
                    self._validate_session_turn_index(connection, session)
                    sessions.append(session)
                return tuple(sessions)
            except ConversationRepositoryError:
                raise
            except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
                raise
            except sqlite3.Error:
                _raise_repository_error(
                    ConversationRepositoryErrorCode.UNAVAILABLE
                )
            finally:
                _close_quietly(connection)

    def get_turn(self, turn_id: str) -> ConversationTurn:
        canonical_id = _canonical_identifier(turn_id)
        with self._lock:
            connection = self._open()
            try:
                row = connection.execute(
                    """
                    SELECT session_id, sequence_number, payload
                    FROM conversation_turns WHERE turn_id = ?
                    """,
                    (canonical_id,),
                ).fetchone()
                if row is None:
                    _raise_repository_error(
                        ConversationRepositoryErrorCode.NOT_FOUND
                    )
                turn = _turn_from_row(canonical_id, row)
                session = self._load_session(connection, turn.session_id)
                _validate_turn_membership(session, turn)
                return turn
            except ConversationRepositoryError:
                raise
            except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
                raise
            except sqlite3.Error:
                _raise_repository_error(
                    ConversationRepositoryErrorCode.UNAVAILABLE
                )
            finally:
                _close_quietly(connection)

    def list_turns(
        self,
        session_id: str,
        limit: int = DEFAULT_CONVERSATION_LIST_LIMIT,
    ) -> Tuple[ConversationTurn, ...]:
        canonical_id = _canonical_identifier(session_id)
        canonical_limit = _canonical_limit(limit)
        with self._lock:
            connection = self._open()
            try:
                session = self._load_session(connection, canonical_id)
                rows = connection.execute(
                    """
                    SELECT turn_id, sequence_number, payload
                    FROM conversation_turns
                    WHERE session_id = ?
                    ORDER BY sequence_number ASC
                    LIMIT ?
                    """,
                    (canonical_id, canonical_limit),
                ).fetchall()
                turns = tuple(
                    _turn_from_row(
                        row[0],
                        (canonical_id, row[1], row[2]),
                    )
                    for row in rows
                )
                if tuple(turn.turn_id for turn in turns) != (
                    session.turn_ids[:canonical_limit]
                ):
                    _raise_repository_error(
                        ConversationRepositoryErrorCode.CORRUPT
                    )
                return turns
            except ConversationRepositoryError:
                raise
            except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
                raise
            except sqlite3.Error:
                _raise_repository_error(
                    ConversationRepositoryErrorCode.UNAVAILABLE
                )
            finally:
                _close_quietly(connection)

    def append_turn(
        self,
        *,
        expected_revision: int,
        session: ConversationSession,
        turn: ConversationTurn,
    ) -> None:
        canonical_session = _canonical_session(session)
        canonical_turn = _canonical_turn(turn)
        canonical_revision = _canonical_revision(expected_revision)
        self._write_transition(
            canonical_session,
            canonical_turn,
            canonical_revision,
            append=True,
        )

    def replace_turn(
        self,
        *,
        expected_revision: int,
        session: ConversationSession,
        turn: ConversationTurn,
    ) -> None:
        canonical_session = _canonical_session(session)
        canonical_turn = _canonical_turn(turn)
        canonical_revision = _canonical_revision(expected_revision)
        self._write_transition(
            canonical_session,
            canonical_turn,
            canonical_revision,
            append=False,
        )

    def close_session(
        self,
        *,
        expected_revision: int,
        session: ConversationSession,
    ) -> None:
        canonical_session = _canonical_session(session)
        canonical_revision = _canonical_revision(expected_revision)
        with self._lock:
            connection = self._open()
            try:
                connection.execute("BEGIN IMMEDIATE")
                current = self._load_session(connection, canonical_session.session_id)
                turns = self._load_turns(connection, current.session_id)
                _validate_close_transition(
                    current,
                    turns,
                    canonical_revision,
                    canonical_session,
                )
                self._update_session(
                    connection,
                    canonical_revision,
                    canonical_session,
                )
                connection.commit()
            except ConversationRepositoryError:
                _rollback_quietly(connection)
                raise
            except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
                _rollback_quietly(connection)
                raise
            except sqlite3.Error:
                _rollback_quietly(connection)
                _raise_repository_error(
                    ConversationRepositoryErrorCode.UNAVAILABLE
                )
            finally:
                _close_quietly(connection)

    def delete_session(self, session_id: str) -> None:
        canonical_id = _canonical_identifier(session_id)
        with self._lock:
            connection = self._open()
            try:
                connection.execute("BEGIN IMMEDIATE")
                self._load_session(connection, canonical_id)
                cursor = connection.execute(
                    "DELETE FROM conversation_sessions WHERE session_id = ?",
                    (canonical_id,),
                )
                if cursor.rowcount != 1:
                    _raise_repository_error(
                        ConversationRepositoryErrorCode.NOT_FOUND
                    )
                connection.commit()
            except ConversationRepositoryError:
                _rollback_quietly(connection)
                raise
            except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
                _rollback_quietly(connection)
                raise
            except sqlite3.Error:
                _rollback_quietly(connection)
                _raise_repository_error(
                    ConversationRepositoryErrorCode.UNAVAILABLE
                )
            finally:
                _close_quietly(connection)

    def purge_expired(
        self,
        cutoff: Any,
        limit: int = MAX_CONVERSATION_LIST_LIMIT,
    ) -> Tuple[str, ...]:
        canonical_cutoff = _canonical_timestamp(cutoff)
        canonical_limit = _canonical_limit(limit)
        cutoff_wire = (
            canonical_cutoff.isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )
        with self._lock:
            connection = self._open()
            try:
                connection.execute("BEGIN IMMEDIATE")
                rows = connection.execute(
                    """
                    SELECT session_id, revision, updated_at, expires_at, payload
                    FROM conversation_sessions
                    WHERE expires_at <= ?
                    ORDER BY expires_at ASC, session_id ASC
                    LIMIT ?
                    """,
                    (cutoff_wire, canonical_limit),
                ).fetchall()
                sessions = []
                for row in rows:
                    session = _session_from_row(row[0], row[1:])
                    self._validate_session_turn_index(connection, session)
                    if (
                        session.expires_at is None
                        or session.expires_at > canonical_cutoff
                    ):
                        _raise_repository_error(
                            ConversationRepositoryErrorCode.CORRUPT
                        )
                    sessions.append(session)
                session_ids = tuple(
                    session.session_id for session in sessions
                )
                for session_id in session_ids:
                    connection.execute(
                        """
                        DELETE FROM conversation_sessions
                        WHERE session_id = ? AND expires_at <= ?
                        """,
                        (session_id, cutoff_wire),
                    )
                connection.commit()
                return session_ids
            except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
                _rollback_quietly(connection)
                raise
            except sqlite3.Error:
                _rollback_quietly(connection)
                _raise_repository_error(
                    ConversationRepositoryErrorCode.UNAVAILABLE
                )
            finally:
                _close_quietly(connection)

    def _initialize(self) -> None:
        with self._lock:
            connection = self._open()
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS conversation_metadata(
                        schema_name TEXT PRIMARY KEY,
                        schema_version INTEGER NOT NULL
                    )
                    """
                )
                metadata = connection.execute(
                    """
                    SELECT schema_version FROM conversation_metadata
                    WHERE schema_name = ?
                    """,
                    (CONVERSATION_REPOSITORY_SCHEMA_NAME,),
                ).fetchone()
                if metadata is None:
                    connection.execute(
                        """
                        INSERT INTO conversation_metadata(
                            schema_name, schema_version
                        ) VALUES (?, ?)
                        """,
                        (
                            CONVERSATION_REPOSITORY_SCHEMA_NAME,
                            CONVERSATION_REPOSITORY_SCHEMA_VERSION,
                        ),
                    )
                elif metadata != (CONVERSATION_REPOSITORY_SCHEMA_VERSION,):
                    _raise_repository_error(
                        ConversationRepositoryErrorCode.SCHEMA_MISMATCH
                    )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS conversation_sessions(
                        session_id TEXT PRIMARY KEY,
                        revision INTEGER NOT NULL,
                        updated_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        payload TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS conversation_turns(
                        turn_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        sequence_number INTEGER NOT NULL,
                        payload TEXT NOT NULL,
                        UNIQUE(session_id, sequence_number),
                        FOREIGN KEY(session_id)
                            REFERENCES conversation_sessions(session_id)
                            ON DELETE CASCADE
                    )
                    """
                )
                self._validate_schema(connection)
                connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS
                        conversation_sessions_expiration
                    ON conversation_sessions(expires_at, session_id)
                    """
                )
                connection.commit()
            except ConversationRepositoryError:
                _rollback_quietly(connection)
                raise
            except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
                _rollback_quietly(connection)
                raise
            except sqlite3.Error:
                _rollback_quietly(connection)
                _raise_repository_error(
                    ConversationRepositoryErrorCode.UNAVAILABLE
                )
            finally:
                _close_quietly(connection)

    def _open(self) -> sqlite3.Connection:
        try:
            connection = sqlite3.connect(self._database_path, timeout=5.0)
            connection.execute("PRAGMA foreign_keys = ON")
            enabled = connection.execute("PRAGMA foreign_keys").fetchone()
            if enabled != (1,):
                _close_quietly(connection)
                _raise_repository_error(
                    ConversationRepositoryErrorCode.UNAVAILABLE
                )
            return connection
        except ConversationRepositoryError:
            raise
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except sqlite3.Error:
            _raise_repository_error(
                ConversationRepositoryErrorCode.UNAVAILABLE
            )

    def _write_transition(
        self,
        session: ConversationSession,
        turn: ConversationTurn,
        expected_revision: int,
        *,
        append: bool,
    ) -> None:
        with self._lock:
            connection = self._open()
            try:
                connection.execute("BEGIN IMMEDIATE")
                current_session = self._load_session(
                    connection,
                    session.session_id,
                )
                if append:
                    existing = connection.execute(
                        """
                        SELECT 1 FROM conversation_turns WHERE turn_id = ?
                        """,
                        (turn.turn_id,),
                    ).fetchone()
                    if existing is not None:
                        _raise_repository_error(
                            ConversationRepositoryErrorCode.DUPLICATE
                        )
                    _validate_append_transition(
                        current_session,
                        expected_revision,
                        session,
                        turn,
                    )
                    connection.execute(
                        """
                        INSERT INTO conversation_turns(
                            turn_id, session_id, sequence_number, payload
                        ) VALUES (?, ?, ?, ?)
                        """,
                        (
                            turn.turn_id,
                            turn.session_id,
                            turn.sequence_number,
                            _encode_record(turn.to_dict()),
                        ),
                    )
                else:
                    current_turn = self._load_turn(connection, turn.turn_id)
                    _validate_replace_turn_transition(
                        current_session,
                        current_turn,
                        expected_revision,
                        session,
                        turn,
                    )
                    cursor = connection.execute(
                        """
                        UPDATE conversation_turns SET payload = ?
                        WHERE turn_id = ?
                        """,
                        (_encode_record(turn.to_dict()), turn.turn_id),
                    )
                    if cursor.rowcount != 1:
                        _raise_repository_error(
                            ConversationRepositoryErrorCode.NOT_FOUND
                        )
                self._update_session(
                    connection,
                    expected_revision,
                    session,
                )
                connection.commit()
            except sqlite3.IntegrityError:
                _rollback_quietly(connection)
                _raise_repository_error(
                    ConversationRepositoryErrorCode.DUPLICATE
                )
            except ConversationRepositoryError:
                _rollback_quietly(connection)
                raise
            except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
                _rollback_quietly(connection)
                raise
            except sqlite3.Error:
                _rollback_quietly(connection)
                _raise_repository_error(
                    ConversationRepositoryErrorCode.UNAVAILABLE
                )
            finally:
                _close_quietly(connection)

    def _update_session(
        self,
        connection: sqlite3.Connection,
        expected_revision: int,
        session: ConversationSession,
    ) -> None:
        wire = session.to_dict()
        cursor = connection.execute(
            """
            UPDATE conversation_sessions
            SET revision = ?, updated_at = ?, expires_at = ?, payload = ?
            WHERE session_id = ? AND revision = ?
            """,
            (
                session.revision,
                wire["updated_at"],
                wire["expires_at"],
                _encode_record(wire),
                session.session_id,
                expected_revision,
            ),
        )
        if cursor.rowcount != 1:
            _raise_repository_error(
                ConversationRepositoryErrorCode.REVISION_CONFLICT
            )

    def _load_session(
        self,
        connection: sqlite3.Connection,
        session_id: str,
    ) -> ConversationSession:
        row = connection.execute(
            """
            SELECT revision, updated_at, expires_at, payload
            FROM conversation_sessions WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()
        if row is None:
            _raise_repository_error(ConversationRepositoryErrorCode.NOT_FOUND)
        session = _session_from_row(session_id, row)
        self._validate_session_turn_index(connection, session)
        return session

    def _load_turn(
        self,
        connection: sqlite3.Connection,
        turn_id: str,
    ) -> ConversationTurn:
        row = connection.execute(
            """
            SELECT session_id, sequence_number, payload
            FROM conversation_turns WHERE turn_id = ?
            """,
            (turn_id,),
        ).fetchone()
        if row is None:
            _raise_repository_error(ConversationRepositoryErrorCode.NOT_FOUND)
        return _turn_from_row(turn_id, row)

    def _load_turns(
        self,
        connection: sqlite3.Connection,
        session_id: str,
    ) -> Tuple[ConversationTurn, ...]:
        rows = connection.execute(
            """
            SELECT turn_id, sequence_number, payload
            FROM conversation_turns
            WHERE session_id = ?
            ORDER BY sequence_number ASC
            """,
            (session_id,),
        ).fetchall()
        turns = tuple(
            _turn_from_row(row[0], (session_id, row[1], row[2]))
            for row in rows
        )
        return turns

    @staticmethod
    def _validate_session_turn_index(
        connection: sqlite3.Connection,
        session: ConversationSession,
    ) -> None:
        rows = connection.execute(
            """
            SELECT turn_id, sequence_number FROM conversation_turns
            WHERE session_id = ?
            ORDER BY sequence_number ASC
            """,
            (session.session_id,),
        ).fetchall()
        if (
            tuple(row[0] for row in rows) != session.turn_ids
            or tuple(row[1] for row in rows)
            != tuple(range(1, len(rows) + 1))
        ):
            _raise_repository_error(
                ConversationRepositoryErrorCode.CORRUPT
            )

    @staticmethod
    def _validate_schema(connection: sqlite3.Connection) -> None:
        session_columns = tuple(
            row[1:6]
            for row in connection.execute(
                "PRAGMA table_info(conversation_sessions)"
            ).fetchall()
        )
        turn_columns = tuple(
            row[1:6]
            for row in connection.execute(
                "PRAGMA table_info(conversation_turns)"
            ).fetchall()
        )
        foreign_keys = connection.execute(
            "PRAGMA foreign_key_list(conversation_turns)"
        ).fetchall()
        expected_sessions = (
            ("session_id", "TEXT", 0, None, 1),
            ("revision", "INTEGER", 1, None, 0),
            ("updated_at", "TEXT", 1, None, 0),
            ("expires_at", "TEXT", 1, None, 0),
            ("payload", "TEXT", 1, None, 0),
        )
        expected_turns = (
            ("turn_id", "TEXT", 0, None, 1),
            ("session_id", "TEXT", 1, None, 0),
            ("sequence_number", "INTEGER", 1, None, 0),
            ("payload", "TEXT", 1, None, 0),
        )
        if (
            session_columns != expected_sessions
            or turn_columns != expected_turns
            or len(foreign_keys) != 1
            or foreign_keys[0][2:8]
            != (
                "conversation_sessions",
                "session_id",
                "session_id",
                "NO ACTION",
                "CASCADE",
                "NONE",
            )
        ):
            _raise_repository_error(
                ConversationRepositoryErrorCode.SCHEMA_MISMATCH
            )


def _validate_append_transition(
    current: ConversationSession,
    expected_revision: int,
    session: ConversationSession,
    turn: ConversationTurn,
) -> None:
    if current.revision != expected_revision:
        _raise_repository_error(
            ConversationRepositoryErrorCode.REVISION_CONFLICT
        )
    if (
        current.status is not ConversationSessionStatus.ACTIVE
        or session.status is not current.status
        or session.session_id != current.session_id
        or session.revision != current.revision + 1
        or session.retention_policy is not current.retention_policy
        or session.connection_context_id != current.connection_context_id
        or session.created_at != current.created_at
        or session.turn_ids != current.turn_ids + (turn.turn_id,)
        or session.updated_at < current.updated_at
        or turn.status is not ConversationTurnStatus.PENDING
        or turn.session_id != current.session_id
        or turn.sequence_number != len(current.turn_ids) + 1
        or turn.created_at != session.updated_at
    ):
        _raise_repository_error(
            ConversationRepositoryErrorCode.STATE_CONFLICT
        )


def _validate_replace_turn_transition(
    current_session: ConversationSession,
    current_turn: ConversationTurn,
    expected_revision: int,
    session: ConversationSession,
    turn: ConversationTurn,
) -> None:
    if current_session.revision != expected_revision:
        _raise_repository_error(
            ConversationRepositoryErrorCode.REVISION_CONFLICT
        )
    if (
        current_session.status is not ConversationSessionStatus.ACTIVE
        or current_turn.status is not ConversationTurnStatus.PENDING
        or turn.status is ConversationTurnStatus.PENDING
        or session.status is not current_session.status
        or session.session_id != current_session.session_id
        or session.revision != current_session.revision + 1
        or session.retention_policy is not current_session.retention_policy
        or session.connection_context_id
        != current_session.connection_context_id
        or session.created_at != current_session.created_at
        or session.turn_ids != current_session.turn_ids
        or session.updated_at < current_session.updated_at
        or turn.turn_id != current_turn.turn_id
        or turn.session_id != current_turn.session_id
        or turn.sequence_number != current_turn.sequence_number
        or turn.user_message != current_turn.user_message
        or turn.created_at != current_turn.created_at
        or turn.completed_at != session.updated_at
    ):
        _raise_repository_error(
            ConversationRepositoryErrorCode.STATE_CONFLICT
        )


def _validate_close_transition(
    current: ConversationSession,
    turns: Tuple[ConversationTurn, ...],
    expected_revision: int,
    session: ConversationSession,
) -> None:
    if current.revision != expected_revision:
        _raise_repository_error(
            ConversationRepositoryErrorCode.REVISION_CONFLICT
        )
    if (
        current.status is not ConversationSessionStatus.ACTIVE
        or any(
            turn.status is ConversationTurnStatus.PENDING for turn in turns
        )
        or session.status is not ConversationSessionStatus.CLOSED
        or session.session_id != current.session_id
        or session.revision != current.revision + 1
        or session.retention_policy is not current.retention_policy
        or session.connection_context_id != current.connection_context_id
        or session.created_at != current.created_at
        or session.turn_ids != current.turn_ids
        or session.updated_at < current.updated_at
    ):
        _raise_repository_error(
            ConversationRepositoryErrorCode.STATE_CONFLICT
        )


def _validate_turn_membership(
    session: ConversationSession,
    turn: ConversationTurn,
) -> None:
    position = turn.sequence_number - 1
    if (
        turn.session_id != session.session_id
        or position < 0
        or position >= len(session.turn_ids)
        or session.turn_ids[position] != turn.turn_id
    ):
        _raise_repository_error(
            ConversationRepositoryErrorCode.CORRUPT
        )


def _canonical_session(value: Any) -> ConversationSession:
    if type(value) is not ConversationSession:
        _raise_repository_error(ConversationRepositoryErrorCode.INVALID_REQUEST)
    try:
        return ConversationSession.from_dict(value.to_dict())
    except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
        raise
    except Exception:
        _raise_repository_error(ConversationRepositoryErrorCode.INVALID_REQUEST)


def _canonical_turn(value: Any) -> ConversationTurn:
    if type(value) is not ConversationTurn:
        _raise_repository_error(ConversationRepositoryErrorCode.INVALID_REQUEST)
    try:
        return ConversationTurn.from_dict(value.to_dict())
    except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
        raise
    except Exception:
        _raise_repository_error(ConversationRepositoryErrorCode.INVALID_REQUEST)


def _canonical_identifier(value: Any) -> str:
    try:
        return validate_run_identifier(value)
    except Exception:
        _raise_repository_error(ConversationRepositoryErrorCode.INVALID_REQUEST)


def _canonical_revision(value: Any) -> int:
    if type(value) is not int or value < 1:
        _raise_repository_error(ConversationRepositoryErrorCode.INVALID_REQUEST)
    return value


def _canonical_limit(value: Any) -> int:
    try:
        return validate_conversation_list_limit(value)
    except Exception:
        _raise_repository_error(ConversationRepositoryErrorCode.INVALID_REQUEST)


def _canonical_timestamp(value: Any):
    try:
        return validate_conversation_timestamp(value, "cutoff")
    except Exception:
        _raise_repository_error(ConversationRepositoryErrorCode.INVALID_REQUEST)


def _encode_record(wire: Dict[str, Any]) -> str:
    try:
        encoded = json.dumps(
            wire,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError):
        _raise_repository_error(ConversationRepositoryErrorCode.INVALID_REQUEST)
    if len(encoded.encode("utf-8")) > MAX_CONVERSATION_RECORD_BYTES:
        _raise_repository_error(ConversationRepositoryErrorCode.INVALID_REQUEST)
    return encoded


def _decode_record(payload: Any) -> Dict[str, Any]:
    if type(payload) is not str:
        _raise_repository_error(ConversationRepositoryErrorCode.CORRUPT)
    try:
        encoded = payload.encode("utf-8")
    except UnicodeError:
        _raise_repository_error(ConversationRepositoryErrorCode.CORRUPT)
    if len(encoded) > MAX_CONVERSATION_RECORD_BYTES:
        _raise_repository_error(ConversationRepositoryErrorCode.CORRUPT)
    try:
        value = json.loads(
            payload,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        _raise_repository_error(ConversationRepositoryErrorCode.CORRUPT)
    if type(value) is not dict or _encode_record(value) != payload:
        _raise_repository_error(ConversationRepositoryErrorCode.CORRUPT)
    return value


def _session_from_wire(wire: Any) -> ConversationSession:
    try:
        return ConversationSession.from_dict(dict(wire))
    except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
        raise
    except (ConversationContractValidationError, TypeError, ValueError):
        _raise_repository_error(ConversationRepositoryErrorCode.CORRUPT)


def _turn_from_wire(wire: Any) -> ConversationTurn:
    try:
        return ConversationTurn.from_dict(dict(wire))
    except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
        raise
    except (ConversationContractValidationError, TypeError, ValueError):
        _raise_repository_error(ConversationRepositoryErrorCode.CORRUPT)


def _session_from_row(
    session_id: Any,
    row: Tuple[Any, ...],
) -> ConversationSession:
    if type(session_id) is not str or len(row) != 4:
        _raise_repository_error(ConversationRepositoryErrorCode.CORRUPT)
    session = _session_from_wire(_decode_record(row[3]))
    wire = session.to_dict()
    if (
        session.session_id != session_id
        or session.revision != row[0]
        or wire["updated_at"] != row[1]
        or wire["expires_at"] != row[2]
        or not session.retention_policy.durable
    ):
        _raise_repository_error(ConversationRepositoryErrorCode.CORRUPT)
    return session


def _turn_from_row(turn_id: Any, row: Tuple[Any, ...]) -> ConversationTurn:
    if type(turn_id) is not str or len(row) != 3:
        _raise_repository_error(ConversationRepositoryErrorCode.CORRUPT)
    turn = _turn_from_wire(_decode_record(row[2]))
    if (
        turn.turn_id != turn_id
        or turn.session_id != row[0]
        or turn.sequence_number != row[1]
    ):
        _raise_repository_error(ConversationRepositoryErrorCode.CORRUPT)
    return turn


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("non-finite JSON number")


def _rollback_quietly(connection: sqlite3.Connection) -> None:
    try:
        connection.rollback()
    except sqlite3.Error:
        pass


def _close_quietly(connection: sqlite3.Connection) -> None:
    try:
        connection.close()
    except sqlite3.Error:
        pass


def _raise_repository_error(
    code: ConversationRepositoryErrorCode,
) -> None:
    raise ConversationRepositoryError(code) from None


__all__ = [
    "CONVERSATION_REPOSITORY_SCHEMA_NAME",
    "CONVERSATION_REPOSITORY_SCHEMA_VERSION",
    "MAX_CONVERSATION_RECORD_BYTES",
    "ConversationRepository",
    "ConversationRepositoryError",
    "ConversationRepositoryErrorCode",
    "InMemoryConversationRepository",
    "SQLiteConversationRepository",
]
