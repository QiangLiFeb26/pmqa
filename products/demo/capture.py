"""Shared bounded SauceDemo capture used by product-owned adapters."""

from dataclasses import dataclass
from typing import Any, Dict, List, Protocol, Sequence, Tuple

from playwright.sync_api import Browser, Page as BrowserPage, sync_playwright

from pmqa.core.normalization import PassthroughNormalizer, SnapshotNormalizer
from pmqa.models import (
    InteractionObservation,
    LocatorCandidateObservation,
    ObservedAttribute,
    ObservedElement,
    ObservedPage,
)
from products.demo.config import DemoConfig
from products.demo.exploration_contracts import SAUCEDEMO_EXPLORATION_ACTIONS
from products.demo.fingerprint import saucedemo_structural_fingerprint


@dataclass(frozen=True)
class SauceDemoCaptureResult:
    """Carries runtime-free observations from one bounded browser capture."""

    pages: Tuple[ObservedPage, ...] = ()
    elements: Tuple[ObservedElement, ...] = ()
    locator_candidates: Tuple[LocatorCandidateObservation, ...] = ()
    interactions: Tuple[InteractionObservation, ...] = ()


class SauceDemoCaptureRunner(Protocol):
    """Defines the narrow product-owned seam for bounded capture execution."""

    def capture(self, actions: Sequence[str]) -> SauceDemoCaptureResult:
        """Execute approved actions and return runtime-free observations."""

        ...


class PlaywrightSauceDemoCapture:
    """Capture stable SauceDemo observations while containing Playwright state."""

    def __init__(
        self,
        config: DemoConfig,
        normalizer: SnapshotNormalizer = PassthroughNormalizer(),
        headless: bool = True,
    ) -> None:
        self._config = config
        self._normalizer = normalizer
        self._headless = headless

    def capture(self, actions: Sequence[str]) -> SauceDemoCaptureResult:
        """Run the bounded action vocabulary and always close the browser."""

        pages: List[ObservedPage] = []
        elements: List[ObservedElement] = []
        locator_candidates: List[LocatorCandidateObservation] = []
        interactions: List[InteractionObservation] = []
        browser: Browser
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self._headless)
            try:
                page = browser.new_page()
                page.goto(self._config.base_url + self._config.start_path)
                for action in actions:
                    if action not in SAUCEDEMO_EXPLORATION_ACTIONS:
                        raise ValueError(
                            "Unsupported bounded SauceDemo exploration action"
                        )
                    if action == "inspect_login_page":
                        self._capture_login(
                            page, pages, elements, locator_candidates
                        )
                    elif action == "login":
                        self._login(page, interactions)
                    elif action == "verify_inventory_page":
                        self._capture_inventory(
                            page, pages, elements, locator_candidates
                        )
                    elif action == "inspect_inventory_item":
                        page.locator("[data-test='inventory-item']").first.wait_for()
            finally:
                browser.close()
        return SauceDemoCaptureResult(
            pages=tuple(pages),
            elements=tuple(elements),
            locator_candidates=tuple(locator_candidates),
            interactions=tuple(interactions),
        )

    def _capture_login(
        self,
        page: BrowserPage,
        pages: List[ObservedPage],
        elements: List[ObservedElement],
        locator_candidates: List[LocatorCandidateObservation],
    ) -> None:
        snapshot = self._snapshot(page)
        pages.append(self._page("page.login", snapshot))
        definitions = (
            ("element.username", "textbox", "Username", "username", None, "text"),
            ("element.password", "textbox", "Password", "password", None, "password"),
            ("element.login", "button", "Login", "login-button", "Login", None),
        )
        for element_id, role, name, test_id, text, input_type in definitions:
            attributes = [ObservedAttribute(name="data-test", value=test_id)]
            if input_type is not None:
                attributes.append(ObservedAttribute(name="type", value=input_type))
            elements.append(
                ObservedElement(
                    element_id=element_id,
                    page_id="page.login",
                    role=role,
                    accessible_name=name,
                    visible_text=text,
                    attributes=tuple(attributes),
                )
            )
            locator_candidates.append(
                LocatorCandidateObservation(
                    locator_candidate_id="locator." + element_id.split(".")[-1],
                    element_id=element_id,
                    strategy="data-test",
                    value=test_id,
                    priority=1,
                )
            )

    def _login(
        self,
        page: BrowserPage,
        interactions: List[InteractionObservation],
    ) -> None:
        username, password = self._config.credentials()
        page.locator("[data-test='username']").fill(username)
        page.locator("[data-test='password']").fill(password)
        page.locator("[data-test='login-button']").click()
        page.wait_for_url("**/inventory.html")
        interactions.append(
            InteractionObservation(
                interaction_id="interaction.login",
                source_page_id="page.login",
                target_element_id="element.login",
                action="click",
                outcome_type="navigation",
                outcome_value="/inventory.html",
            )
        )

    def _capture_inventory(
        self,
        page: BrowserPage,
        pages: List[ObservedPage],
        elements: List[ObservedElement],
        locator_candidates: List[LocatorCandidateObservation],
    ) -> None:
        page.locator("[data-test='title']").wait_for()
        snapshot = self._snapshot(page)
        pages.append(self._page("page.inventory", snapshot))
        elements.append(
            ObservedElement(
                element_id="element.inventory_title",
                page_id="page.inventory",
                role="heading",
                accessible_name="Products",
                visible_text="Products",
                attributes=(ObservedAttribute(name="data-test", value="title"),),
            )
        )
        locator_candidates.append(
            LocatorCandidateObservation(
                locator_candidate_id="locator.inventory_title",
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

    @staticmethod
    def _page(page_id: str, snapshot: Dict[str, Any]) -> ObservedPage:
        return ObservedPage(
            page_id=page_id,
            url=snapshot["url"],
            title=snapshot["title"],
            structural_fingerprint=saucedemo_structural_fingerprint(
                snapshot["elements"]
            ),
        )
