"""Offline tests for the SauceDemo Task 5 application and CLI command."""

import json
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from pmqa import cli
from pmqa.core import Artifact
from pmqa.models import (
    ArtifactStatus,
    InteractionObservation,
    KnowledgeArtifact,
    LocatorCandidateObservation,
    ObservedAttribute,
    ObservedElement,
    ObservedPage,
)
from pmqa.providers import StorageProvider
from pmqa.workflow import TerminationReason, WorkflowStatus
from products.demo import application as application_module
from products.demo.application import (
    TASK5_DEMO_FAILURE_CODE,
    SauceDemoApplicationError,
    SauceDemoApplicationResult,
    run_saucedemo_demo,
)
from products.demo.artifact_handoff import SauceDemoArtifactHandoffError
from products.demo.capture import SauceDemoCaptureResult
from products.demo.config import DemoConfig
from products.demo.knowledge_mapping import SauceDemoKnowledgeCandidate


INVALID_APPLICATION_CONFIG_UPDATES = (
    {"product_id": "runtime-invalid-product-marker"},
    {"allowed_safe_actions": "runtime-invalid-allowed-marker"},
    {"blocked_destructive_actions": "runtime-invalid-blocked-marker"},
    {"maximum_exploration_steps": 0},
    {"artifact_output_location": "runtime-invalid-artifact-path-marker"},
    {
        "generated_test_output_location": "runtime-invalid-generated-path-marker"
    },
    {
        "credential_environment_variables": {
            "username": "runtime-invalid-credential-marker"
        }
    },
    {
        "demo_only_default_credentials": {
            "password": "runtime-invalid-default-marker"
        }
    },
)


def test_application_runs_real_offline_workflow_persists_and_generates(
    tmp_path,
) -> None:
    config = _config(tmp_path)
    original_config = deepcopy(config)
    capture = _CaptureRunner()
    storage = _RecordingStorage()
    output = tmp_path / "generated"

    result = _run_application(
        config=config,
        capture=capture,
        storage=storage,
        output=output,
    )

    assert isinstance(result, SauceDemoApplicationResult)
    assert result.final_state.status is WorkflowStatus.COMPLETED
    assert (
        result.final_state.termination_reason
        is TerminationReason.GOAL_COMPLETED
    )
    assert len(storage.saved) == 1
    assert result.stored_artifact_id == "knowledge"
    assert result.persisted_artifact_path is None
    assert result.generated_test_path == (
        output / "test_saucedemo_generated.py"
    )
    content = result.generated_test_path.read_text(encoding="utf-8")
    assert "def test_successful_login(page: Page)" in content
    assert "def test_inventory_page(page: Page)" in content
    candidate = SauceDemoKnowledgeCandidate.from_workflow_payload(
        result.final_state.knowledge_candidates[-1]
    )
    persisted = KnowledgeArtifact.from_dict(storage.saved[0].data)
    assert all(
        item.lifecycle.state is ArtifactStatus.NEW
        for item in _knowledge_items(candidate.knowledge)
    )
    assert all(
        item.lifecycle.state is ArtifactStatus.VERIFIED
        for item in _knowledge_items(persisted)
    )
    assert capture.calls
    assert config == original_config
    assert not any(
        isinstance(value, (StorageProvider, _CaptureRunner))
        for value in vars(result).values()
    )
    json.loads(result.final_state.model_dump_json())


def test_default_storage_and_output_paths_are_used(tmp_path) -> None:
    config = _config(tmp_path)

    result = run_saucedemo_demo(
        config=config,
        workflow_id="workflow-default-output",
        product_version="1",
        goal="Run the Task 5 demo",
        max_iterations=1,
        created_at=_timestamp(),
        headless=True,
        capture_runner=_CaptureRunner(),
        tool_clock=lambda: _timestamp(),
    )

    assert result.persisted_artifact_path == (
        config.artifact_output_location / "knowledge.json"
    )
    assert result.persisted_artifact_path.exists()
    assert result.generated_test_path == (
        config.generated_test_output_location
        / "test_saucedemo_generated.py"
    )


