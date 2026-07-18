"""Safe subprocess transport for GitHub Copilot CLI reasoning."""

import shutil
import subprocess
from abc import ABC, abstractmethod
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from pmqa.reasoning.models import ReasoningRequest, ReasoningResponse
from pmqa.reasoning.prompting import (
    ReasoningPromptPackage,
    ReasoningResponseParser,
    render_prompt_package,
)
from pmqa.reasoning.provider import ReasoningProvider
from pmqa.reasoning.validation import RequestInput


class CopilotCliConfig(BaseModel):
    """Configures one explicit Copilot CLI executable and argument list."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    executable: str = Field(min_length=1)
    arguments: List[str] = Field(default_factory=list)
    timeout_seconds: float = Field(default=60.0, gt=0.0)
    provider_name: Literal["github-copilot-cli"] = "github-copilot-cli"
    model_name: str = Field(default="copilot-cli", min_length=1)


class CliExecutionResult(BaseModel):
    """Captures process output without environment or credential values."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    command: List[str]
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


class CopilotCliUnavailableError(RuntimeError):
    """Reports that the configured executable cannot be resolved."""


class CopilotCliExecutionError(RuntimeError):
    """Reports a safe CLI execution or structured-output failure."""


class CopilotCliTimeoutError(TimeoutError):
    """Reports that Copilot CLI exceeded its configured timeout."""


class CopilotCliRunner(ABC):
    """Isolates executable discovery and subprocess transport from reasoning."""

    @abstractmethod
    def is_available(self, executable: str) -> bool:
        """Return whether the executable can be resolved without invoking AI."""

    @abstractmethod
    def run(
        self,
        *,
        command: List[str],
        prompt: str,
        timeout_seconds: float,
    ) -> CliExecutionResult:
        """Execute one command with the prompt transported through stdin."""


class SubprocessCopilotCliRunner(CopilotCliRunner):
    """Runs an argument-list command without a shell and captures its streams."""

    def is_available(self, executable: str) -> bool:
        """Resolve the configured executable without making an AI request."""

        return shutil.which(executable) is not None

    def run(
        self,
        *,
        command: List[str],
        prompt: str,
        timeout_seconds: float,
    ) -> CliExecutionResult:
        """Run with inherited unrecorded environment and stdin prompt transport."""

        try:
            completed = subprocess.run(
                command,
                input=prompt,
                capture_output=True,
                check=False,
                shell=False,
                text=True,
                timeout=timeout_seconds,
            )
        except FileNotFoundError as error:
            raise CopilotCliUnavailableError(
                "Configured Copilot CLI executable was not found"
            ) from error
        except subprocess.TimeoutExpired:
            return CliExecutionResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr="",
                timed_out=True,
            )
        return CliExecutionResult(
            command=command,
            exit_code=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
        )


class CopilotCliReasoningProvider(ReasoningProvider):
    """Reasons through an injected safe GitHub Copilot CLI transport."""

    def __init__(
        self,
        config: CopilotCliConfig,
        runner: Optional[CopilotCliRunner] = None,
    ) -> None:
        self.config = config
        self._runner = runner or SubprocessCopilotCliRunner()
        self._parser = ReasoningResponseParser(
            config.provider_name,
            error_type=CopilotCliExecutionError,
            label="Copilot CLI",
        )

    def is_available(self) -> bool:
        """Check executable availability without invoking a reasoning request."""

        return self._runner.is_available(self.config.executable)

    def prepare(self, request: RequestInput) -> ReasoningPromptPackage:
        """Build the same deterministic prompt package used by manual transport."""

        return render_prompt_package(
            request,
            provider_name=self.config.provider_name,
            model_guidance=f'set model to "{self.config.model_name}".',
        )

    def _reason(self, request: ReasoningRequest) -> ReasoningResponse:
        """Execute the CLI once and validate its canonical structured response."""

        if not self.is_available():
            raise CopilotCliUnavailableError(
                "Configured Copilot CLI executable is unavailable"
            )
        package = self.prepare(request)
        result = self._runner.run(
            command=build_copilot_command(self.config),
            prompt=package.prompt_text,
            timeout_seconds=self.config.timeout_seconds,
        )
        if result.timed_out:
            raise CopilotCliTimeoutError("Copilot CLI execution timed out")
        if result.exit_code != 0:
            raise CopilotCliExecutionError(
                f"Copilot CLI exited with code {result.exit_code}"
            )
        if not result.stdout.strip():
            raise CopilotCliExecutionError("Copilot CLI returned an empty response")
        response = self._parser.parse(result.stdout, request.request_id)
        if response.model != self.config.model_name:
            raise CopilotCliExecutionError(
                "Copilot CLI response model does not match configured model"
            )
        return response


def build_copilot_command(config: CopilotCliConfig) -> List[str]:
    """Return deterministic argument tokens without shell interpolation."""

    return [config.executable, *config.arguments]
