"""Tests for strict PMQA local API contracts and security configuration."""

from datetime import datetime, timezone
import json
import pickle

import pytest

from pmqa.conversation import (
    ConversationRetentionPolicy,
    ConversationSession,
    ConversationSessionStatus,
)
from pmqa.web import (
    CloseSessionRequest,
    CreateSessionRequest,
    CreateTurnRequest,
    PMQAWebSecurityConfigurationError,
    PMQAWebSecurityContext,
    SessionResponse,
    WebAPIContractValidationError,
    parse_canonical_json_object,
)


NOW = datetime(2026, 7, 25, 12, tzinfo=timezone.utc)
SESSION_TOKEN = "a" * 43
CSRF_TOKEN = "b" * 43


def _session() -> ConversationSession:
    return ConversationSession(
        schema_version="1",
        session_id="conversation.session.1",
        revision=1,
        status=ConversationSessionStatus.ACTIVE,
        retention_policy=ConversationRetentionPolicy.SESSION_ONLY,
        connection_context_id=None,
        turn_ids=(),
        created_at=NOW,
        updated_at=NOW,
        expires_at=None,
    )


def test_security_context_validates_and_redacts_runtime_tokens() -> None:
    context = PMQAWebSecurityContext(
        session_token=SESSION_TOKEN,
        csrf_token=CSRF_TOKEN,
        host="127.0.0.1",
        port=8765,
    )

    assert context.host == "127.0.0.1"
    assert context.port == 8765
    assert context.host_authority == "127.0.0.1:8765"
    assert context.origin == "http://127.0.0.1:8765"
    assert context.authenticates(SESSION_TOKEN)
    assert context.validates_csrf(CSRF_TOKEN)
    assert SESSION_TOKEN not in repr(context)
    assert CSRF_TOKEN not in repr(context)
    assert "redacted" in repr(context)
    with pytest.raises(TypeError):
        json.dumps(context)
    with pytest.raises(TypeError):
        pickle.dumps(context)


def test_ipv6_security_context_derives_unambiguous_authority() -> None:
    context = PMQAWebSecurityContext(
        session_token=SESSION_TOKEN,
        csrf_token=CSRF_TOKEN,
        host="::1",
        port=9000,
    )

    assert context.host_authority == "[::1]:9000"
    assert context.origin == "http://[::1]:9000"


@pytest.mark.parametrize(
    "updates",
    (
        {"session_token": "short"},
        {"csrf_token": "has+non_base64url" * 4},
        {"csrf_token": SESSION_TOKEN},
        {"host": "localhost"},
        {"host": "0.0.0.0"},
        {"host": "127.0.0.1/path"},
        {"host": "127.0.0.1\x00"},
        {"port": 0},
        {"port": 65536},
        {"port": True},
    ),
)
def test_security_context_rejects_ambiguous_or_invalid_values(updates) -> None:
    values = {
        "session_token": SESSION_TOKEN,
        "csrf_token": CSRF_TOKEN,
        "host": "127.0.0.1",
        "port": 8765,
    }
    values.update(updates)

    with pytest.raises(PMQAWebSecurityConfigurationError) as captured:
        PMQAWebSecurityContext(**values)

    assert str(captured.value) == (
        "invalid PMQA Web security configuration"
    )
    assert SESSION_TOKEN not in str(captured.value)
    assert CSRF_TOKEN not in str(captured.value)
    assert captured.value.__cause__ is None


def test_create_session_contract_applies_only_approved_default() -> None:
    request = CreateSessionRequest.from_dict({"schema_version": "1"})

    assert request.retention_policy is (
        ConversationRetentionPolicy.THIRTY_DAYS
    )
    assert request.connection_context_id is None
    assert request.to_dict() == {
        "schema_version": "1",
        "retention_policy": "30_days",
        "connection_context_id": None,
    }


@pytest.mark.parametrize(
    "contract_type,payload",
    (
        (
            CreateSessionRequest,
            {"schema_version": "1", "retention_policy": "forever"},
        ),
        (
            CreateSessionRequest,
            {"schema_version": "1", "unknown": "runtime-secret-marker"},
        ),
        (
            CloseSessionRequest,
            {
                "schema_version": "1",
                "session_id": "conversation.session.1",
                "expected_revision": "1",
            },
        ),
        (
            CloseSessionRequest,
            {
                "schema_version": "2",
                "session_id": "conversation.session.1",
                "expected_revision": 1,
            },
        ),
        (
            CreateTurnRequest,
            {
                "schema_version": "1",
                "session_id": "conversation.session.1",
                "expected_revision": True,
                "user_message": "Analyze",
            },
        ),
        (
            CreateTurnRequest,
            {
                "schema_version": "1",
                "session_id": "../wrong",
                "expected_revision": 1,
                "user_message": "Analyze",
            },
        ),
    ),
)
def test_request_contracts_reject_extra_coercive_or_noncanonical_input(
    contract_type,
    payload,
) -> None:
    with pytest.raises(WebAPIContractValidationError) as captured:
        contract_type.from_dict(payload)

    assert str(captured.value) == "invalid PMQA Web API contract"
    assert "runtime-secret-marker" not in str(captured.value)
    assert captured.value.__cause__ is None


def test_response_contract_snapshots_domain_record() -> None:
    session = _session()
    response = SessionResponse(schema_version="1", session=session)
    session.__dict__["session_id"] = "conversation.session.redirected"

    assert response.session.session_id == "conversation.session.1"
    assert response.to_dict()["session"]["session_id"] == (
        "conversation.session.1"
    )


@pytest.mark.parametrize(
    "payload",
    (
        b'{"schema_version":"1","schema_version":"1"}',
        b'{"value":NaN}',
        b'{"value":Infinity}',
        b'{"value":-Infinity}',
        b'["not","an","object"]',
        b'{"value":"\\ud800"}',
        b"\xff",
        b"",
    ),
)
def test_canonical_json_parser_rejects_ambiguous_input(payload) -> None:
    with pytest.raises(WebAPIContractValidationError):
        parse_canonical_json_object(payload)


def test_canonical_json_parser_rejects_excessive_depth_and_items() -> None:
    deep = b'{"a":' + (b"[" * 17) + (b"]" * 17) + b"}"
    many = json.dumps({"items": list(range(2050))}).encode("utf-8")

    with pytest.raises(WebAPIContractValidationError):
        parse_canonical_json_object(deep)
    with pytest.raises(WebAPIContractValidationError):
        parse_canonical_json_object(many)
