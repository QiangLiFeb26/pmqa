"""Offline and opt-in live tests for the SauceDemo exploration Tool."""

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from pmqa.core import RunContext, Task
from pmqa.models import (
    ExplorationEvidence,
    InteractionObservation,
    LocatorCandidateObservation,
    ObservedAttribute,
    ObservedElement,
    ObservedPage,
)
from pmqa.runtime import WorkflowRuntime
from pmqa.workflow import (
    AgentRole,
    ToolCategory,
    ToolExecutionStatus,
    ToolRegistry,
    ToolRequest,
)
from products.demo.capture import (
    SAUCEDEMO_EXPLORATION_ACTIONS,
    PlaywrightSauceDemoCapture,
    SauceDemoCaptureResult,
)
from products.demo.config import DemoConfig, load_config
from products.demo.execution import SauceDemoExecutionProvider
from products.demo.exploration_tool import (
    SAUCEDEMO_EXPLORATION_TOOL_ID,
    SauceDemoExplorationTool,
)


def test_tool_metadata_and_registry_contract() -> None:
    tool = _tool(_FakeCapture())
    registry = ToolRegistry([tool])

    assert tool.metadata.tool_id == "playwright.saucedemo_explore"
    assert tool.metadata.category is ToolCategory.PLAYWRIGHT
    assert tool.metadata.description
    assert tool.metadata.input_schema_version == "1"
    assert tool.metadata.output_schema_version == "1"
    assert registry.get(SAUCEDEMO_EXPLORATION_TOOL_ID) is tool


def test_runtime_invokes_tool_and_returns_correlated_evidence() -> None:
    capture = _FakeCapture()
    runtime = WorkflowRuntime(ToolRegistry([_tool(capture)]))
    request = _request()

    result = runtime.invoke_tool(request)
    evidence = ExplorationEvidence.from_workflow_payload(result.output["evidence"])

    assert result.status is ToolExecutionStatus.SUCCEEDED
    assert result.tool_id == request.tool_id
    assert result.workflow_id == request.workflow_id
    assert result.invocation_id == request.invocation_id
    assert result.completed_at == _timestamp()
    assert evidence.workflow_id == request.workflow_id
    assert evidence.product_id == "demo"
    assert evidence.source.tool_id == request.tool_id
    assert evidence.source.capture_id == request.invocation_id
    assert evidence.captured_at == _timestamp()
    assert {page.page_id for page in evidence.pages} == {
        "page.login",
        "page.inventory",
    }
    assert all(
        element.page_id in {page.page_id for page in evidence.pages}
        for element in evidence.elements
    )
    assert result.summary == {
        "page_count": 2,
        "element_count": 4,
        "locator_candidate_count": 4,
        "interaction_count": 1,
    }
    assert capture.calls == [SAUCEDEMO_EXPLORATION_ACTIONS]


def test_identical_offline_inputs_produce_identical_results() -> None:
    first = WorkflowRuntime(ToolRegistry([_tool(_FakeCapture())])).invoke_tool(
        _request()
    )
    second = WorkflowRuntime(ToolRegistry([_tool(_FakeCapture())])).invoke_tool(
        _request()
    )

    assert first == second
    assert first.model_dump_json() == second.model_dump_json()
    assert first.output["evidence"]["evidence_id"].startswith(
        "evidence.saucedemo."
    )


@pytest.mark.parametrize(
    ("input_value", "expected_code"),
    [
        (
            {"product_id": "other", "actions": ["inspect_login_page"]},
            "invalid_product",
        ),
        (
            {"product_id": "demo", "actions": ["unsupported"]},
            "invalid_input",
        ),
        (
            {
                "product_id": "demo",
                "actions": [*SAUCEDEMO_EXPLORATION_ACTIONS, "inspect_login_page"],
            },
            "invalid_action_plan",
        ),
        (
            {"product_id": "demo", "actions": ["login"]},
            "invalid_action_plan",
        ),
    ],
)
def test_invalid_product_or_action_plan_does_not_capture(
    input_value, expected_code: str
) -> None:
    capture = _FakeCapture()
    result = _tool(capture).invoke(_request(input=input_value))

    assert result.status is ToolExecutionStatus.FAILED
    assert result.errors[0].code == expected_code
    assert result.output == {}
    assert capture.calls == []


