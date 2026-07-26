"""Deterministic application service for local conversation lifecycle."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional, Tuple
from uuid import uuid4

from pydantic import ValidationError

from pmqa.conversation.contracts import (
    CONVERSATION_SCHEMA_VERSION,
    DEFAULT_CONVERSATION_LIST_LIMIT,
    MAX_CONVERSATION_MESSAGE_LENGTH,
    MAX_CONVERSATION_TURNS,
    ConversationRetentionPolicy,
    ConversationSession,
    ConversationSessionStatus,
    ConversationTurn,
    ConversationTurnErrorCode,
    ConversationTurnStatus,
    conversation_expiration,
    conversation_turn_error_message,
    validate_conversation_list_limit,
    validate_conversation_timestamp,
)
from pmqa.conversation.repository import (
    ConversationRepository,
    ConversationRepositoryError,
    ConversationRepositoryErrorCode,
)
from pmqa.run import validate_run_identifier
from pmqa.security.sensitive_text import contains_recognizable_sensitive_text


DEFAULT_CONVERSATION_RETENTION = ConversationRetentionPolicy.THIRTY_DAYS

_RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS = (
    MemoryError,
    KeyboardInterrupt,
    SystemExit,
    GeneratorExit,
)


class ConversationApplicationErrorCode(str, Enum):
    """Stable safe application failure classifications."""

    INVALID_REQUEST = "invalid_request"
    INVALID_CLOCK = "invalid_clock"
    INVALID_ID_GENERATOR = "invalid_id_generator"
    SENSITIVE_TEXT_REJECTED = "sensitive_text_rejected"
    SESSION_NOT_FOUND = "session_not_found"
    TURN_NOT_FOUND = "turn_not_found"
    IDENTIFIER_CONFLICT = "identifier_conflict"
    REVISION_CONFLICT = "revision_conflict"
    STATE_CONFLICT = "state_conflict"
    SESSION_CLOSED = "session_closed"
    TURN_LIMIT_REACHED = "turn_limit_reached"
    REPOSITORY_FAILED = "repository_failed"


_APPLICATION_ERROR_MESSAGES = {
    ConversationApplicationErrorCode.INVALID_REQUEST:
        "invalid conversation application request",
    ConversationApplicationErrorCode.INVALID_CLOCK:
        "invalid conversation application clock",
    ConversationApplicationErrorCode.INVALID_ID_GENERATOR:
        "invalid conversation identifier generator",
    ConversationApplicationErrorCode.SENSITIVE_TEXT_REJECTED:
        "conversation text contains sensitive material",
    ConversationApplicationErrorCode.SESSION_NOT_FOUND:
        "conversation session was not found",
    ConversationApplicationErrorCode.TURN_NOT_FOUND:
        "conversation turn was not found",
    ConversationApplicationErrorCode.IDENTIFIER_CONFLICT:
        "conversation identifier already exists",
    ConversationApplicationErrorCode.REVISION_CONFLICT:
        "conversation session revision conflict",
    ConversationApplicationErrorCode.STATE_CONFLICT:
        "conversation state transition conflict",
    ConversationApplicationErrorCode.SESSION_CLOSED:
        "conversation session is closed",
    ConversationApplicationErrorCode.TURN_LIMIT_REACHED:
        "conversation session reached its turn limit",
    ConversationApplicationErrorCode.REPOSITORY_FAILED:
        "conversation repository operation failed",
}


class ConversationApplicationError(RuntimeError):
    """Expose only one fixed application code and safe message."""

    def __init__(self, code: ConversationApplicationErrorCode) -> None:
        if type(code) is not ConversationApplicationErrorCode:
            raise TypeError("code must be a ConversationApplicationErrorCode")
        self.code = code
        super().__init__(_APPLICATION_ERROR_MESSAGES[code])


def _safe_application_method(method):
    @wraps(method)
    def boundary(*args, **kwargs):
        failure = None
        try:
            return method(*args, **kwargs)
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except ConversationApplicationError as error:
            failure = error.code
        if failure is not None:
            _raise_application_error(failure)

    return boundary


def _safe_application_class(cls):
    for name in (
        "__init__",
        "create_session",
        "get_session",
        "list_sessions",
        "get_turn",
        "list_turns",
        "start_turn",
        "complete_turn",
        "fail_turn",
        "close_session",
        "delete_session",
        "purge_expired",
    ):
        if name in cls.__dict__:
            setattr(cls, name, _safe_application_method(getattr(cls, name)))
    return cls


@_safe_application_class
class ConversationApplicationService:
    """Coordinate canonical sessions and turns across explicit repositories."""

    __slots__ = (
        "_clock",
        "_durable_repository",
        "_session_id_generator",
        "_turn_id_generator",
        "_volatile_repository",
    )

    def __init__(
        self,
        *,
        volatile_repository: ConversationRepository,
        durable_repository: ConversationRepository,
        clock: Callable[[], datetime],
        session_id_generator: Optional[Callable[[], str]] = None,
        turn_id_generator: Optional[Callable[[], str]] = None,
    ) -> None:
        if (
            not isinstance(volatile_repository, ConversationRepository)
            or not isinstance(durable_repository, ConversationRepository)
            or volatile_repository is durable_repository
        ):
            _raise_application_error(
                ConversationApplicationErrorCode.INVALID_REQUEST
            )
        selected_session_generator = (
            _default_session_id
            if session_id_generator is None
            else session_id_generator
        )
        selected_turn_generator = (
            _default_turn_id
            if turn_id_generator is None
            else turn_id_generator
        )
        if not callable(clock):
            _raise_application_error(
                ConversationApplicationErrorCode.INVALID_CLOCK
            )
        if not callable(selected_session_generator) or not callable(
            selected_turn_generator
        ):
            _raise_application_error(
                ConversationApplicationErrorCode.INVALID_ID_GENERATOR
            )
        self._volatile_repository = volatile_repository
        self._durable_repository = durable_repository
        self._clock = clock
        self._session_id_generator = selected_session_generator
        self._turn_id_generator = selected_turn_generator

    def create_session(
        self,
        retention_policy: ConversationRetentionPolicy = (
            DEFAULT_CONVERSATION_RETENTION
        ),
        *,
        connection_context_id: Optional[str] = None,
    ) -> ConversationSession:
        policy = _canonical_policy(retention_policy)
        context_id = _canonical_optional_identifier(connection_context_id)
        now = self._sample_clock()
        session_id = self._sample_identifier(
            self._session_id_generator,
        )
        self._ensure_session_identifier_available(session_id)
        session = ConversationSession(
            schema_version=CONVERSATION_SCHEMA_VERSION,
            session_id=session_id,
            revision=1,
            status=ConversationSessionStatus.ACTIVE,
            retention_policy=policy,
            connection_context_id=context_id,
            turn_ids=(),
            created_at=now,
            updated_at=now,
            expires_at=conversation_expiration(policy, now),
        )
        repository = self._repository_for_policy(policy)
        self._create_session(repository, session)
        return _session_snapshot(session)

    def get_session(self, session_id: str) -> ConversationSession:
        _, session = self._find_session(_canonical_identifier(session_id))
        return _session_snapshot(session)

    def list_sessions(
        self,
        limit: int = DEFAULT_CONVERSATION_LIST_LIMIT,
    ) -> Tuple[ConversationSession, ...]:
        canonical_limit = _canonical_limit(limit)
        volatile = self._list_sessions(
            self._volatile_repository,
            canonical_limit,
            volatile=True,
        )
        durable = self._list_sessions(
            self._durable_repository,
            canonical_limit,
            volatile=False,
        )
        combined = volatile + durable
        identities = tuple(item.session_id for item in combined)
        if len(identities) != len(set(identities)):
            _raise_application_error(
                ConversationApplicationErrorCode.REPOSITORY_FAILED
            )
        by_identifier = sorted(combined, key=lambda item: item.session_id)
        ordered = sorted(
            by_identifier,
            key=lambda item: item.updated_at,
            reverse=True,
        )
        return tuple(
            _session_snapshot(item) for item in ordered[:canonical_limit]
        )

    def get_turn(self, session_id: str, turn_id: str) -> ConversationTurn:
        canonical_session_id = _canonical_identifier(session_id)
        canonical_turn_id = _canonical_identifier(turn_id)
        repository, session = self._find_session(canonical_session_id)
        turn = self._get_turn(
            repository,
            session,
            canonical_turn_id,
        )
        return _turn_snapshot(turn)

    def list_turns(
        self,
        session_id: str,
        limit: int = DEFAULT_CONVERSATION_LIST_LIMIT,
    ) -> Tuple[ConversationTurn, ...]:
        canonical_id = _canonical_identifier(session_id)
        canonical_limit = _canonical_limit(limit)
        repository, session = self._find_session(canonical_id)
        try:
            turns = repository.list_turns(canonical_id, canonical_limit)
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except ConversationRepositoryError as error:
            self._raise_repository_failure(error)
        if type(turns) is not tuple or len(turns) > canonical_limit:
            _raise_application_error(
                ConversationApplicationErrorCode.REPOSITORY_FAILED
            )
        canonical_turns = tuple(_turn_snapshot(turn) for turn in turns)
        turn_ids = tuple(turn.turn_id for turn in canonical_turns)
        if (
            any(
                turn.session_id != canonical_id for turn in canonical_turns
            )
            or tuple(turn.sequence_number for turn in canonical_turns)
            != tuple(range(1, len(canonical_turns) + 1))
            or len(set(turn_ids)) != len(turn_ids)
            or turn_ids != session.turn_ids[:len(canonical_turns)]
        ):
            _raise_application_error(
                ConversationApplicationErrorCode.REPOSITORY_FAILED
            )
        return canonical_turns

    def start_turn(
        self,
        session_id: str,
        *,
        expected_revision: int,
        user_message: str,
    ) -> Tuple[ConversationSession, ConversationTurn]:
        canonical_id = _canonical_identifier(session_id)
        canonical_revision = _canonical_revision(expected_revision)
        _inspect_text(user_message)
        now = self._sample_clock()
        turn_id = self._sample_identifier(self._turn_id_generator)
        self._ensure_turn_identifier_available(turn_id)
        repository, current = self._find_session(canonical_id)
        if current.status is ConversationSessionStatus.CLOSED:
            _raise_application_error(
                ConversationApplicationErrorCode.SESSION_CLOSED
            )
        if len(current.turn_ids) >= MAX_CONVERSATION_TURNS:
            _raise_application_error(
                ConversationApplicationErrorCode.TURN_LIMIT_REACHED
            )
        turn = self._build_pending_turn(
            current,
            turn_id,
            user_message,
            now,
        )
        updated = self._advance_session(current, now, turn_id=turn_id)
        try:
            repository.append_turn(
                expected_revision=canonical_revision,
                session=updated,
                turn=turn,
            )
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except ConversationRepositoryError as error:
            self._raise_repository_failure(error)
        return _session_snapshot(updated), _turn_snapshot(turn)

    def complete_turn(
        self,
        session_id: str,
        turn_id: str,
        *,
        expected_revision: int,
        assistant_response: str,
    ) -> Tuple[ConversationSession, ConversationTurn]:
        _inspect_text(assistant_response, allow_empty=True)
        return self._terminalize_turn(
            session_id,
            turn_id,
            expected_revision=expected_revision,
            assistant_response=assistant_response,
            error_code=None,
        )

    def fail_turn(
        self,
        session_id: str,
        turn_id: str,
        *,
        expected_revision: int,
        error_code: ConversationTurnErrorCode = (
            ConversationTurnErrorCode.PROCESSING_FAILED
        ),
    ) -> Tuple[ConversationSession, ConversationTurn]:
        canonical_error_code = _canonical_turn_error_code(error_code)
        return self._terminalize_turn(
            session_id,
            turn_id,
            expected_revision=expected_revision,
            assistant_response=None,
            error_code=canonical_error_code,
        )

    def close_session(
        self,
        session_id: str,
        *,
        expected_revision: int,
    ) -> ConversationSession:
        canonical_id = _canonical_identifier(session_id)
        canonical_revision = _canonical_revision(expected_revision)
        now = self._sample_clock()
        repository, current = self._find_session(canonical_id)
        if current.status is ConversationSessionStatus.CLOSED:
            _raise_application_error(
                ConversationApplicationErrorCode.SESSION_CLOSED
            )
        updated = self._advance_session(
            current,
            now,
            status=ConversationSessionStatus.CLOSED,
        )
        try:
            repository.close_session(
                expected_revision=canonical_revision,
                session=updated,
            )
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except ConversationRepositoryError as error:
            self._raise_repository_failure(error)
        return _session_snapshot(updated)

    def delete_session(self, session_id: str) -> None:
        canonical_id = _canonical_identifier(session_id)
        repository, _ = self._find_session(canonical_id)
        try:
            repository.delete_session(canonical_id)
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except ConversationRepositoryError as error:
            self._raise_repository_failure(error)

    def purge_expired(
        self,
        limit: int = MAX_CONVERSATION_TURNS,
    ) -> Tuple[str, ...]:
        canonical_limit = _canonical_limit(limit)
        cutoff = self._sample_clock()
        try:
            session_ids = self._durable_repository.purge_expired(
                cutoff,
                canonical_limit,
            )
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except ConversationRepositoryError as error:
            self._raise_repository_failure(error)
        if type(session_ids) is not tuple or len(session_ids) > canonical_limit:
            _raise_application_error(
                ConversationApplicationErrorCode.REPOSITORY_FAILED
            )
        try:
            canonical_ids = tuple(
                validate_run_identifier(item) for item in session_ids
            )
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except Exception:
            _raise_application_error(
                ConversationApplicationErrorCode.REPOSITORY_FAILED
            )
        if len(canonical_ids) != len(set(canonical_ids)):
            _raise_application_error(
                ConversationApplicationErrorCode.REPOSITORY_FAILED
            )
        return canonical_ids

    def _terminalize_turn(
        self,
        session_id: str,
        turn_id: str,
        *,
        expected_revision: int,
        assistant_response: Optional[str],
        error_code: Optional[ConversationTurnErrorCode],
    ) -> Tuple[ConversationSession, ConversationTurn]:
        canonical_session_id = _canonical_identifier(session_id)
        canonical_turn_id = _canonical_identifier(turn_id)
        canonical_revision = _canonical_revision(expected_revision)
        now = self._sample_clock()
        repository, current_session = self._find_session(
            canonical_session_id
        )
        if current_session.status is ConversationSessionStatus.CLOSED:
            _raise_application_error(
                ConversationApplicationErrorCode.SESSION_CLOSED
            )
        current_turn = self._get_turn(
            repository,
            current_session,
            canonical_turn_id,
        )
        if error_code is None:
            turn = current_turn.model_copy(
                update={
                    "status": ConversationTurnStatus.COMPLETED,
                    "assistant_response": assistant_response,
                    "completed_at": now,
                }
            )
        else:
            turn = current_turn.model_copy(
                update={
                    "status": ConversationTurnStatus.FAILED,
                    "error_code": error_code,
                    "error_message": conversation_turn_error_message(
                        error_code
                    ),
                    "completed_at": now,
                }
            )
        updated = self._advance_session(current_session, now)
        try:
            repository.replace_turn(
                expected_revision=canonical_revision,
                session=updated,
                turn=turn,
            )
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except ConversationRepositoryError as error:
            self._raise_repository_failure(error)
        return _session_snapshot(updated), _turn_snapshot(turn)

    def _sample_clock(self) -> datetime:
        try:
            value = self._clock()
            return validate_conversation_timestamp(value, "clock")
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except Exception:
            _raise_application_error(
                ConversationApplicationErrorCode.INVALID_CLOCK
            )

    @staticmethod
    def _sample_identifier(generator: Callable[[], str]) -> str:
        try:
            return validate_run_identifier(generator())
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except Exception:
            _raise_application_error(
                ConversationApplicationErrorCode.INVALID_ID_GENERATOR
            )

    def _repository_for_policy(
        self,
        policy: ConversationRetentionPolicy,
    ) -> ConversationRepository:
        if policy is ConversationRetentionPolicy.SESSION_ONLY:
            return self._volatile_repository
        return self._durable_repository

    def _find_session(
        self,
        session_id: str,
    ) -> Tuple[ConversationRepository, ConversationSession]:
        matches = []
        malformed = False
        for repository, volatile in (
            (self._volatile_repository, True),
            (self._durable_repository, False),
        ):
            try:
                session = repository.get_session(session_id)
            except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
                raise
            except ConversationRepositoryError as error:
                if error.code is ConversationRepositoryErrorCode.NOT_FOUND:
                    continue
                malformed = True
                continue
            try:
                canonical_session = _session_snapshot(session)
                if (
                    canonical_session.session_id != session_id
                    or (
                        volatile
                        and canonical_session.retention_policy
                        is not ConversationRetentionPolicy.SESSION_ONLY
                    )
                    or (
                        not volatile
                        and not canonical_session.retention_policy.durable
                    )
                ):
                    _raise_application_error(
                        ConversationApplicationErrorCode.REPOSITORY_FAILED
                    )
            except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
                raise
            except ConversationApplicationError:
                malformed = True
                continue
            matches.append((repository, canonical_session))
        if malformed or len(matches) > 1:
            _raise_application_error(
                ConversationApplicationErrorCode.REPOSITORY_FAILED
            )
        if matches:
            return matches[0]
        _raise_application_error(
            ConversationApplicationErrorCode.SESSION_NOT_FOUND
        )

    def _ensure_session_identifier_available(self, session_id: str) -> None:
        for repository, volatile in (
            (self._volatile_repository, True),
            (self._durable_repository, False),
        ):
            try:
                session = repository.get_session(session_id)
            except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
                raise
            except ConversationRepositoryError as error:
                if error.code is ConversationRepositoryErrorCode.NOT_FOUND:
                    continue
                self._raise_repository_failure(error)
            canonical_session = _session_snapshot(session)
            if (
                canonical_session.session_id != session_id
                or (
                    volatile
                    and canonical_session.retention_policy
                    is not ConversationRetentionPolicy.SESSION_ONLY
                )
                or (
                    not volatile
                    and not canonical_session.retention_policy.durable
                )
            ):
                _raise_application_error(
                    ConversationApplicationErrorCode.REPOSITORY_FAILED
                )
            _raise_application_error(
                ConversationApplicationErrorCode.IDENTIFIER_CONFLICT
            )

    def _ensure_turn_identifier_available(self, turn_id: str) -> None:
        for repository in (
            self._volatile_repository,
            self._durable_repository,
        ):
            try:
                turn = repository.get_turn(turn_id)
            except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
                raise
            except ConversationRepositoryError as error:
                if error.code is ConversationRepositoryErrorCode.NOT_FOUND:
                    continue
                self._raise_repository_failure(error)
            if _turn_snapshot(turn).turn_id != turn_id:
                _raise_application_error(
                    ConversationApplicationErrorCode.REPOSITORY_FAILED
                )
            _raise_application_error(
                ConversationApplicationErrorCode.IDENTIFIER_CONFLICT
            )

    @staticmethod
    def _get_turn(
        repository: ConversationRepository,
        session: ConversationSession,
        turn_id: str,
    ) -> ConversationTurn:
        try:
            turn = _turn_snapshot(repository.get_turn(turn_id))
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except ConversationRepositoryError as error:
            if error.code is ConversationRepositoryErrorCode.NOT_FOUND:
                _raise_application_error(
                    ConversationApplicationErrorCode.TURN_NOT_FOUND
                )
            ConversationApplicationService._raise_repository_failure(error)
        sequence_index = turn.sequence_number - 1
        if (
            turn.turn_id != turn_id
            or turn.session_id != session.session_id
            or sequence_index < 0
            or sequence_index >= len(session.turn_ids)
            or session.turn_ids[sequence_index] != turn_id
        ):
            _raise_application_error(
                ConversationApplicationErrorCode.REPOSITORY_FAILED
            )
        return turn

    @staticmethod
    def _create_session(
        repository: ConversationRepository,
        session: ConversationSession,
    ) -> None:
        try:
            repository.create_session(_session_snapshot(session))
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except ConversationRepositoryError as error:
            ConversationApplicationService._raise_repository_failure(error)

    @staticmethod
    def _list_sessions(
        repository: ConversationRepository,
        limit: int,
        *,
        volatile: bool,
    ) -> Tuple[ConversationSession, ...]:
        try:
            sessions = repository.list_sessions(limit)
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except ConversationRepositoryError as error:
            ConversationApplicationService._raise_repository_failure(error)
        if type(sessions) is not tuple or len(sessions) > limit:
            _raise_application_error(
                ConversationApplicationErrorCode.REPOSITORY_FAILED
            )
        canonical_sessions = tuple(
            _session_snapshot(item) for item in sessions
        )
        identities = tuple(item.session_id for item in canonical_sessions)
        if (
            len(identities) != len(set(identities))
            or any(
                (
                    item.retention_policy
                    is not ConversationRetentionPolicy.SESSION_ONLY
                )
                if volatile
                else not item.retention_policy.durable
                for item in canonical_sessions
            )
        ):
            _raise_application_error(
                ConversationApplicationErrorCode.REPOSITORY_FAILED
            )
        return canonical_sessions

    @staticmethod
    def _build_pending_turn(
        session: ConversationSession,
        turn_id: str,
        user_message: str,
        now: datetime,
    ) -> ConversationTurn:
        try:
            return ConversationTurn(
                schema_version=CONVERSATION_SCHEMA_VERSION,
                turn_id=turn_id,
                session_id=session.session_id,
                sequence_number=len(session.turn_ids) + 1,
                status=ConversationTurnStatus.PENDING,
                user_message=user_message,
                assistant_response=None,
                error_code=None,
                error_message=None,
                created_at=now,
                completed_at=None,
            )
        except ValidationError:
            _raise_application_error(
                ConversationApplicationErrorCode.INVALID_REQUEST
            )

    @staticmethod
    def _advance_session(
        session: ConversationSession,
        now: datetime,
        *,
        turn_id: Optional[str] = None,
        status: Optional[ConversationSessionStatus] = None,
    ) -> ConversationSession:
        turn_ids = (
            session.turn_ids
            if turn_id is None
            else session.turn_ids + (turn_id,)
        )
        selected_status = session.status if status is None else status
        try:
            return session.model_copy(
                update={
                    "revision": session.revision + 1,
                    "status": selected_status,
                    "turn_ids": turn_ids,
                    "updated_at": now,
                    "expires_at": conversation_expiration(
                        session.retention_policy,
                        now,
                    ),
                }
            )
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except Exception:
            _raise_application_error(
                ConversationApplicationErrorCode.STATE_CONFLICT
            )

    @staticmethod
    def _raise_repository_failure(
        error: ConversationRepositoryError,
    ) -> None:
        mapping = {
            ConversationRepositoryErrorCode.DUPLICATE:
                ConversationApplicationErrorCode.IDENTIFIER_CONFLICT,
            ConversationRepositoryErrorCode.REVISION_CONFLICT:
                ConversationApplicationErrorCode.REVISION_CONFLICT,
            ConversationRepositoryErrorCode.STATE_CONFLICT:
                ConversationApplicationErrorCode.STATE_CONFLICT,
        }
        _raise_application_error(
            mapping.get(
                error.code,
                ConversationApplicationErrorCode.REPOSITORY_FAILED,
            )
        )


def _inspect_text(value: Any, *, allow_empty: bool = False) -> None:
    if (
        type(value) is not str
        or len(value) > MAX_CONVERSATION_MESSAGE_LENGTH
        or (not allow_empty and not value.strip())
        or any(
            not character.isprintable() and character not in "\r\n\t"
            for character in value
        )
    ):
        _raise_application_error(
            ConversationApplicationErrorCode.INVALID_REQUEST
        )
    try:
        sensitive = contains_recognizable_sensitive_text(value)
    except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
        raise
    except Exception:
        _raise_application_error(
            ConversationApplicationErrorCode.INVALID_REQUEST
        )
    if sensitive:
        _raise_application_error(
            ConversationApplicationErrorCode.SENSITIVE_TEXT_REJECTED
        )


def _canonical_policy(value: Any) -> ConversationRetentionPolicy:
    if type(value) is not ConversationRetentionPolicy:
        _raise_application_error(
            ConversationApplicationErrorCode.INVALID_REQUEST
        )
    return value


def _canonical_identifier(value: Any) -> str:
    try:
        return validate_run_identifier(value)
    except Exception:
        _raise_application_error(
            ConversationApplicationErrorCode.INVALID_REQUEST
        )


def _canonical_optional_identifier(value: Any) -> Optional[str]:
    if value is None:
        return None
    return _canonical_identifier(value)


def _canonical_revision(value: Any) -> int:
    if type(value) is not int or value < 1:
        _raise_application_error(
            ConversationApplicationErrorCode.INVALID_REQUEST
        )
    return value


def _canonical_limit(value: Any) -> int:
    try:
        return validate_conversation_list_limit(value)
    except Exception:
        _raise_application_error(
            ConversationApplicationErrorCode.INVALID_REQUEST
        )


def _canonical_turn_error_code(value: Any) -> ConversationTurnErrorCode:
    if type(value) is not ConversationTurnErrorCode:
        _raise_application_error(
            ConversationApplicationErrorCode.INVALID_REQUEST
        )
    return value


def _session_snapshot(value: Any) -> ConversationSession:
    if type(value) is not ConversationSession:
        _raise_application_error(
            ConversationApplicationErrorCode.REPOSITORY_FAILED
        )
    try:
        return ConversationSession.from_dict(value.to_dict())
    except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
        raise
    except Exception:
        _raise_application_error(
            ConversationApplicationErrorCode.REPOSITORY_FAILED
        )


def _turn_snapshot(value: Any) -> ConversationTurn:
    if type(value) is not ConversationTurn:
        _raise_application_error(
            ConversationApplicationErrorCode.REPOSITORY_FAILED
        )
    try:
        return ConversationTurn.from_dict(value.to_dict())
    except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
        raise
    except Exception:
        _raise_application_error(
            ConversationApplicationErrorCode.REPOSITORY_FAILED
        )


def _default_session_id() -> str:
    return f"conversation.session.{uuid4().hex}"


def _default_turn_id() -> str:
    return f"conversation.turn.{uuid4().hex}"


def _raise_application_error(
    code: ConversationApplicationErrorCode,
) -> None:
    raise ConversationApplicationError(code) from None


__all__ = [
    "DEFAULT_CONVERSATION_RETENTION",
    "ConversationApplicationError",
    "ConversationApplicationErrorCode",
    "ConversationApplicationService",
]
