"""Provider-independent contracts for structured reasoning."""

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
    "ReasoningScrubber",
    "ReasoningDecision",
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
