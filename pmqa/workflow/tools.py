"""Provider-independent contracts for external capability execution."""

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Protocol, Tuple

from pydantic import Field, field_validator, model_validator

from pmqa.workflow.errors import ToolContractValidationError
from pmqa.workflow.models import (
    AgentRole,
    _WorkflowContract,
    _freeze,
    _require_aware,
    _validate_payload,
)


class ToolCategory(str, Enum):
    """Groups stable tool capabilities without naming an implementation."""

    PLAYWRIGHT = "playwright"
    REASONING = "reasoning"
    PRODUCT_MEMORY = "product_memory"
    FILESYSTEM = "filesystem"
    VALIDATION = "validation"
    UTILITY = "utility"


class ToolExecutionStatus(str, Enum):
    """Describes the outcome of exactly one tool execution."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL = "partial"
    SKIPPED = "skipped"


class ToolMetadata(_WorkflowContract):
    """Publishes the stable identity and schema versions of a tool."""

    tool_id: str = Field(min_length=1)
    category: ToolCategory
    description: str = Field(min_length=1)
    input_schema_version: str = Field(min_length=1)
    output_schema_version: str = Field(min_length=1)

    @field_validator("tool_id")
    @classmethod
    def validate_tool_id(cls, value: str) -> str:
        """Require a namespaced provider-independent tool identifier."""

        _validate_tool_id(value)
        return value

    @model_validator(mode="after")
    def validate_contract(self) -> "ToolMetadata":
        """Require the identifier namespace to match the declared category."""

        _validate_tool_category(self.tool_id, self.category)
        return self


class ArtifactReference(_WorkflowContract):
    """References a stored tool artifact without embedding its content."""

    artifact_id: str = Field(min_length=1)
    artifact_type: str = Field(min_length=1)
    content_type: str = Field(min_length=1)
    location: str = Field(min_length=1)
    created_at: datetime

    @model_validator(mode="after")
    def validate_contract(self) -> "ArtifactReference":
        """Require a timezone-aware artifact creation timestamp."""

        _require_aware(self.created_at, "created_at")
        return self


class ToolError(_WorkflowContract):
    """Carries a safe structured execution failure across the tool boundary."""

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    retryable: bool = False


class ToolRequest(_WorkflowContract):
    """Requests one tool execution using only immutable structured input."""

    tool_id: str = Field(min_length=1)
    category: ToolCategory
    workflow_id: str = Field(min_length=1)
    invocation_id: str = Field(min_length=1)
    requested_by_agent: AgentRole
    requested_at: datetime
    input: Mapping[str, Any] = Field(default_factory=dict)

    @field_validator("tool_id")
    @classmethod
    def validate_tool_id(cls, value: str) -> str:
        """Require a namespaced provider-independent tool identifier."""

        _validate_tool_id(value)
        return value

    @model_validator(mode="after")
    def validate_contract(self) -> "ToolRequest":
        """Validate and freeze request input before it crosses the boundary."""

        _require_aware(self.requested_at, "requested_at")
        _validate_tool_category(self.tool_id, self.category)
        _validate_payload(self.input, "input")
        object.__setattr__(self, "input", _freeze(self.input))
        return self


class ToolResult(_WorkflowContract):
    """Represents the structured outcome of exactly one tool execution."""

    tool_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    invocation_id: str = Field(min_length=1)
    completed_at: datetime
    status: ToolExecutionStatus
    output: Mapping[str, Any] = Field(default_factory=dict)
    summary: Mapping[str, Any] = Field(default_factory=dict)
    artifacts: Tuple[ArtifactReference, ...] = Field(default_factory=tuple)
    warnings: Tuple[str, ...] = Field(default_factory=tuple)
    errors: Tuple[ToolError, ...] = Field(default_factory=tuple)

    @field_validator("tool_id")
    @classmethod
    def validate_tool_id(cls, value: str) -> str:
        """Require a namespaced provider-independent tool identifier."""

        _validate_tool_id(value)
        return value

    @model_validator(mode="after")
    def validate_contract(self) -> "ToolResult":
        """Validate and freeze result payloads before returning them to an agent."""

        _require_aware(self.completed_at, "completed_at")
        _validate_payload(self.output, "output")
        _validate_payload(self.summary, "summary")
        object.__setattr__(self, "output", _freeze(self.output))
        object.__setattr__(self, "summary", _freeze(self.summary))
        return self


class PMQATool(Protocol):
    """Defines the synchronous execution boundary for a PMQA capability."""

    @property
    def metadata(self) -> ToolMetadata:
        """Return the tool's immutable provider-independent metadata."""

        ...

    def invoke(self, request: ToolRequest) -> ToolResult:
        """Execute one request and return a structured result."""

        ...


@dataclass(frozen=True)
class ToolRegistry:
    """Provides deterministic immutable lookup for explicitly supplied tools."""

    _tools: Mapping[str, PMQATool]

    def __init__(self, tools: Iterable[PMQATool] = ()) -> None:
        """Build a sorted registry and reject duplicate stable identifiers."""

        registered = {}
        for tool in tools:
            tool_id = tool.metadata.tool_id
            if tool_id in registered:
                raise ToolContractValidationError(
                    f"Duplicate tool registration for tool_id: {tool_id}"
                )
            registered[tool_id] = tool
        ordered = dict(sorted(registered.items()))
        object.__setattr__(self, "_tools", MappingProxyType(ordered))

    @property
    def tool_ids(self) -> Tuple[str, ...]:
        """Return registered identifiers in deterministic order."""

        return tuple(self._tools)

    def get(self, tool_id: str) -> PMQATool:
        """Return a registered tool or raise a contract-level lookup error."""

        try:
            return self._tools[tool_id]
        except KeyError as error:
            raise ToolContractValidationError(
                f"Tool is not registered: {tool_id}"
            ) from error

    def __len__(self) -> int:
        """Return the number of registered tools."""

        return len(self._tools)


def validate_tool_result(request: ToolRequest, result: ToolResult) -> ToolResult:
    """Validate request/result correlation without execution or mutation."""

    if result.tool_id != request.tool_id:
        raise ToolContractValidationError(
            "Tool result tool_id must match the request tool_id"
        )
    if result.workflow_id != request.workflow_id:
        raise ToolContractValidationError(
            "Tool result workflow_id must match the request workflow_id"
        )
    if result.invocation_id != request.invocation_id:
        raise ToolContractValidationError(
            "Tool result invocation_id must match the request invocation_id"
        )
    if result.completed_at < request.requested_at:
        raise ToolContractValidationError(
            "Tool result completed_at must not precede requested_at"
        )
    return result


_TOOL_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
_CATEGORY_NAMESPACES = {
    ToolCategory.PLAYWRIGHT: "playwright",
    ToolCategory.REASONING: "reasoning",
    ToolCategory.PRODUCT_MEMORY: "memory",
    ToolCategory.FILESYSTEM: "filesystem",
    ToolCategory.VALIDATION: "validation",
    ToolCategory.UTILITY: "utility",
}


def _validate_tool_id(tool_id: str) -> None:
    if _TOOL_ID_PATTERN.fullmatch(tool_id) is None:
        raise ValueError(
            "tool_id must be a lowercase namespaced identifier such as category.action"
        )


def _validate_tool_category(tool_id: str, category: ToolCategory) -> None:
    if tool_id.split(".", 1)[0] != _CATEGORY_NAMESPACES[category]:
        raise ValueError("tool_id namespace must match category")
