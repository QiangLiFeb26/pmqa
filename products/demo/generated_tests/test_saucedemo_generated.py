"""Generated from products/demo/artifacts/knowledge.json."""

import json
import os
from pathlib import Path

import pytest
from playwright.sync_api import Page, sync_playwright


ROOT = Path(__file__).resolve().parents[3]
ARTIFACT = json.loads((ROOT / "products/demo/artifacts/knowledge.json").read_text())
CONFIG = json.loads((ROOT / "products/demo/config/product.json").read_text())


def _locator(page: Page, element_id: str):
    known = [item for item in ARTIFACT["locators"] if item["element_id"] == element_id]
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
    _locator(page, "element.username").fill(username)
    _locator(page, "element.password").fill(password)
    _locator(page, "element.login").click()


def test_successful_login(page: Page) -> None:
    _login(page)
    page.wait_for_url("**/inventory.html")
    assert page.url.endswith("/inventory.html")


def test_inventory_page(page: Page) -> None:
    _login(page)
    title = _locator(page, "element.inventory_title")
    assert title.is_visible()
    assert title.text_content() == "Products"
