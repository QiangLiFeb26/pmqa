"""Canonical prompt packages and structured response parsing."""

import json
import re
from typing import Any, Dict, Type

from pydantic import BaseModel, ConfigDict, Field

from pmqa.reasoning.models import ReasoningRequest, ReasoningResponse
from pmqa.reasoning.validation import (
    RequestInput,
    validate_reasoning_request,
    validate_reasoning_response,
)
from pmqa.utils.hashing import canonical_json, canonical_json_sha256


class PromptPackage(BaseModel):
    """Carries one deterministic, persist-safe reasoning prompt contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    package_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    request_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    prompt_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    prompt_text: str = Field(min_length=1)
    request_json: str = Field(min_length=1)
    response_schema_json: str = Field(min_length=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)


ReasoningPromptPackage = PromptPackage


class PromptPackageError(ValueError):
    """Reports an invalid or inconsistent prompt package."""


class PromptPackageBuilder:
    """Builds deterministic prompt packages from validated safe requests."""

    _format = "pmqa-reasoning-prompt-v1"

    def build(self, *, request: RequestInput, provider: str) -> PromptPackage:
        """Build a provider-aware package using shared canonical rendering."""

        if not provider:
            raise PromptPackageError("provider must not be empty")
        valid_request = validate_reasoning_request(request)
        request_payload = valid_request.model_dump(mode="json")
        request_json = canonical_json(request_payload)
        response_schema_json = canonical_json(ReasoningResponse.model_json_schema())
        prompt_text = _render_prompt(
            request_json,
            response_schema_json,
            provider,
            "identify the model you used.",
        )
        request_hash = canonical_json_sha256(request_payload)
        prompt_hash = canonical_json_sha256(prompt_text)
        identity = {
            "format": self._format,
            "provider": provider,
            "request_hash": request_hash,
            "prompt_hash": prompt_hash,
        }
        return PromptPackage(
            package_id=canonical_json_sha256(identity),
            request_id=valid_request.request_id,
            provider=provider,
            request_hash=request_hash,
            prompt_hash=prompt_hash,
            prompt_text=prompt_text,
            request_json=request_json,
            response_schema_json=response_schema_json,
            metadata={"format": self._format},
        )

    def validate(
        self,
        package: PromptPackage,
        *,
        request: ReasoningRequest,
        provider: str,
    ) -> PromptPackage:
        """Enforce package, request, provider, and hash correlation."""

        expected = self.build(request=request, provider=provider)
        if package != expected:
            raise PromptPackageError(
                "Prompt package does not match its request and provider"
            )
        return package


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
) -> PromptPackage:
    """Build the canonical package; retained for existing provider callers."""

    return PromptPackageBuilder().build(request=request, provider=provider_name)


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
