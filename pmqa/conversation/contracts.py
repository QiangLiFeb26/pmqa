"""Canonical provider-neutral conversation session and turn contracts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
import math
import re
from typing import Any, Dict, Literal, Optional, Tuple, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_serializer,
    field_validator,
    model_validator,
)

from pmqa.run import validate_run_identifier
from pmqa.security.sensitive_text import contains_recognizable_sensitive_text


CONVERSATION_SCHEMA_VERSION = "1"
DEFAULT_CONVERSATION_LIST_LIMIT = 100
MAX_CONVERSATION_LIST_LIMIT = 256
MAX_CONVERSATION_REVISION = (2 ** 63) - 1
MAX_CONVERSATION_TURNS = 256
MAX_CONVERSATION_MESSAGE_LENGTH = 32 * 1024
MAX_CONVERSATION_TREE_DEPTH = 16
MAX_CONVERSATION_TREE_ITEMS = 2048
MAX_CONVERSATION_TREE_STRING_LENGTH = 32 * 1024

_CANONICAL_TIMESTAMP_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{6})?Z$",
    flags=re.ASCII,
)
_INVALID_CONTRACT_MESSAGE = "invalid PMQA conversation contract"
_SENSITIVE_TEXT_MESSAGE = "conversation text contains sensitive material"

_ContractT = TypeVar("_ContractT", bound="_ConversationContract")


class ConversationContractValidationError(ValueError):
    """Report one fixed failure at the persisted conversation boundary."""

    def __init__(self) -> None:
        super().__init__(_INVALID_CONTRACT_MESSAGE)


class ConversationSensitiveTextError(ValueError):
    """Reject recognizable credentials without echoing inspected text."""

    def __init__(self) -> None:
        super().__init__(_SENSITIVE_TEXT_MESSAGE)


class ConversationRetentionPolicy(str, Enum):
    """Approved local conversation retention choices."""

    SESSION_ONLY = "session_only"
    SEVEN_DAYS = "7_days"
    THIRTY_DAYS = "30_days"
    NINETY_DAYS = "90_days"

    @property
    def durable(self) -> bool:
        return self is not ConversationRetentionPolicy.SESSION_ONLY

    @property
    def duration(self) -> Optional[timedelta]:
        days = {
            ConversationRetentionPolicy.SESSION_ONLY: None,
            ConversationRetentionPolicy.SEVEN_DAYS: 7,
            ConversationRetentionPolicy.THIRTY_DAYS: 30,
            ConversationRetentionPolicy.NINETY_DAYS: 90,
        }[self]
        return None if days is None else timedelta(days=days)


class ConversationSessionStatus(str, Enum):
    """Lifecycle of one local conversation session."""

    ACTIVE = "active"
    CLOSED = "closed"


class ConversationTurnStatus(str, Enum):
    """Lifecycle of one user/assistant conversation turn."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class ConversationTurnErrorCode(str, Enum):
    """Fixed safe classifications retained by failed turns."""

    PROCESSING_FAILED = "processing_failed"
    RESPONSE_REJECTED = "response_rejected"
    PROVIDER_UNAVAILABLE = "provider_unavailable"


_TURN_ERROR_MESSAGES = {
    ConversationTurnErrorCode.PROCESSING_FAILED:
        "conversation processing failed",
    ConversationTurnErrorCode.RESPONSE_REJECTED:
        "conversation response was rejected",
    ConversationTurnErrorCode.PROVIDER_UNAVAILABLE:
        "conversation provider is unavailable",
}


class _ConversationContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        strict=True,
        defer_build=True,
    )

    def to_dict(self) -> Dict[str, Any]:
        """Return a fresh canonical plain-JSON tree."""

        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls: type[_ContractT], value: Any) -> _ContractT:
        """Reconstruct one exact bounded canonical plain-JSON record."""

        if type(value) is not dict or not _is_plain_json(value):
            raise ConversationContractValidationError() from None
        try:
            result = cls.model_validate(dict(value))
        except ValidationError:
            pass
        else:
            if value == result.to_dict():
                return result
        raise ConversationContractValidationError() from None

    def model_copy(
        self: _ContractT,
        *,
        update: Optional[Dict[str, Any]] = None,
        deep: bool = False,
    ) -> _ContractT:
        """Return a fully revalidated copy."""

        _ = deep
        values = self.model_dump(mode="python")
        values.update(update or {})
        return type(self).model_validate(values)

    @model_validator(mode="after")
    def validate_canonical_tree(self: _ContractT) -> _ContractT:
        if not _is_plain_json(self.model_dump(mode="json")):
            raise ValueError("conversation contract exceeds persistence bounds")
        return self


