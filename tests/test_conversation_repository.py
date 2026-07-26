"""Tests for in-memory and SQLite conversation repositories."""

from datetime import datetime, timedelta, timezone
import json
import sqlite3

import pytest

from pmqa.conversation import (
    CONVERSATION_REPOSITORY_SCHEMA_NAME,
    ConversationRepositoryError,
    ConversationRepositoryErrorCode,
    ConversationRetentionPolicy,
    ConversationSession,
    ConversationSessionStatus,
    ConversationTurn,
    ConversationTurnStatus,
    InMemoryConversationRepository,
    SQLiteConversationRepository,
    conversation_expiration,
)


NOW = datetime(2026, 7, 25, 12, tzinfo=timezone.utc)


def _session(
    session_id: str = "conversation.session.1",
    *,
    policy: ConversationRetentionPolicy = (
        ConversationRetentionPolicy.THIRTY_DAYS
    ),
    revision: int = 1,
    status: ConversationSessionStatus = ConversationSessionStatus.ACTIVE,
    turn_ids=(),
    created_at: datetime = NOW,
    updated_at: datetime = NOW,
) -> ConversationSession:
    return ConversationSession(
        schema_version="1",
        session_id=session_id,
        revision=revision,
        status=status,
        retention_policy=policy,
        connection_context_id=None,
        turn_ids=turn_ids,
        created_at=created_at,
        updated_at=updated_at,
        expires_at=conversation_expiration(policy, updated_at),
    )


def _pending_turn(
    turn_id: str = "conversation.turn.1",
    *,
    session_id: str = "conversation.session.1",
    sequence_number: int = 1,
    created_at: datetime = NOW + timedelta(minutes=1),
) -> ConversationTurn:
    return ConversationTurn(
        schema_version="1",
        turn_id=turn_id,
        session_id=session_id,
        sequence_number=sequence_number,
        status=ConversationTurnStatus.PENDING,
        user_message="What are the main QA risks?",
        assistant_response=None,
        error_code=None,
        error_message=None,
        created_at=created_at,
        completed_at=None,
    )


def _repository(request, tmp_path):
    if request.param == "memory":
        return InMemoryConversationRepository()
    return SQLiteConversationRepository(str(tmp_path / "conversation.sqlite3"))


@pytest.fixture(params=("memory", "sqlite"))
def repository(request, tmp_path):
    return _repository(request, tmp_path)


def _append(repository, current: ConversationSession, turn: ConversationTurn):
    updated = current.model_copy(
        update={
            "revision": current.revision + 1,
            "turn_ids": current.turn_ids + (turn.turn_id,),
            "updated_at": turn.created_at,
            "expires_at": conversation_expiration(
                current.retention_policy,
                turn.created_at,
            ),
        }
    )
    repository.append_turn(
        expected_revision=current.revision,
        session=updated,
        turn=turn,
    )
    return updated


def _complete(
    repository,
    current: ConversationSession,
    pending: ConversationTurn,
):
    completed_at = pending.created_at + timedelta(minutes=1)
    completed = pending.model_copy(
        update={
            "status": ConversationTurnStatus.COMPLETED,
            "assistant_response": "Risk analysis complete.",
            "completed_at": completed_at,
        }
    )
    updated = current.model_copy(
        update={
            "revision": current.revision + 1,
            "updated_at": completed_at,
            "expires_at": conversation_expiration(
                current.retention_policy,
                completed_at,
            ),
        }
    )
    repository.replace_turn(
        expected_revision=current.revision,
        session=updated,
        turn=completed,
    )
    return updated, completed


def test_repository_round_trip_and_immutable_snapshots(repository) -> None:
    session = _session()
    repository.create_session(session)

    first = repository.get_session(session.session_id)
    second = repository.get_session(session.session_id)

    assert first == session
    assert second == session
    assert first is not second
    assert first.to_dict() is not second.to_dict()


