"""Provider-neutral application-level contracts for one PMQA run."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import math
import re
from typing import Any, Dict, Literal, Mapping, Optional, Tuple, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_serializer,
    field_validator,
    model_validator,
)

from pmqa.security.boundary_policy import (
    RUN_PAYLOAD_PROHIBITED_KEYS,
    is_prohibited_key,
)


RUN_CONTRACT_SCHEMA_VERSION = "1"
RUN_IDENTIFIER_MAX_LENGTH = 256
RUN_IDENTIFIER_PATTERN = (
    r"^[a-z0-9]+(?:[._:-][a-z0-9]+)*$"
)
MAX_RUN_PAYLOAD_DEPTH = 32
MAX_RUN_PAYLOAD_ITEMS = 4096
MAX_RUN_PAYLOAD_STRING_LENGTH = 65536

_IDENTIFIER_PATTERN = re.compile(RUN_IDENTIFIER_PATTERN, flags=re.ASCII)
_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$", flags=re.ASCII)
_STORAGE_KEY_PATTERN = re.compile(
    r"^[a-z0-9]+(?:[._:-][a-z0-9]+)*(?:/[a-z0-9]+(?:[._:-][a-z0-9]+)*)*$",
    flags=re.ASCII,
)
_ABSOLUTE_WINDOWS_PATH_PATTERN = re.compile(r"^[a-z]:/", flags=re.ASCII)
_CANONICAL_TIMESTAMP_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{6})?Z$",
    flags=re.ASCII,
)
_MAX_DISPLAY_NAME_LENGTH = 160
_MAX_DESCRIPTION_LENGTH = 2000
_MAX_SAFE_MESSAGE_LENGTH = 1000
_MAX_STORAGE_KEY_LENGTH = 512
_MAX_COLLECTION_ITEMS = 1024
_TERMINAL_RUN_STATUSES = frozenset(
    {
        "succeeded",
        "partially_succeeded",
        "failed",
        "cancelled",
    }
)
_TERMINAL_INVOCATION_STATUSES = frozenset(
    {
        "succeeded",
        "partially_succeeded",
        "failed",
        "cancelled",
    }
)
_INVALID_CONTRACT_MESSAGE = "invalid PMQA run contract"

_ContractT = TypeVar("_ContractT", bound="_RunContract")


class RunContractValidationError(ValueError):
    """Reports a fixed, safe failure at a persisted Run Contract boundary."""

    def __init__(self) -> None:
        super().__init__(_INVALID_CONTRACT_MESSAGE)


class RunStatus(str, Enum):
    """Lifecycle state of one canonical PMQA run."""

    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunnerInvocationStatus(str, Enum):
    """Lifecycle state of one logical runner invocation."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ApprovalMode(str, Enum):
    """Supported application-level approval modes."""

    NONE = "none"
    PRE_RUN = "pre_run"


class RunErrorCategory(str, Enum):
    """Small stable vocabulary for safe run failures."""

    VALIDATION = "validation"
    CONFIGURATION = "configuration"
    EXECUTION = "execution"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    PROVIDER = "provider"
    INTERNAL = "internal"


class _FrozenDict(dict):
    """JSON-compatible mapping that rejects mutation."""

    def _immutable(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("run contract mappings are immutable")

    __delitem__ = _immutable
    __ior__ = _immutable
    __setitem__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable


class _RunContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        strict=True,
        defer_build=True,
    )

    def to_dict(self) -> Dict[str, Any]:
        """Return a fresh canonical tree accepted by standard JSON encoders."""

        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls: type[_ContractT], value: Any) -> _ContractT:
        """Reconstruct from one exact, bounded, canonical plain-JSON object."""

        if type(value) is not dict or not _is_plain_json(value):
            raise RunContractValidationError() from None
        try:
            result = cls.model_validate(dict(value))
        except ValidationError:
            pass
        else:
            if _plain_json_equal(value, result.to_dict()):
                return result
        raise RunContractValidationError() from None

    def model_copy(
        self: _ContractT,
        *,
        update: Optional[Dict[str, Any]] = None,
        deep: bool = False,
    ) -> _ContractT:
        """Return a fully revalidated copy so updates cannot bypass contracts."""

        _ = deep
        values = self.model_dump(mode="python")
        values.update(update or {})
        return type(self).model_validate(values)

    @model_validator(mode="after")
    def validate_canonical_tree(self: _ContractT) -> _ContractT:
        """Keep every constructible contract inside its persistence boundary."""

        if not _is_plain_json(self.model_dump(mode="json")):
            raise ValueError(
                "canonical run contract exceeds the persistence boundary"
            )
        return self


