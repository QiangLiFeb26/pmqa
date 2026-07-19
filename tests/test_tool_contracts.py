"""Tests for provider-independent tool runtime contracts."""

import json
import subprocess
import sys
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from pmqa.workflow import (
    AgentRole,
    ArtifactReference,
    PMQATool,
    ToolCategory,
    ToolContractValidationError,
    ToolError,
    ToolExecutionStatus,
    ToolMetadata,
    ToolRegistry,
    ToolRequest,
    ToolResult,
    validate_tool_result,
)


def test_tool_request_is_typed_immutable_and_json_round_trips() -> None:
    request = _request(input={"target": {"ids": ["element-1"]}})

    assert request.category is ToolCategory.PLAYWRIGHT
    assert request.requested_by_agent is AgentRole.EXPLORER
    assert ToolRequest.model_validate_json(request.model_dump_json()) == request
    assert json.loads(request.model_dump_json())["input"] == {
        "target": {"ids": ["element-1"]}
    }
    with pytest.raises(ValidationError, match="frozen"):
        request.workflow_id = "changed"
    with pytest.raises(TypeError, match="immutable"):
        request.input["changed"] = True
    with pytest.raises(AttributeError):
        request.input["target"]["ids"].append("element-2")


def test_tool_result_is_typed_immutable_and_json_round_trips() -> None:
    result = _result(
        output={"nested": {"ids": ["output-1"]}},
        summary={"operation": "navigate"},
        artifacts=(_artifact(),),
        errors=(ToolError(code="warning", message="bounded failure"),),
    )

    restored = ToolResult.model_validate_json(result.model_dump_json())
    assert restored == result
    assert restored.artifacts[0].artifact_type == "trace"
    assert restored.errors[0].retryable is False
    with pytest.raises(TypeError, match="immutable"):
        result.output["changed"] = True
    with pytest.raises(AttributeError):
        result.output["nested"]["ids"].append("output-2")
    with pytest.raises(TypeError, match="immutable"):
        result.summary["changed"] = True


def test_tool_models_reject_unknown_fields_and_invalid_enums() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        _request(unexpected=True)
    with pytest.raises(ValidationError, match="category"):
        _request(category="network")
    with pytest.raises(ValidationError, match="status"):
        _result(status="running")


def test_tool_id_namespace_must_match_category() -> None:
    with pytest.raises(ValidationError, match="namespace must match"):
        _request(category=ToolCategory.REASONING)
    with pytest.raises(ValidationError, match="namespace must match"):
        _metadata(category=ToolCategory.REASONING)


@pytest.mark.parametrize("contract_name", ["request", "result"])
def test_tool_payloads_reject_runtime_objects(contract_name: str) -> None:
    class RuntimeConnection:
        pass

    model_factory = _request if contract_name == "request" else _result
    payload_field = "input" if contract_name == "request" else "output"
    with pytest.raises(ValidationError, match="runtime object"):
        model_factory(**{payload_field: {"handle": RuntimeConnection()}})


@pytest.mark.parametrize("field_name", ["api_key", "raw-dom", "browser_context"])
def test_tool_payloads_reject_prohibited_fields_without_exposing_values(
    field_name: str,
) -> None:
    sensitive_value = "do-not-report-this-value"

    with pytest.raises(ValidationError) as captured:
        _request(input={field_name: sensitive_value})

    assert sensitive_value not in str(captured.value)


def test_tool_payloads_reject_non_json_values() -> None:
    with pytest.raises(ValidationError, match="non-finite"):
        _request(input={"score": float("nan")})
    with pytest.raises(ValidationError, match="valid string"):
        _result(output={1: "value"})


def test_model_copy_revalidates_and_refreezes_updates() -> None:
    request = _request()

    copied = request.model_copy(update={"input": {"nested": ["value"]}})
    assert copied.input["nested"] == ("value",)
    with pytest.raises(ValidationError):
        request.model_copy(update={"input": {"password": "hidden"}})


def test_tool_metadata_and_artifact_reference_are_strict_contracts() -> None:
    metadata = _metadata()
    artifact = _artifact()

    assert ToolMetadata.model_validate_json(metadata.model_dump_json()) == metadata
    assert ArtifactReference.model_validate_json(artifact.model_dump_json()) == artifact
    with pytest.raises(ValidationError, match="timezone"):
        _artifact(created_at=datetime(2026, 1, 1))
    with pytest.raises(ValidationError, match="Extra inputs"):
        _metadata(provider="chromium")


@pytest.mark.parametrize(
    "tool_id",
    ["navigate", "Playwright.navigate", "playwright.Navigate", "playwright..click"],
)
def test_tool_id_must_be_stable_and_namespaced(tool_id: str) -> None:
    with pytest.raises(ValidationError, match="namespaced"):
        _metadata(tool_id=tool_id)
    with pytest.raises(ValidationError, match="namespaced"):
        _request(tool_id=tool_id)


