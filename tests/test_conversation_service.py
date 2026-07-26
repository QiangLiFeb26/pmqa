"""Tests for deterministic conversation application-service behavior."""

from datetime import datetime, timedelta, timezone

import pytest

from pmqa.conversation import (
    DEFAULT_CONVERSATION_RETENTION,
    ConversationApplicationError,
    ConversationApplicationErrorCode,
    ConversationApplicationService,
    ConversationRepositoryError,
    ConversationRepositoryErrorCode,
    ConversationRetentionPolicy,
    ConversationSessionStatus,
    ConversationTurnErrorCode,
    ConversationTurnStatus,
    InMemoryConversationRepository,
    SQLiteConversationRepository,
)


NOW = datetime(2026, 7, 25, 12, tzinfo=timezone.utc)


class Sequence:
    def __init__(self, *values) -> None:
        self.values = list(values)
        self.calls = 0

    def __call__(self):
        value = self.values[self.calls]
        self.calls += 1
        if isinstance(value, BaseException):
            raise value
        return value


class CountingRepository:
    def __init__(self, delegate=None) -> None:
        self.delegate = delegate or InMemoryConversationRepository()
        self.calls = []
        self.failure = None
        self.results = {}

    def _call(self, name, *args, **kwargs):
        self.calls.append(name)
        if self.failure is not None and name == self.failure[0]:
            raise self.failure[1]
        if name in self.results:
            result = self.results[name]
            if isinstance(result, BaseException):
                raise result
            return result(*args, **kwargs) if callable(result) else result
        return getattr(self.delegate, name)(*args, **kwargs)

    def create_session(self, session):
        return self._call("create_session", session)

    def get_session(self, session_id):
        return self._call("get_session", session_id)

    def list_sessions(self, limit=100):
        return self._call("list_sessions", limit)

    def get_turn(self, turn_id):
        return self._call("get_turn", turn_id)

    def list_turns(self, session_id, limit=100):
        return self._call("list_turns", session_id, limit)

    def append_turn(self, *, expected_revision, session, turn):
        return self._call(
            "append_turn",
            expected_revision=expected_revision,
            session=session,
            turn=turn,
        )

    def replace_turn(self, *, expected_revision, session, turn):
        return self._call(
            "replace_turn",
            expected_revision=expected_revision,
            session=session,
            turn=turn,
        )

    def close_session(self, *, expected_revision, session):
        return self._call(
            "close_session",
            expected_revision=expected_revision,
            session=session,
        )

    def delete_session(self, session_id):
        return self._call("delete_session", session_id)

    def purge_expired(self, cutoff, limit=256):
        return self._call("purge_expired", cutoff, limit)


def _service(
    *,
    clock=None,
    session_ids=None,
    turn_ids=None,
    volatile=None,
    durable=None,
):
    volatile_repository = volatile or CountingRepository()
    durable_repository = durable or CountingRepository()
    selected_clock = clock or Sequence(
        NOW,
        NOW + timedelta(minutes=1),
        NOW + timedelta(minutes=2),
        NOW + timedelta(minutes=3),
    )
    session_generator = session_ids or Sequence("conversation.session.1")
    turn_generator = turn_ids or Sequence("conversation.turn.1")
    service = ConversationApplicationService(
        volatile_repository=volatile_repository,
        durable_repository=durable_repository,
        clock=selected_clock,
        session_id_generator=session_generator,
        turn_id_generator=turn_generator,
    )
    return (
        service,
        volatile_repository,
        durable_repository,
        selected_clock,
        session_generator,
        turn_generator,
    )


def test_default_retention_is_approved_30_days_and_routes_durable() -> None:
    service, volatile, durable, clock, session_ids, _ = _service()

    session = service.create_session()

    assert DEFAULT_CONVERSATION_RETENTION is (
        ConversationRetentionPolicy.THIRTY_DAYS
    )
    assert session.retention_policy is ConversationRetentionPolicy.THIRTY_DAYS
    assert session.expires_at == NOW + timedelta(days=30)
    assert "create_session" not in volatile.calls
    assert durable.calls.count("create_session") == 1
    assert clock.calls == 1
    assert session_ids.calls == 1