class RunReference(_RunContract):
    """Safe external correlation without provider or Azure DevOps coupling."""

    reference_type: str = Field(min_length=1, max_length=RUN_IDENTIFIER_MAX_LENGTH)
    reference_id: str = Field(min_length=1, max_length=RUN_IDENTIFIER_MAX_LENGTH)

    @field_validator("reference_type", "reference_id")
    @classmethod
    def validate_identifiers(cls, value: str) -> str:
        return validate_run_identifier(value)


class RunRequest(_RunContract):
    """One validated request to start a PMQA workflow."""

    schema_version: Literal["1"]
    request_id: str
    session_id: str
    workflow_id: str
    workflow_version: str
    runner_id: str
    input_schema_id: str
    input_schema_version: str
    inputs: Mapping[str, Any]
    references: Tuple[RunReference, ...]
    requested_at: datetime

    @field_validator(
        "request_id",
        "session_id",
        "workflow_id",
        "workflow_version",
        "runner_id",
        "input_schema_id",
        "input_schema_version",
    )
    @classmethod
    def validate_identifiers(cls, value: str) -> str:
        return validate_run_identifier(value)

    @field_validator("inputs", mode="before")
    @classmethod
    def validate_inputs(cls, value: Any) -> Mapping[str, Any]:
        return _safe_payload_mapping(value, "inputs")

    @field_validator("inputs")
    @classmethod
    def freeze_inputs(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        return _freeze_json(dict(value))

    @field_validator("references", mode="before")
    @classmethod
    def validate_references(
        cls, value: Any
    ) -> Tuple[Any, ...]:
        return _contract_array(value, "references")

    @field_validator("requested_at", mode="before")
    @classmethod
    def validate_requested_at(cls, value: Any) -> datetime:
        return _canonical_timestamp(value, "requested_at")

    @field_serializer("requested_at")
    def serialize_requested_at(self, value: datetime) -> str:
        return _serialize_timestamp(value)

    @model_validator(mode="after")
    def validate_contract(self) -> "RunRequest":
        _reject_duplicate_references(self.references)
        return self


class WorkflowPreviewStep(_RunContract):
    """Trusted, static workflow presentation metadata."""

    step_id: str
    display_name: str
    description: Optional[str] = None

    @field_validator("step_id")
    @classmethod
    def validate_step_id(cls, value: str) -> str:
        return validate_run_identifier(value)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        return _bounded_text(value, "display_name", _MAX_DISPLAY_NAME_LENGTH)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _bounded_text(value, "description", _MAX_DESCRIPTION_LENGTH)


class WorkflowDefinition(_RunContract):
    """Safe metadata for a future Workflow Registry and local interfaces."""

    schema_version: Literal["1"]
    workflow_id: str
    workflow_version: str
    display_name: str
    description: str
    input_schema_id: str
    input_schema_version: str
    result_schema_id: str
    result_schema_version: str
    preview_steps: Tuple[WorkflowPreviewStep, ...]
    required_runner_capabilities: Tuple[str, ...]
    approval_mode: ApprovalMode

    @field_validator(
        "workflow_id",
        "workflow_version",
        "input_schema_id",
        "input_schema_version",
        "result_schema_id",
        "result_schema_version",
    )
    @classmethod
    def validate_identifiers(cls, value: str) -> str:
        return validate_run_identifier(value)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        return _bounded_text(value, "display_name", _MAX_DISPLAY_NAME_LENGTH)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        return _bounded_text(value, "description", _MAX_DESCRIPTION_LENGTH)

    @field_validator("preview_steps", mode="before")
    @classmethod
    def validate_preview_steps(cls, value: Any) -> Tuple[Any, ...]:
        return _contract_array(value, "preview_steps")

    @field_validator("required_runner_capabilities", mode="before")
    @classmethod
    def validate_capabilities(cls, value: Any) -> Tuple[str, ...]:
        values = _string_identifier_array(value, "required_runner_capabilities")
        if len(set(values)) != len(values):
            raise ValueError("runner capabilities must be duplicate-free")
        return tuple(sorted(values))

    @field_validator("approval_mode", mode="before")
    @classmethod
    def validate_approval_mode(cls, value: Any) -> ApprovalMode:
        return _parse_enum(value, ApprovalMode, "approval_mode")

    @model_validator(mode="after")
    def validate_contract(self) -> "WorkflowDefinition":
        step_ids = tuple(step.step_id for step in self.preview_steps)
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("preview step identifiers must be unique")
        return self


class PMQARunContext(_RunContract):
    """Safe application-level runtime correlation only."""

    schema_version: Literal["1"]
    run_id: str
    request_id: str
    session_id: str
    workflow_id: str
    workflow_version: str
    runner_id: str
    references: Tuple[RunReference, ...]
    started_at: datetime

    @field_validator(
        "run_id",
        "request_id",
        "session_id",
        "workflow_id",
        "workflow_version",
        "runner_id",
    )
    @classmethod
    def validate_identifiers(cls, value: str) -> str:
        return validate_run_identifier(value)

    @field_validator("references", mode="before")
    @classmethod
    def validate_references(cls, value: Any) -> Tuple[Any, ...]:
        return _contract_array(value, "references")

    @field_validator("started_at", mode="before")
    @classmethod
    def validate_started_at(cls, value: Any) -> datetime:
        return _canonical_timestamp(value, "started_at")

    @field_serializer("started_at")
    def serialize_started_at(self, value: datetime) -> str:
        return _serialize_timestamp(value)

    @model_validator(mode="after")
    def validate_contract(self) -> "PMQARunContext":
        _reject_duplicate_references(self.references)
        return self


class StructuredResult(_RunContract):
    """Workflow-neutral structured result data with an explicit payload schema."""

    schema_version: Literal["1"]
    schema_id: str
    result_schema_version: str
    data: Mapping[str, Any]

    @field_validator("schema_id", "result_schema_version")
    @classmethod
    def validate_identifiers(cls, value: str) -> str:
        return validate_run_identifier(value)

    @field_validator("data", mode="before")
    @classmethod
    def validate_data(cls, value: Any) -> Mapping[str, Any]:
        return _safe_payload_mapping(value, "data")

    @field_validator("data")
    @classmethod
    def freeze_data(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        return _freeze_json(dict(value))


class RunArtifact(_RunContract):
    """Logical artifact reference without artifact contents or storage clients."""

    artifact_id: str
    artifact_type: str
    artifact_schema_version: str
    storage_key: str
    content_digest: str
    created_at: datetime

    @field_validator(
        "artifact_id",
        "artifact_type",
        "artifact_schema_version",
    )
    @classmethod
    def validate_identifiers(cls, value: str) -> str:
        return validate_run_identifier(value)

    @field_validator("storage_key")
    @classmethod
    def validate_storage_key(cls, value: str) -> str:
        if (
            type(value) is not str
            or len(value) > _MAX_STORAGE_KEY_LENGTH
            or _STORAGE_KEY_PATTERN.fullmatch(value) is None
            or _ABSOLUTE_WINDOWS_PATH_PATTERN.match(value) is not None
            or value.startswith(("file:", "http:", "https:"))
            or ".." in value
        ):
            raise ValueError("storage_key must be a logical storage key")
        return value

    @field_validator("content_digest")
    @classmethod
    def validate_content_digest(cls, value: str) -> str:
        if type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None:
            raise ValueError("content_digest must be lowercase SHA-256 hexadecimal")
        return value

    @field_validator("created_at", mode="before")
    @classmethod
    def validate_created_at(cls, value: Any) -> datetime:
        return _canonical_timestamp(value, "created_at")

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return _serialize_timestamp(value)


class RunError(_RunContract):
    """Safe, bounded error information for a run or runner invocation."""

    code: str
    category: RunErrorCategory
    safe_message: str
    step_id: Optional[str] = None
    retryable: bool
    error_type: Optional[str] = None

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        return validate_run_identifier(value)

    @field_validator("category", mode="before")
    @classmethod
    def validate_category(cls, value: Any) -> RunErrorCategory:
        return _parse_enum(value, RunErrorCategory, "category")

    @field_validator("safe_message")
    @classmethod
    def validate_safe_message(cls, value: str) -> str:
        return _bounded_text(value, "safe_message", _MAX_SAFE_MESSAGE_LENGTH)

    @field_validator("step_id", "error_type")
    @classmethod
    def validate_optional_identifiers(
        cls, value: Optional[str]
    ) -> Optional[str]:
        if value is None:
            return None
        return validate_run_identifier(value)


class OutcomeMetrics(_RunContract):
    """Optional reliable outcome facts; unavailable values remain ``None``."""

    tests_generated: Optional[int] = Field(default=None, ge=0)
    tests_updated: Optional[int] = Field(default=None, ge=0)
    tests_passed: Optional[int] = Field(default=None, ge=0)
    tests_failed: Optional[int] = Field(default=None, ge=0)
    files_changed: Optional[int] = Field(default=None, ge=0)
    knowledge_items_created: Optional[int] = Field(default=None, ge=0)
    knowledge_items_updated: Optional[int] = Field(default=None, ge=0)
    coverage_suggestions_generated: Optional[int] = Field(default=None, ge=0)
    human_review_required: Optional[bool] = None


class RunnerInvocationRecord(_RunContract):
    """One logical future-runner call and retry/fallback correlation."""

    schema_version: Literal["1"]
    invocation_id: str
    run_id: str
    runner_id: str
    operation: str
    step_id: Optional[str] = None
    status: RunnerInvocationStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = Field(default=None, ge=0)
    attempt_number: int = Field(ge=1)
    retry_of_invocation_id: Optional[str] = None
    fallback_from_invocation_id: Optional[str] = None
    errors: Tuple[RunError, ...]

    @field_validator(
        "invocation_id",
        "run_id",
        "runner_id",
        "operation",
    )
    @classmethod
    def validate_identifiers(cls, value: str) -> str:
        return validate_run_identifier(value)

    @field_validator(
        "step_id",
        "retry_of_invocation_id",
        "fallback_from_invocation_id",
    )
    @classmethod
    def validate_optional_identifiers(
        cls, value: Optional[str]
    ) -> Optional[str]:
        if value is None:
            return None
        return validate_run_identifier(value)

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, value: Any) -> RunnerInvocationStatus:
        return _parse_enum(value, RunnerInvocationStatus, "status")

    @field_validator("started_at", mode="before")
    @classmethod
    def validate_started_at(cls, value: Any) -> datetime:
        return _canonical_timestamp(value, "started_at")

    @field_validator("completed_at", mode="before")
    @classmethod
    def validate_completed_at(cls, value: Any) -> Optional[datetime]:
        if value is None:
            return None
        return _canonical_timestamp(value, "completed_at")

    @field_serializer("started_at", "completed_at")
    def serialize_timestamps(self, value: Optional[datetime]) -> Optional[str]:
        return None if value is None else _serialize_timestamp(value)

    @field_validator("errors", mode="before")
    @classmethod
    def validate_errors(cls, value: Any) -> Tuple[Any, ...]:
        return _contract_array(value, "errors")

    @model_validator(mode="after")
    def validate_contract(self) -> "RunnerInvocationRecord":
        terminal = self.status.value in _TERMINAL_INVOCATION_STATUSES
        if (self.completed_at is None) != (self.duration_ms is None):
            raise ValueError(
                "completed_at and duration_ms must be present together"
            )
        completion_present = (
            self.completed_at is not None and self.duration_ms is not None
        )
        if terminal != completion_present:
            raise ValueError(
                "completion metadata must be present exactly for terminal invocation status"
            )
        if self.completed_at is not None and self.completed_at < self.started_at:
            raise ValueError("completed_at must not precede started_at")
        if self.retry_of_invocation_id == self.invocation_id:
            raise ValueError("retry correlation cannot reference the invocation itself")
        if self.fallback_from_invocation_id == self.invocation_id:
            raise ValueError(
                "fallback correlation cannot reference the invocation itself"
            )
        predecessor_count = sum(
            predecessor is not None
            for predecessor in (
                self.retry_of_invocation_id,
                self.fallback_from_invocation_id,
            )
        )
        if self.attempt_number == 1 and predecessor_count != 0:
            raise ValueError("first attempt must not declare a predecessor")
        if self.attempt_number > 1 and predecessor_count != 1:
            raise ValueError(
                "later attempt must declare exactly one predecessor"
            )
        return self


class RunRecord(_RunContract):
    """Canonical persisted state of one PMQA run."""

    schema_version: Literal["1"]
    run_id: str
    request_id: str
    session_id: str
    workflow_id: str
    workflow_version: str
    runner_id: str
    status: RunStatus
    references: Tuple[RunReference, ...]
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = Field(default=None, ge=0)
    current_step_id: Optional[str] = None
    result: Optional[StructuredResult] = None
    artifacts: Tuple[RunArtifact, ...]
    errors: Tuple[RunError, ...]
    runner_invocation_ids: Tuple[str, ...]
    outcome_metrics: Optional[OutcomeMetrics]
    created_at: datetime
    updated_at: datetime

    @field_validator(
        "run_id",
        "request_id",
        "session_id",
        "workflow_id",
        "workflow_version",
        "runner_id",
    )
    @classmethod
    def validate_identifiers(cls, value: str) -> str:
        return validate_run_identifier(value)

    @field_validator("current_step_id")
    @classmethod
    def validate_current_step_id(
        cls, value: Optional[str]
    ) -> Optional[str]:
        if value is None:
            return None
        return validate_run_identifier(value)

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, value: Any) -> RunStatus:
        return _parse_enum(value, RunStatus, "status")

    @field_validator("references", "artifacts", "errors", mode="before")
    @classmethod
    def validate_contract_arrays(cls, value: Any, info: Any) -> Tuple[Any, ...]:
        return _contract_array(value, info.field_name)

    @field_validator("runner_invocation_ids", mode="before")
    @classmethod
    def validate_invocation_ids(cls, value: Any) -> Tuple[str, ...]:
        return _string_identifier_array(value, "runner_invocation_ids")

    @field_validator(
        "started_at",
        "created_at",
        "updated_at",
        mode="before",
    )
    @classmethod
    def validate_required_timestamps(cls, value: Any, info: Any) -> datetime:
        return _canonical_timestamp(value, info.field_name)

    @field_validator("completed_at", mode="before")
    @classmethod
    def validate_completed_at(cls, value: Any) -> Optional[datetime]:
        if value is None:
            return None
        return _canonical_timestamp(value, "completed_at")

    @field_serializer("started_at", "completed_at", "created_at", "updated_at")
    def serialize_timestamps(self, value: Optional[datetime]) -> Optional[str]:
        return None if value is None else _serialize_timestamp(value)

    @model_validator(mode="after")
    def validate_contract(self) -> "RunRecord":
        terminal = self.status.value in _TERMINAL_RUN_STATUSES
        if (self.completed_at is None) != (self.duration_ms is None):
            raise ValueError(
                "completed_at and duration_ms must be present together"
            )
        completion_present = (
            self.completed_at is not None and self.duration_ms is not None
        )
        if terminal != completion_present:
            raise ValueError(
                "completion metadata must be present exactly for terminal run status"
            )
        if self.completed_at is not None and self.completed_at < self.started_at:
            raise ValueError("completed_at must not precede started_at")
        if self.started_at < self.created_at:
            raise ValueError("started_at must not precede created_at")
        if self.updated_at < self.started_at:
            raise ValueError("updated_at must not precede started_at")
        if self.completed_at is not None and self.completed_at > self.updated_at:
            raise ValueError("completed_at must not follow updated_at")
        if (
            self.status is not RunStatus.RUNNING
            and self.current_step_id is not None
        ):
            raise ValueError(
                "current_step_id is allowed only while a run is running"
            )
        if self.result is not None and self.status not in {
            RunStatus.SUCCEEDED,
            RunStatus.PARTIALLY_SUCCEEDED,
        }:
            raise ValueError(
                "structured result is allowed only for successful run statuses"
            )
        _reject_duplicate_references(self.references)
        artifact_ids = tuple(artifact.artifact_id for artifact in self.artifacts)
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("artifact identifiers must be unique")
        if len(self.runner_invocation_ids) != len(set(self.runner_invocation_ids)):
            raise ValueError("runner invocation identifiers must be unique")
        return self


