"""Offline tests for the reasoning-boundary scrubber."""

import pytest

from pmqa.models import Element, Interaction, Lifecycle, Page
from pmqa.reasoning import (
    DeterministicReasoningScrubber,
    ReasoningRequest,
    ScrubInput,
    ScrubStatus,
    ScrubValidationError,
    validate_reasoning_request,
)
from products.demo.reasoning import DeterministicDemoReasoningProvider


def test_clean_structured_product_knowledge_is_preserved() -> None:
    source = _input()

    result = DeterministicReasoningScrubber().scrub(source)

    assert result.request.pages == source.pages
    assert result.request.elements == source.elements
    assert result.request.interactions == source.interactions
    assert result.request.constraints == source.constraints
    assert result.report.status is ScrubStatus.COMPLETED
    assert result.report.removed_fields == []
    assert result.report.redacted_values == []


def test_prohibited_keys_are_removed_case_insensitively_with_separator_variants() -> None:
    source = _input(
        metadata={
            "Password": "fake-password",
            "ACCESS-TOKEN": "fake-access-token",
            "api_key": "fake-api-key",
            "safe": "preserved",
        }
    )

    result = DeterministicReasoningScrubber().scrub(source)

    assert result.request.metadata == {"safe": "preserved"}
    assert result.report.removed_fields == [
        "metadata.ACCESS-TOKEN",
        "metadata.Password",
        "metadata.api_key",
    ]
    assert "prohibited-key-removal" in result.report.rules_applied


def test_nested_dictionaries_and_lists_are_scrubbed() -> None:
    source = _input(
        constraints={
            "nested": {
                "credentials": {"user": "fake", "password": "fake-secret"},
                "items": [
                    {"safe": "one", "refresh_token": "fake-refresh"},
                    "password=fake-list-secret",
                ],
            }
        }
    )

    result = DeterministicReasoningScrubber().scrub(source)

    assert result.request.constraints == {
        "nested": {
            "items": [
                {"safe": "one"},
                "password=[REDACTED]",
            ]
        }
    }
    assert "constraints.nested.credentials" in result.report.removed_fields
    assert "constraints.nested.items[0].refresh_token" in result.report.removed_fields


@pytest.mark.parametrize(
    ("source_text", "expected"),
    [
        ("Authorization: Bearer fake.token-123", "Authorization: Bearer [REDACTED]"),
        ("password=fake-password", "password=[REDACTED]"),
        ("api-key: fake-api-key", "api-key:[REDACTED]"),
        ("Cookie: session=fake-cookie", "Cookie: [REDACTED]"),
        ("token = fake-token", "token=[REDACTED]"),
    ],
)
def test_sensitive_string_patterns_are_redacted(source_text: str, expected: str) -> None:
    result = DeterministicReasoningScrubber().scrub(
        _input(metadata={"note": source_text})
    )

    assert result.request.metadata["note"] == expected
    assert result.report.redacted_values[0].path == "metadata.note"
    assert result.report.redacted_values[0].replacement == "[REDACTED]"


def test_raw_dom_and_html_fields_do_not_cross_the_boundary() -> None:
    result = DeterministicReasoningScrubber().scrub(
        _input(metadata={"raw_dom": "<body>fake</body>", "HTML": "<p>fake</p>"})
    )

    assert result.request.metadata == {}
    assert result.report.removed_fields == ["metadata.HTML", "metadata.raw_dom"]


def test_runtime_objects_are_rejected_without_revealing_their_values() -> None:
    class FakeBrowserContext:
        def __repr__(self) -> str:
            return "FakeBrowserContext(token=fake-runtime-secret)"

    source = _input(metadata={"session": FakeBrowserContext()})

    with pytest.raises(ScrubValidationError) as captured:
        DeterministicReasoningScrubber().scrub(source)

    assert str(captured.value) == "Unsupported runtime object at metadata.session"
    assert "fake-runtime-secret" not in str(captured.value)


def test_prohibited_runtime_object_is_rejected_instead_of_silently_removed() -> None:
    source = _input(metadata={"browser-context": object()})

    with pytest.raises(
        ScrubValidationError,
        match="Unsupported runtime object at metadata.browser-context",
    ):
        DeterministicReasoningScrubber().scrub(source)


def test_report_never_contains_original_secret_values() -> None:
    fake_secrets = ["fake-key-secret", "fake-bearer-secret", "fake-cookie-secret"]
    source = _input(
        metadata={
            "api_key": fake_secrets[0],
            "note": f"Bearer {fake_secrets[1]}",
            "header": f"Cookie: session={fake_secrets[2]}",
        }
    )

    report_json = DeterministicReasoningScrubber().scrub(source).report.model_dump_json()

    assert all(secret not in report_json for secret in fake_secrets)


def test_hashes_and_output_are_deterministic_for_equivalent_inputs() -> None:
    first = _input(metadata={"z": "last", "a": "first"})
    second = _input(metadata={"a": "first", "z": "last"})
    scrubber = DeterministicReasoningScrubber()

    first_result = scrubber.scrub(first)
    repeated_result = scrubber.scrub(first)
    equivalent_result = scrubber.scrub(second)

    assert first_result == repeated_result
    assert first_result.request == equivalent_result.request
    assert first_result.report.input_hash == equivalent_result.report.input_hash
    assert first_result.report.output_hash == equivalent_result.report.output_hash
    assert len(first_result.report.input_hash) == 64
    assert len(first_result.report.output_hash) == 64


def test_final_output_passes_canonical_request_validation() -> None:
    result = DeterministicReasoningScrubber().scrub(
        _input(metadata={"note": "password=fake-secret"})
    )

    assert validate_reasoning_request(result.request) == result.request
    assert isinstance(result.request, ReasoningRequest)


def test_saucedemo_provider_receives_request_through_scrub_boundary() -> None:
    result = DeterministicReasoningScrubber().scrub(_input())

    response = DeterministicDemoReasoningProvider().reason(result.request)

    assert response.request_id == result.request.request_id
    assert [decision.value["action"] for decision in response.decisions] == [
        "inspect_login_page",
        "login",
        "verify_inventory_page",
        "inspect_inventory_item",
    ]


def _input(
    *,
    constraints=None,
    metadata=None,
) -> ScrubInput:
    lifecycle = Lifecycle()
    page = Page("page.login", lifecycle, "https://example.test/", "Login", "fingerprint")
    element = Element(
        "element.login",
        lifecycle,
        page.id,
        "button",
        "Login",
        "Login",
        {"data-test": "login-button"},
    )
    interaction = Interaction(
        "interaction.login",
        lifecycle,
        page.id,
        element.id,
        "click",
        "navigation",
        "/inventory.html",
    )
    return ScrubInput(
        request_id="request-1",
        workflow_id="workflow-1",
        task_type="explore",
        provider_hint="deterministic",
        product_id="demo",
        artifact_version="1",
        pages=[page],
        elements=[element],
        interactions=[interaction],
        constraints=constraints or {"maximum_steps": 4},
        metadata=metadata or {},
    )
