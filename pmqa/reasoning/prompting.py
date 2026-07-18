"""Shared deterministic prompt rendering and structured response parsing."""

import json
import re
from typing import Type

from pydantic import BaseModel, ConfigDict, Field

from pmqa.reasoning.models import ReasoningResponse
from pmqa.reasoning.validation import RequestInput, validate_reasoning_request, validate_reasoning_response
from pmqa.utils.hashing import canonical_json_sha256


class ReasoningPromptPackage(BaseModel):
    """Contains a deterministic prompt and canonical contract guidance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    prompt_text: str = Field(min_length=1)
    request_json: str = Field(min_length=1)
    response_schema_json: str = Field(min_length=1)
    request_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class ReasoningOutputError(ValueError):
    """Reports invalid structured output without echoing the raw response."""


class ReasoningResponseParser:
    """Parses one optional-fenced JSON object and enforces its provenance."""

    _fence = re.compile(r"\A```(?:json)?\s*(.*?)\s*```\Z", re.IGNORECASE | re.DOTALL)

    def __init__(
        self,
        expected_provider: str,
        *,
        error_type: Type[Exception] = ReasoningOutputError,
        label: str = "Reasoning",
    ) -> None:
        self._expected_provider = expected_provider
        self._error_type = error_type
        self._label = label

    def parse(self, raw_text: str, request_id: str) -> ReasoningResponse:
        """Parse and validate exactly one correlated response object."""

        text = raw_text.strip()
        if not text:
            raise self._error_type(f"{self._label} response is empty")
        fence = self._fence.fullmatch(text)
        if fence:
            text = fence.group(1).strip()
            if "```" in text:
                raise self._object_error()
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as error:
            raise self._error_type(
                f"{self._label} response must contain exactly one JSON object "
                f"(invalid JSON at line {error.lineno}, column {error.colno})"
            ) from error
        if not isinstance(payload, dict):
            raise self._object_error()
        response = validate_reasoning_response(payload, expected_request_id=request_id)
        if response.provider != self._expected_provider:
            raise self._error_type(
                f"{self._label} response provider must be {self._expected_provider!r}"
            )
        return response

    def _object_error(self) -> Exception:
        return self._error_type(
            f"{self._label} response must contain exactly one JSON object"
        )


def render_prompt_package(
    request: RequestInput,
    *,
    provider_name: str,
    model_guidance: str,
) -> ReasoningPromptPackage:
    """Build the shared deterministic prompt package for a safe request."""

    valid_request = validate_reasoning_request(request)
    request_payload = valid_request.model_dump(mode="json")
    request_json = canonical_json(request_payload)
    schema_json = canonical_json(ReasoningResponse.model_json_schema())
    return ReasoningPromptPackage(
        request_id=valid_request.request_id,
        provider=provider_name,
        prompt_text=_render_prompt(
            request_json,
            schema_json,
            provider_name,
            model_guidance,
        ),
        request_json=request_json,
        response_schema_json=schema_json,
        request_hash=canonical_json_sha256(request_payload),
    )


def canonical_json(value) -> str:
    """Serialize a value as compact canonical JSON for prompt transport."""

    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _render_prompt(
    request_json: str,
    response_schema_json: str,
    provider_name: str,
    model_guidance: str,
) -> str:
    return "\n".join(
        [
            "You are performing structured QA reasoning for PMQA.",
            "Use only the structured product knowledge in REQUEST_JSON below.",
            "Do not invent browser state, DOM, credentials, execution results, or evidence.",
            "Return exactly one JSON object and no prose or markdown fences.",
            "The response must conform to RESPONSE_SCHEMA_JSON.",
            "Preserve the exact request_id from the request.",
            f'Set provider to "{provider_name}" and {model_guidance}',
            "Use the typed decision envelope for every decision.",
            "Represent uncertainty with decision confidence, response confidence, or warnings.",
            "",
            "REQUEST_JSON:",
            request_json,
            "",
            "RESPONSE_SCHEMA_JSON:",
            response_schema_json,
        ]
    )
