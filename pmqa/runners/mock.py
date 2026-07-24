"""Deterministic in-process validation runner."""

from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Callable, Optional, Tuple

from pmqa.run import (
    RunArtifact,
    RunError,
    RunErrorCategory,
    RunnerInvocationStatus,
    StructuredResult,
)
from pmqa.runners.base import RunnerControl
from pmqa.runners.contracts import (
    RUNNER_CONTRACT_SCHEMA_VERSION,
    RunnerBoundaryValidationError,
    RunnerMetadata,
    RunnerRequest,
    RunnerResponse,
    validate_runner_response,
)


_DEFAULT_COMPLETION = datetime(2100, 1, 1, tzinfo=timezone.utc)
_SUPPORTED_OUTCOMES = frozenset(
    {
        RunnerInvocationStatus.SUCCEEDED,
        RunnerInvocationStatus.PARTIALLY_SUCCEEDED,
        RunnerInvocationStatus.FAILED,
    }
)


def _default_wall_clock() -> datetime:
    return _DEFAULT_COMPLETION


def _default_monotonic_clock() -> float:
    return 0.0


class MockRunner:
    """Deterministic runner for boundary validation, not an AI provider."""

    def __init__(
        self,
        *,
        outcome: RunnerInvocationStatus = RunnerInvocationStatus.SUCCEEDED,
        metadata: Optional[RunnerMetadata] = None,
        output_artifacts: Tuple[RunArtifact, ...] = (),
        wall_clock: Callable[[], datetime] = _default_wall_clock,
        monotonic_clock: Callable[[], float] = _default_monotonic_clock,
    ) -> None:
        if (
            type(outcome) is not RunnerInvocationStatus
            or outcome not in _SUPPORTED_OUTCOMES
        ):
            raise RunnerBoundaryValidationError() from None
        if metadata is not None and type(metadata) is not RunnerMetadata:
            raise RunnerBoundaryValidationError() from None
        if not callable(wall_clock) or not callable(monotonic_clock):
            raise RunnerBoundaryValidationError() from None
        if type(output_artifacts) is not tuple:
            raise RunnerBoundaryValidationError() from None
        self._outcome = outcome
        self._metadata = metadata or RunnerMetadata(
            schema_version=RUNNER_CONTRACT_SCHEMA_VERSION,
            runner_id="runner.mock",
            runner_version="1",
            display_name="Deterministic mock runner",
            capabilities=("deterministic-execution",),
        )
        self._output_artifacts = tuple(output_artifacts)
        self._wall_clock = wall_clock
        self._monotonic_clock = monotonic_clock

    @property
    def metadata(self) -> RunnerMetadata:
        return self._metadata

    def execute(
        self,
        request: RunnerRequest,
        control: RunnerControl,
    ) -> RunnerResponse:
        if (
            type(request) is not RunnerRequest
            or type(control) is not RunnerControl
        ):
            raise RunnerBoundaryValidationError() from None
        if request.context.runner_id != self.metadata.runner_id:
            raise RunnerBoundaryValidationError() from None

        started_monotonic = self._sample_monotonic()
        cancelled = control.is_cancellation_requested
        completed_at = self._sample_wall_clock()
        completed_monotonic = self._sample_monotonic()
        if completed_monotonic < started_monotonic:
            raise RunnerBoundaryValidationError() from None
        if completed_at < request.invocation.started_at:
            raise RunnerBoundaryValidationError() from None
        elapsed = completed_monotonic - started_monotonic
        if not math.isfinite(elapsed):
            raise RunnerBoundaryValidationError() from None
        duration_ms = int(elapsed * 1000)

        status = (
            RunnerInvocationStatus.CANCELLED
            if cancelled
            else self._outcome
        )
        result = self._result(request, status)
        errors = self._errors(status)
        invocation = request.invocation.model_copy(
            update={
                "status": status,
                "completed_at": completed_at,
                "duration_ms": duration_ms,
                "errors": errors,
            }
        )
        response = RunnerResponse(
            schema_version=RUNNER_CONTRACT_SCHEMA_VERSION,
            invocation=invocation,
            result=result,
            artifacts=self._output_artifacts,
        )
        return validate_runner_response(request, response)

    def _sample_wall_clock(self) -> datetime:
        try:
            sampled = self._wall_clock()
        except (KeyboardInterrupt, SystemExit, GeneratorExit):
            raise
        except Exception:
            raise RunnerBoundaryValidationError() from None
        if (
            type(sampled) is not datetime
            or sampled.tzinfo is None
            or sampled.utcoffset() is None
        ):
            raise RunnerBoundaryValidationError() from None
        return sampled.astimezone(timezone.utc)

    def _sample_monotonic(self) -> float:
        try:
            sampled = self._monotonic_clock()
        except (KeyboardInterrupt, SystemExit, GeneratorExit):
            raise
        except Exception:
            raise RunnerBoundaryValidationError() from None
        if type(sampled) not in {int, float} or not math.isfinite(sampled):
            raise RunnerBoundaryValidationError() from None
        return float(sampled)

    @staticmethod
    def _result(
        request: RunnerRequest,
        status: RunnerInvocationStatus,
    ) -> Optional[StructuredResult]:
        if status not in {
            RunnerInvocationStatus.SUCCEEDED,
            RunnerInvocationStatus.PARTIALLY_SUCCEEDED,
        }:
            return None
        return StructuredResult(
            schema_version="1",
            schema_id=request.expected_result_schema_id,
            result_schema_version=request.expected_result_schema_version,
            data={"outcome": status.value},
        )

    @staticmethod
    def _errors(status: RunnerInvocationStatus) -> Tuple[RunError, ...]:
        if status is RunnerInvocationStatus.SUCCEEDED:
            return ()
        if status is RunnerInvocationStatus.PARTIALLY_SUCCEEDED:
            return (
                RunError(
                    code="runner.mock.partial",
                    category=RunErrorCategory.EXECUTION,
                    safe_message="Mock execution completed partially.",
                    step_id=None,
                    retryable=False,
                    error_type="mock-partial",
                ),
            )
        if status is RunnerInvocationStatus.CANCELLED:
            return (
                RunError(
                    code="runner.mock.cancelled",
                    category=RunErrorCategory.CANCELLED,
                    safe_message="Mock execution was cancelled.",
                    step_id=None,
                    retryable=False,
                    error_type="mock-cancelled",
                ),
            )
        return (
            RunError(
                code="runner.mock.failed",
                category=RunErrorCategory.EXECUTION,
                safe_message="Mock execution failed.",
                step_id=None,
                retryable=False,
                error_type="mock-failed",
            ),
        )


__all__ = ["MockRunner"]