@pytest.mark.parametrize(
    ("policy", "duration", "durable_selected"),
    (
        (ConversationRetentionPolicy.SESSION_ONLY, None, False),
        (ConversationRetentionPolicy.SEVEN_DAYS, timedelta(days=7), True),
        (ConversationRetentionPolicy.THIRTY_DAYS, timedelta(days=30), True),
        (ConversationRetentionPolicy.NINETY_DAYS, timedelta(days=90), True),
    ),
)
def test_all_approved_modes_route_without_cross_store_write(
    policy,
    duration,
    durable_selected,
) -> None:
    service, volatile, durable, _, _, _ = _service()

    session = service.create_session(policy)

    assert session.expires_at == (None if duration is None else NOW + duration)
    assert volatile.calls.count("create_session") == (not durable_selected)
    assert durable.calls.count("create_session") == durable_selected


def test_start_complete_and_close_advance_revision_time_and_expiry_once() -> None:
    service, _, _, clock, _, turn_ids = _service()
    session = service.create_session()

    started_session, pending = service.start_turn(
        session.session_id,
        expected_revision=session.revision,
        user_message="Story risks?",
    )
    completed_session, completed = service.complete_turn(
        session.session_id,
        pending.turn_id,
        expected_revision=started_session.revision,
        assistant_response="Risk analysis.",
    )
    closed = service.close_session(
        session.session_id,
        expected_revision=completed_session.revision,
    )

    assert started_session.revision == 2
    assert started_session.updated_at == NOW + timedelta(minutes=1)
    assert started_session.expires_at == (
        NOW + timedelta(days=30, minutes=1)
    )
    assert pending.created_at == started_session.updated_at
    assert pending.sequence_number == 1
    assert completed_session.revision == 3
    assert completed.completed_at == completed_session.updated_at
    assert closed.revision == 4
    assert closed.status is ConversationSessionStatus.CLOSED
    assert closed.updated_at == NOW + timedelta(minutes=3)
    assert clock.calls == 4
    assert turn_ids.calls == 1


def test_failed_turn_stores_only_fixed_safe_failure() -> None:
    service, _, _, _, _, _ = _service()
    session = service.create_session()
    current, pending = service.start_turn(
        session.session_id,
        expected_revision=1,
        user_message="Analyze this story.",
    )

    updated, failed = service.fail_turn(
        session.session_id,
        pending.turn_id,
        expected_revision=current.revision,
        error_code=ConversationTurnErrorCode.PROVIDER_UNAVAILABLE,
    )

    assert updated.revision == 3
    assert failed.status is ConversationTurnStatus.FAILED
    assert failed.assistant_response is None
    assert failed.error_code is ConversationTurnErrorCode.PROVIDER_UNAVAILABLE
    assert failed.error_message == "conversation provider is unavailable"


def test_successful_turn_sequence_is_gap_free() -> None:
    service, _, _, _, _, _ = _service(
        clock=Sequence(
            NOW,
            NOW + timedelta(minutes=1),
            NOW + timedelta(minutes=2),
            NOW + timedelta(minutes=3),
        ),
        turn_ids=Sequence("conversation.turn.1", "conversation.turn.2"),
    )
    session = service.create_session()
    current, first = service.start_turn(
        session.session_id,
        expected_revision=1,
        user_message="First",
    )
    current, _ = service.complete_turn(
        session.session_id,
        first.turn_id,
        expected_revision=current.revision,
        assistant_response="Done",
    )
    current, second = service.start_turn(
        session.session_id,
        expected_revision=current.revision,
        user_message="Second",
    )

    assert first.sequence_number == 1
    assert second.sequence_number == 2
    assert current.turn_ids == (first.turn_id, second.turn_id)


def test_reads_and_lists_do_not_sample_clock_or_extend_retention() -> None:
    service, _, _, clock, _, _ = _service()
    created = service.create_session()

    assert service.get_session(created.session_id) == created
    assert service.list_sessions() == (created,)
    assert service.list_turns(created.session_id) == ()

    assert clock.calls == 1
    assert service.get_session(created.session_id).expires_at == created.expires_at