def test_non_explorer_caller_does_not_capture() -> None:
    capture = _FakeCapture()

    result = _tool(capture).invoke(
        _request(requested_by_agent=AgentRole.KNOWLEDGE)
    )

    assert result.status is ToolExecutionStatus.FAILED
    assert result.errors[0].code == "unauthorized_agent"
    assert capture.calls == []


@pytest.mark.parametrize(
    "extra_field",
    ["url", "selector", "script", "username", "browser_options", "file_path", "command"],
)
def test_arbitrary_execution_input_is_rejected_before_capture(
    extra_field: str,
) -> None:
    capture = _FakeCapture()
    input_value = _input()
    input_value[extra_field] = "runtime-secret-marker"

    result = _tool(capture).invoke(_request(input=input_value))

    assert result.status is ToolExecutionStatus.FAILED
    assert result.errors[0].code == "invalid_input"
    assert "runtime-secret-marker" not in result.model_dump_json()
    assert capture.calls == []


def test_generic_request_rejects_credential_fields_before_tool_invocation() -> None:
    with pytest.raises(ValidationError):
        _request(input={**_input(), "credentials": "runtime-secret-marker"})


def test_destructive_action_is_rejected_before_capture() -> None:
    capture = _FakeCapture()

    result = _tool(capture).invoke(
        _request(input={"product_id": "demo", "actions": ["checkout"]})
    )

    assert result.status is ToolExecutionStatus.FAILED
    assert result.errors[0].code == "invalid_input"
    assert capture.calls == []


def test_capture_exception_becomes_safe_failed_result() -> None:
    capture = _FakeCapture(error=RuntimeError("runtime-secret-marker <html>raw</html>"))

    result = _tool(capture).invoke(_request())

    serialized = result.model_dump_json()
    assert result.status is ToolExecutionStatus.FAILED
    assert result.errors[0].code == "capture_failed"
    assert result.errors[0].retryable is True
    assert result.output == {}
    assert "runtime-secret-marker" not in serialized
    assert "<html>" not in serialized
    assert len(capture.calls) == 1


def test_invalid_or_runtime_capture_output_becomes_safe_failure() -> None:
    invalid = SauceDemoCaptureResult(
        interactions=(
            InteractionObservation(
                interaction_id="interaction.invalid",
                source_page_id="page.missing",
                target_element_id="element.missing",
                action="click",
                outcome_type="navigation",
                outcome_value="/missing",
            ),
        )
    )
    invalid_result = _tool(_FakeCapture(result=invalid)).invoke(_request())
    runtime_result = _tool(_RuntimeCapture()).invoke(_request())

    assert invalid_result.status is ToolExecutionStatus.FAILED
    assert invalid_result.errors[0].code == "invalid_evidence"
    assert runtime_result.status is ToolExecutionStatus.FAILED
    assert runtime_result.errors[0].code == "invalid_evidence"
    assert "runtime-secret-marker" not in runtime_result.model_dump_json()


def test_credentials_never_cross_successful_tool_boundary() -> None:
    config = _config()
    result = _tool(_FakeCapture(), config=config).invoke(_request())
    serialized = result.model_dump_json()

    username, password = config.credentials()
    assert username not in serialized
    assert password not in serialized
    assert result.artifacts == ()
    assert result.warnings == ()
    assert result.errors == ()


