"""Human-mediated GitHub Copilot reasoning without automated transport."""

from abc import ABC, abstractmethod
from typing import Optional

from pmqa.reasoning.models import ReasoningRequest, ReasoningResponse
from pmqa.reasoning.prompting import (
    ReasoningPromptPackage,
    ReasoningResponseParser,
    render_prompt_package,
)
from pmqa.reasoning.provider import ReasoningProvider
from pmqa.reasoning.validation import RequestInput, validate_reasoning_request


ManualPromptPackage = ReasoningPromptPackage


class ManualReasoningError(ValueError):
    """Reports a safe failure in manual prompt transport or response parsing."""


class ManualResponseParser(ReasoningResponseParser):
    """Parses manual Copilot output through the shared response parser."""

    def __init__(self) -> None:
        super().__init__(
            "github-copilot-manual",
            error_type=ManualReasoningError,
            label="Manual reasoning",
        )


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


class ManualCopilotReasoningProvider(ReasoningProvider):
    """Runs a validated, human-mediated GitHub Copilot reasoning exchange."""

    provider_name = "github-copilot-manual"

    def __init__(self, channel: Optional[ManualReasoningChannel] = None) -> None:
        self._channel = channel
        self._parser = ManualResponseParser()

    def prepare(self, request: RequestInput) -> ManualPromptPackage:
        """Build the shared deterministic prompt package for manual transport."""

        return render_prompt_package(
            request,
            provider_name=self.provider_name,
            model_guidance="identify the model you used.",
        )

    def complete(self, request: RequestInput, pasted_text: str) -> ReasoningResponse:
        """Parse pasted JSON and enforce schema, correlation, and provenance."""

        valid_request = validate_reasoning_request(request)
        return self._parser.parse(pasted_text, valid_request.request_id)

    def _reason(self, request: ReasoningRequest) -> ReasoningResponse:
        """Run the interactive wrapper only when a channel was injected."""

        if self._channel is None:
            raise ManualReasoningError(
                "No manual channel configured; use prepare() and complete() for two-phase operation"
            )
        package = self.prepare(request)
        self._channel.present_prompt(package)
        return self.complete(request, self._channel.receive_response())