@pytest.mark.parametrize(
    "message",
    (
        "Bearer runtime-secret-marker",
        "Cookie: value=runtime-secret-marker",
        "password=runtime-secret-marker",
        "secret: runtime-secret-marker",
    ),
)
def test_sensitive_user_text_fails_before_repository_write(message) -> None:
    service, volatile, durable, clock, _, turn_ids = _service()
    session = service.create_session(
        ConversationRetentionPolicy.SESSION_ONLY
    )
    volatile.calls.clear()
    durable.calls.clear()

    with pytest.raises(ConversationApplicationError) as captured:
        service.start_turn(
            session.session_id,
            expected_revision=1,
            user_message=message,
        )

    assert captured.value.code is (
        ConversationApplicationErrorCode.SENSITIVE_TEXT_REJECTED
    )
    assert str(captured.value) == "conversation text contains sensitive material"
    assert "runtime-secret-marker" not in str(captured.value)
    assert "append_turn" not in volatile.calls + durable.calls
    assert clock.calls == 1
    assert turn_ids.calls == 0
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None


def test_sensitive_assistant_response_fails_before_repository_write() -> None:
    service, volatile, durable, clock, _, _ = _service()
    session = service.create_session()
    current, pending = service.start_turn(
        session.session_id,
        expected_revision=1,
        user_message="test the password field",
    )
    volatile.calls.clear()
    durable.calls.clear()

    with pytest.raises(ConversationApplicationError) as captured:
        service.complete_turn(
            session.session_id,
            pending.turn_id,
            expected_revision=current.revision,
            assistant_response="token=runtime-secret-marker",
        )

    assert captured.value.code is (
        ConversationApplicationErrorCode.SENSITIVE_TEXT_REJECTED
    )
    assert "replace_turn" not in volatile.calls + durable.calls
    assert clock.calls == 2
    assert service.get_turn(session.session_id, pending.turn_id) == pending


@pytest.mark.parametrize(
    "message",
    (
        "test the password field",
        "token usage is unavailable",
        "type=password",
        "密码与 token 标签都需要可访问性检查",
    ),
)
def test_normal_security_discussion_is_persisted(message) -> None:
    service, _, _, _, _, _ = _service()
    session = service.create_session()

    _, turn = service.start_turn(
        session.session_id,
        expected_revision=1,
        user_message=message,
    )

    assert turn.user_message == message


@pytest.mark.parametrize(
    ("clock_value", "code"),
    (
        (datetime(2026, 7, 25, 12), ConversationApplicationErrorCode.INVALID_CLOCK),
        ("not-a-clock", ConversationApplicationErrorCode.INVALID_CLOCK),
    ),
)
def test_invalid_clock_fails_before_repository_effects(clock_value, code) -> None:
    clock = Sequence(clock_value)
    service, volatile, durable, _, session_ids, _ = _service(clock=clock)

    with pytest.raises(ConversationApplicationError) as captured:
        service.create_session()

    assert captured.value.code is code
    assert "create_session" not in volatile.calls + durable.calls
    assert session_ids.calls == 0


def test_invalid_generated_identifier_fails_before_repository_write() -> None:
    service, volatile, durable, clock, session_ids, _ = _service(
        session_ids=Sequence("../runtime-secret-marker")
    )

    with pytest.raises(ConversationApplicationError) as captured:
        service.create_session()

    assert captured.value.code is (
        ConversationApplicationErrorCode.INVALID_ID_GENERATOR
    )
    assert "runtime-secret-marker" not in str(captured.value)
    assert "create_session" not in volatile.calls + durable.calls
    assert clock.calls == 1
    assert session_ids.calls == 1


def test_unapproved_retention_mode_fails_before_sampling_or_repository() -> None:
    service, volatile, durable, clock, session_ids, _ = _service()

    with pytest.raises(ConversationApplicationError) as captured:
        service.create_session("forever")

    assert captured.value.code is ConversationApplicationErrorCode.INVALID_REQUEST
    assert clock.calls == 0
    assert session_ids.calls == 0
    assert "create_session" not in volatile.calls + durable.calls