def test_atomic_append_complete_and_close_transitions(repository) -> None:
    session = _session()
    repository.create_session(session)
    pending = _pending_turn()
    after_start = _append(repository, session, pending)
    after_complete, completed = _complete(repository, after_start, pending)
    closed_at = completed.completed_at + timedelta(minutes=1)
    closed = after_complete.model_copy(
        update={
            "revision": after_complete.revision + 1,
            "status": ConversationSessionStatus.CLOSED,
            "updated_at": closed_at,
            "expires_at": conversation_expiration(
                after_complete.retention_policy,
                closed_at,
            ),
        }
    )
    repository.close_session(
        expected_revision=after_complete.revision,
        session=closed,
    )

    assert repository.get_session(session.session_id) == closed
    assert repository.get_turn(pending.turn_id) == completed
    assert repository.list_turns(session.session_id) == (completed,)


def test_stale_revision_leaves_no_partial_append(repository) -> None:
    session = _session()
    repository.create_session(session)
    pending = _pending_turn()
    updated = session.model_copy(
        update={
            "revision": 2,
            "turn_ids": (pending.turn_id,),
            "updated_at": pending.created_at,
            "expires_at": conversation_expiration(
                session.retention_policy,
                pending.created_at,
            ),
        }
    )

    with pytest.raises(ConversationRepositoryError) as captured:
        repository.append_turn(
            expected_revision=2,
            session=updated,
            turn=pending,
        )

    assert captured.value.code is ConversationRepositoryErrorCode.REVISION_CONFLICT
    assert repository.get_session(session.session_id) == session
    with pytest.raises(ConversationRepositoryError) as missing:
        repository.get_turn(pending.turn_id)
    assert missing.value.code is ConversationRepositoryErrorCode.NOT_FOUND


def test_duplicate_turn_id_or_sequence_is_atomic(repository) -> None:
    first = _session("conversation.session.1")
    second = _session("conversation.session.2")
    repository.create_session(first)
    repository.create_session(second)
    first_turn = _pending_turn()
    _append(repository, first, first_turn)

    duplicate_id = _pending_turn(
        turn_id=first_turn.turn_id,
        session_id=second.session_id,
    )
    with pytest.raises(ConversationRepositoryError) as captured:
        _append(repository, second, duplicate_id)
    assert captured.value.code is ConversationRepositoryErrorCode.DUPLICATE
    assert repository.get_session(second.session_id) == second


def test_cannot_close_session_with_pending_turn(repository) -> None:
    session = _session()
    repository.create_session(session)
    pending = _pending_turn()
    current = _append(repository, session, pending)
    closed_at = pending.created_at + timedelta(minutes=1)
    closed = current.model_copy(
        update={
            "revision": current.revision + 1,
            "status": ConversationSessionStatus.CLOSED,
            "updated_at": closed_at,
            "expires_at": conversation_expiration(
                current.retention_policy,
                closed_at,
            ),
        }
    )

    with pytest.raises(ConversationRepositoryError) as captured:
        repository.close_session(
            expected_revision=current.revision,
            session=closed,
        )

    assert captured.value.code is ConversationRepositoryErrorCode.STATE_CONFLICT
    assert repository.get_session(session.session_id) == current


def test_deterministic_bounded_session_and_turn_order(repository) -> None:
    for index, minute in ((1, 1), (2, 3), (3, 3)):
        updated = NOW + timedelta(minutes=minute)
        repository.create_session(
            _session(
                f"conversation.session.{index}",
                created_at=NOW,
                updated_at=updated,
            )
        )

    assert tuple(item.session_id for item in repository.list_sessions(2)) == (
        "conversation.session.2",
        "conversation.session.3",
    )

    session = repository.get_session("conversation.session.1")
    first = _pending_turn(
        "conversation.turn.1",
        session_id=session.session_id,
        created_at=NOW + timedelta(minutes=2),
    )
    current = _append(repository, session, first)
    current, _ = _complete(repository, current, first)
    second = _pending_turn(
        "conversation.turn.2",
        session_id=session.session_id,
        sequence_number=2,
        created_at=NOW + timedelta(minutes=4),
    )
    _append(repository, current, second)

    assert tuple(
        item.sequence_number for item in repository.list_turns(session.session_id)
    ) == (1, 2)


def test_manual_delete_cascades_and_second_delete_is_not_found(repository) -> None:
    session = _session()
    repository.create_session(session)
    pending = _pending_turn()
    _append(repository, session, pending)

    repository.delete_session(session.session_id)

    with pytest.raises(ConversationRepositoryError) as session_missing:
        repository.get_session(session.session_id)
    with pytest.raises(ConversationRepositoryError) as turn_missing:
        repository.get_turn(pending.turn_id)
    with pytest.raises(ConversationRepositoryError) as second_delete:
        repository.delete_session(session.session_id)
    assert session_missing.value.code is ConversationRepositoryErrorCode.NOT_FOUND
    assert turn_missing.value.code is ConversationRepositoryErrorCode.NOT_FOUND
    assert second_delete.value.code is ConversationRepositoryErrorCode.NOT_FOUND