def test_existing_execution_provider_maps_shared_capture_to_knowledge() -> None:
    capture = _FakeCapture()
    provider = SauceDemoExecutionProvider(
        config=_config(),
        actions=SAUCEDEMO_EXPLORATION_ACTIONS,
        provenance="deterministic-rule-based",
        capture_runner=capture,
    )

    result = provider.execute(
        Task("explore", "Explore bounded product behavior"),
        RunContext("run-1", "demo"),
    )

    assert result.succeeded is True
    assert result.artifact is not None
    knowledge = result.artifact.data
    assert [page["id"] for page in knowledge["pages"]] == [
        "page.login",
        "page.inventory",
    ]
    assert [locator["id"] for locator in knowledge["locators"]] == [
        "locator.username",
        "locator.password",
        "locator.login",
        "locator.inventory_title",
    ]
    password = next(
        item for item in knowledge["elements"] if item["id"] == "element.password"
    )
    assert password["attributes"] == {"data-test": "password"}
    assert capture.calls == [SAUCEDEMO_EXPLORATION_ACTIONS]


def test_playwright_capture_closes_browser_after_navigation_failure(monkeypatch) -> None:
    browser = _FailingBrowser()
    monkeypatch.setattr(
        "products.demo.capture.sync_playwright",
        lambda: _FakePlaywrightContext(browser),
    )
    runner = PlaywrightSauceDemoCapture(_config())

    with pytest.raises(RuntimeError, match="navigation failed"):
        runner.capture(("inspect_login_page",))

    assert browser.closed is True