class ConversationSession(_ConversationContract):
    """One immutable snapshot of a local conversation session."""

    schema_version: Literal["1"]
    session_id: str
    revision: int = Field(ge=1, le=MAX_CONVERSATION_REVISION)
    status: ConversationSessionStatus
    retention_policy: ConversationRetentionPolicy
    connection_context_id: Optional[str] = None
    turn_ids: Tuple[str, ...]
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime] = None

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, value: str) -> str:
        return validate_run_identifier(value)

    @field_validator("connection_context_id")
    @classmethod
    def validate_connection_context_id(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        return None if value is None else validate_run_identifier(value)

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, value: Any) -> ConversationSessionStatus:
        return _parse_enum(value, ConversationSessionStatus)

    @field_validator("retention_policy", mode="before")
    @classmethod
    def validate_retention_policy(
        cls,
        value: Any,
    ) -> ConversationRetentionPolicy:
        return _parse_enum(value, ConversationRetentionPolicy)

    @field_validator("turn_ids", mode="before")
    @classmethod
    def validate_turn_ids(cls, value: Any) -> Tuple[str, ...]:
        if type(value) not in {list, tuple} or len(value) > MAX_CONVERSATION_TURNS:
            raise ValueError("turn_ids must be a bounded ordered collection")
        result = tuple(validate_run_identifier(item) for item in value)
        if len(result) != len(set(result)):
            raise ValueError("turn identifiers must be unique")
        return result

    @field_validator(
        "created_at",
        "updated_at",
        "expires_at",
        mode="before",
    )
    @classmethod
    def validate_timestamps(
        cls,
        value: Any,
        info: Any,
    ) -> Optional[datetime]:
        if value is None and info.field_name == "expires_at":
            return None
        return _canonical_timestamp(value, info.field_name)

    @field_serializer("created_at", "updated_at", "expires_at")
    def serialize_timestamps(self, value: Optional[datetime]) -> Optional[str]:
        return None if value is None else _serialize_timestamp(value)

    @model_validator(mode="after")
    def validate_session(self) -> "ConversationSession":
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")
        expected_expiration = conversation_expiration(
            self.retention_policy,
            self.updated_at,
        )
        if self.expires_at != expected_expiration:
            raise ValueError("expiration does not match retention policy")
        return self


class ConversationTurn(_ConversationContract):
    """One immutable user-message and assistant-response lifecycle snapshot."""

    schema_version: Literal["1"]
    turn_id: str
    session_id: str
    sequence_number: int = Field(ge=1, le=MAX_CONVERSATION_TURNS)
    status: ConversationTurnStatus
    user_message: str
    assistant_response: Optional[str] = None
    error_code: Optional[ConversationTurnErrorCode] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    @field_validator("turn_id", "session_id")
    @classmethod
    def validate_identifiers(cls, value: str) -> str:
        return validate_run_identifier(value)

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, value: Any) -> ConversationTurnStatus:
        return _parse_enum(value, ConversationTurnStatus)

    @field_validator("error_code", mode="before")
    @classmethod
    def validate_error_code(
        cls,
        value: Any,
    ) -> Optional[ConversationTurnErrorCode]:
        if value is None:
            return None
        return _parse_enum(value, ConversationTurnErrorCode)

    @field_validator("user_message")
    @classmethod
    def validate_user_message(cls, value: Any) -> str:
        return _conversation_text(value, allow_empty=False)

    @field_validator("assistant_response")
    @classmethod
    def validate_assistant_response(cls, value: Any) -> Optional[str]:
        if value is None:
            return None
        return _conversation_text(value, allow_empty=True)

    @field_validator("created_at", "completed_at", mode="before")
    @classmethod
    def validate_timestamps(
        cls,
        value: Any,
        info: Any,
    ) -> Optional[datetime]:
        if value is None and info.field_name == "completed_at":
            return None
        return _canonical_timestamp(value, info.field_name)

    @field_serializer("created_at", "completed_at")
    def serialize_timestamps(self, value: Optional[datetime]) -> Optional[str]:
        return None if value is None else _serialize_timestamp(value)

    @model_validator(mode="after")
    def validate_turn(self) -> "ConversationTurn":
        if (
            self.completed_at is not None
            and self.completed_at < self.created_at
        ):
            raise ValueError("completed_at must not precede created_at")
        if self.status is ConversationTurnStatus.PENDING:
            valid = (
                self.assistant_response is None
                and self.error_code is None
                and self.error_message is None
                and self.completed_at is None
            )
        elif self.status is ConversationTurnStatus.COMPLETED:
            valid = (
                self.assistant_response is not None
                and self.error_code is None
                and self.error_message is None
                and self.completed_at is not None
            )
        else:
            valid = (
                self.assistant_response is None
                and self.error_code is not None
                and self.error_message == _TURN_ERROR_MESSAGES.get(
                    self.error_code
                )
                and self.completed_at is not None
            )
        if not valid:
            raise ValueError("turn fields do not match lifecycle status")
        return self


