"""Tests for canonical conversation session and turn contracts."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone

from pydantic import ValidationError
import pytest

from pmqa.conversation import (
    MAX_CONVERSATION_MESSAGE_LENGTH,
    ConversationContractValidationError,
    ConversationRetentionPolicy,
    ConversationSession,
    ConversationSessionStatus,
    ConversationTurn,
    ConversationTurnErrorCode,
    ConversationTurnStatus,
    conversation_expiration,
    conversation_turn_error_message,
)


NOW = datetime(2026, 7, 25, 12, tzinfo=timezone.utc)


def _session(**updates) -> ConversationSession:
    values = {
        "schema_version": "1",
        "session_id": "conversation.session.1",
        "revision": 1,
        "status": ConversationSessionStatus.ACTIVE,
        "retention_policy": ConversationRetentionPolicy.THIRTY_DAYS,
        "connection_context_id": "connection.local.1",
        "turn_ids": (),
        "created_at": NOW,
        "updated_at": NOW,
        "expires_at": NOW + timedelta(days=30),
    }
    values.update(updates)
    return ConversationSession(**values)


def _turn(
    status: ConversationTurnStatus = ConversationTurnStatus.PENDING,
    **updates,
) -> ConversationTurn:
    values = {
        "schema_version": "1",
        "turn_id": "conversation.turn.1",
        "session_id": "conversation.session.1",
        "sequence_number": 1,
        "status": status,
        "user_message": "Story risks?\nInclude boundary cases.",
        "assistant_response": None,
        "error_code": None,
        "error_message": None,
        "created_at": NOW,
        "completed_at": None,
    }
    if status is ConversationTurnStatus.COMPLETED:
        values.update(
            {
                "assistant_response": "Observed risks.",
                "completed_at": NOW + timedelta(seconds=1),
            }
        )
    elif status is ConversationTurnStatus.FAILED:
        code = ConversationTurnErrorCode.PROCESSING_FAILED
        values.update(
            {
                "error_code": code,
                "error_message": conversation_turn_error_message(code),
                "completed_at": NOW + timedelta(seconds=1),
            }
        )
    values.update(updates)
    return ConversationTurn(**values)


@pytest.mark.parametrize(
    ("policy", "expected"),
    (
        (ConversationRetentionPolicy.SESSION_ONLY, None),
        (ConversationRetentionPolicy.SEVEN_DAYS, NOW + timedelta(days=7)),
        (ConversationRetentionPolicy.THIRTY_DAYS, NOW + timedelta(days=30)),
        (ConversationRetentionPolicy.NINETY_DAYS, NOW + timedelta(days=90)),
    ),
)
def test_retention_policy_has_exact_expiration(policy, expected) -> None:
    assert conversation_expiration(policy, NOW) == expected
    assert policy.durable is (expected is not None)


def test_session_round_trip_copy_and_caller_collection_isolation() -> None:
    turn_ids = ["conversation.turn.1"]
    session = _session(
        revision=2,
        turn_ids=turn_ids,
        updated_at=NOW + timedelta(minutes=1),
        expires_at=NOW + timedelta(days=30, minutes=1),
    )
    turn_ids.append("conversation.turn.redirected")

    wire = session.to_dict()
    restored = ConversationSession.from_dict(deepcopy(wire))
    copied = session.model_copy(update={"status": ConversationSessionStatus.CLOSED})

    assert session.turn_ids == ("conversation.turn.1",)
    assert restored == session
    assert restored.to_dict() == wire
    assert copied.status is ConversationSessionStatus.CLOSED
    assert session.status is ConversationSessionStatus.ACTIVE
    with pytest.raises(TypeError):
        session.turn_ids[0] = "conversation.turn.redirected"


def test_session_only_has_no_expiration_and_durable_requires_exact_expiration() -> None:
    assert _session(
        retention_policy=ConversationRetentionPolicy.SESSION_ONLY,
        expires_at=None,
    ).expires_at is None

    with pytest.raises(ValidationError):
        _session(
            retention_policy=ConversationRetentionPolicy.SESSION_ONLY,
            expires_at=NOW,
        )
    with pytest.raises(ValidationError):
        _session(expires_at=None)
    with pytest.raises(ValidationError):
        _session(expires_at=NOW + timedelta(days=7))


@pytest.mark.parametrize(
    "status",
    (
        ConversationTurnStatus.PENDING,
        ConversationTurnStatus.COMPLETED,
        ConversationTurnStatus.FAILED,
    ),
)
def test_turn_lifecycles_round_trip_canonically(status) -> None:
    turn = _turn(status)

    assert ConversationTurn.from_dict(turn.to_dict()) == turn
    assert turn.model_copy() == turn


def test_completed_turn_preserves_observed_empty_assistant_response() -> None:
    turn = _turn(
        ConversationTurnStatus.COMPLETED,
        assistant_response="",
    )

    assert turn.assistant_response == ""
    assert turn.to_dict()["assistant_response"] == ""


@pytest.mark.parametrize("message", ("", " \n\t "))
def test_user_message_must_not_be_blank(message) -> None:
    with pytest.raises(ValidationError):
        _turn(user_message=message)


@pytest.mark.parametrize(
    "message",
    (
        "test the password field",
        "token usage is unavailable",
        "the selector is input[type=password]",
        "密码字段应接受 Unicode 文本",
        "Compare the access-token label without supplying a value",
    ),
)
def test_ordinary_qa_security_discussion_remains_valid(message) -> None:
    assert _turn(user_message=message).user_message == message


@pytest.mark.parametrize(
    "message",
    (
        "Authorization: Bearer runtime-secret-marker",
        "Cookie: session=runtime-secret-marker",
        "Set-Cookie: session=runtime-secret-marker",
        "password=runtime-secret-marker",
        "token: runtime-secret-marker",
        "api-key=runtime-secret-marker",
        "secret=runtime-secret-marker",
        "credential: runtime-secret-marker",
    ),
)
def test_recognizable_sensitive_text_is_rejected_without_marker(message) -> None:
    with pytest.raises(ValidationError) as direct:
        _turn(user_message=message)
    assert "runtime-secret-marker" not in str(direct.value)

    wire = _turn().to_dict()
    wire["user_message"] = message
    with pytest.raises(ConversationContractValidationError) as reconstructed:
        ConversationTurn.from_dict(wire)
    assert str(reconstructed.value) == "invalid PMQA conversation contract"
    assert "runtime-secret-marker" not in str(reconstructed.value)
    assert reconstructed.value.__cause__ is None
    assert reconstructed.value.__context__ is None


@pytest.mark.parametrize(
    "updates",
    (
        {"assistant_response": "unexpected"},
        {"completed_at": NOW},
        {"error_code": ConversationTurnErrorCode.PROCESSING_FAILED},
        {"error_message": "conversation processing failed"},
    ),
)
def test_pending_turn_rejects_terminal_fields(updates) -> None:
    with pytest.raises(ValidationError):
        _turn(**updates)


@pytest.mark.parametrize(
    "updates",
    (
        {"assistant_response": None},
        {"completed_at": None},
        {"error_code": ConversationTurnErrorCode.PROCESSING_FAILED},
        {"error_message": "conversation processing failed"},
    ),
)
def test_completed_turn_requires_only_response_and_completion(updates) -> None:
    with pytest.raises(ValidationError):
        _turn(ConversationTurnStatus.COMPLETED, **updates)


@pytest.mark.parametrize(
    "updates",
    (
        {"error_code": None},
        {"error_message": None},
        {"error_message": "runtime-secret-marker"},
        {"assistant_response": "unexpected"},
        {"completed_at": None},
    ),
)
def test_failed_turn_requires_only_fixed_safe_failure(updates) -> None:
    with pytest.raises(ValidationError) as captured:
        _turn(ConversationTurnStatus.FAILED, **updates)
    assert "runtime-secret-marker" not in str(captured.value)


def test_terminal_completion_cannot_precede_creation() -> None:
    with pytest.raises(ValidationError):
        _turn(
            ConversationTurnStatus.COMPLETED,
            completed_at=NOW - timedelta(microseconds=1),
        )


@pytest.mark.parametrize(
    ("factory", "updates"),
    (
        (_session, {"session_id": "../session"}),
        (_session, {"revision": True}),
        (_session, {"revision": 2 ** 63}),
        (_session, {"status": "ACTIVE"}),
        (_session, {"retention_policy": "forever"}),
        (_session, {"created_at": NOW.replace(tzinfo=None)}),
        (_session, {"updated_at": NOW - timedelta(seconds=1)}),
        (_session, {"turn_ids": ("conversation.turn.1", "conversation.turn.1")}),
        (_turn, {"turn_id": "../turn"}),
        (_turn, {"sequence_number": 0}),
        (_turn, {"sequence_number": True}),
        (_turn, {"status": "COMPLETED"}),
        (_turn, {"user_message": "a" * (MAX_CONVERSATION_MESSAGE_LENGTH + 1)}),
        (_turn, {"user_message": object()}),
        (_turn, {"user_message": "invalid\u0000text"}),
        (_turn, {"created_at": NOW.replace(tzinfo=None)}),
    ),
)
def test_contracts_reject_invalid_values(factory, updates) -> None:
    with pytest.raises(ValidationError):
        factory(**updates)


def test_model_copy_fully_revalidates() -> None:
    with pytest.raises(ValidationError):
        _session().model_copy(update={"expires_at": None})
    with pytest.raises(ValidationError):
        _turn().model_copy(update={"status": ConversationTurnStatus.COMPLETED})


def test_from_dict_rejects_unknown_coercive_runtime_and_nonfinite_values() -> None:
    wire = _session().to_dict()
    cases = []
    unknown = deepcopy(wire)
    unknown["credentials"] = "runtime-secret-marker"
    cases.append(unknown)
    coercive = deepcopy(wire)
    coercive["revision"] = "1"
    cases.append(coercive)
    runtime = deepcopy(wire)
    runtime["revision"] = object()
    cases.append(runtime)
    nonfinite = deepcopy(wire)
    nonfinite["revision"] = float("nan")
    cases.append(nonfinite)

    for candidate in cases:
        with pytest.raises(ConversationContractValidationError) as captured:
            ConversationSession.from_dict(candidate)
        assert str(captured.value) == "invalid PMQA conversation contract"
        assert "runtime-secret-marker" not in str(captured.value)


def test_from_dict_rejects_cycles_and_overdeep_trees_safely() -> None:
    cyclic = _session().to_dict()
    cyclic["unknown"] = cyclic
    nested = _session().to_dict()
    value = nested
    for _ in range(20):
        child = {}
        value["unknown"] = child
        value = child

    for wire in (cyclic, nested):
        with pytest.raises(ConversationContractValidationError) as captured:
            ConversationSession.from_dict(wire)
        assert str(captured.value) == "invalid PMQA conversation contract"


def test_canonical_timestamp_wire_is_utc_z_with_fixed_precision() -> None:
    session = _session(
        created_at=datetime(
            2026,
            7,
            25,
            8,
            tzinfo=timezone(timedelta(hours=-4)),
        ),
        updated_at=datetime(
            2026,
            7,
            25,
            8,
            tzinfo=timezone(timedelta(hours=-4)),
        ),
        expires_at=datetime(
            2026,
            8,
            24,
            8,
            tzinfo=timezone(timedelta(hours=-4)),
        ),
    )

    assert session.to_dict()["created_at"] == "2026-07-25T12:00:00.000000Z"
