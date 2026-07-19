"""Provider-independent contracts for structured reasoning."""

from typing import Any, TYPE_CHECKING

from pmqa.reasoning.copilot_cli import (
    CliExecutionResult,
    CopilotCliConfig,
    CopilotCliExecutionError,
    CopilotCliReasoningProvider,
    CopilotCliRunner,
    CopilotCliTimeoutError,
    CopilotCliUnavailableError,
    SubprocessCopilotCliRunner,
    build_copilot_command,
)
from pmqa.reasoning.deterministic import DeterministicReasoningProvider
from pmqa.reasoning.manual import (
    ManualCopilotReasoningProvider,
    ManualPromptPackage,
    ManualReasoningChannel,
    ManualReasoningError,
    ManualResponseParser,
    TerminalManualReasoningChannel,
)
from pmqa.reasoning.models import (
    ReasoningDecision,
    ReasoningRequest,
    ReasoningResponse,
    ReasoningStatus,
)
from pmqa.reasoning.provider import ReasoningProvider
from pmqa.reasoning.prompting import (
    PromptPackage,
    PromptPackageBuilder,
    PromptPackageError,
)
from pmqa.reasoning.scrubber import (
    DeterministicReasoningScrubber,
    ReasoningScrubber,
    RedactionRecord,
    ScrubInput,
    ScrubReport,
    ScrubResult,
    ScrubStatus,
    ScrubValidationError,
)
from pmqa.reasoning.validation import (
    ReasoningValidationError,
    validate_reasoning_exchange,
    validate_reasoning_request,
    validate_reasoning_response,
)

if TYPE_CHECKING:
    from pmqa.reasoning.execution import (
        PreparedManualReasoning,
        ReasoningExecutionError,
        ReasoningExecutionResult,
        ReasoningExecutionService,
    )

_EXECUTION_EXPORTS = {
    "PreparedManualReasoning",
    "ReasoningExecutionError",
    "ReasoningExecutionResult",
    "ReasoningExecutionService",
}


def __getattr__(name: str) -> Any:
    """Load execution exports lazily to keep trace imports acyclic."""

    if name in _EXECUTION_EXPORTS:
        from pmqa.reasoning import execution

        return getattr(execution, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "CliExecutionResult",
    "CopilotCliConfig",
    "CopilotCliExecutionError",
    "CopilotCliReasoningProvider",
    "CopilotCliRunner",
    "CopilotCliTimeoutError",
    "CopilotCliUnavailableError",
    "DeterministicReasoningProvider",
    "DeterministicReasoningScrubber",
    "ManualCopilotReasoningProvider",
    "ManualPromptPackage",
    "ManualReasoningChannel",
    "ManualReasoningError",
    "ManualResponseParser",
    "PreparedManualReasoning",
    "PromptPackage",
    "PromptPackageBuilder",
    "PromptPackageError",
    "ReasoningScrubber",
    "ReasoningDecision",
    "ReasoningExecutionError",
    "ReasoningExecutionResult",
    "ReasoningExecutionService",
    "ReasoningProvider",
    "ReasoningRequest",
    "ReasoningResponse",
    "ReasoningStatus",
    "ReasoningValidationError",
    "RedactionRecord",
    "ScrubInput",
    "ScrubReport",
    "ScrubResult",
    "ScrubStatus",
    "ScrubValidationError",
    "SubprocessCopilotCliRunner",
    "TerminalManualReasoningChannel",
    "validate_reasoning_exchange",
    "validate_reasoning_request",
    "validate_reasoning_response",
    "build_copilot_command",
]
