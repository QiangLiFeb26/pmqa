"""Offline tests for the generic Product Pack exploration Tool adapter."""

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import subprocess
import sys

import pytest

from pmqa.models import ExplorationEvidence, ExplorationSource
from pmqa.product_pack import (
    LoadedProductPack,
    PRODUCT_PACK_EXPLORATION_FAILURE_CODE,
    ProductPackBridgeExecutionError,
    ProductPackBridgeExecutionErrorCode,
    ProductPackBridgeFailureCode,
    ProductPackBridgeOperation,
    ProductPackBridgeProcessConfig,
    ProductPackBridgeResponse,
    ProductPackBridgeStatus,
    ProductPackCapability,
    ProductPackExplorationTool,
    ProductPackExplorationToolError,
    ProductPackManifest,
)
from pmqa.workflow import (
    AgentRole,
    ToolCategory,
    ToolExecutionStatus,
    ToolRequest,
)


TOOL_ID = "playwright.saucedemo_explore"


def _time(seconds: int = 0) -> datetime:
    return datetime(2026, 7, 20, 12, tzinfo=timezone.utc) + timedelta(
        seconds=seconds
    )


def _manifest(**updates) -> ProductPackManifest:
    values = {
        "schema_version": "1",
        "product_pack_api_version": "1",
        "pack_id": "saucedemo",
        "pack_version": "0.1.0",
        "product_id": "demo",
        "display_name": "SauceDemo Product Pack",
        "capabilities": (ProductPackCapability.EXPLORATION_CAPTURE,),
    }
    values.update(updates)
    return ProductPackManifest(**values)


def _loaded(**manifest_updates) -> LoadedProductPack:
    return LoadedProductPack(
        "pmqa-product-pack-saucedemo",
        _manifest(**manifest_updates),
    )


@pytest.fixture
def process_config(tmp_path) -> ProductPackBridgeProcessConfig:
    bridge = tmp_path / "bridge.js"
    bridge.write_text("// offline fixture\n", encoding="utf-8")
    return ProductPackBridgeProcessConfig(
        executable_path=os.path.normpath(sys.executable),
        bridge_path=str(bridge),
    )


def _request(**updates) -> ToolRequest:
    values = {
        "tool_id": TOOL_ID,
        "category": ToolCategory.PLAYWRIGHT,
        "workflow_id": "workflow.1",
        "invocation_id": "tool.saucedemo.1234",
        "requested_by_agent": AgentRole.EXPLORER,
        "requested_at": _time(),
        "input": {
            "product_id": "demo",
            "actions": (
                "inspect_login_page",
                "login",
                "verify_inventory_page",
                "inspect_inventory_item",
            ),
        },
    }
    values.update(updates)
    return ToolRequest(**values)


def _evidence(bridge_request, **updates) -> ExplorationEvidence:
    values = {
        "schema_version": "1",
        "evidence_id": "evidence.saucedemo.1",
        "workflow_id": bridge_request.workflow_id,
        "product_id": bridge_request.product_id,
        "source": ExplorationSource(
            source_type="typescript-playwright",
            tool_id=bridge_request.tool_id,
            capture_id=bridge_request.request_id,
        ),
        "captured_at": _time(1),
    }
    values.update(updates)
    return ExplorationEvidence(**values)


def _response(bridge_request, **updates) -> ProductPackBridgeResponse:
    values = {
        "protocol_version": "1",
        "request_id": bridge_request.request_id,
        "workflow_id": bridge_request.workflow_id,
        "product_id": bridge_request.product_id,
        "pack_id": bridge_request.pack_id,
        "tool_id": bridge_request.tool_id,
        "operation": ProductPackBridgeOperation.EXPLORATION_CAPTURE,
        "status": ProductPackBridgeStatus.SUCCEEDED,
        "completed_at": _time(2),
        "evidence": _evidence(bridge_request),
        "failure_code": None,
    }
    values.update(updates)
    return ProductPackBridgeResponse(**values)


def test_success_maps_one_exact_bridge_request_and_validated_evidence(
    process_config,
) -> None:
    calls = []

    def runner(bridge_request, config):
        calls.append((bridge_request, config))
        return _response(bridge_request)

    tool = ProductPackExplorationTool(
        _loaded(),
        process_config,
        TOOL_ID,
        bridge_runner=runner,
    )
    request = _request()
    result = tool.invoke(request)

    assert tool.metadata.tool_id == TOOL_ID
    assert tool.metadata.category is ToolCategory.PLAYWRIGHT
    assert len(calls) == 1
    bridge_request, observed_config = calls[0]
    assert observed_config == process_config
    assert observed_config is not process_config
    assert bridge_request.request_id == request.invocation_id
    assert bridge_request.workflow_id == request.workflow_id
    assert bridge_request.pack_id == "saucedemo"
    assert bridge_request.product_id == "demo"
    assert bridge_request.tool_id == TOOL_ID
    assert bridge_request.requested_at == request.requested_at
    assert bridge_request.action_plan == request.input["actions"]
    assert result.status is ToolExecutionStatus.SUCCEEDED
    evidence = ExplorationEvidence.from_workflow_payload(result.output["evidence"])
    assert evidence.source.capture_id == request.invocation_id
    assert result.completed_at == _time(2)
    assert result.summary == {
        "page_count": 0,
        "element_count": 0,
        "locator_candidate_count": 0,
        "interaction_count": 0,
    }


