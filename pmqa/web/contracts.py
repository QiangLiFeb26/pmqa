"""Strict immutable contracts for the PMQA local API v1 boundary."""

from __future__ import annotations

import json
import math
from typing import Any, Dict, Literal, Optional, Tuple, TypeVar

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from pmqa.conversation import (
    DEFAULT_CONVERSATION_RETENTION,
    MAX_CONVERSATION_MESSAGE_LENGTH,
    MAX_CONVERSATION_REVISION,
    ConversationRetentionPolicy,
    ConversationSession,
    ConversationTurn,
)
from pmqa.run import WorkflowDefinition, validate_run_identifier


WEB_API_SCHEMA_VERSION = "1"
MAX_WEB_REQUEST_BODY_BYTES = 64 * 1024
_INVALID_CONTRACT_MESSAGE = "invalid PMQA Web API contract"
_MAX_JSON_TREE_DEPTH = 16
_MAX_JSON_TREE_ITEMS = 2048
_MAX_JSON_TREE_STRING_LENGTH = 32 * 1024

_ContractT = TypeVar("_ContractT", bound="_WebContract")


class WebAPIContractValidationError(ValueError):
    """Report one fixed API-contract validation failure."""

    def __init__(self) -> None:
        super().__init__(_INVALID_CONTRACT_MESSAGE)


