"""Human-mediated GitHub Copilot reasoning without automated transport."""

import json
import re
from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from pmqa.reasoning.models import ReasoningRequest, ReasoningResponse
from pmqa.reasoning.provider import ReasoningProvider
from pmqa.reasoning.validation import (
    RequestInput,
    validate_reasoning_request,
    validate_reasoning_response,
)
from pmqa.utils.hashing import canonical_json_sha256


class ManualPromptPackage(BaseModel):
    """Contains a deterministic copy/paste package for one safe request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    prompt_text: str = Field(min_length=1)
    request_json: str = Field(min_length=1)
    response_schema_json: str = Field(min_length=1)
    request_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class ManualReasoningError(ValueError):
    """Reports a safe failure in manual prompt transport or response parsing."""


class ManualReasoningChannel(ABC):
    """Defines the human-controlled prompt and response transport boundary."""

    @abstractmethod
    def present_prompt(self, package: ManualPromptPackage) -> None:
        """Present a complete prompt package to a human operator."""

    @abstractmethod
    def receive_response(self) -> str:
        """Receive the human-pasted structured response text."""


class TerminalManualReasoningChannel(ManualReasoningChannel):
    """Presents and receives a manual response through the terminal."""

    def present_prompt(self, package: ManualPromptPackage) -> None:
        """Print deterministic copy/paste instructions and the full prompt."""

        print("Copy the prompt below into an approved GitHub Copilot interface.")
        print("Paste Copilot's JSON-only response when prompted.\n")
        print(package.prompt_text)

    def receive_response(self) -> str:
        """Read one pasted JSON response without clipboard automation."""

        return input("\nPaste the JSON response on one line: ")


class ManualResponseParser:
    """Parses exactly one JSON object with one optional JSON markdown fence."""

    _fence = re.compile(r"\A```(?:json)?\s*(.*?)\s*```\Z", re.IGNORECASE | re.DOTALL)

    def parse(self, pasted_text: str, request_id: str) -> ReasoningResponse:
        """Parse and validate a correlated manual Copilot response."""

        text = pasted_text.strip()
        if not text:
            raise ManualReasoningError("Manual reasoning response is empty")
        fence = self._fence.fullmatch(text)
        if fence:
            text = fence.group(1).strip()
            if "```" in text:
                raise ManualReasoningError("Manual response must contain exactly one JSON object")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as error:
            raise ManualReasoningError(
                "Manual response must contain exactly one JSON object "
                f"(invalid JSON at line {error.lineno}, column {error.colno})"
            ) from error
        if not isinstance(payload, dict):
            raise ManualReasoningError("Manual response must be one JSON object")
        return validate_reasoning_response(payload, expected_request_id=request_id)


class ManualCopilotReasoningProvider(ReasoningProvider):
    """Runs a validated, human-mediated GitHub Copilot reasoning exchange."""

    provider_name = "github-copilot-manual"

    def __init__(self, channel: Optional[ManualReasoningChannel] = None) -> None:
        self._channel = channel
        self._parser = ManualResponseParser()

    def prepare(self, request: RequestInput) -> ManualPromptPackage:
        """Build a deterministic prompt package from a validated safe request."""

        valid_request = validate_reasoning_request(request)
        request_payload = valid_request.model_dump(mode="json")
        request_json = _canonical_json(request_payload)
        schema_json = _canonical_json(ReasoningResponse.model_json_schema())
        prompt_text = _render_prompt(request_json, schema_json)
        return ManualPromptPackage(
            request_id=valid_request.request_id,
            provider=self.provider_name,
            prompt_text=prompt_text,
            request_json=request_json,
            response_schema_json=schema_json,
            request_hash=canonical_json_sha256(request_payload),
        )

    def complete(self, request: RequestInput, pasted_text: str) -> ReasoningResponse:
        """Parse pasted JSON and enforce schema, correlation, and provenance."""

        valid_request = validate_reasoning_request(request)
        response = self._parser.parse(pasted_text, valid_request.request_id)
        if response.provider != self.provider_name:
            raise ManualReasoningError(
                f"Manual response provider must be {self.provider_name!r}"
            )
        return validate_reasoning_response(response, valid_request.request_id)

    def _reason(self, request: ReasoningRequest) -> ReasoningResponse:
        """Run the interactive wrapper only when a channel was injected."""

        if self._channel is None:
            raise ManualReasoningError(
                "No manual channel configured; use prepare() and complete() for two-phase operation"
            )
        package = self.prepare(request)
        self._channel.present_prompt(package)
        return self.complete(request, self._channel.receive_response())


def _canonical_json(value) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _render_prompt(request_json: str, response_schema_json: str) -> str:
    return "\n".join(
        [
            "You are performing structured QA reasoning for PMQA.",
            "Use only the structured product knowledge in REQUEST_JSON below.",
            "Do not invent browser state, DOM, credentials, execution results, or evidence.",
            "Return exactly one JSON object and no prose or markdown fences.",
            "The response must conform to RESPONSE_SCHEMA_JSON.",
            "Preserve the exact request_id from the request.",
            'Set provider to "github-copilot-manual" and identify the model you used.',
            "Use the typed decision envelope for every decision.",
            "Represent uncertainty with decision confidence, response confidence, or warnings.",
            "",
            "REQUEST_JSON:",
            request_json,
            "",
            "RESPONSE_SCHEMA_JSON:",
            response_schema_json,
        ]
    )