@pytest.mark.parametrize(
    "construction",
    [
        lambda config: ({}, config, TOOL_ID, None),
        lambda config: (_loaded(), {}, TOOL_ID, None),
        lambda config: (_loaded(), config, "Playwright.Bad", None),
        lambda config: (
            _loaded(capabilities=()),
            config,
            TOOL_ID,
            None,
        ),
        lambda config: (_loaded(), config, TOOL_ID, object()),
    ],
)
def test_invalid_construction_fails_before_runner(
    process_config,
    construction,
) -> None:
    loaded, config, tool_id, runner = construction(process_config)
    with pytest.raises(ProductPackExplorationToolError):
        ProductPackExplorationTool(
            loaded,
            config,
            tool_id,
            bridge_runner=runner,
        )


@pytest.mark.parametrize(
    "updates",
    [
        {"requested_by_agent": AgentRole.KNOWLEDGE},
        {"tool_id": "playwright.other"},
        {"input": {"product_id": "other", "actions": ("inspect_login_page",)}},
        {"input": {"product_id": "demo", "actions": ()}},
        {
            "input": {
                "product_id": "demo",
                "actions": ("inspect_login_page", "inspect_login_page"),
            }
        },
        {"input": {"product_id": "demo", "actions": ("browser_context",)}},
        {"input": {"product_id": "demo", "actions": ("Unknown",)}},
        {"input": {"product_id": "demo", "actions": ("inspect_login_page",), "extra": True}},
        {"invocation_id": "invalid:bridge-request"},
    ],
)
def test_invalid_invocation_returns_safe_failure_before_bridge(
    process_config,
    updates,
) -> None:
    calls = []
    tool = ProductPackExplorationTool(
        _loaded(),
        process_config,
        TOOL_ID,
        bridge_runner=lambda *args: calls.append(args),
    )

    result = tool.invoke(_request(**updates))

    assert calls == []
    _assert_safe_failure(result)


@pytest.mark.parametrize(
    "code",
    list(ProductPackBridgeExecutionErrorCode),
)
def test_expected_bridge_execution_failures_are_stable_and_not_retried(
    process_config,
    code,
) -> None:
    calls = []

    def runner(*args):
        calls.append(args)
        raise ProductPackBridgeExecutionError(code)

    tool = ProductPackExplorationTool(
        _loaded(), process_config, TOOL_ID, bridge_runner=runner,
    )
    result = tool.invoke(_request())

    assert len(calls) == 1
    _assert_safe_failure(result)


def test_failed_domain_response_capture_mismatch_and_runner_exception_are_safe(
    process_config,
) -> None:
    def failed(bridge_request, config):
        return _response(
            bridge_request,
            status=ProductPackBridgeStatus.FAILED,
            evidence=None,
            failure_code=ProductPackBridgeFailureCode.EXPLORATION_FAILED,
        )

    def mismatched(bridge_request, config):
        return _response(
            bridge_request,
            evidence=_evidence(
                bridge_request,
                source=ExplorationSource(
                    source_type="typescript-playwright",
                    tool_id=bridge_request.tool_id,
                    capture_id="another-capture",
                ),
            ),
        )

    def unexpected(bridge_request, config):
        raise RuntimeError("runtime-secret-marker raw bridge detail")

    for runner in (failed, mismatched, unexpected):
        tool = ProductPackExplorationTool(
            _loaded(), process_config, TOOL_ID, bridge_runner=runner,
        )
        _assert_safe_failure(tool.invoke(_request()))


@pytest.mark.parametrize(
    "error_type",
    [MemoryError, KeyboardInterrupt, SystemExit, GeneratorExit],
)
def test_control_flow_from_bridge_runner_propagates(process_config, error_type) -> None:
    def runner(*args):
        raise error_type()

    tool = ProductPackExplorationTool(
        _loaded(), process_config, TOOL_ID, bridge_runner=runner,
    )
    with pytest.raises(error_type):
        tool.invoke(_request())


def test_generic_adapter_import_is_product_process_and_playwright_lazy() -> None:
    statement = "\n".join(
        [
            "import os, subprocess, sys",
            "before = dict(os.environ)",
            "def forbidden(*args, **kwargs): raise AssertionError('launched')",
            "subprocess.Popen = forbidden",
            "import pmqa.product_pack.exploration_tool",
            "blocked = ('products', 'playwright', 'langgraph', 'pmqa.runtime', 'pmqa.supervisor', 'pmqa.orchestration')",
            "assert not any(name == prefix or name.startswith(prefix + '.') for prefix in blocked for name in sys.modules)",
            "assert os.environ == before",
        ]
    )
    completed = subprocess.run(
        [sys.executable, "-c", statement],
        capture_output=True,
        check=False,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def _assert_safe_failure(result) -> None:
    assert result.status is ToolExecutionStatus.FAILED
    assert result.output == {}
    assert result.summary == {}
    assert len(result.errors) == 1
    assert result.errors[0].code == PRODUCT_PACK_EXPLORATION_FAILURE_CODE
    assert result.errors[0].message == "Product Pack exploration failed"
    assert "runtime-secret-marker" not in repr(result)