def validate_run_identifier(value: str) -> str:
    """Validate a bounded lowercase ASCII segmented correlation identifier."""

    if (
        type(value) is not str
        or len(value) > RUN_IDENTIFIER_MAX_LENGTH
        or _IDENTIFIER_PATTERN.fullmatch(value) is None
        or ".." in value
    ):
        raise ValueError("identifier must use canonical lowercase ASCII segments")
    return value


def _bounded_text(value: Any, field_name: str, maximum: int) -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > maximum
        or value.strip() != value
        or not value.isprintable()
    ):
        raise ValueError(f"{field_name} must be bounded printable text")
    return value


def _parse_enum(value: Any, enum_type: Any, field_name: str) -> Any:
    if isinstance(value, enum_type):
        return value
    if type(value) is str:
        try:
            return enum_type(value)
        except ValueError:
            pass
    raise ValueError(f"{field_name} is unsupported")


def _contract_array(value: Any, field_name: str) -> Tuple[Any, ...]:
    if type(value) not in {list, tuple}:
        raise ValueError(f"{field_name} must be an ordered JSON array")
    if len(value) > _MAX_COLLECTION_ITEMS:
        raise ValueError(f"{field_name} exceeds the maximum item count")
    return tuple(value)


def _string_identifier_array(value: Any, field_name: str) -> Tuple[str, ...]:
    values = _contract_array(value, field_name)
    if any(type(item) is not str for item in values):
        raise ValueError(f"{field_name} must contain identifiers")
    return tuple(validate_run_identifier(item) for item in values)