class _WebContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        strict=True,
        defer_build=True,
    )

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")

    def model_copy(
        self: _ContractT,
        *,
        update: Optional[Dict[str, Any]] = None,
        deep: bool = False,
    ) -> _ContractT:
        _ = deep
        if update is not None and type(update) is not dict:
            raise WebAPIContractValidationError() from None
        values = {
            name: getattr(self, name)
            for name in type(self).model_fields
        }
        values.update(update or {})
        try:
            return type(self).model_validate(values)
        except (
            ValidationError,
            TypeError,
            ValueError,
        ):
            raise WebAPIContractValidationError() from None

    @classmethod
    def from_dict(cls: type[_ContractT], value: Any) -> _ContractT:
        if (
            type(value) is not dict
            or not _bounded_plain_json(value)
        ):
            raise WebAPIContractValidationError() from None
        try:
            result = cls.model_validate(cls._wire_values(value))
        except (
            ValidationError,
            TypeError,
            ValueError,
        ):
            pass
        else:
            if value == result.to_dict():
                return result
        raise WebAPIContractValidationError() from None

    @classmethod
    def _wire_values(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        return dict(value)


class HealthResponse(_WebContract):
    schema_version: Literal["1"]
    api_version: Literal["v1"]
    readiness: Literal["ready"]


class WorkflowCatalogResponse(_WebContract):
    schema_version: Literal["1"]
    workflows: Tuple[WorkflowDefinition, ...]

    @field_validator("workflows", mode="before")
    @classmethod
    def snapshot_workflows(cls, value: Any) -> Tuple[WorkflowDefinition, ...]:
        if type(value) is not tuple:
            raise ValueError("workflows must be an exact tuple")
        return tuple(_workflow_snapshot(item) for item in value)

    @classmethod
    def _wire_values(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        selected = dict(value)
        workflows = selected.get("workflows")
        if type(workflows) is not list:
            raise ValueError("workflows must be a canonical array")
        selected["workflows"] = tuple(
            WorkflowDefinition.from_dict(item) for item in workflows
        )
        return selected


class CreateSessionRequest(_WebContract):
    schema_version: Literal["1"]
    retention_policy: ConversationRetentionPolicy = (
        DEFAULT_CONVERSATION_RETENTION
    )
    connection_context_id: Optional[str] = None

    @classmethod
    def from_dict(cls, value: Any) -> "CreateSessionRequest":
        if type(value) is not dict:
            raise WebAPIContractValidationError() from None
        selected = dict(value)
        selected.setdefault(
            "retention_policy",
            DEFAULT_CONVERSATION_RETENTION.value,
        )
        selected.setdefault("connection_context_id", None)
        return super().from_dict(selected)

    @classmethod
    def _wire_values(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        selected = dict(value)
        policy = selected.get("retention_policy")
        if type(policy) is not str:
            raise ValueError("retention policy must be canonical")
        selected["retention_policy"] = ConversationRetentionPolicy(policy)
        return selected

    @field_validator("retention_policy", mode="before")
    @classmethod
    def parse_retention_policy(
        cls,
        value: Any,
    ) -> ConversationRetentionPolicy:
        if type(value) is not ConversationRetentionPolicy:
            raise ValueError("retention policy must be canonical")
        return value

    @field_validator("connection_context_id")
    @classmethod
    def validate_connection_context_id(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        return None if value is None else validate_run_identifier(value)


class CloseSessionRequest(_WebContract):
    schema_version: Literal["1"]
    session_id: str
    expected_revision: int

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, value: str) -> str:
        return validate_run_identifier(value)

    @field_validator("expected_revision")
    @classmethod
    def validate_revision(cls, value: int) -> int:
        if (
            type(value) is not int
            or value < 1
            or value > MAX_CONVERSATION_REVISION
        ):
            raise ValueError("expected revision must be positive")
        return value


class CreateTurnRequest(_WebContract):
    schema_version: Literal["1"]
    session_id: str
    expected_revision: int
    user_message: str

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, value: str) -> str:
        return validate_run_identifier(value)

    @field_validator("expected_revision")
    @classmethod
    def validate_revision(cls, value: int) -> int:
        if (
            type(value) is not int
            or value < 1
            or value > MAX_CONVERSATION_REVISION
        ):
            raise ValueError("expected revision must be positive")
        return value

    @field_validator("user_message")
    @classmethod
    def validate_user_message(cls, value: str) -> str:
        if (
            type(value) is not str
            or not value.strip()
            or len(value) > MAX_CONVERSATION_MESSAGE_LENGTH
            or any(
                not character.isprintable() and character not in "\r\n\t"
                for character in value
            )
        ):
            raise ValueError("user message must be bounded text")
        return value


class SessionResponse(_WebContract):
    schema_version: Literal["1"]
    session: ConversationSession

    @field_validator("session", mode="before")
    @classmethod
    def snapshot_session(cls, value: Any) -> ConversationSession:
        return _session_snapshot(value)

    @classmethod
    def _wire_values(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        selected = dict(value)
        selected["session"] = ConversationSession.from_dict(
            selected.get("session")
        )
        return selected


class SessionListResponse(_WebContract):
    schema_version: Literal["1"]
    sessions: Tuple[ConversationSession, ...]

    @field_validator("sessions", mode="before")
    @classmethod
    def snapshot_sessions(cls, value: Any) -> Tuple[ConversationSession, ...]:
        if type(value) is not tuple:
            raise ValueError("sessions must be an exact tuple")
        return tuple(_session_snapshot(item) for item in value)

    @classmethod
    def _wire_values(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        selected = dict(value)
        sessions = selected.get("sessions")
        if type(sessions) is not list:
            raise ValueError("sessions must be a canonical array")
        selected["sessions"] = tuple(
            ConversationSession.from_dict(item) for item in sessions
        )
        return selected


class TurnResponse(_WebContract):
    schema_version: Literal["1"]
    turn: ConversationTurn

    @field_validator("turn", mode="before")
    @classmethod
    def snapshot_turn(cls, value: Any) -> ConversationTurn:
        return _turn_snapshot(value)

    @classmethod
    def _wire_values(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        selected = dict(value)
        selected["turn"] = ConversationTurn.from_dict(
            selected.get("turn")
        )
        return selected


class TurnListResponse(_WebContract):
    schema_version: Literal["1"]
    turns: Tuple[ConversationTurn, ...]

    @field_validator("turns", mode="before")
    @classmethod
    def snapshot_turns(cls, value: Any) -> Tuple[ConversationTurn, ...]:
        if type(value) is not tuple:
            raise ValueError("turns must be an exact tuple")
        return tuple(_turn_snapshot(item) for item in value)

    @classmethod
    def _wire_values(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        selected = dict(value)
        turns = selected.get("turns")
        if type(turns) is not list:
            raise ValueError("turns must be a canonical array")
        selected["turns"] = tuple(
            ConversationTurn.from_dict(item) for item in turns
        )
        return selected


class TurnMutationResponse(_WebContract):
    schema_version: Literal["1"]
    session: ConversationSession
    turn: ConversationTurn

    @field_validator("session", mode="before")
    @classmethod
    def snapshot_session(cls, value: Any) -> ConversationSession:
        return _session_snapshot(value)

    @field_validator("turn", mode="before")
    @classmethod
    def snapshot_turn(cls, value: Any) -> ConversationTurn:
        return _turn_snapshot(value)

    @classmethod
    def _wire_values(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        selected = dict(value)
        selected["session"] = ConversationSession.from_dict(
            selected.get("session")
        )
        selected["turn"] = ConversationTurn.from_dict(
            selected.get("turn")
        )
        return selected


class DeleteSessionResponse(_WebContract):
    schema_version: Literal["1"]
    deleted: Literal[True]


def parse_canonical_json_object(value: bytes) -> Dict[str, Any]:
    """Parse one bounded duplicate-free finite UTF-8 JSON object."""

    if type(value) is not bytes or not value or len(value) > (
        MAX_WEB_REQUEST_BODY_BYTES
    ):
        raise WebAPIContractValidationError() from None
    try:
        text = value.decode("utf-8", errors="strict")
        parsed = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        OverflowError,
        RecursionError,
        ValueError,
    ):
        raise WebAPIContractValidationError() from None
    if type(parsed) is not dict or not _bounded_plain_json(parsed):
        raise WebAPIContractValidationError() from None
    return parsed


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    _ = value
    raise ValueError("non-finite JSON number")


def _bounded_plain_json(value: Any) -> bool:
    stack = [(value, 1)]
    seen_items = 0
    while stack:
        current, depth = stack.pop()
        if depth > _MAX_JSON_TREE_DEPTH:
            return False
        seen_items += 1
        if seen_items > _MAX_JSON_TREE_ITEMS:
            return False
        if current is None or type(current) in {bool, int}:
            continue
        if type(current) is float:
            if not math.isfinite(current):
                return False
            continue
        if type(current) is str:
            if not _valid_json_string(current, allow_layout=True):
                return False
            continue
        if type(current) is list:
            stack.extend((item, depth + 1) for item in current)
            continue
        if type(current) is dict:
            if any(
                type(key) is not str or not _valid_json_string(key)
                for key in current
            ):
                return False
            stack.extend((item, depth + 1) for item in current.values())
            continue
        return False
    return True


def _valid_json_string(value: str, *, allow_layout: bool = False) -> bool:
    return len(value) <= _MAX_JSON_TREE_STRING_LENGTH and not any(
        (
            ord(character) < 32
            and not (allow_layout and character in "\r\n\t")
        )
        or 0xD800 <= ord(character) <= 0xDFFF
        for character in value
    )


def _workflow_snapshot(value: Any) -> WorkflowDefinition:
    if type(value) is not WorkflowDefinition:
        raise ValueError("workflow must be canonical")
    return WorkflowDefinition.from_dict(value.to_dict())


def _session_snapshot(value: Any) -> ConversationSession:
    if type(value) is not ConversationSession:
        raise ValueError("session must be canonical")
    return ConversationSession.from_dict(value.to_dict())


def _turn_snapshot(value: Any) -> ConversationTurn:
    if type(value) is not ConversationTurn:
        raise ValueError("turn must be canonical")
    return ConversationTurn.from_dict(value.to_dict())


__all__ = [
    "CloseSessionRequest",
    "CreateSessionRequest",
    "CreateTurnRequest",
    "DeleteSessionResponse",
    "HealthResponse",
    "MAX_WEB_REQUEST_BODY_BYTES",
    "SessionListResponse",
    "SessionResponse",
    "TurnListResponse",
    "TurnMutationResponse",
    "TurnResponse",
    "WEB_API_SCHEMA_VERSION",
    "WebAPIContractValidationError",
    "WorkflowCatalogResponse",
    "parse_canonical_json_object",
]
