"""Minimal offline implementation of the reasoning provider contract."""

from pmqa.reasoning.models import (
    ReasoningDecision,
    ReasoningRequest,
    ReasoningResponse,
    ReasoningStatus,
)
from pmqa.reasoning.provider import ReasoningProvider


class DeterministicReasoningProvider(ReasoningProvider):
    """Returns a stable acknowledgement decision for offline contract testing."""

    provider_name = "deterministic"
    model_name = "rules-v1"

    def _reason(self, request: ReasoningRequest) -> ReasoningResponse:
        """Return a deterministic decision derived from request identifiers."""

        return ReasoningResponse(
            request_id=request.request_id,
            provider=self.provider_name,
            model=self.model_name,
            status=ReasoningStatus.COMPLETED,
            decisions=[
                ReasoningDecision(
                    decision_type="acknowledge",
                    value={
                        "task_type": request.task_type,
                        "workflow_id": request.workflow_id,
                    },
                    reason_summary="Deterministic offline acknowledgement",
                    confidence=1.0,
                )
            ],
            confidence=1.0,
            metadata={"mode": "offline"},
        )