def _reject_duplicate_references(references: Tuple[RunReference, ...]) -> None:
    pairs = tuple(
        (reference.reference_type, reference.reference_id)
        for reference in references
    )
    if len(pairs) != len(set(pairs)):
        raise ValueError("run references must be duplicate-free")


def _safe_payload_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    counter = [0]
    _validate_safe_json(
        value,
        field_name,
        depth=0,
        counter=counter,
        active_containers=set(),
    )
    if type(value) is not dict:
        raise ValueError(f"{field_name} must be a JSON object")
    return _freeze_json(value)


def _validate_safe_json(
    value: Any,
    path: str,
    *,
    depth: int,
    counter: list[int],
    active_containers: set[int],
) -> None:
    if depth > MAX_RUN_PAYLOAD_DEPTH:
        raise ValueError("run payload exceeds the maximum nesting depth")
    counter[0] += 1
    if counter[0] > MAX_RUN_PAYLOAD_ITEMS:
        raise ValueError("run payload exceeds the maximum item count")

    value_type = type(value)
    if value is None or value_type in {bool, int}:
        return
    if value_type is float:
        if not math.isfinite(value):
            raise ValueError("run payload contains a non-finite number")
        return
    if value_type is str:
        if len(value) > MAX_RUN_PAYLOAD_STRING_LENGTH:
            raise ValueError("run payload string exceeds the maximum length")
        return
    if value_type not in {dict, list, tuple}:
        raise ValueError(f"run payload contains a runtime object at {path}")

    identity = id(value)
    if identity in active_containers:
        raise ValueError("run payload contains a cyclic container")
    active_containers.add(identity)
    try:
        if value_type in {list, tuple}:
            for index, item in enumerate(value):
                _validate_safe_json(
                    item,
                    f"{path}[{index}]",
                    depth=depth + 1,
                    counter=counter,
                    active_containers=active_containers,
                )
            return
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError(f"run payload contains a non-string key at {path}")
            if (
                not key
                or len(key) > RUN_IDENTIFIER_MAX_LENGTH
                or not key.isascii()
                or not key.isprintable()
                or key.strip() != key
            ):
                raise ValueError(f"run payload contains an invalid key at {path}")
            if is_prohibited_key(key, RUN_PAYLOAD_PROHIBITED_KEYS):
                raise ValueError(f"run payload contains a prohibited field at {path}")
            _validate_safe_json(
                item,
                f"{path}.{key}",
                depth=depth + 1,
                counter=counter,
                active_containers=active_containers,
            )
    finally:
        active_containers.remove(identity)


