"""Task 2 knowledge adapter over shared bounded SauceDemo capture."""

from datetime import datetime, timezone
from typing import Optional, Sequence

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
from products.demo.capture import (
    PlaywrightSauceDemoCapture,
    SauceDemoCaptureRunner,
)
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
        capture_runner: Optional[SauceDemoCaptureRunner] = None,
    ) -> None:
        self._actions = list(actions)[: config.maximum_exploration_steps]
        self._provenance = provenance
        self._capture_runner = capture_runner or PlaywrightSauceDemoCapture(
            config=config,
            normalizer=normalizer,
            headless=headless,
        )

    def execute(self, task: Task, context: RunContext) -> ExecutionResult:
        """Run the approved actions and return normalized knowledge."""

        captured = self._capture_runner.capture(self._actions)
        lifecycle = _verified_lifecycle()
        pages = [
            Page(
                id=item.page_id,
                lifecycle=lifecycle,
                url=item.url,
                title=item.title,
                structural_fingerprint=item.structural_fingerprint,
            )
            for item in captured.pages
        ]
        elements = [
            Element(
                id=item.element_id,
                lifecycle=lifecycle,
                page_id=item.page_id,
                role=item.role,
                accessible_name=item.accessible_name,
                visible_text=item.visible_text,
                attributes={
                    attribute.name: attribute.value
                    for attribute in item.attributes
                    if attribute.name == "data-test"
                },
            )
            for item in captured.elements
        ]
        locators = [
            Locator(
                id=item.locator_candidate_id,
                lifecycle=lifecycle,
                element_id=item.element_id,
                strategy=item.strategy,
                value=item.value,
                priority=item.priority,
            )
            for item in captured.locator_candidates
        ]
        interactions = [
            Interaction(
                id=item.interaction_id,
                lifecycle=lifecycle,
                source_page_id=item.source_page_id,
                target_element_id=item.target_element_id,
                action=item.action,
                expected_outcome_type=item.outcome_type,
                expected_outcome_value=item.outcome_value,
            )
            for item in captured.interactions
        ]
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

def _verified_lifecycle() -> Lifecycle:
    return Lifecycle(ArtifactStatus.VERIFIED, datetime.now(timezone.utc).isoformat())