@pytest.mark.parametrize(
    "updates",
    [
        {"workflow_id": ""},
        {"product_version": "bad version"},
        {"goal": "   "},
        {"max_iterations": 0},
        {"created_at": datetime(2026, 7, 19, 15)},
        {"headless": "yes"},
        {"recursion_limit": 0},
        {"generated_test_output_directory": "not-a-path"},
    ],
)
def test_invalid_application_inputs_fail_before_capture(tmp_path, updates) -> None:
    capture = _CaptureRunner()
    storage = _RecordingStorage()
    values = _application_values(
        config=_config(tmp_path),
        capture=capture,
        storage=storage,
        output=tmp_path / "generated",
    )
    values.update(updates)

    with pytest.raises(SauceDemoApplicationError, match=TASK5_DEMO_FAILURE_CODE):
        run_saucedemo_demo(**values)

    assert capture.calls == []
    assert storage.saved == []
    assert not (tmp_path / "generated").exists()


@pytest.mark.parametrize("updates", INVALID_APPLICATION_CONFIG_UPDATES)
def test_application_rejects_invalid_config_before_external_effects(
    tmp_path, updates
) -> None:
    capture = _CaptureRunner()
    storage = _RecordingStorage()
    output = tmp_path / "generated"
    invalid = replace(_config(tmp_path), **updates)

    with pytest.raises(SauceDemoApplicationError) as captured:
        _run_application(
            config=invalid,
            capture=capture,
            storage=storage,
            output=output,
        )

    assert str(captured.value) == TASK5_DEMO_FAILURE_CODE
    assert capture.calls == []
    assert storage.saved == []
    assert not output.exists()
    assert "runtime-invalid" not in str(captured.value)


def test_capture_failure_has_no_storage_or_generation_and_is_safe(
    tmp_path,
) -> None:
    capture = _CaptureRunner(
        error=RuntimeError(
            "runtime-secret-marker <html>capture</html> credential-marker"
        )
    )
    storage = _RecordingStorage()
    output = tmp_path / "generated"

    with pytest.raises(SauceDemoApplicationError) as captured:
        _run_application(
            config=_config(tmp_path),
            capture=capture,
            storage=storage,
            output=output,
        )

    assert str(captured.value) == TASK5_DEMO_FAILURE_CODE
    assert storage.saved == []
    assert not output.exists()
    assert "runtime-secret-marker" not in str(captured.value)
    assert "<html>" not in str(captured.value)


def test_handoff_failure_has_no_storage_or_generation(
    tmp_path, monkeypatch
) -> None:
    storage = _RecordingStorage()
    output = tmp_path / "generated"

    def fail_handoff(*args, **kwargs):
        raise SauceDemoArtifactHandoffError("safe-handoff-failure")

    monkeypatch.setattr(
        application_module, "persist_verified_knowledge", fail_handoff
    )

    with pytest.raises(SauceDemoApplicationError):
        _run_application(
            config=_config(tmp_path),
            capture=_CaptureRunner(),
            storage=storage,
            output=output,
        )

    assert storage.saved == []
    assert not output.exists()


def test_storage_failure_prevents_generation_and_redacts_marker(tmp_path) -> None:
    storage = _RecordingStorage(
        error=RuntimeError("runtime-secret-marker <html>storage</html>")
    )
    output = tmp_path / "generated"

    with pytest.raises(SauceDemoApplicationError) as captured:
        _run_application(
            config=_config(tmp_path),
            capture=_CaptureRunner(),
            storage=storage,
            output=output,
        )

    assert str(captured.value) == TASK5_DEMO_FAILURE_CODE
    assert len(storage.saved) == 1
    assert not output.exists()
    assert "runtime-secret-marker" not in str(captured.value)


def test_generator_failure_is_safe_after_verified_persistence(
    tmp_path, monkeypatch
) -> None:
    storage = _RecordingStorage()

    def fail_generation(*args, **kwargs):
        raise SauceDemoArtifactHandoffError(
            "runtime-secret-marker <html>generator</html>"
        )

    monkeypatch.setattr(
        application_module,
        "generate_tests_from_verified_workflow",
        fail_generation,
    )

    with pytest.raises(SauceDemoApplicationError) as captured:
        _run_application(
            config=_config(tmp_path),
            capture=_CaptureRunner(),
            storage=storage,
            output=tmp_path / "generated",
        )

    assert len(storage.saved) == 1
    assert str(captured.value) == TASK5_DEMO_FAILURE_CODE
    assert "runtime-secret-marker" not in str(captured.value)


def test_unsupported_product_fails_before_product_loading(capsys) -> None:
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("product capability must not load")

    code = cli.task5_demo(
        "unsupported",
        workflow_id="workflow-1",
        product_version="1",
        goal="goal",
        max_iterations=1,
        headed=False,
        _config_loader=forbidden,
        _application_runner=forbidden,
    )

    output = capsys.readouterr()
    assert code == 2
    assert calls == []
    assert output.out == ""
    assert output.err.strip() == TASK5_DEMO_FAILURE_CODE