def test_tool_error_is_structured_immutable_and_json_serializable() -> None:
    error = ToolError(
        code="navigation_failed", message="Navigation failed", retryable=True
    )

    assert ToolError.model_validate_json(error.model_dump_json()) == error
    with pytest.raises(ValidationError, match="frozen"):
        error.retryable = False
    with pytest.raises(ValidationError, match="code"):
        ToolError(code="", message="safe")


def test_tool_registry_is_sorted_immutable_and_supports_lookup() -> None:
    second = _FakeTool(
        _metadata(
            tool_id="validation.schema",
            category=ToolCategory.VALIDATION,
        )
    )
    first = _FakeTool(_metadata(tool_id="playwright.navigate"))
    registry = ToolRegistry([second, first])

    assert registry.tool_ids == ("playwright.navigate", "validation.schema")
    assert registry.get("playwright.navigate") is first
    assert len(registry) == 2
    with pytest.raises(FrozenInstanceError):
        registry._tools = {}
    with pytest.raises(TypeError):
        registry._tools["utility.noop"] = first
    with pytest.raises(ToolContractValidationError, match="not registered"):
        registry.get("utility.noop")


def test_tool_registry_rejects_duplicate_identifiers() -> None:
    metadata = _metadata()

    with pytest.raises(ToolContractValidationError, match="Duplicate"):
        ToolRegistry([_FakeTool(metadata), _FakeTool(metadata)])


def test_fake_tool_satisfies_protocol_shape() -> None:
    tool: PMQATool = _FakeTool(_metadata())

    result = tool.invoke(_request())
    assert validate_tool_result(_request(), result) is result


@pytest.mark.parametrize(
    ("result_update", "message"),
    [
        ({"tool_id": "playwright.click"}, "tool_id"),
        ({"workflow_id": "workflow-2"}, "workflow_id"),
        ({"invocation_id": "invocation-2"}, "invocation_id"),
        (
            {
                "completed_at": datetime(2026, 1, 1, tzinfo=timezone.utc)
                - timedelta(seconds=1)
            },
            "completed_at",
        ),
    ],
)
def test_tool_result_correlation_rejects_mismatches(result_update, message) -> None:
    with pytest.raises(ToolContractValidationError, match=message):
        validate_tool_result(_request(), _result(**result_update))


def test_tool_result_correlation_is_pure() -> None:
    request = _request()
    result = _result()
    request_json = request.model_dump_json()
    result_json = result.model_dump_json()

    assert validate_tool_result(request, result) is result
    assert request.model_dump_json() == request_json
    assert result.model_dump_json() == result_json


def test_tool_timestamps_must_be_timezone_aware() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        _request(requested_at=datetime(2026, 1, 1))
    with pytest.raises(ValidationError, match="timezone"):
        _result(completed_at=datetime(2026, 1, 1))


def test_tool_contract_import_has_no_runtime_dependencies() -> None:
    script = """
import sys
from pmqa.workflow.tools import ToolRequest, ToolResult
for prohibited in ("langgraph", "playwright", "pmqa.providers"):
    assert prohibited not in sys.modules, (prohibited, sorted(sys.modules))
assert ToolRequest is not None and ToolResult is not None
"""

    subprocess.run([sys.executable, "-c", script], check=True)


class _FakeTool:
    def __init__(self, metadata: ToolMetadata) -> None:
        self._metadata = metadata

    @property
    def metadata(self) -> ToolMetadata:
        return self._metadata

    def invoke(self, request: ToolRequest) -> ToolResult:
        return _result(
            tool_id=request.tool_id,
            workflow_id=request.workflow_id,
            invocation_id=request.invocation_id,
            completed_at=request.requested_at,
        )


def _timestamp() -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


def _metadata(**updates) -> ToolMetadata:
    values = {
        "tool_id": "playwright.navigate",
        "category": ToolCategory.PLAYWRIGHT,
        "description": "Navigate using structured input",
        "input_schema_version": "1",
        "output_schema_version": "1",
    }
    values.update(updates)
    return ToolMetadata(**values)


def _artifact(**updates) -> ArtifactReference:
    values = {
        "artifact_id": "artifact-1",
        "artifact_type": "trace",
        "content_type": "application/zip",
        "location": "artifact://trace/artifact-1",
        "created_at": _timestamp(),
    }
    values.update(updates)
    return ArtifactReference(**values)


def _request(**updates) -> ToolRequest:
    values = {
        "tool_id": "playwright.navigate",
        "category": ToolCategory.PLAYWRIGHT,
        "workflow_id": "workflow-1",
        "invocation_id": "invocation-1",
        "requested_by_agent": AgentRole.EXPLORER,
        "requested_at": _timestamp(),
        "input": {"url_ref": "product.start_url"},
    }
    values.update(updates)
    return ToolRequest(**values)


def _result(**updates) -> ToolResult:
    values = {
        "tool_id": "playwright.navigate",
        "workflow_id": "workflow-1",
        "invocation_id": "invocation-1",
        "completed_at": _timestamp(),
        "status": ToolExecutionStatus.SUCCEEDED,
        "output": {"page_id": "login"},
        "summary": {"operation": "navigate"},
    }
    values.update(updates)
    return ToolResult(**values)
