"""Application service coordinating one safe reasoning exchange."""

from datetime import datetime, timezone
from typing import Callable, Optional, Tuple
from uuid import uuid4

from pydantic import BaseModel, ConfigDict

from pmqa.reasoning.manual import ManualCopilotReasoningProvider
from pmqa.reasoning.models import ReasoningRequest, ReasoningResponse
from pmqa.reasoning.prompting import PromptPackage, PromptPackageBuilder
from pmqa.reasoning.provider import ReasoningProvider
from pmqa.reasoning.scrubber import (
    DeterministicReasoningScrubber,
    ReasoningScrubber,
    ScrubInput,
    ScrubReport,
)
from pmqa.reasoning.validation import validate_reasoning_response
from pmqa.trace import TraceRecord, TraceStore


class ReasoningExecutionError(ValueError):
    """Reports failed correlation across an integrated reasoning exchange."""


class ReasoningExecutionResult(BaseModel):
    """Returns typed, correlated artifacts from a completed reasoning exchange."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request: ReasoningRequest
    scrub_report: ScrubReport
    prompt_package: PromptPackage
    response: ReasoningResponse
    trace: TraceRecord


class PreparedManualReasoning(BaseModel):
    """Carries the safe state needed to complete a manual exchange later."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request: ReasoningRequest
    scrub_report: ScrubReport
    prompt_package: PromptPackage
    provider: str


class ReasoningExecutionService:
    """Sequences scrubbing, prompting, provider invocation, and trace storage."""

    def __init__(
        self,
        *,
        trace_store: TraceStore,
        scrubber: Optional[ReasoningScrubber] = None,
        package_builder: Optional[PromptPackageBuilder] = None,
        clock: Optional[Callable[[], datetime]] = None,
        trace_id_factory: Optional[Callable[[], str]] = None,
    ) -> None:
        self._trace_store = trace_store
        self._scrubber = scrubber or DeterministicReasoningScrubber()
        self._package_builder = package_builder or PromptPackageBuilder()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._trace_id_factory = trace_id_factory or (lambda: str(uuid4()))

    def execute(
        self,
        *,
        scrub_input: ScrubInput,
        provider: ReasoningProvider,
    ) -> ReasoningExecutionResult:
        """Execute and persist one automated provider exchange."""

        if (
            isinstance(provider, ManualCopilotReasoningProvider)
            and provider.uses_interactive_terminal
        ):
            raise ReasoningExecutionError(
                "Interactive manual providers cannot use execute(); use "
                "prepare_manual() and complete_manual()"
            )
        request, report, package, provider_name = self._prepare(
            scrub_input, provider
        )
        response = provider.reason(request)
        return self._complete(
            request=request,
            report=report,
            package=package,
            response=response,
            provider_name=provider_name,
            execution_mode="automated",
        )

    def prepare_manual(
        self,
        *,
        scrub_input: ScrubInput,
        provider: ManualCopilotReasoningProvider,
    ) -> PreparedManualReasoning:
        """Prepare a safe package without reading terminal input or persisting."""

        request, report, package, provider_name = self._prepare(
            scrub_input, provider
        )
        provider_package = provider.prepare(request)
        self._package_builder.validate(
            provider_package, request=request, provider=provider_name
        )
        if provider_package != package:
            raise ReasoningExecutionError(
                "Manual provider package does not match the prepared package"
            )
        return PreparedManualReasoning(
            request=request,
            scrub_report=report,
            prompt_package=package,
            provider=provider_name,
        )

    def complete_manual(
        self,
        *,
        prepared: PreparedManualReasoning,
        raw_response: str,
        provider: ManualCopilotReasoningProvider,
    ) -> ReasoningExecutionResult:
        """Validate pasted JSON and persist the prepared manual exchange."""

        provider_name = self._provider_name(provider)
        if provider_name != prepared.provider:
            raise ReasoningExecutionError(
                "Manual completion provider does not match prepared provider"
            )
        self._package_builder.validate(
            prepared.prompt_package,
            request=prepared.request,
            provider=provider_name,
        )
        response = provider.complete(prepared.request, raw_response)
        return self._complete(
            request=prepared.request,
            report=prepared.scrub_report,
            package=prepared.prompt_package,
            response=response,
            provider_name=provider_name,
            execution_mode="manual",
        )

    def _prepare(
        self, scrub_input: ScrubInput, provider: ReasoningProvider
    ) -> Tuple[ReasoningRequest, ScrubReport, PromptPackage, str]:
        scrubbed = self._scrubber.scrub(scrub_input)
        provider_name = self._provider_name(provider)
        package = self._package_builder.build(
            request=scrubbed.request, provider=provider_name
        )
        self._package_builder.validate(
            package, request=scrubbed.request, provider=provider_name
        )
        return scrubbed.request, scrubbed.report, package, provider_name

    def _complete(
        self,
        *,
        request: ReasoningRequest,
        report: ScrubReport,
        package: PromptPackage,
        response: ReasoningResponse,
        provider_name: str,
        execution_mode: str,
    ) -> ReasoningExecutionResult:
        valid_response = validate_reasoning_response(
            response, expected_request_id=request.request_id
        )
        if valid_response.provider != provider_name:
            raise ReasoningExecutionError(
                "Reasoning response provider does not match invoked provider"
            )
        self._package_builder.validate(
            package, request=request, provider=provider_name
        )
        trace = TraceRecord.from_exchange(
            trace_id=self._trace_id_factory(),
            request=request,
            response=valid_response,
            created_at=self._clock(),
            metadata={
                "execution_mode": execution_mode,
                "package_id": package.package_id,
                "prompt_hash": package.prompt_hash,
                "scrub_output_hash": report.output_hash,
                "scrub_audit": {
                    "output_hash": report.output_hash,
                    "redacted_values": [
                        item.model_dump(mode="json")
                        for item in report.redacted_values
                    ],
                    "removed_fields": list(report.removed_fields),
                    "rules_applied": list(report.rules_applied),
                    "warnings": list(report.warnings),
                },
            },
        )
        if trace.request_id != package.request_id:
            raise ReasoningExecutionError(
                "Trace request does not match the prompt package"
            )
        self._trace_store.save_trace(trace)
        return ReasoningExecutionResult(
            request=request,
            scrub_report=report,
            prompt_package=package,
            response=valid_response,
            trace=trace,
        )

    @staticmethod
    def _provider_name(provider: ReasoningProvider) -> str:
        provider_name = getattr(provider, "provider_name", None)
        if not isinstance(provider_name, str) or not provider_name:
            raise ReasoningExecutionError(
                "Reasoning provider must expose a non-empty provider_name"
            )
        return provider_name
