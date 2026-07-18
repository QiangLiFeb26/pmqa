"""Abstract provider contract for structured reasoning."""

from abc import ABC, abstractmethod

from pmqa.reasoning.models import ReasoningRequest, ReasoningResponse
from pmqa.reasoning.validation import (
    RequestInput,
    validate_reasoning_request,
    validate_reasoning_response,
)


class ReasoningProvider(ABC):
    """Validates one structured request and returns one structured response."""

    provider_name: str = ""

    def reason(self, request: RequestInput) -> ReasoningResponse:
        """Validate, reason, and validate the correlated provider response."""

        valid_request = validate_reasoning_request(request)
        response = self._reason(valid_request)
        return validate_reasoning_response(response, valid_request.request_id)

    @abstractmethod
    def _reason(self, request: ReasoningRequest) -> ReasoningResponse:
        """Perform provider-specific reasoning over a validated request."""
