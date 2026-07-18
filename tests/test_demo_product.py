"""Offline tests for demo configuration and artifact-driven generation."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from pmqa.reasoning import ReasoningDecision, ReasoningRequest
from pmqa.models import (
    Element,
    Interaction,
    KnowledgeArtifact,
    Lifecycle,
    Locator,
    Page,
)
from products.demo.config import load_config
from products.demo.generator import generate_tests
from products.demo.reasoning import DeterministicDemoReasoningProvider


def test_demo_plan_is_bounded_and_has_explicit_provenance() -> None:
    root = Path(__file__).resolve().parents[1]
    config = load_config(root)
    provider = DeterministicDemoReasoningProvider()

    plan = provider.reason(
        ReasoningRequest(
            request_id="request-1",
            workflow_id="run",
            task_type="explore",
            provider_hint="deterministic",
            product_id="demo",
            artifact_version="1",
            constraints={"maximum_steps": config.maximum_exploration_steps},
        )
    )

    actions = [decision.value["action"] for decision in plan.decisions]
    assert plan.provider == "deterministic-rule-based"
    assert all(isinstance(decision, ReasoningDecision) for decision in plan.decisions)
    assert len(actions) <= config.maximum_exploration_steps
    assert "checkout" not in actions


def test_generator_derives_content_from_artifact_relationships(tmp_path) -> None:
    artifact = _artifact()

    first = generate_tests(artifact, tmp_path).read_text(encoding="utf-8")
    changed_elements = [
        replace(element, id="element.catalog_heading", visible_text="Catalog")
        if element.id == "element.inventory_title"
        else element
        for element in artifact.elements
    ]
    changed_locators = [
        replace(locator, element_id="element.catalog_heading")
        if locator.element_id == "element.inventory_title"
        else locator
        for locator in artifact.locators
    ]
    changed = replace(artifact, elements=changed_elements, locators=changed_locators)

    second = generate_tests(changed, tmp_path).read_text(encoding="utf-8")

    assert 'INVENTORY_ASSERTION_ELEMENT_ID = "element.inventory_title"' in first
    assert 'EXPECTED_INVENTORY_TEXT = "Products"' in first
    assert 'INVENTORY_ASSERTION_ELEMENT_ID = "element.catalog_heading"' in second
    assert 'EXPECTED_INVENTORY_TEXT = "Catalog"' in second
    assert first != second


def test_generator_fails_without_required_interaction(tmp_path) -> None:
    artifact = replace(_artifact(), interactions=[])

    with pytest.raises(ValueError, match="login navigation interaction"):
        generate_tests(artifact, tmp_path)


def test_generator_fails_without_expected_destination(tmp_path) -> None:
    artifact = _artifact()
    broken = replace(
        artifact,
        interactions=[replace(artifact.interactions[0], expected_outcome_value="/missing.html")],
    )

    with pytest.raises(ValueError, match="destination page evidence"):
        generate_tests(broken, tmp_path)


def test_generator_fails_without_assertion_evidence(tmp_path) -> None:
    artifact = _artifact()
    broken = replace(
        artifact,
        elements=[
            replace(element, visible_text=None)
            if element.id == "element.inventory_title"
            else element
            for element in artifact.elements
        ],
    )

    with pytest.raises(ValueError, match="assertion evidence"):
        generate_tests(broken, tmp_path)


def test_persisted_artifact_contains_no_demo_credential_values() -> None:
    root = Path(__file__).resolve().parents[1]
    config = load_config(root)
    artifact_text = (config.artifact_output_location / "knowledge.json").read_text(
        encoding="utf-8"
    )

    assert config.demo_only_default_credentials["username"] not in artifact_text
    assert config.demo_only_default_credentials["password"] not in artifact_text
    assert not _contains_sensitive_key(json.loads(artifact_text))


def _artifact() -> KnowledgeArtifact:
    lifecycle = Lifecycle()
    pages = [
        Page("page.login", lifecycle, "https://example.test/", "Login", "login-fp"),
        Page(
            "page.inventory",
            lifecycle,
            "https://example.test/inventory.html",
            "Inventory",
            "inventory-fp",
        ),
    ]
    elements = [
        Element("element.user", lifecycle, "page.login", "textbox", "Username"),
        Element("element.pass", lifecycle, "page.login", "textbox", "Password"),
        Element("element.submit", lifecycle, "page.login", "button", "Login", "Login"),
        Element(
            "element.inventory_title",
            lifecycle,
            "page.inventory",
            "heading",
            "Products",
            "Products",
        ),
    ]
    locators = [
        Locator("locator.user", lifecycle, "element.user", "data-test", "username", 1),
        Locator("locator.pass", lifecycle, "element.pass", "data-test", "password", 1),
        Locator("locator.submit", lifecycle, "element.submit", "data-test", "login-button", 1),
        Locator(
            "locator.heading",
            lifecycle,
            "element.inventory_title",
            "data-test",
            "title",
            1,
        ),
    ]
    interaction = Interaction(
        "interaction.sign_in",
        lifecycle,
        "page.login",
        "element.submit",
        "click",
        "navigation",
        "/inventory.html",
    )
    return KnowledgeArtifact(
        artifact_id="knowledge",
        product_id="demo",
        reasoning_provenance="deterministic-rule-based",
        pages=pages,
        elements=elements,
        locators=locators,
        interactions=[interaction],
    )


def _contains_sensitive_key(value) -> bool:
    blocked = ("cookie", "token", "password_value", "secret", "storage_state")
    if isinstance(value, dict):
        return any(
            any(term in key.casefold() for term in blocked) or _contains_sensitive_key(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_sensitive_key(item) for item in value)
    return False