def test_generic_imports_remain_product_and_playwright_free() -> None:
    statement = "\n".join(
        [
            "import sys",
            "from pmqa.models.exploration import ExplorationEvidence",
            "from pmqa.runtime import WorkflowRuntime",
            "from pmqa.workflow import ToolRegistry",
            "assert ExplorationEvidence and WorkflowRuntime and ToolRegistry",
            "for prefix in ('products', 'playwright'):",
            "    assert not any(name == prefix or name.startswith(prefix + '.') "
            "for name in sys.modules)",
        ]
    )

    completed = subprocess.run(
        [sys.executable, "-c", statement],
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


@pytest.mark.skipif(
    os.getenv("PMQA_RUN_LIVE_SAUCEDEMO") != "1",
    reason="set PMQA_RUN_LIVE_SAUCEDEMO=1 to run live browser smoke",
)
def test_live_tool_smoke_through_workflow_runtime() -> None:
    root = Path(__file__).resolve().parents[1]
    config = load_config(root)
    now = datetime.now(timezone.utc)
    tool = SauceDemoExplorationTool(config)
    runtime = WorkflowRuntime(ToolRegistry([tool]))
    result = runtime.invoke_tool(_request(requested_at=now))

    assert result.status is ToolExecutionStatus.SUCCEEDED
    evidence = ExplorationEvidence.from_workflow_payload(result.output["evidence"])
    assert {page.page_id for page in evidence.pages} == {
        "page.login",
        "page.inventory",
    }
    assert {element.element_id for element in evidence.elements} >= {
        "element.login",
        "element.inventory_title",
    }
    assert evidence.interactions[0].target_element_id == "element.login"
    serialized = result.model_dump_json()
    username, password = config.credentials()
    assert username not in serialized
    assert password not in serialized


class _FakeCapture:
    def __init__(self, *, result=None, error=None) -> None:
        self.result = result or _capture_result()
        self.error = error
        self.calls = []

    def capture(self, actions):
        self.calls.append(tuple(actions))
        if self.error is not None:
            raise self.error
        return self.result


class _RuntimeCapture:
    def capture(self, actions):
        _ = actions

        class RuntimeResult:
            def __repr__(self) -> str:
                return "RuntimeResult(runtime-secret-marker)"

        return RuntimeResult()


class _FailingPage:
    def goto(self, url):
        _ = url
        raise RuntimeError("navigation failed")


class _FailingBrowser:
    def __init__(self) -> None:
        self.closed = False

    def new_page(self):
        return _FailingPage()

    def close(self) -> None:
        self.closed = True


class _FakeChromium:
    def __init__(self, browser) -> None:
        self.browser = browser

    def launch(self, *, headless):
        _ = headless
        return self.browser


class _FakePlaywright:
    def __init__(self, browser) -> None:
        self.chromium = _FakeChromium(browser)


class _FakePlaywrightContext:
    def __init__(self, browser) -> None:
        self.playwright = _FakePlaywright(browser)

    def __enter__(self):
        return self.playwright

    def __exit__(self, exc_type, exc, traceback):
        _ = exc_type, exc, traceback


def _tool(capture, *, config=None) -> SauceDemoExplorationTool:
    return SauceDemoExplorationTool(
        config or _config(),
        capture_runner=capture,
        clock=_timestamp,
    )


def _request(**updates) -> ToolRequest:
    values = {
        "tool_id": SAUCEDEMO_EXPLORATION_TOOL_ID,
        "category": ToolCategory.PLAYWRIGHT,
        "workflow_id": "workflow-1",
        "invocation_id": "invocation-1",
        "requested_by_agent": AgentRole.EXPLORER,
        "requested_at": _timestamp(),
        "input": _input(),
    }
    values.update(updates)
    return ToolRequest(**values)


def _input():
    return {
        "product_id": "demo",
        "actions": list(SAUCEDEMO_EXPLORATION_ACTIONS),
    }


def _timestamp() -> datetime:
    return datetime(2026, 7, 19, 15, tzinfo=timezone.utc)


def _config() -> DemoConfig:
    root = Path(__file__).resolve().parents[1]
    return DemoConfig(
        product_id="demo",
        base_url="https://example.test",
        start_path="/",
        maximum_exploration_steps=4,
        allowed_safe_actions=["inspect", "fill", "click", "stop"],
        blocked_destructive_actions=["checkout", "purchase", "delete"],
        artifact_output_location=root / "products/demo/artifacts",
        generated_test_output_location=root / "products/demo/generated_tests",
        credential_environment_variables={
            "username": "PMQA_TEST_DEMO_USERNAME",
            "password": "PMQA_TEST_DEMO_PASSWORD",
        },
        demo_only_default_credentials={
            "username": "runtime-username-marker",
            "password": "runtime-password-marker",
        },
    )


def _capture_result() -> SauceDemoCaptureResult:
    pages = (
        ObservedPage(
            page_id="page.login",
            url="https://example.test/",
            title="Login",
            structural_fingerprint="login-fingerprint",
        ),
        ObservedPage(
            page_id="page.inventory",
            url="https://example.test/inventory.html",
            title="Inventory",
            structural_fingerprint="inventory-fingerprint",
        ),
    )
    elements = (
        _element("element.username", "page.login", "textbox", "Username", "username"),
        _element(
            "element.password",
            "page.login",
            "textbox",
            "Password",
            "password",
            input_type="password",
        ),
        _element("element.login", "page.login", "button", "Login", "login-button"),
        _element(
            "element.inventory_title",
            "page.inventory",
            "heading",
            "Products",
            "title",
        ),
    )
    locator_candidates = tuple(
        LocatorCandidateObservation(
            locator_candidate_id="locator." + element.element_id.split(".")[-1],
            element_id=element.element_id,
            strategy="data-test",
            value=next(
                attribute.value
                for attribute in element.attributes
                if attribute.name == "data-test"
            ),
            priority=1,
        )
        for element in elements
    )
    interactions = (
        InteractionObservation(
            interaction_id="interaction.login",
            source_page_id="page.login",
            target_element_id="element.login",
            action="click",
            outcome_type="navigation",
            outcome_value="/inventory.html",
        ),
    )
    return SauceDemoCaptureResult(
        pages=pages,
        elements=elements,
        locator_candidates=locator_candidates,
        interactions=interactions,
    )


def _element(
    element_id,
    page_id,
    role,
    accessible_name,
    test_id,
    *,
    input_type=None,
):
    attributes = [ObservedAttribute(name="data-test", value=test_id)]
    if input_type is not None:
        attributes.append(ObservedAttribute(name="type", value=input_type))
    return ObservedElement(
        element_id=element_id,
        page_id=page_id,
        role=role,
        accessible_name=accessible_name,
        visible_text=accessible_name if role != "textbox" else None,
        attributes=tuple(attributes),
    )