@pytest.mark.parametrize(
    ("offset", "purged"),
    (
        (timedelta(microseconds=-1), ()),
        (timedelta(0), ("conversation.session.1",)),
        (timedelta(microseconds=1), ("conversation.session.1",)),
    ),
)
def test_expiry_boundary_before_at_and_after(repository, offset, purged) -> None:
    session = _session()
    repository.create_session(session)

    assert repository.purge_expired(session.expires_at + offset) == purged
    if not purged:
        assert repository.get_session(session.session_id) == session


def test_purge_is_bounded_and_never_touches_unexpired_or_session_only() -> None:
    repository = InMemoryConversationRepository()
    expired_one = _session(
        "conversation.session.1",
        policy=ConversationRetentionPolicy.SEVEN_DAYS,
    )
    expired_two = _session(
        "conversation.session.2",
        policy=ConversationRetentionPolicy.SEVEN_DAYS,
    )
    unexpired = _session(
        "conversation.session.3",
        policy=ConversationRetentionPolicy.NINETY_DAYS,
    )
    volatile = _session(
        "conversation.session.4",
        policy=ConversationRetentionPolicy.SESSION_ONLY,
    )
    for session in (expired_one, expired_two, unexpired, volatile):
        repository.create_session(session)

    assert repository.purge_expired(NOW + timedelta(days=30), 1) == (
        "conversation.session.1",
    )
    assert repository.get_session(unexpired.session_id) == unexpired
    assert repository.get_session(volatile.session_id) == volatile


def test_sqlite_rejects_session_only_before_writing(tmp_path) -> None:
    repository = SQLiteConversationRepository(str(tmp_path / "conversation.db"))

    with pytest.raises(ConversationRepositoryError) as captured:
        repository.create_session(
            _session(policy=ConversationRetentionPolicy.SESSION_ONLY)
        )

    assert captured.value.code is ConversationRepositoryErrorCode.INVALID_REQUEST
    assert repository.list_sessions() == ()


def test_separate_repositories_do_not_cross_mutate(tmp_path) -> None:
    volatile = InMemoryConversationRepository()
    durable = SQLiteConversationRepository(str(tmp_path / "conversation.db"))
    session_only = _session(
        "conversation.session.volatile",
        policy=ConversationRetentionPolicy.SESSION_ONLY,
    )
    persisted = _session("conversation.session.durable")
    volatile.create_session(session_only)
    durable.create_session(persisted)

    volatile.delete_session(session_only.session_id)

    assert durable.get_session(persisted.session_id) == persisted
    assert durable.list_sessions() == (persisted,)