def test_cli_success_prints_only_bounded_summary_and_does_not_run_pytest(
    tmp_path, capsys, monkeypatch
) -> None:
    final_state = _run_application(
        config=_config(tmp_path),
        capture=_CaptureRunner(),
        storage=_RecordingStorage(),
        output=tmp_path / "generated",
    ).final_state
    application_result = SimpleNamespace(
        final_state=final_state,
        persisted_artifact_path=tmp_path / "artifacts/knowledge.json",
        generated_test_path=tmp_path / "generated/test_saucedemo_generated.py",
    )

    def fail_if_pytest_runs(*args, **kwargs):
        raise AssertionError("task5-demo must not run pytest")

    monkeypatch.setattr(cli.subprocess, "run", fail_if_pytest_runs)
    code = cli.task5_demo(
        "demo",
        workflow_id="workflow-cli",
        product_version="1",
        goal="Run Task 5",
        max_iterations=1,
        headed=True,
        _config_loader=lambda root: _config(tmp_path),
        _application_runner=lambda **kwargs: application_result,
        _clock=lambda: _timestamp(),
    )

    output = capsys.readouterr()
    assert code == 0
    for expected in (
        "workflow_id=workflow-1",
        "status=completed",
        "termination_reason=goal_completed",
        "iteration=1",
        "evidence_count=1",
        "candidate_count=1",
        "validation_result_count=1",
        "artifact_path=",
        "generated_test_path=",
    ):
        assert expected in output.out
    assert output.err == ""
    assert "runtime-username-marker" not in output.out
    assert "password" not in output.out.casefold()


@pytest.mark.parametrize(
    "config_error",
    [
        OSError("runtime-config-os-marker"),
        json.JSONDecodeError(
            "runtime-config-json-marker",
            "runtime-config-document-marker",
            0,
        ),
        KeyError("runtime-config-key-marker"),
    ],
)
def test_cli_config_loader_failures_are_safe(
    capsys, config_error
) -> None:
    application_calls = []

    def fail_config_load(root):
        raise config_error

    def forbidden_application(**kwargs):
        application_calls.append(kwargs)
        raise AssertionError("application must not execute")

    code = cli.task5_demo(
        "demo",
        workflow_id="workflow-cli",
        product_version="1",
        goal="Run Task 5",
        max_iterations=1,
        headed=False,
        _config_loader=fail_config_load,
        _application_runner=forbidden_application,
        _clock=lambda: _timestamp(),
    )

    output = capsys.readouterr()
    assert code == 2
    assert application_calls == []
    assert output.out == ""
    assert output.err.strip() == TASK5_DEMO_FAILURE_CODE
    assert "Traceback" not in output.err
    assert "runtime-config" not in output.err


def test_cli_invalid_loaded_config_fails_before_application(
    tmp_path, capsys
) -> None:
    application_calls = []
    invalid = replace(
        _config(tmp_path),
        allowed_safe_actions="runtime-invalid-config-marker",
    )

    def forbidden_application(**kwargs):
        application_calls.append(kwargs)
        raise AssertionError("application must not execute")

    code = cli.task5_demo(
        "demo",
        workflow_id="workflow-cli",
        product_version="1",
        goal="Run Task 5",
        max_iterations=1,
        headed=False,
        _config_loader=lambda root: invalid,
        _application_runner=forbidden_application,
        _clock=lambda: _timestamp(),
    )

    output = capsys.readouterr()
    assert code == 2
    assert application_calls == []
    assert output.out == ""
    assert output.err.strip() == TASK5_DEMO_FAILURE_CODE
    assert "runtime-invalid-config-marker" not in output.err


def test_cli_application_failure_is_code_2_without_detail(
    tmp_path, capsys
) -> None:
    def fail_application(**kwargs):
        raise SauceDemoApplicationError(
            "runtime-secret-marker <html>failure</html>"
        )

    code = cli.task5_demo(
        "demo",
        workflow_id="workflow-cli",
        product_version="1",
        goal="Run Task 5",
        max_iterations=1,
        headed=False,
        _config_loader=lambda root: _config(tmp_path),
        _application_runner=fail_application,
        _clock=lambda: _timestamp(),
    )

    output = capsys.readouterr()
    assert code == 2
    assert output.out == ""
    assert output.err.strip() == TASK5_DEMO_FAILURE_CODE
    assert "Traceback" not in output.err
    assert "runtime-secret-marker" not in output.err


