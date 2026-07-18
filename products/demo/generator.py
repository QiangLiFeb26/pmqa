"""Artifact-driven test generation rules for the SauceDemo product pack."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from pmqa.models import Element, Interaction, KnowledgeArtifact, Locator, Page


@dataclass(frozen=True)
class GenerationEvidence:
    """Contains the artifact relationships required by the demo tests."""

    interaction: Interaction
    destination_page: Page
    username_element: Element
    password_element: Element
    assertion_element: Element


GENERATED_TEST = '''"""Generated from products/demo/artifacts/knowledge.json."""

import json
import os
from pathlib import Path

import pytest
from playwright.sync_api import Page, sync_playwright


ROOT = Path(__file__).resolve().parents[3]
ARTIFACT = json.loads((ROOT / "products/demo/artifacts/knowledge.json").read_text())
CONFIG = json.loads((ROOT / "products/demo/config/product.json").read_text())

USERNAME_ELEMENT_ID = __USERNAME_ELEMENT_ID__
PASSWORD_ELEMENT_ID = __PASSWORD_ELEMENT_ID__
LOGIN_TARGET_ELEMENT_ID = __LOGIN_TARGET_ELEMENT_ID__
INVENTORY_ASSERTION_ELEMENT_ID = __ASSERTION_ELEMENT_ID__
EXPECTED_DESTINATION = __EXPECTED_DESTINATION__
EXPECTED_INVENTORY_TEXT = __EXPECTED_INVENTORY_TEXT__


def _locator(page: Page, element_id: str):
    known = [item for item in ARTIFACT["locators"] if item["element_id"] == element_id]
    if not known:
        raise AssertionError(f"No stored locator for artifact element: {element_id}")
    locator = sorted(known, key=lambda item: item["priority"])[0]
    if locator["strategy"] == "data-test":
        return page.locator(f"[data-test='{locator['value']}']")
    raise AssertionError(f"Unsupported stored locator strategy: {locator['strategy']}")


def _credentials():
    names = CONFIG["credential_environment_variables"]
    defaults = CONFIG["demo_only_default_credentials"]
    return (
        os.getenv(names["username"], defaults["username"]),
        os.getenv(names["password"], defaults["password"]),
    )


@pytest.fixture
def page():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        yield page
        browser.close()


def _login(page: Page) -> None:
    username, password = _credentials()
    page.goto(CONFIG["base_url"] + CONFIG["start_path"])
    _locator(page, USERNAME_ELEMENT_ID).fill(username)
    _locator(page, PASSWORD_ELEMENT_ID).fill(password)
    _locator(page, LOGIN_TARGET_ELEMENT_ID).click()


def test_successful_login(page: Page) -> None:
    _login(page)
    page.wait_for_url(f"**{EXPECTED_DESTINATION}")
    assert page.url.endswith(EXPECTED_DESTINATION)


def test_inventory_page(page: Page) -> None:
    _login(page)
    assertion = _locator(page, INVENTORY_ASSERTION_ELEMENT_ID)
    assert assertion.is_visible()
    assert assertion.text_content() == EXPECTED_INVENTORY_TEXT
'''


def generate_tests(artifact: KnowledgeArtifact, output_directory: Path) -> Path:
    """Generate deterministic tests from complete stored interaction evidence."""

    evidence = _resolve_evidence(artifact)
    replacements = {
        "__USERNAME_ELEMENT_ID__": json.dumps(evidence.username_element.id),
        "__PASSWORD_ELEMENT_ID__": json.dumps(evidence.password_element.id),
        "__LOGIN_TARGET_ELEMENT_ID__": json.dumps(evidence.interaction.target_element_id),
        "__ASSERTION_ELEMENT_ID__": json.dumps(evidence.assertion_element.id),
        "__EXPECTED_DESTINATION__": json.dumps(evidence.interaction.expected_outcome_value),
        "__EXPECTED_INVENTORY_TEXT__": json.dumps(evidence.assertion_element.visible_text),
    }
    generated = GENERATED_TEST
    for marker, value in replacements.items():
        generated = generated.replace(marker, value)
    output_directory.mkdir(parents=True, exist_ok=True)
    output = output_directory / "test_saucedemo_generated.py"
    output.write_text(generated, encoding="utf-8")
    return output


def _resolve_evidence(artifact: KnowledgeArtifact) -> GenerationEvidence:
    pages = {page.id: page for page in artifact.pages}
    elements = {element.id: element for element in artifact.elements}
    locators_by_element: Dict[str, List[Locator]] = {}
    for locator in artifact.locators:
        locators_by_element.setdefault(locator.element_id, []).append(locator)

    candidates = [
        interaction
        for interaction in artifact.interactions
        if interaction.action == "click"
        and interaction.expected_outcome_type == "navigation"
    ]
    if len(candidates) != 1:
        raise ValueError("Artifact must contain exactly one replayable login navigation interaction")
    interaction = candidates[0]
    source_page = pages.get(interaction.source_page_id)
    target = elements.get(interaction.target_element_id)
    if source_page is None or target is None or target.page_id != source_page.id:
        raise ValueError("Login interaction source page or target element evidence is missing")
    _require_locator(target.id, locators_by_element)

    destinations = [
        page for page in artifact.pages if page.url.endswith(interaction.expected_outcome_value)
    ]
    if not interaction.expected_outcome_value or len(destinations) != 1:
        raise ValueError("Expected login destination page evidence is missing or ambiguous")
    destination_page = destinations[0]

    source_elements = [element for element in artifact.elements if element.page_id == source_page.id]
    username = _unique_named(source_elements, "username")
    password = _unique_named(source_elements, "password")
    _require_locator(username.id, locators_by_element)
    _require_locator(password.id, locators_by_element)

    assertions = [
        element
        for element in artifact.elements
        if element.page_id == destination_page.id
        and element.role == "heading"
        and bool(element.visible_text)
        and element.id in locators_by_element
    ]
    if len(assertions) != 1:
        raise ValueError("Expected destination assertion evidence is missing or ambiguous")
    return GenerationEvidence(
        interaction=interaction,
        destination_page=destination_page,
        username_element=username,
        password_element=password,
        assertion_element=assertions[0],
    )


def _unique_named(elements: List[Element], accessible_name: str) -> Element:
    matches = [
        element
        for element in elements
        if element.accessible_name.casefold() == accessible_name.casefold()
    ]
    if len(matches) != 1:
        raise ValueError("Required source-page input evidence is missing or ambiguous: " + accessible_name)
    return matches[0]


def _require_locator(element_id: str, locators: Dict[str, List[Locator]]) -> None:
    if element_id not in locators:
        raise ValueError("Artifact has no locator related to element: " + element_id)
