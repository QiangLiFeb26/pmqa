"""Tests for canonical deterministic Prompt Packages."""

import json

import pytest

from pmqa.reasoning import (
    PromptPackage,
    PromptPackageBuilder,
    PromptPackageError,
    ReasoningRequest,
)
from pmqa.utils.hashing import canonical_json, canonical_json_sha256


def test_prompt_package_is_deterministic_and_json_serializable() -> None:
    builder = PromptPackageBuilder()

    first = builder.build(request=_request(), provider="deterministic")
    second = builder.build(request=_request(), provider="deterministic")

    assert first == second
    assert PromptPackage.model_validate_json(first.model_dump_json()) == first
    assert canonical_json(first.model_dump(mode="json"))


def test_safe_request_content_changes_package_identity() -> None:
    builder = PromptPackageBuilder()
    changed = _request().model_copy(update={"task_type": "changed-task"})

    first = builder.build(request=_request(), provider="deterministic")
    second = builder.build(request=changed, provider="deterministic")

    assert first.request_hash != second.request_hash
    assert first.prompt_hash != second.prompt_hash
    assert first.package_id != second.package_id


def test_provider_changes_prompt_and_package_identity_not_request_hash() -> None:
    builder = PromptPackageBuilder()

    first = builder.build(request=_request(), provider="provider-a")
    second = builder.build(request=_request(), provider="provider-b")

    assert first.request_hash == second.request_hash
    assert first.prompt_hash != second.prompt_hash
    assert first.package_id != second.package_id


def test_package_hashes_match_canonical_content() -> None:
    package = PromptPackageBuilder().build(
        request=_request(), provider="deterministic"
    )

    assert package.request_hash == canonical_json_sha256(
        json.loads(package.request_json)
    )
    assert package.prompt_hash == canonical_json_sha256(package.prompt_text)
    assert package.request_id == json.loads(package.request_json)["request_id"]


def test_tampered_package_fails_correlation_validation() -> None:
    builder = PromptPackageBuilder()
    package = builder.build(request=_request(), provider="deterministic")
    tampered = package.model_copy(update={"prompt_hash": "0" * 64})

    with pytest.raises(PromptPackageError, match="does not match"):
        builder.validate(
            tampered, request=_request(), provider="deterministic"
        )


def _request() -> ReasoningRequest:
    return ReasoningRequest(
        request_id="request-1",
        workflow_id="workflow-1",
        task_type="offline-test",
        product_id="demo",
        artifact_version="1",
        constraints={"offline": True},
    )