def test_stale_revision_has_no_partial_turn() -> None:
    service, _, _, _, _, _ = _service()
    session = service.create_session()

    with pytest.raises(ConversationApplicationError) as captured:
        service.start_turn(
            session.session_id,
            expected_revision=2,
            user_message="Analyze",
        )

    assert captured.value.code is (
        ConversationApplicationErrorCode.REVISION_CONFLICT
    )
    assert service.get_session(session.session_id) == session
    assert service.list_turns(session.session_id) == ()


def test_closed_session_rejects_new_turn_without_mutation() -> None:
    service, _, _, _, _, _ = _service()
    session = service.create_session()
    closed = service.close_session(session.session_id, expected_revision=1)

    with pytest.raises(ConversationApplicationError) as captured:
        service.start_turn(
            session.session_id,
            expected_revision=closed.revision,
            user_message="Another question",
        )

    assert captured.value.code is ConversationApplicationErrorCode.SESSION_CLOSED
    assert service.get_session(session.session_id) == closed


def test_close_rejects_pending_turn_without_mutation() -> None:
    service, _, _, _, _, _ = _service()
    session = service.create_session()
    current, pending = service.start_turn(
        session.session_id,
        expected_revision=1,
        user_message="Analyze",
    )

    with pytest.raises(ConversationApplicationError) as captured:
        service.close_session(
            session.session_id,
            expected_revision=current.revision,
        )

    assert captured.value.code is ConversationApplicationErrorCode.STATE_CONFLICT
    assert service.get_session(session.session_id) == current
    assert service.get_turn(session.session_id, pending.turn_id) == pending


def test_manual_delete_is_immediate_and_second_delete_is_not_found() -> None:
    service, _, _, _, _, _ = _service()
    session = service.create_session()

    service.delete_session(session.session_id)

    with pytest.raises(ConversationApplicationError) as captured:
        service.delete_session(session.session_id)
    assert captured.value.code is (
        ConversationApplicationErrorCode.SESSION_NOT_FOUND
    )


def test_purge_samples_once_and_only_calls_durable_repository(tmp_path) -> None:
    volatile = CountingRepository()
    durable = CountingRepository(
        SQLiteConversationRepository(str(tmp_path / "conversation.db"))
    )
    cutoff = NOW + timedelta(days=30)
    service, _, _, clock, _, _ = _service(
        volatile=volatile,
        durable=durable,
        clock=Sequence(NOW, cutoff),
    )
    session = service.create_session()
    volatile.calls.clear()
    durable.calls.clear()

    assert service.purge_expired() == (session.session_id,)
    assert "purge_expired" not in volatile.calls
    assert durable.calls == ["purge_expired"]
    assert clock.calls == 2


@pytest.mark.parametrize(
    "failure",
    (
        MemoryError(),
        KeyboardInterrupt(),
        SystemExit(),
        GeneratorExit(),
    ),
)
def test_clock_resource_and_control_flow_exceptions_propagate(failure) -> None:
    service, volatile, durable, _, _, _ = _service(clock=Sequence(failure))

    with pytest.raises(type(failure)) as captured:
        service.create_session()

    assert captured.value is failure
    assert "create_session" not in volatile.calls + durable.calls


def test_repository_expected_failure_is_fixed_and_makes_no_partial_change() -> None:
    durable = CountingRepository()
    durable.failure = (
        "append_turn",
        ConversationRepositoryError(ConversationRepositoryErrorCode.UNAVAILABLE),
    )
    service, _, _, _, _, _ = _service(durable=durable)
    session = service.create_session()

    with pytest.raises(ConversationApplicationError) as captured:
        service.start_turn(
            session.session_id,
            expected_revision=1,
            user_message="Analyze",
        )

    assert captured.value.code is (
        ConversationApplicationErrorCode.REPOSITORY_FAILED
    )
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
    assert service.get_session(session.session_id) == session
    assert service.list_turns(session.session_id) == ()


class TupleSubclass(tuple):
    pass


