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
_RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS = (
    MemoryError,
    KeyboardInterrupt,
    SystemExit,
    GeneratorExit,
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
        if (
            type(output_artifacts) is not tuple
            or any(type(artifact) is not RunArtifact for artifact in output_artifacts)
        ):
            raise RunnerBoundaryValidationError() from None
        artifact_snapshot_failed = False
        artifact_snapshot: Tuple[RunArtifact, ...] = ()
        try:
            artifact_snapshot = tuple(
                RunArtifact.from_dict(artifact.to_dict())
                for artifact in output_artifacts
            )
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except Exception:
            artifact_snapshot_failed = True
        if artifact_snapshot_failed:
            raise RunnerBoundaryValidationError() from None
        self._outcome = outcome
        self._metadata = metadata or RunnerMetadata(
            schema_version=RUNNER_CONTRACT_SCHEMA_VERSION,
            runner_id="runner.mock",
            runner_version="1",
            display_name="Deterministic mock runner",
            capabilities=("deterministic-execution",),
        )
        self._output_artifacts = artifact_snapshot
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
        duration_ms = self._duration_milliseconds(
            started_monotonic,
            completed_monotonic,
        )

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
            artifacts=() if cancelled else self._output_artifacts,
        )
        return validate_runner_response(request, response)

    def _sample_wall_clock(self) -> datetime:
        failed = False
        normalized: Optional[datetime] = None
        try:
            sampled = self._wall_clock()
            if (
                type(sampled) is not datetime
                or sampled.tzinfo is None
                or sampled.utcoffset() is None
            ):
                failed = True
            else:
                normalized = sampled.astimezone(timezone.utc)
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except Exception:
            failed = True
        if failed or normalized is None:
            raise RunnerBoundaryValidationError() from None
        return normalized

    def _sample_monotonic(self) -> float:
        failed = False
        normalized: Optional[float] = None
        try:
            sampled = self._monotonic_clock()
            if (
                type(sampled) not in {int, float}
                or not math.isfinite(sampled)
            ):
                failed = True
            else:
                normalized = float(sampled)
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except Exception:
            failed = True
        if failed or normalized is None:
            raise RunnerBoundaryValidationError() from None
        return normalized

    @staticmethod
    def _duration_milliseconds(started: float, completed: float) -> int:
        failed = False
        duration_ms: Optional[int] = None
        try:
            elapsed = completed - started
            scaled = elapsed * 1000
            if (
                elapsed < 0
                or not math.isfinite(elapsed)
                or not math.isfinite(scaled)
            ):
                failed = True
            else:
                duration_ms = int(scaled)
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except Exception:
            failed = True
        if failed or duration_ms is None:
            raise RunnerBoundaryValidationError() from None
        return duration_ms

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