def test_sqlite_corrupt_payload_and_typed_column_fail_safely(tmp_path) -> None:
    path = tmp_path / "conversation.db"
    repository = SQLiteConversationRepository(str(path))
    session = _session()
    repository.create_session(session)
    marker = "runtime-secret-marker"
    connection = sqlite3.connect(str(path))
    try:
        connection.execute(
            """
            UPDATE conversation_sessions SET payload = ?
            WHERE session_id = ?
            """,
            (f'{{"marker":"{marker}"}}', session.session_id),
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(ConversationRepositoryError) as captured:
        repository.get_session(session.session_id)

    assert captured.value.code is ConversationRepositoryErrorCode.CORRUPT
    assert str(captured.value) == "conversation repository is corrupt"
    assert marker not in str(captured.value)
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None


def test_sqlite_rejects_noncanonical_json_and_duplicate_keys(tmp_path) -> None:
    path = tmp_path / "conversation.db"
    repository = SQLiteConversationRepository(str(path))
    session = _session()
    repository.create_session(session)
    wire = session.to_dict()
    payload = json.dumps(wire, ensure_ascii=False)
    payload = payload[:-1] + ',"session_id":"conversation.session.other"}'
    connection = sqlite3.connect(str(path))
    try:
        connection.execute(
            "UPDATE conversation_sessions SET payload = ?",
            (payload,),
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(ConversationRepositoryError) as captured:
        repository.get_session(session.session_id)
    assert captured.value.code is ConversationRepositoryErrorCode.CORRUPT


def test_sqlite_schema_mismatch_is_fixed_and_safe(tmp_path) -> None:
    path = tmp_path / "conversation.db"
    connection = sqlite3.connect(str(path))
    try:
        connection.execute(
            """
            CREATE TABLE conversation_metadata(
                schema_name TEXT PRIMARY KEY,
                schema_version INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO conversation_metadata VALUES (?, ?)",
            (CONVERSATION_REPOSITORY_SCHEMA_NAME, 999),
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(ConversationRepositoryError) as captured:
        SQLiteConversationRepository(str(path))

    assert captured.value.code is ConversationRepositoryErrorCode.SCHEMA_MISMATCH
    assert str(captured.value) == (
        "conversation repository schema is incompatible"
    )
    assert str(path) not in str(captured.value)


def test_sqlite_malformed_existing_table_is_schema_mismatch(tmp_path) -> None:
    path = tmp_path / "conversation.db"
    connection = sqlite3.connect(str(path))
    try:
        connection.execute(
            """
            CREATE TABLE conversation_metadata(
                schema_name TEXT PRIMARY KEY,
                schema_version INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO conversation_metadata VALUES (?, ?)",
            (CONVERSATION_REPOSITORY_SCHEMA_NAME, 1),
        )
        connection.execute(
            "CREATE TABLE conversation_sessions(session_id TEXT PRIMARY KEY)"
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(ConversationRepositoryError) as captured:
        SQLiteConversationRepository(str(path))

    assert captured.value.code is ConversationRepositoryErrorCode.SCHEMA_MISMATCH
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None


def test_sqlite_detects_session_turn_index_corruption(tmp_path) -> None:
    path = tmp_path / "conversation.db"
    repository = SQLiteConversationRepository(str(path))
    session = _session()
    repository.create_session(session)
    pending = _pending_turn()
    current = _append(repository, session, pending)
    connection = sqlite3.connect(str(path))
    try:
        connection.execute(
            "DELETE FROM conversation_turns WHERE turn_id = ?",
            (pending.turn_id,),
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(ConversationRepositoryError) as captured:
        repository.get_session(current.session_id)

    assert captured.value.code is ConversationRepositoryErrorCode.CORRUPT


@pytest.mark.parametrize("operation", ("delete", "purge"))
def test_sqlite_corruption_blocks_delete_and_purge_atomically(
    tmp_path,
    operation,
) -> None:
    path = tmp_path / "conversation.db"
    repository = SQLiteConversationRepository(str(path))
    session = _session()
    repository.create_session(session)
    connection = sqlite3.connect(str(path))
    try:
        connection.execute(
            "UPDATE conversation_sessions SET payload = ?",
            ('{"corrupt":true}',),
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(ConversationRepositoryError) as captured:
        if operation == "delete":
            repository.delete_session(session.session_id)
        else:
            repository.purge_expired(session.expires_at)

    assert captured.value.code is ConversationRepositoryErrorCode.CORRUPT
    connection = sqlite3.connect(str(path))
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM conversation_sessions"
        ).fetchone() == (1,)
    finally:
        connection.close()


def test_sqlite_unavailable_database_is_fixed_and_safe(tmp_path) -> None:
    path = tmp_path / "directory"
    path.mkdir()

    with pytest.raises(ConversationRepositoryError) as captured:
        SQLiteConversationRepository(str(path))

    assert captured.value.code is ConversationRepositoryErrorCode.UNAVAILABLE
    assert str(path) not in str(captured.value)
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None


@pytest.mark.parametrize("repository_kind", ("memory", "sqlite"))
def test_invalid_repository_requests_are_fixed_and_marker_safe(
    repository_kind,
    tmp_path,
) -> None:
    repository = (
        InMemoryConversationRepository()
        if repository_kind == "memory"
        else SQLiteConversationRepository(str(tmp_path / "conversation.db"))
    )
    marker = "runtime-secret-marker"

    with pytest.raises(ConversationRepositoryError) as captured:
        repository.get_session(f"../{marker}")

    assert captured.value.code is ConversationRepositoryErrorCode.INVALID_REQUEST
    assert marker not in str(captured.value)
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