def _durable_copy(session):
    return session.model_copy(
        update={
            "retention_policy": ConversationRetentionPolicy.THIRTY_DAYS,
            "expires_at": session.updated_at + timedelta(days=30),
        }
    )


def _two_turn_service():
    service, volatile, durable, _, _, _ = _service(
        clock=Sequence(
            NOW,
            NOW + timedelta(minutes=1),
            NOW + timedelta(minutes=2),
            NOW + timedelta(minutes=3),
        ),
        turn_ids=Sequence("conversation.turn.1", "conversation.turn.2"),
    )
    created = service.create_session()
    current, first = service.start_turn(
        created.session_id,
        expected_revision=1,
        user_message="First",
    )
    current, first = service.complete_turn(
        created.session_id,
        first.turn_id,
        expected_revision=current.revision,
        assistant_response="First result",
    )
    current, second = service.start_turn(
        created.session_id,
        expected_revision=current.revision,
        user_message="Second",
    )
    return service, volatile, durable, current, first, second


@pytest.mark.parametrize("different_payload", (False, True))
def test_lookup_rejects_same_session_id_in_both_repositories(
    different_payload,
) -> None:
    service, volatile, durable, _, _, _ = _service()
    session = service.create_session(ConversationRetentionPolicy.SESSION_ONLY)
    if different_payload:
        duplicate = _durable_copy(session).model_copy(
            update={"connection_context_id": "connection.other"}
        )
        durable.delegate.create_session(duplicate)
    else:
        durable.results["get_session"] = session
    volatile.calls.clear()
    durable.calls.clear()

    with pytest.raises(ConversationApplicationError) as captured:
        service.get_session(session.session_id)

    assert captured.value.code is (
        ConversationApplicationErrorCode.REPOSITORY_FAILED
    )
    assert volatile.calls == ["get_session"]
    assert durable.calls == ["get_session"]
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None


@pytest.mark.parametrize(
    ("owner", "policy"),
    (
        ("volatile", ConversationRetentionPolicy.THIRTY_DAYS),
        ("durable", ConversationRetentionPolicy.SESSION_ONLY),
    ),
)
def test_lookup_rejects_repository_retention_role_mismatch(
    owner,
    policy,
) -> None:
    volatile = CountingRepository()
    durable = CountingRepository()
    service, _, _, _, _, _ = _service(
        volatile=volatile,
        durable=durable,
    )
    seed, _, _, _, _, _ = _service()
    session = seed.create_session(policy)
    selected = volatile if owner == "volatile" else durable
    selected.results["get_session"] = session

    with pytest.raises(ConversationApplicationError) as captured:
        service.get_session(session.session_id)

    assert captured.value.code is (
        ConversationApplicationErrorCode.REPOSITORY_FAILED
    )
    assert volatile.calls == ["get_session"]
    assert durable.calls == ["get_session"]


def test_lookup_rejects_miscorrelated_session_and_inspects_both_roles() -> None:
    service, volatile, durable, _, _, _ = _service()
    requested = service.create_session()
    other = requested.model_copy(update={"session_id": "conversation.other"})
    durable.results["get_session"] = other
    volatile.calls.clear()
    durable.calls.clear()

    with pytest.raises(ConversationApplicationError) as captured:
        service.get_session(requested.session_id)

    assert captured.value.code is (
        ConversationApplicationErrorCode.REPOSITORY_FAILED
    )
    assert volatile.calls == ["get_session"]
    assert durable.calls == ["get_session"]
    assert "conversation.other" not in str(captured.value)


@pytest.mark.parametrize(
    "action",
    ("start", "complete", "fail", "close", "delete"),
)
def test_ambiguous_ownership_fails_before_every_mutation(action) -> None:
    service, volatile, durable, _, _, _ = _service()
    session = service.create_session(ConversationRetentionPolicy.SESSION_ONLY)
    durable.delegate.create_session(_durable_copy(session))
    volatile.calls.clear()
    durable.calls.clear()

    with pytest.raises(ConversationApplicationError) as captured:
        if action == "start":
            service.start_turn(
                session.session_id,
                expected_revision=1,
                user_message="Analyze",
            )
        elif action == "complete":
            service.complete_turn(
                session.session_id,
                "conversation.turn.unknown",
                expected_revision=1,
                assistant_response="Done",
            )
        elif action == "fail":
            service.fail_turn(
                session.session_id,
                "conversation.turn.unknown",
                expected_revision=1,
            )
        elif action == "close":
            service.close_session(session.session_id, expected_revision=1)
        else:
            service.delete_session(session.session_id)

    assert captured.value.code is (
        ConversationApplicationErrorCode.REPOSITORY_FAILED
    )
    mutation_names = {
        "append_turn",
        "replace_turn",
        "close_session",
        "delete_session",
    }
    assert mutation_names.isdisjoint(volatile.calls + durable.calls)