def conversation_turn_error_message(
    code: ConversationTurnErrorCode,
) -> str:
    """Return the one fixed persisted message for a turn failure code."""

    if type(code) is not ConversationTurnErrorCode:
        raise TypeError("code must be a ConversationTurnErrorCode")
    return _TURN_ERROR_MESSAGES[code]


def conversation_expiration(
    policy: ConversationRetentionPolicy,
    updated_at: datetime,
) -> Optional[datetime]:
    """Derive exact approved expiration from one authoritative activity."""

    if type(policy) is not ConversationRetentionPolicy:
        raise ValueError("invalid conversation retention policy")
    canonical_updated_at = _canonical_timestamp(updated_at, "updated_at")
    duration = policy.duration
    if duration is None:
        return None
    try:
        return canonical_updated_at + duration
    except OverflowError:
        raise ValueError("conversation expiration is out of range") from None


def validate_conversation_list_limit(limit: Any) -> int:
    """Validate one bounded repository/service list limit."""

    if (
        type(limit) is not int
        or not 1 <= limit <= MAX_CONVERSATION_LIST_LIMIT
    ):
        raise ValueError("invalid conversation list limit")
    return limit


def validate_conversation_timestamp(
    value: Any,
    field_name: str = "timestamp",
) -> datetime:
    """Return one timezone-aware timestamp normalized to UTC."""

    return _canonical_timestamp(value, field_name)


def _conversation_text(value: Any, *, allow_empty: bool) -> str:
    if (
        type(value) is not str
        or len(value) > MAX_CONVERSATION_MESSAGE_LENGTH
        or (not allow_empty and not value.strip())
        or any(
            not character.isprintable() and character not in "\r\n\t"
            for character in value
        )
    ):
        raise ValueError("conversation text is invalid")
    if contains_recognizable_sensitive_text(value):
        raise ConversationSensitiveTextError() from None
    return value


def _parse_enum(value: Any, enum_type: Any) -> Any:
    if isinstance(value, enum_type):
        return value
    if type(value) is str:
        try:
            return enum_type(value)
        except ValueError:
            pass
    raise ValueError("unsupported conversation enum value")


def _canonical_timestamp(value: Any, field_name: str) -> datetime:
    if type(value) is datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{field_name} must include timezone information")
        return value.astimezone(timezone.utc)
    if type(value) is str and _CANONICAL_TIMESTAMP_PATTERN.fullmatch(value):
        try:
            parsed = datetime.fromisoformat(value[:-1] + "+00:00")
        except ValueError:
            pass
        else:
            if _serialize_timestamp(parsed) == value:
                return parsed
    raise ValueError(f"{field_name} must be a canonical UTC timestamp")


def _serialize_timestamp(value: datetime) -> str:
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _is_plain_json(
    value: Any,
    *,
    depth: int = 0,
    counter: Optional[list[int]] = None,
    active_containers: Optional[set[int]] = None,
) -> bool:
    if depth > MAX_CONVERSATION_TREE_DEPTH:
        return False
    count = [0] if counter is None else counter
    count[0] += 1
    if count[0] > MAX_CONVERSATION_TREE_ITEMS:
        return False

    value_type = type(value)
    if value is None or value_type in {bool, int}:
        return True
    if value_type is str:
        return len(value) <= MAX_CONVERSATION_TREE_STRING_LENGTH
    if value_type is float:
        return math.isfinite(value)
    if value_type not in {dict, list}:
        return False

    active = set() if active_containers is None else active_containers
    identity = id(value)
    if identity in active:
        return False
    active.add(identity)
    try:
        if value_type is list:
            return all(
                _is_plain_json(
                    item,
                    depth=depth + 1,
                    counter=count,
                    active_containers=active,
                )
                for item in value
            )
        return all(
            type(key) is str
            and len(key) <= MAX_CONVERSATION_TREE_STRING_LENGTH
            and _is_plain_json(
                item,
                depth=depth + 1,
                counter=count,
                active_containers=active,
            )
            for key, item in value.items()
        )
    finally:
        active.remove(identity)


__all__ = [
    "CONVERSATION_SCHEMA_VERSION",
    "DEFAULT_CONVERSATION_LIST_LIMIT",
    "MAX_CONVERSATION_LIST_LIMIT",
    "MAX_CONVERSATION_MESSAGE_LENGTH",
    "MAX_CONVERSATION_REVISION",
    "MAX_CONVERSATION_TURNS",
    "ConversationContractValidationError",
    "ConversationRetentionPolicy",
    "ConversationSensitiveTextError",
    "ConversationSession",
    "ConversationSessionStatus",
    "ConversationTurn",
    "ConversationTurnErrorCode",
    "ConversationTurnStatus",
    "conversation_expiration",
    "conversation_turn_error_message",
    "validate_conversation_list_limit",
    "validate_conversation_timestamp",
]