@pytest.mark.parametrize(
    "application_error",
    [
        RuntimeError("unexpected runtime programming error"),
        OSError("unexpected os boundary error"),
    ],
)
def test_cli_does_not_hide_unexpected_application_errors(
    tmp_path, application_error
) -> None:
    def fail_application(**kwargs):
        raise application_error

    with pytest.raises(type(application_error), match=str(application_error)):
        cli.task5_demo(
            "demo",
            workflow_id="workflow-cli",
            product_version="1",
            goal="Run Task 5",
            max_iterations=1,
            headed=False,
            _config_loader=lambda root: _config(tmp_path),
            _application_runner=fail_application,
            _clock=lambda: _timestamp(),
        )


def test_main_parser_dispatches_documented_task5_arguments(monkeypatch) -> None:
    observed = {}

    def fake_task5(product, **kwargs):
        observed["product"] = product
        observed.update(kwargs)
        return 0

    monkeypatch.setattr(cli, "task5_demo", fake_task5)

    code = cli.main(
        [
            "task5-demo",
            "--product",
            "demo",
            "--workflow-id",
            "workflow-custom",
            "--product-version",
            "2",
            "--goal",
            "Custom goal",
            "--max-iterations",
            "3",
            "--headed",
        ]
    )

    assert code == 0
    assert observed == {
        "product": "demo",
        "workflow_id": "workflow-custom",
        "product_version": "2",
        "goal": "Custom goal",
        "max_iterations": 3,
        "headed": True,
    }


def test_test_generated_cli_dispatch_remains_supported(monkeypatch) -> None:
    observed = []

    def fake_test_generated(product):
        observed.append(product)
        return 17

    monkeypatch.setattr(cli, "test_generated", fake_test_generated)

    assert cli.main(["test-generated", "--product", "demo"]) == 17
    assert observed == ["demo"]


def test_task5_cli_still_persists_verified_knowledge_and_generates_tests(
    tmp_path, capsys
) -> None:
    product_root = tmp_path / "products/demo"
    config = replace(
        _config(tmp_path),
        artifact_output_location=product_root / "artifacts",
        generated_test_output_location=product_root / "generated_tests",
    )

    def run_offline_application(**kwargs):
        return run_saucedemo_demo(
            **kwargs,
            capture_runner=_CaptureRunner(),
            tool_clock=lambda: _timestamp(),
        )

    code = cli.task5_demo(
        "demo",
        workflow_id="workflow-authoritative-cli",
        product_version="1",
        goal="Build verified SauceDemo product memory",
        max_iterations=1,
        headed=False,
        _config_loader=lambda root: config,
        _application_runner=run_offline_application,
        _clock=lambda: _timestamp(),
    )

    artifact_path = product_root / "artifacts/knowledge.json"
    generated_path = (
        product_root / "generated_tests/test_saucedemo_generated.py"
    )
    artifact = KnowledgeArtifact.from_dict(
        json.loads(artifact_path.read_text(encoding="utf-8"))
    )
    generated = generated_path.read_text(encoding="utf-8")
    committed_regression = (
        Path(__file__).resolve().parents[1]
        / "products/demo/generated_tests/test_saucedemo_generated.py"
    ).read_text(encoding="utf-8")

    assert code == 0
    assert all(
        item.lifecycle.state is ArtifactStatus.VERIFIED
        for item in _knowledge_items(artifact)
    )
    assert "def test_successful_login(page: Page)" in generated
    assert "def test_inventory_page(page: Page)" in generated
    assert generated == committed_regression
    assert "artifact_path=" + str(artifact_path) in capsys.readouterr().out