@pytest.mark.parametrize(
    "failure",
    (MemoryError(), KeyboardInterrupt(), SystemExit(), GeneratorExit()),
)
def test_lookup_resource_and_control_flow_remains_authoritative(failure) -> None:
    volatile = CountingRepository()
    durable = CountingRepository()
    volatile.results["get_session"] = failure
    service, _, _, _, _, _ = _service(
        volatile=volatile,
        durable=durable,
    )

    with pytest.raises(type(failure)) as captured:
        service.get_session("conversation.session.1")

    assert captured.value is failure
    assert durable.calls == []


@pytest.mark.parametrize("kind", ("wrong_id", "foreign_session", "wrong_slot"))
def test_get_turn_rejects_uncorrelated_repository_result(kind) -> None:
    service, _, durable, session, first, second = _two_turn_service()
    if kind == "wrong_id":
        returned = first.model_copy(update={"turn_id": "conversation.turn.other"})
    elif kind == "foreign_session":
        returned = first.model_copy(
            update={"session_id": "conversation.session.other"}
        )
    else:
        returned = second.model_copy(update={"sequence_number": 1})
    durable.results["get_turn"] = returned

    with pytest.raises(ConversationApplicationError) as captured:
        service.get_turn(session.session_id, first.turn_id)

    assert captured.value.code is (
        ConversationApplicationErrorCode.REPOSITORY_FAILED
    )
    assert "other" not in str(captured.value)


@pytest.mark.parametrize(
    "case",
    (
        "list",
        "tuple_subclass",
        "oversized",
        "duplicate",
        "reordered",
        "gapped",
        "foreign",
        "wrong_prefix",
    ),
)
def test_list_turns_rejects_noncanonical_or_uncorrelated_results(case) -> None:
    service, _, durable, session, first, second = _two_turn_service()
    if case == "list":
        result = [first]
    elif case == "tuple_subclass":
        result = TupleSubclass((first,))
    elif case == "oversized":
        result = (first, second)
    elif case == "duplicate":
        result = (first, first)
    elif case == "reordered":
        result = (second, first)
    elif case == "gapped":
        result = (second,)
    elif case == "foreign":
        result = (
            first.model_copy(
                update={"session_id": "conversation.session.other"}
            ),
        )
    else:
        result = (
            first.model_copy(update={"turn_id": "conversation.turn.other"}),
        )
    durable.results["list_turns"] = result
    limit = 1 if case == "oversized" else 100

    with pytest.raises(ConversationApplicationError) as captured:
        service.list_turns(session.session_id, limit=limit)

    assert captured.value.code is (
        ConversationApplicationErrorCode.REPOSITORY_FAILED
    )


def test_list_turns_accepts_exact_correlated_prefix() -> None:
    service, _, durable, session, first, _ = _two_turn_service()
    durable.results["list_turns"] = (first,)

    assert service.list_turns(session.session_id, limit=1) == (first,)


