"""Generated from verified SauceDemo knowledge."""

import json
import os
from pathlib import Path

import pytest
from playwright.sync_api import Page, sync_playwright


ROOT = Path(__file__).resolve().parents[3]
CONFIG = json.loads((ROOT / "products/demo/config/product.json").read_text())
LOCATORS = {"element.inventory_title": {"strategy": "data-test", "value": "title"}, "element.login": {"strategy": "data-test", "value": "login-button"}, "element.password": {"strategy": "data-test", "value": "password"}, "element.username": {"strategy": "data-test", "value": "username"}}

USERNAME_ELEMENT_ID = "element.username"
PASSWORD_ELEMENT_ID = "element.password"
LOGIN_TARGET_ELEMENT_ID = "element.login"
INVENTORY_ASSERTION_ELEMENT_ID = "element.inventory_title"
EXPECTED_DESTINATION = "/inventory.html"
EXPECTED_INVENTORY_TEXT = "Products"


def _locator(page: Page, element_id: str):
    locator = LOCATORS.get(element_id)
    if locator is None:
        raise AssertionError(f"No stored locator for artifact element: {element_id}")
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