def _freeze_json(value: Any) -> Any:
    if type(value) is dict:
        return _FrozenDict(
            {key: _freeze_json(item) for key, item in value.items()}
        )
    if type(value) in {list, tuple}:
        return tuple(_freeze_json(item) for item in value)
    return value


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
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_plain_json(
    value: Any,
    *,
    depth: int = 0,
    counter: Optional[list[int]] = None,
    active_containers: Optional[set[int]] = None,
) -> bool:
    if depth > MAX_RUN_PAYLOAD_DEPTH:
        return False
    count = [0] if counter is None else counter
    count[0] += 1
    if count[0] > MAX_RUN_PAYLOAD_ITEMS:
        return False

    value_type = type(value)
    if value is None or value_type in {bool, int}:
        return True
    if value_type is str:
        return len(value) <= MAX_RUN_PAYLOAD_STRING_LENGTH
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


def _plain_json_equal(submitted: Any, canonical: Any) -> bool:
    if type(submitted) is not type(canonical):
        return False
    if type(submitted) is dict:
        if submitted.keys() != canonical.keys():
            return False
        return all(
            _plain_json_equal(submitted[key], canonical[key])
            for key in submitted
        )
    if type(submitted) is list:
        return len(submitted) == len(canonical) and all(
            _plain_json_equal(left, right)
            for left, right in zip(submitted, canonical)
        )
    return submitted == canonical


__all__ = [
    "ApprovalMode",
    "MAX_RUN_PAYLOAD_DEPTH",
    "MAX_RUN_PAYLOAD_ITEMS",
    "MAX_RUN_PAYLOAD_STRING_LENGTH",
    "OutcomeMetrics",
    "PMQARunContext",
    "RUN_CONTRACT_SCHEMA_VERSION",
    "RUN_IDENTIFIER_MAX_LENGTH",
    "RUN_IDENTIFIER_PATTERN",
    "RunArtifact",
    "RunContractValidationError",
    "RunError",
    "RunErrorCategory",
    "RunRecord",
    "RunReference",
    "RunRequest",
    "RunStatus",
    "RunnerInvocationRecord",
    "RunnerInvocationStatus",
    "StructuredResult",
    "WorkflowDefinition",
    "WorkflowPreviewStep",
    "validate_run_identifier",
]