@pytest.mark.parametrize(
    "case",
    (
        "list",
        "tuple_subclass",
        "oversized",
        "duplicate_within",
        "wrong_volatile_role",
        "wrong_durable_role",
    ),
)
def test_list_sessions_rejects_noncanonical_bounded_or_role_results(case) -> None:
    service, volatile, durable, _, _, _ = _service(
        session_ids=Sequence(
            "conversation.session.volatile",
            "conversation.session.durable",
        ),
        clock=Sequence(NOW, NOW + timedelta(minutes=1)),
    )
    session_only = service.create_session(
        ConversationRetentionPolicy.SESSION_ONLY
    )
    durable_session = service.create_session(
        ConversationRetentionPolicy.THIRTY_DAYS
    )
    volatile.calls.clear()
    durable.calls.clear()
    if case == "list":
        volatile.results["list_sessions"] = [session_only]
    elif case == "tuple_subclass":
        volatile.results["list_sessions"] = TupleSubclass((session_only,))
    elif case == "oversized":
        volatile.results["list_sessions"] = (session_only, session_only)
    elif case == "duplicate_within":
        volatile.results["list_sessions"] = (session_only, session_only)
    elif case == "wrong_volatile_role":
        volatile.results["list_sessions"] = (durable_session,)
    else:
        durable.results["list_sessions"] = (session_only,)
    limit = 1 if case == "oversized" else 100

    with pytest.raises(ConversationApplicationError) as captured:
        service.list_sessions(limit=limit)

    assert captured.value.code is (
        ConversationApplicationErrorCode.REPOSITORY_FAILED
    )


def test_list_sessions_rejects_duplicate_id_across_repository_roles() -> None:
    service, volatile, durable, _, _, _ = _service()
    session_only = service.create_session(
        ConversationRetentionPolicy.SESSION_ONLY
    )
    volatile.results["list_sessions"] = (session_only,)
    durable.results["list_sessions"] = (_durable_copy(session_only),)

    with pytest.raises(ConversationApplicationError) as captured:
        service.list_sessions()

    assert captured.value.code is (
        ConversationApplicationErrorCode.REPOSITORY_FAILED
    )


def test_list_sessions_preserves_global_order_and_limit() -> None:
    service, _, _, _, _, _ = _service(
        session_ids=Sequence(
            "conversation.session.volatile",
            "conversation.session.durable",
        ),
        clock=Sequence(NOW, NOW + timedelta(minutes=1)),
    )
    older = service.create_session(ConversationRetentionPolicy.SESSION_ONLY)
    newer = service.create_session(ConversationRetentionPolicy.THIRTY_DAYS)

    assert service.list_sessions() == (newer, older)
    assert service.list_sessions(limit=1) == (newer,)


@pytest.mark.parametrize(
    "result",
    (
        ["conversation.session.1"],
        TupleSubclass(("conversation.session.1",)),
        iter(("conversation.session.1",)),
        {"conversation.session.1"},
        {"session": "conversation.session.1"},
        (["runtime-secret-marker"],),
        (object(),),
        ("conversation.session.1", "conversation.session.1"),
    ),
)
def test_purge_rejects_noncanonical_or_duplicate_results_without_leak(
    result,
) -> None:
    durable = CountingRepository()
    durable.results["purge_expired"] = result
    service, _, _, _, _, _ = _service(durable=durable)

    with pytest.raises(ConversationApplicationError) as captured:
        service.purge_expired()

    assert captured.value.code is (
        ConversationApplicationErrorCode.REPOSITORY_FAILED
    )
    assert "runtime-secret-marker" not in str(captured.value)
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None


def test_purge_rejects_oversized_exact_tuple() -> None:
    durable = CountingRepository()
    durable.results["purge_expired"] = (
        "conversation.session.1",
        "conversation.session.2",
    )
    service, _, _, _, _, _ = _service(durable=durable)

    with pytest.raises(ConversationApplicationError) as captured:
        service.purge_expired(limit=1)

    assert captured.value.code is (
        ConversationApplicationErrorCode.REPOSITORY_FAILED
    )


def test_marker_bearing_malformed_session_result_is_fixed_and_safe() -> None:
    volatile = CountingRepository()
    volatile.results["get_session"] = "runtime-secret-marker"
    service, _, durable, _, _, _ = _service(volatile=volatile)

    with pytest.raises(ConversationApplicationError) as captured:
        service.get_session("conversation.session.requested")

    assert captured.value.code is (
        ConversationApplicationErrorCode.REPOSITORY_FAILED
    )
    assert "runtime-secret-marker" not in str(captured.value)
    assert durable.calls == ["get_session"]
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
