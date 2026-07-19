"""Formal PMQA Tool for bounded SauceDemo Playwright exploration."""

import hashlib
from datetime import datetime, timezone
from typing import Callable, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from pmqa.models import ExplorationEvidence, ExplorationSource
from pmqa.workflow import (
    AgentRole,
    ToolCategory,
    ToolError,
    ToolExecutionStatus,
    ToolMetadata,
    ToolRequest,
    ToolResult,
)
from products.demo.capture import (
    SAUCEDEMO_EXPLORATION_ACTIONS,
    PlaywrightSauceDemoCapture,
    SauceDemoCaptureRunner,
)
from products.demo.config import DemoConfig


SAUCEDEMO_EXPLORATION_TOOL_ID = "playwright.saucedemo_explore"

SauceDemoExplorationAction = Literal[
    "inspect_login_page",
    "login",
    "verify_inventory_page",
    "inspect_inventory_item",
]


class SauceDemoExplorationInput(BaseModel):
    """Strict product-owned input for the bounded SauceDemo action plan."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
    )

    product_id: str = Field(min_length=1)
    actions: Tuple[SauceDemoExplorationAction, ...] = Field(min_length=1)


class SauceDemoExplorationTool:
    """Run bounded product capture and return serialized exploration evidence."""

    def __init__(
        self,
        config: DemoConfig,
        *,
        capture_runner: Optional[SauceDemoCaptureRunner] = None,
        clock: Optional[Callable[[], datetime]] = None,
        headless: bool = True,
    ) -> None:
        self._config = config
        self._capture_runner = capture_runner or PlaywrightSauceDemoCapture(
            config=config,
            headless=headless,
        )
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._metadata = ToolMetadata(
            tool_id=SAUCEDEMO_EXPLORATION_TOOL_ID,
            category=ToolCategory.PLAYWRIGHT,
            description="Capture bounded, runtime-free SauceDemo exploration evidence",
            input_schema_version="1",
            output_schema_version="1",
        )

    @property
    def metadata(self) -> ToolMetadata:
        """Return the stable Tool identity and schema versions."""

        return self._metadata

    def invoke(self, request: ToolRequest) -> ToolResult:
        """Validate, capture, and return one correlated Tool result."""

        if request.requested_by_agent is not AgentRole.EXPLORER:
            return self._failure(
                request,
                code="unauthorized_agent",
                message="SauceDemo exploration requires the Explorer agent",
            )
        if (
            request.tool_id != self.metadata.tool_id
            or request.category is not self.metadata.category
        ):
            return self._failure(
                request,
                code="invalid_request",
                message="Tool request identity does not match SauceDemo exploration",
            )
        try:
            tool_input = SauceDemoExplorationInput.model_validate(request.input)
        except ValidationError:
            return self._failure(
                request,
                code="invalid_input",
                message="SauceDemo exploration input is invalid",
            )
        if tool_input.product_id != self._config.product_id:
            return self._failure(
                request,
                code="invalid_product",
                message="Requested product does not match the configured product",
            )
        if len(tool_input.actions) > self._config.maximum_exploration_steps:
            return self._failure(
                request,
                code="invalid_action_plan",
                message="SauceDemo exploration action limit was exceeded",
            )
        expected_prefix = SAUCEDEMO_EXPLORATION_ACTIONS[: len(tool_input.actions)]
        if tool_input.actions != expected_prefix:
            return self._failure(
                request,
                code="invalid_action_plan",
                message="SauceDemo exploration actions must follow the bounded order",
            )

        try:
            captured = self._capture_runner.capture(tool_input.actions)
        except Exception:
            return self._failure(
                request,
                code="capture_failed",
                message="SauceDemo exploration capture failed",
                retryable=True,
            )

        completed_at = self._completion_time(request)
        try:
            evidence = ExplorationEvidence(
                schema_version="1",
                evidence_id=_evidence_id(request),
                workflow_id=request.workflow_id,
                product_id=tool_input.product_id,
                source=ExplorationSource(
                    source_type="browser-automation",
                    tool_id=self.metadata.tool_id,
                    capture_id=request.invocation_id,
                ),
                captured_at=completed_at,
                pages=captured.pages,
                elements=captured.elements,
                locator_candidates=captured.locator_candidates,
                interactions=captured.interactions,
            )
        except (AttributeError, TypeError, ValidationError):
            return self._failure(
                request,
                code="invalid_evidence",
                message="SauceDemo capture produced invalid exploration evidence",
            )

        return ToolResult(
            tool_id=request.tool_id,
            workflow_id=request.workflow_id,
            invocation_id=request.invocation_id,
            completed_at=completed_at,
            status=ToolExecutionStatus.SUCCEEDED,
            output={"evidence": evidence.to_workflow_payload()},
            summary={
                "page_count": len(evidence.pages),
                "element_count": len(evidence.elements),
                "locator_candidate_count": len(evidence.locator_candidates),
                "interaction_count": len(evidence.interactions),
            },
        )

    def _failure(
        self,
        request: ToolRequest,
        *,
        code: str,
        message: str,
        retryable: bool = False,
    ) -> ToolResult:
        return ToolResult(
            tool_id=request.tool_id,
            workflow_id=request.workflow_id,
            invocation_id=request.invocation_id,
            completed_at=self._completion_time(request),
            status=ToolExecutionStatus.FAILED,
            errors=(
                ToolError(code=code, message=message, retryable=retryable),
            ),
        )

    def _completion_time(self, request: ToolRequest) -> datetime:
        completed_at = self._clock()
        return max(completed_at, request.requested_at)


def _evidence_id(request: ToolRequest) -> str:
    correlation = f"{request.workflow_id}\0{request.invocation_id}".encode()
    return "evidence.saucedemo." + hashlib.sha256(correlation).hexdigest()[:24]