def test_cli_import_is_lazy_and_generic_pmqa_remains_product_independent() -> None:
    statement = "\n".join(
        [
            "import sys",
            "import pmqa.cli, pmqa.workflow, pmqa.runtime, pmqa.orchestration",
            "assert not any(name == 'products.demo' or ",
            "name.startswith('products.demo.') for name in sys.modules)",
        ]
    )
    completed = subprocess.run(
        [sys.executable, "-c", statement],
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_unsupported_cli_product_does_not_import_demo_package() -> None:
    statement = "\n".join(
        [
            "import sys",
            "from pmqa.cli import task5_demo",
            "code = task5_demo('unsupported', workflow_id='workflow-1', ",
            "product_version='1', goal='goal', max_iterations=1, headed=False)",
            "assert code == 2",
            "assert not any(name == 'products.demo' or ",
            "name.startswith('products.demo.') for name in sys.modules)",
        ]
    )
    completed = subprocess.run(
        [sys.executable, "-c", statement],
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == ""
    assert completed.stderr.strip() == TASK5_DEMO_FAILURE_CODE


class _RecordingStorage(StorageProvider):
    def __init__(self, *, error=None):
        self.saved = []
        self.error = error

    def save(self, artifact: Artifact) -> None:
        self.saved.append(artifact)
        if self.error is not None:
            raise self.error

    def load(self, artifact_id):
        return None


class _CaptureRunner:
    def __init__(self, *, error=None):
        self.calls = []
        self.error = error

    def capture(self, actions):
        self.calls.append(tuple(actions))
        if self.error is not None:
            raise self.error
        return _capture_result()


def _run_application(*, config, capture, storage, output):
    return run_saucedemo_demo(
        **_application_values(
            config=config,
            capture=capture,
            storage=storage,
            output=output,
        )
    )


def _application_values(*, config, capture, storage, output):
    return {
        "config": config,
        "workflow_id": "workflow-1",
        "product_version": "1",
        "goal": "Build verified SauceDemo product memory",
        "max_iterations": 1,
        "created_at": _timestamp(),
        "headless": True,
        "recursion_limit": 24,
        "capture_runner": capture,
        "tool_clock": lambda: _timestamp(),
        "storage": storage,
        "generated_test_output_directory": output,
    }


def _capture_result():
    return SauceDemoCaptureResult(
        pages=(
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
        ),
        elements=(
            ObservedElement(
                element_id="element.username",
                page_id="page.login",
                role="textbox",
                accessible_name="Username",
                attributes=(
                    ObservedAttribute(name="data-test", value="username"),
                    ObservedAttribute(name="type", value="text"),
                ),
            ),
            ObservedElement(
                element_id="element.password",
                page_id="page.login",
                role="textbox",
                accessible_name="Password",
                attributes=(
                    ObservedAttribute(name="data-test", value="password"),
                    ObservedAttribute(name="type", value="password"),
                ),
            ),
            ObservedElement(
                element_id="element.login",
                page_id="page.login",
                role="button",
                accessible_name="Login",
                visible_text="Login",
                attributes=(
                    ObservedAttribute(name="data-test", value="login-button"),
                ),
            ),
            ObservedElement(
                element_id="element.inventory_title",
                page_id="page.inventory",
                role="heading",
                accessible_name="Products",
                visible_text="Products",
                attributes=(ObservedAttribute(name="data-test", value="title"),),
            ),
        ),
        locator_candidates=(
            LocatorCandidateObservation(
                locator_candidate_id="locator.username",
                element_id="element.username",
                strategy="data-test",
                value="username",
                priority=1,
            ),
            LocatorCandidateObservation(
                locator_candidate_id="locator.password",
                element_id="element.password",
                strategy="data-test",
                value="password",
                priority=1,
            ),
            LocatorCandidateObservation(
                locator_candidate_id="locator.login",
                element_id="element.login",
                strategy="data-test",
                value="login-button",
                priority=1,
            ),
            LocatorCandidateObservation(
                locator_candidate_id="locator.inventory_title",
                element_id="element.inventory_title",
                strategy="data-test",
                value="title",
                priority=1,
            ),
        ),
        interactions=(
            InteractionObservation(
                interaction_id="interaction.login",
                source_page_id="page.login",
                target_element_id="element.login",
                action="click",
                outcome_type="navigation",
                outcome_value="/inventory.html",
            ),
        ),
    )


def _config(tmp_path):
    return DemoConfig(
        product_id="demo",
        base_url="https://example.test",
        start_path="/",
        maximum_exploration_steps=4,
        allowed_safe_actions=["inspect", "fill", "click", "stop"],
        blocked_destructive_actions=["checkout", "purchase", "delete"],
        artifact_output_location=tmp_path / "artifacts",
        generated_test_output_location=tmp_path / "generated-default",
        credential_environment_variables={
            "username": "PMQA_TEST_DEMO_USERNAME",
            "password": "PMQA_TEST_DEMO_PASSWORD",
        },
        demo_only_default_credentials={
            "username": "runtime-username-marker",
            "password": "runtime-password-marker",
        },
    )


def _knowledge_items(knowledge):
    return (
        *knowledge.pages,
        *knowledge.elements,
        *knowledge.locators,
        *knowledge.interactions,
    )


def _timestamp():
    return datetime(2026, 7, 19, 15, tzinfo=timezone.utc)
