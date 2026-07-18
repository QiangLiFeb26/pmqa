"""Immutable records for persisted reasoning exchanges."""

import json
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from pmqa.reasoning.models import (
    ReasoningRequest,
    ReasoningResponse,
    ReasoningStatus,
)
from pmqa.reasoning.validation import (
    validate_reasoning_exchange,
    validate_reasoning_request,
    validate_reasoning_response,
)
from pmqa.utils.hashing import canonical_json, canonical_json_sha256


class TraceRecord(BaseModel):
    """Captures one immutable, provider-independent reasoning exchange."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    trace_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    status: ReasoningStatus
    request_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_json: str = Field(min_length=1)
    response_json: str = Field(min_length=1)
    created_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_exchange(
        cls,
        trace_id: str,
        request: ReasoningRequest,
        response: ReasoningResponse,
        created_at: datetime,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "TraceRecord":
        """Build a canonical record from a validated reasoning exchange."""

        valid_request, valid_response = validate_reasoning_exchange(request, response)
        request_data = valid_request.model_dump(mode="json")
        response_data = valid_response.model_dump(mode="json")
        record_metadata = {} if metadata is None else metadata
        canonical_json(record_metadata)
        return cls(
            trace_id=trace_id,
            request_id=valid_request.request_id,
            provider=valid_response.provider,
            model=valid_response.model,
            status=valid_response.status,
            request_hash=canonical_json_sha256(request_data),
            request_json=canonical_json(request_data),
            response_json=canonical_json(response_data),
            created_at=created_at,
            metadata=record_metadata,
        )

    def reasoning_request(self) -> ReasoningRequest:
        """Deserialize and validate the stored request payload."""

        return validate_reasoning_request(json.loads(self.request_json))

    def reasoning_response(self) -> ReasoningResponse:
        """Deserialize and validate the stored response payload."""

        return validate_reasoning_response(
            json.loads(self.response_json), expected_request_id=self.request_id
        )
