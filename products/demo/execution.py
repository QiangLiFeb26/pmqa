"""Bounded Playwright execution for the SauceDemo product pack."""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Sequence

from playwright.sync_api import Browser, Page as BrowserPage, sync_playwright

from pmqa.core import Artifact, ExecutionResult, RunContext, Task
from pmqa.core.normalization import PassthroughNormalizer, SnapshotNormalizer
from pmqa.models import (
    ArtifactStatus,
    Element,
    Interaction,
    KnowledgeArtifact,
    Lifecycle,
    Locator,
    Page,
)
from pmqa.providers import ExecutionProvider
from products.demo.config import DemoConfig


class SauceDemoExecutionProvider(ExecutionProvider):
    """Executes one bounded, safe SauceDemo exploration plan in Chromium."""

    def __init__(
        self,
        config: DemoConfig,
        actions: Sequence[str],
        provenance: str,
        normalizer: SnapshotNormalizer = PassthroughNormalizer(),
        headless: bool = True,
    ) -> None:
        self._config = config
        self._actions = list(actions)[: config.maximum_exploration_steps]
        self._provenance = provenance
        self._normalizer = normalizer
        self._headless = headless

    def execute(self, task: Task, context: RunContext) -> ExecutionResult:
        """Run the approved actions and return normalized knowledge."""

        pages: List[Page] = []
        elements: List[Element] = []
        locators: List[Locator] = []
        interactions: List[Interaction] = []
        browser: Browser
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self._headless)
            try:
                page = browser.new_page()
                page.goto(self._config.base_url + self._config.start_path)
                for action in self._actions:
                    if action == "inspect_login_page":
                        self._capture_login(page, pages, elements, locators)
                    elif action == "login":
                        self._login(page, interactions)
                    elif action == "verify_inventory_page":
                        self._capture_inventory(page, pages, elements, locators)
                    elif action == "inspect_inventory_item":
                        page.locator("[data-test='inventory-item']").first.wait_for()
                    else:
                        raise ValueError("Reasoning provider returned an unsupported action: " + action)
            finally:
                browser.close()
        knowledge = KnowledgeArtifact(
            artifact_id="knowledge",
            product_id=context.product,
            reasoning_provenance=self._provenance,
            pages=pages,
            elements=elements,
            locators=locators,
            interactions=interactions,
        )
        return ExecutionResult(True, Artifact("knowledge", knowledge.to_dict()))

    def _capture_login(
        self,
        page: BrowserPage,
        pages: List[Page],
        elements: List[Element],
        locators: List[Locator],
    ) -> None:
        snapshot = self._snapshot(page)
        pages.append(self._page("page.login", snapshot))
        definitions = [
            ("element.username", "textbox", "Username", "username", "Username"),
            ("element.password", "textbox", "Password", "password", "Password"),
            ("element.login", "button", "Login", "login-button", "Login"),
        ]
        for element_id, role, name, test_id, text in definitions:
            elements.append(
                Element(
                    id=element_id,
                    lifecycle=_verified_lifecycle(),
                    page_id="page.login",
                    role=role,
                    accessible_name=name,
                    visible_text=text if role == "button" else None,
                    attributes={"data-test": test_id},
                )
            )
            locators.append(
                Locator(
                    id="locator." + element_id.split(".")[-1],
                    lifecycle=_verified_lifecycle(),
                    element_id=element_id,
                    strategy="data-test",
                    value=test_id,
                    priority=1,
                )
            )

    def _login(self, page: BrowserPage, interactions: List[Interaction]) -> None:
        username, password = self._config.credentials()
        page.locator("[data-test='username']").fill(username)
        page.locator("[data-test='password']").fill(password)
        page.locator("[data-test='login-button']").click()
        page.wait_for_url("**/inventory.html")
        interactions.append(
            Interaction(
                id="interaction.login",
                lifecycle=_verified_lifecycle(),
                page_id="page.login",
                target_element_id="element.login",
                action="click",
                outcome="navigated:/inventory.html",
            )
        )

    def _capture_inventory(
        self,
        page: BrowserPage,
        pages: List[Page],
        elements: List[Element],
        locators: List[Locator],
    ) -> None:
        page.locator("[data-test='title']").wait_for()
        snapshot = self._snapshot(page)
        pages.append(self._page("page.inventory", snapshot))
        elements.append(
            Element(
                id="element.inventory_title",
                lifecycle=_verified_lifecycle(),
                page_id="page.inventory",
                role="heading",
                accessible_name="Products",
                visible_text="Products",
                attributes={"data-test": "title"},
            )
        )
        locators.append(
            Locator(
                id="locator.inventory_title",
                lifecycle=_verified_lifecycle(),
                element_id="element.inventory_title",
                strategy="data-test",
                value="title",
                priority=1,
            )
        )

    def _snapshot(self, page: BrowserPage) -> Dict[str, Any]:
        safe_structure = page.locator("body").evaluate(
            """body => ({
                title: document.title,
                url: location.href,
                elements: Array.from(body.querySelectorAll('[data-test]')).map(el => ({
                    tag: el.tagName.toLowerCase(),
                    dataTest: el.getAttribute('data-test'),
                    type: el.getAttribute('type'),
                    text: el.matches('input') ? null : (el.textContent || '').trim().slice(0, 200)
                }))
            })"""
        )
        return self._normalizer.normalize(safe_structure)

    def _page(self, page_id: str, snapshot: Dict[str, Any]) -> Page:
        canonical = json.dumps(snapshot["elements"], sort_keys=True, separators=(",", ":"))
        return Page(
            id=page_id,
            lifecycle=_verified_lifecycle(),
            url=snapshot["url"],
            title=snapshot["title"],
            structural_fingerprint=hashlib.sha256(canonical.encode()).hexdigest(),
        )


def _verified_lifecycle() -> Lifecycle:
    return Lifecycle(ArtifactStatus.VERIFIED, datetime.now(timezone.utc).isoformat())
