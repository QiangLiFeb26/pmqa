"""Offline tests for demo configuration and artifact-driven generation."""

from pathlib import Path

from pmqa.models import KnowledgeArtifact, Lifecycle, Locator
from products.demo.config import load_config
from products.demo.generator import generate_tests
from products.demo.reasoning import DeterministicDemoReasoningProvider
from pmqa.core import RunContext, Task


def test_demo_plan_is_bounded_and_has_explicit_provenance() -> None:
    root = Path(__file__).resolve().parents[1]
    config = load_config(root)
    provider = DeterministicDemoReasoningProvider()

    plan = provider.reason(Task("explore", "safe demo"), RunContext("run", "demo"))

    assert plan.data["provenance"] == "deterministic-rule-based"
    assert len(plan.data["actions"]) <= config.maximum_exploration_steps
    assert "checkout" not in plan.data["actions"]


def test_generator_requires_and_uses_artifact_locators(tmp_path) -> None:
    lifecycle = Lifecycle()
    artifact = KnowledgeArtifact(
        artifact_id="knowledge",
        product_id="demo",
        reasoning_provenance="deterministic-rule-based",
        locators=[
            Locator("l1", lifecycle, "element.username", "data-test", "user", 1),
            Locator("l2", lifecycle, "element.password", "data-test", "pass", 1),
            Locator("l3", lifecycle, "element.login", "data-test", "login", 1),
            Locator("l4", lifecycle, "element.inventory_title", "data-test", "title", 1),
        ],
    )

    output = generate_tests(artifact, tmp_path)

    generated = output.read_text(encoding="utf-8")
    assert "ARTIFACT[\"locators\"]" in generated
    assert "test_successful_login" in generated
    assert "test_inventory_page" in generated
