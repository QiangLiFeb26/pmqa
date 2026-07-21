"""Offline vertical-slice tests for the SauceDemo external Product Pack."""

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import pytest

from pmqa.models import (
    ArtifactStatus,
    ExplorationEvidence,
    ExplorationSource,
    InteractionObservation,
    LocatorCandidateObservation,
    ObservedAttribute,
    ObservedElement,
    ObservedPage,
)
from pmqa.product_pack import (
    LoadedProductPack,
    ProductPackBackendSourceState,
    ProductPackBridgeFailureCode,
    ProductPackBridgeOperation,
    ProductPackBridgeProcessConfig,
    ProductPackBridgeRequest,
    ProductPackBridgeResponse,
    ProductPackBridgeStatus,
    ProductPackCapability,
    ProductPackLoadRequest,
    load_product_pack_manifest,
    run_product_pack_bridge,
    validate_product_pack_source,
)
from pmqa.storage import JsonFileStorage
from pmqa.workflow import AgentRole, TerminationReason, WorkflowStatus
from products.demo.artifact_handoff import (
    extract_verified_knowledge,
    generate_tests_from_verified_workflow,
    persist_verified_knowledge,
)
from products.demo.capture import SauceDemoCaptureResult
from products.demo.config import DemoConfig
from products.demo.product_pack_workflow import (
    SAUCEDEMO_PRODUCT_PACK_DISTRIBUTION,
    SAUCEDEMO_PRODUCT_PACK_MANIFEST,
    SauceDemoProductPackWorkflowCompositionError,
    run_saucedemo_product_pack_workflow,
)
from products.demo.workflow import (
    create_saucedemo_workflow_state,
    run_saucedemo_workflow,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_ROOT = REPOSITORY_ROOT / "examples/product_packs/saucedemo"


def _time(seconds: int = 0) -> datetime:
    return datetime(2026, 7, 20, 12, tzinfo=timezone.utc) + timedelta(
        seconds=seconds
    )


def _config(tmp_path: Path) -> DemoConfig:
    return DemoConfig(
        product_id="demo",
        base_url="https://example.test",
        start_path="/",
        maximum_exploration_steps=4,
        allowed_safe_actions=["inspect", "fill", "click", "stop"],
        blocked_destructive_actions=["checkout", "purchase", "delete"],
        artifact_output_location=tmp_path / "artifacts",
        generated_test_output_location=tmp_path / "generated",
        credential_environment_variables={
            "username": "PMQA_DEMO_USERNAME",
            "password": "PMQA_DEMO_PASSWORD",
        },
        demo_only_default_credentials={
            "username": "standard_user",
            "password": "secret_sauce",
        },
    )


def _loaded(**manifest_updates) -> LoadedProductPack:
    manifest = SAUCEDEMO_PRODUCT_PACK_MANIFEST.model_copy(
        update=manifest_updates
    )
    return LoadedProductPack(SAUCEDEMO_PRODUCT_PACK_DISTRIBUTION, manifest)


def _initial(config: DemoConfig):
    return create_saucedemo_workflow_state(
        config,
        workflow_id="workflow.saucedemo.pack",
        product_version="1",
        goal="Build verified SauceDemo product memory",
        max_iterations=1,
        created_at=_time(),
    )


@pytest.fixture
def process_config(tmp_path) -> ProductPackBridgeProcessConfig:
    bridge = tmp_path / "bridge.js"
    bridge.write_text("// offline fake bridge seam\n", encoding="utf-8")
    return ProductPackBridgeProcessConfig(
        executable_path=os.path.normpath(sys.executable),
        bridge_path=str(bridge),
    )


def _observations():
    pages = (
        ObservedPage(
            page_id="page.login",
            url="https://example.test/",
            title="Swag Labs",
            structural_fingerprint="login-fingerprint",
        ),
        ObservedPage(
            page_id="page.inventory",
            url="https://example.test/inventory.html",
            title="Swag Labs",
            structural_fingerprint="inventory-fingerprint",
        ),
    )
    elements = (
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
    )
    locators = tuple(
        LocatorCandidateObservation(
            locator_candidate_id="locator." + suffix,
            element_id="element." + suffix,
            strategy="data-test",
            value=value,
            priority=1,
        )
        for suffix, value in (
            ("username", "username"),
            ("password", "password"),
            ("login", "login-button"),
            ("inventory_title", "title"),
        )
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
    return pages, elements, locators, interactions


class _FakeBridgeRunner:
    def __init__(self, *, failure=None, exception=None):
        self.failure = failure
        self.exception = exception
        self.calls = []

    def __call__(self, request, config):
        self.calls.append((request, config))
        if self.exception is not None:
            raise self.exception
        if self.failure is not None:
            return ProductPackBridgeResponse(
                protocol_version="1",
                request_id=request.request_id,
                workflow_id=request.workflow_id,
                product_id=request.product_id,
                pack_id=request.pack_id,
                tool_id=request.tool_id,
                operation=request.operation,
                status=ProductPackBridgeStatus.FAILED,
                completed_at=_time(1),
                evidence=None,
                failure_code=self.failure,
            )
        pages, elements, locators, interactions = _observations()
        digest = hashlib.sha256(
            (request.workflow_id + "\0" + request.request_id).encode()
        ).hexdigest()[:24]
        evidence = ExplorationEvidence(
            schema_version="1",
            evidence_id="evidence.saucedemo." + digest,
            workflow_id=request.workflow_id,
            product_id=request.product_id,
            source=ExplorationSource(
                source_type="typescript-playwright",
                tool_id=request.tool_id,
                capture_id=request.request_id,
            ),
            captured_at=_time(1),
            pages=pages,
            elements=elements,
            locator_candidates=locators,
            interactions=interactions,
        )
        return ProductPackBridgeResponse(
            protocol_version="1",
            request_id=request.request_id,
            workflow_id=request.workflow_id,
            product_id=request.product_id,
            pack_id=request.pack_id,
            tool_id=request.tool_id,
            operation=ProductPackBridgeOperation.EXPLORATION_CAPTURE,
            status=ProductPackBridgeStatus.SUCCEEDED,
            completed_at=_time(1),
            evidence=evidence,
            failure_code=None,
        )


def test_external_example_source_is_custom_conformant_and_manifest_is_exact() -> None:
    result = validate_product_pack_source(
        str(EXAMPLE_ROOT.resolve()),
        SAUCEDEMO_PRODUCT_PACK_MANIFEST,
    )
    assert result.is_conformant is True
    assert result.backend_source_state is ProductPackBackendSourceState.CUSTOM
    assert result.is_runtime_verified is False
    assert SAUCEDEMO_PRODUCT_PACK_MANIFEST.to_dict() == {
        "schema_version": "1",
        "product_pack_api_version": "1",
        "pack_id": "saucedemo",
        "pack_version": "0.1.0",
        "product_id": "demo",
        "display_name": "SauceDemo Product Pack",
        "capabilities": ["exploration_capture"],
    }
    assert 'version = "0.1.0a1"' in (EXAMPLE_ROOT / "pyproject.toml").read_text()
    package = json.loads((EXAMPLE_ROOT / "bridge/package.json").read_text())
    lock = json.loads((EXAMPLE_ROOT / "bridge/package-lock.json").read_text())
    assert package["dependencies"] == {"playwright": "1.60.0"}
    assert package["devDependencies"] == {
        "@types/node": "24.10.1",
        "typescript": "5.9.3",
    }
    assert lock["packages"][""]["dependencies"] == package["dependencies"]
    source_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (EXAMPLE_ROOT / "bridge").rglob("*")
        if path.is_file()
    ).casefold()
    for prohibited in (
        "@playwright/mcp",
        "playwright-mcp",
        "child_process",
        "npx ",
        '"latest"',
        '"preinstall"',
        '"postinstall"',
    ):
        assert prohibited not in source_text
    forbidden_parts = {
        "node_modules",
        "dist",
        "screenshots",
        "traces",
        "test-results",
        "artifacts",
        ".env",
    }
    assert not any(
        forbidden_parts.intersection(path.relative_to(EXAMPLE_ROOT).parts)
        for path in EXAMPLE_ROOT.rglob("*")
    )


def test_offline_external_pack_workflow_handoff_and_generation_match_direct_path(
    tmp_path,
    process_config,
) -> None:
    config = _config(tmp_path)
    config_before = deepcopy(config)
    initial = _initial(config)
    initial_before = initial.model_dump_json()
    runner = _FakeBridgeRunner()

    external = run_saucedemo_product_pack_workflow(
        config,
        initial,
        _loaded(),
        process_config,
        bridge_runner=runner,
        recursion_limit=24,
    )
    pages, elements, locators, interactions = _observations()
    direct = run_saucedemo_workflow(
        config,
        initial,
        capture_runner=_CaptureRunner(
            SauceDemoCaptureResult(pages, elements, locators, interactions)
        ),
        clock=lambda: _time(1),
        recursion_limit=24,
    )

    assert external.status is WorkflowStatus.COMPLETED
    assert external.termination_reason is TerminationReason.GOAL_COMPLETED
    assert external.iteration == external.max_iterations == 1
    assert len(runner.calls) == 1
    assert len(external.evidence) == 1
    assert len(external.knowledge_candidates) == 1
    assert len(external.validation_results) == 1
    assert [item.agent for item in external.step_history] == [
        AgentRole.EXPLORER,
        AgentRole.KNOWLEDGE,
        AgentRole.VALIDATOR,
    ]
    assert external.validation_results[0]["status"] == "passed"
    assert external.warnings == () and external.errors == ()
    candidate = external.knowledge_candidates[0]["knowledge"]
    assert all(
        item["lifecycle"]["state"] == ArtifactStatus.NEW.value
        for collection in ("pages", "elements", "locators", "interactions")
        for item in candidate[collection]
    )
    external_knowledge = extract_verified_knowledge(external, config)
    direct_knowledge = extract_verified_knowledge(direct, config)
    assert external_knowledge.to_dict() == direct_knowledge.to_dict()

    storage = JsonFileStorage(tmp_path / "stored")
    stored = persist_verified_knowledge(external, config, storage)
    assert storage.load(stored.artifact_id).data == external_knowledge.to_dict()
    external_test = generate_tests_from_verified_workflow(
        external, config, tmp_path / "external-generated"
    )
    direct_test = generate_tests_from_verified_workflow(
        direct, config, tmp_path / "direct-generated"
    )
    assert external_test.read_bytes() == direct_test.read_bytes()

    serialized = external.model_dump_json()
    for forbidden in (
        process_config.executable_path,
        process_config.bridge_path,
        "SAUCEDEMO_USERNAME",
        "SAUCEDEMO_PASSWORD",
        "runtime-secret-marker",
        "node_modules",
    ):
        assert forbidden not in serialized
    assert config == config_before
    assert initial.model_dump_json() == initial_before


@pytest.mark.parametrize(
    "loaded",
    [
        _loaded(pack_version="0.2.0"),
        _loaded(capabilities=()),
        _loaded(product_id="other"),
        _loaded(pack_id="other"),
    ],
)
def test_manifest_capability_product_and_pack_mismatch_fail_before_bridge(
    tmp_path,
    process_config,
    loaded,
) -> None:
    runner = _FakeBridgeRunner()
    config = _config(tmp_path)
    with pytest.raises(SauceDemoProductPackWorkflowCompositionError):
        run_saucedemo_product_pack_workflow(
            config,
            _initial(config),
            loaded,
            process_config,
            bridge_runner=runner,
        )
    assert runner.calls == []


def test_invalid_config_and_workflow_mismatch_fail_before_bridge(
    tmp_path,
    process_config,
) -> None:
    runner = _FakeBridgeRunner()
    config = _config(tmp_path)
    invalid_config = replace(config, maximum_exploration_steps=0)
    mismatched_state = _initial(config).model_copy(update={"product_id": "other"})
    for selected_config, state in (
        (invalid_config, _initial(config)),
        (config, mismatched_state),
    ):
        with pytest.raises(SauceDemoProductPackWorkflowCompositionError):
            run_saucedemo_product_pack_workflow(
                selected_config,
                state,
                _loaded(),
                process_config,
                bridge_runner=runner,
            )
    assert runner.calls == []


def test_bridge_failure_produces_bounded_existing_workflow_failure(
    tmp_path,
    process_config,
) -> None:
    config = _config(tmp_path)
    runner = _FakeBridgeRunner(
        exception=RuntimeError("runtime-secret-marker raw bridge detail")
    )
    final = run_saucedemo_product_pack_workflow(
        config,
        _initial(config),
        _loaded(),
        process_config,
        bridge_runner=runner,
    )

    assert len(runner.calls) == 1
    assert final.status is WorkflowStatus.FAILED
    assert final.termination_reason is TerminationReason.ERROR
    assert final.evidence == ()
    assert final.knowledge_candidates == ()
    assert final.validation_results == ()
    assert final.errors == ("explorer_tool_failed",)
    assert len(final.step_history) == 1
    assert final.step_history[0].agent is AgentRole.EXPLORER
    assert final.step_history[0].status.value == "failed"
    assert "runtime-secret-marker" not in final.model_dump_json()


def test_external_example_wheel_loads_explicitly_outside_repository(tmp_path) -> None:
    wheel_dir = tmp_path / "wheel"
    installed = tmp_path / "installed"
    unrelated = tmp_path / "unrelated"
    wheel_dir.mkdir()
    installed.mkdir()
    unrelated.mkdir()
    built = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            str(wheel_dir),
            str(EXAMPLE_ROOT),
        ],
        cwd=tmp_path,
        capture_output=True,
        check=False,
        text=True,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    (wheel,) = tuple(wheel_dir.glob("*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        assert "pmqa_product_pack_saucedemo/manifest.py" in names
        assert not any(name.startswith("bridge/") for name in names)
        archive.extractall(installed)

    statement = """
import sys
from pathlib import Path
from pmqa.product_pack import ProductPackLoadRequest, load_product_pack_manifest
from products.demo.product_pack_workflow import SAUCEDEMO_PRODUCT_PACK_MANIFEST
installed = Path(sys.argv[1]).resolve()
repository = Path(sys.argv[2]).resolve()
loaded = load_product_pack_manifest(ProductPackLoadRequest(
    distribution_name="pmqa-product-pack-saucedemo",
    expected_manifest=SAUCEDEMO_PRODUCT_PACK_MANIFEST,
))
assert loaded.manifest == SAUCEDEMO_PRODUCT_PACK_MANIFEST
import pmqa_product_pack_saucedemo
path = Path(pmqa_product_pack_saucedemo.__file__).resolve()
path.relative_to(installed)
try: path.relative_to(repository)
except ValueError: pass
else: raise AssertionError("external pack loaded from repository")
"""
    environment = {
        key: value for key, value in os.environ.items()
        if key not in {"PYTHONHOME", "PYTHONPATH"}
    }
    environment["PYTHONPATH"] = os.pathsep.join(
        (str(REPOSITORY_ROOT), str(installed))
    )
    loaded = subprocess.run(
        [sys.executable, "-c", statement, str(installed), str(REPOSITORY_ROOT)],
        cwd=unrelated,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
    )
    assert loaded.returncode == 0, loaded.stdout + loaded.stderr


@pytest.mark.skipif(
    os.getenv("PMQA_RUN_PRODUCT_PACK_NODE_SMOKE") != "1",
    reason="set PMQA_RUN_PRODUCT_PACK_NODE_SMOKE=1 for real Node bridge smoke",
)
def test_real_typescript_bridge_process_framing_and_correlation(tmp_path) -> None:
    node, bridge = _build_typescript_bridge(tmp_path)
    requested_at = datetime.now(timezone.utc)
    config = ProductPackBridgeProcessConfig(
        executable_path=node,
        bridge_path=str(bridge),
    )
    rejected_plans = (
        ("unknown_action",),
        ("inspect_login_page", "inspect_login_page"),
        ("login", "inspect_login_page"),
        ("login",),
        (
            "inspect_login_page",
            "login",
            "verify_inventory_page",
            "inspect_inventory_item",
            "extra_action",
        ),
    )
    for index, action_plan in enumerate(rejected_plans):
        request = ProductPackBridgeRequest(
            protocol_version="1",
            request_id="tool.saucedemo.node.smoke." + str(index),
            workflow_id="workflow.saucedemo.node.smoke",
            product_id="demo",
            pack_id="saucedemo",
            tool_id="playwright.saucedemo_explore",
            operation=ProductPackBridgeOperation.EXPLORATION_CAPTURE,
            requested_at=requested_at,
            action_plan=action_plan,
        )
        response = run_product_pack_bridge(request, config)
        assert response.request_id == request.request_id
        assert response.workflow_id == request.workflow_id
        assert response.status is ProductPackBridgeStatus.FAILED
        assert response.failure_code is (
            ProductPackBridgeFailureCode.ACTION_PLAN_REJECTED
        )


@pytest.mark.skipif(
    os.getenv("PMQA_RUN_PRODUCT_PACK_LIVE") != "1"
    or not os.getenv("SAUCEDEMO_USERNAME")
    or not os.getenv("SAUCEDEMO_PASSWORD"),
    reason="enable live Product Pack smoke with child-environment credentials",
)
def test_real_typescript_playwright_product_pack_workflow(tmp_path) -> None:
    node, bridge = _build_typescript_bridge(tmp_path)
    config = _config(tmp_path)
    created_at = datetime.now(timezone.utc)
    initial = create_saucedemo_workflow_state(
        config,
        workflow_id="workflow.saucedemo.live.pack",
        product_version="live",
        goal="Validate the real external SauceDemo Product Pack",
        max_iterations=1,
        created_at=created_at,
    )
    final = run_saucedemo_product_pack_workflow(
        config,
        initial,
        _loaded(),
        ProductPackBridgeProcessConfig(
            executable_path=node,
            bridge_path=str(bridge),
            timeout_seconds=60,
        ),
        recursion_limit=24,
    )
    knowledge = extract_verified_knowledge(final, config)
    assert final.status is WorkflowStatus.COMPLETED
    assert final.termination_reason is TerminationReason.GOAL_COMPLETED
    assert len(final.evidence) == 1
    assert len(final.validation_results) == 1
    assert knowledge.pages and knowledge.elements and knowledge.locators
    assert final.errors == () and final.warnings == ()


def _build_typescript_bridge(tmp_path: Path):
    npm = shutil.which("npm")
    node = shutil.which("node")
    assert npm is not None and node is not None
    source = tmp_path / "bridge"
    shutil.copytree(EXAMPLE_ROOT / "bridge", source)
    environment = dict(os.environ)
    environment["PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD"] = "1"
    installed = subprocess.run(
        [npm, "ci", "--ignore-scripts", "--no-audit", "--no-fund"],
        cwd=source,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
    )
    assert installed.returncode == 0, installed.stdout + installed.stderr
    built = subprocess.run(
        [npm, "run", "build"],
        cwd=source,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    bridge = source / "dist/main.js"
    assert bridge.is_file()
    return os.path.normpath(node), bridge


class _CaptureRunner:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def capture(self, actions):
        self.calls.append(tuple(actions))
        return self.result
