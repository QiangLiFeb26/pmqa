"""Tests for strict PMQA local API contracts and security configuration."""

from datetime import datetime, timezone
import json
import pickle

import pytest
from pydantic import ValidationError

import pmqa.web.contracts as web_contracts
from pmqa.conversation import (
    ConversationRetentionPolicy,
    ConversationSession,
    ConversationSessionStatus,
    ConversationTurn,
    ConversationTurnStatus,
)
from pmqa.run import ApprovalMode, WorkflowDefinition
from pmqa.web import (
    CloseSessionRequest,
    CreateSessionRequest,
    CreateTurnRequest,
    DeleteSessionResponse,
    HealthResponse,
    PMQAWebSecurityConfigurationError,
    PMQAWebSecurityContext,
    SessionResponse,
    SessionListResponse,
    TurnListResponse,
    TurnMutationResponse,
    TurnResponse,
    WebAPIContractValidationError,
    WorkflowCatalogResponse,
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


def _turn() -> ConversationTurn:
    return ConversationTurn(
        schema_version="1",
        turn_id="conversation.turn.1",
        session_id="conversation.session.1",
        sequence_number=1,
        status=ConversationTurnStatus.PENDING,
        user_message="Analyze",
        assistant_response=None,
        error_code=None,
        error_message=None,
        created_at=NOW,
        completed_at=None,
    )


def _workflow() -> WorkflowDefinition:
    return WorkflowDefinition(
        schema_version="1",
        workflow_id="workflow.test",
        workflow_version="1",
        display_name="Test workflow",
        description="Canonical workflow.",
        input_schema_id="schema.input",
        input_schema_version="1",
        result_schema_id="schema.result",
        result_schema_version="1",
        preview_steps=(),
        required_runner_capabilities=(),
        approval_mode=ApprovalMode.NONE,
    )


def _public_contracts():
    session = _session()
    turn = _turn()
    return (
        HealthResponse(
            schema_version="1",
            api_version="v1",
            readiness="ready",
        ),
        WorkflowCatalogResponse(
            schema_version="1",
            workflows=(_workflow(),),
        ),
        CreateSessionRequest(schema_version="1"),
        CloseSessionRequest(
            schema_version="1",
            session_id=session.session_id,
            expected_revision=1,
        ),
        CreateTurnRequest(
            schema_version="1",
            session_id=session.session_id,
            expected_revision=1,
            user_message="Analyze",
        ),
        SessionResponse(schema_version="1", session=session),
        SessionListResponse(schema_version="1", sessions=(session,)),
        TurnResponse(schema_version="1", turn=turn),
        TurnListResponse(schema_version="1", turns=(turn,)),
        TurnMutationResponse(
            schema_version="1",
            session=session,
            turn=turn,
        ),
        DeleteSessionResponse(schema_version="1", deleted=True),
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


def test_every_public_contract_has_canonical_json_round_trip() -> None:
    for contract in _public_contracts():
        wire = contract.to_dict()
        restored = type(contract).from_dict(
            json.loads(json.dumps(wire))
        )

        assert restored == contract
        assert restored is not contract
        assert restored.to_dict() == wire


@pytest.mark.parametrize(
    ("contract_type", "values"),
    (
        (
            WorkflowCatalogResponse,
            {"schema_version": "1", "workflows": [_workflow()]},
        ),
        (
            SessionResponse,
            {"schema_version": "1", "session": _session().to_dict()},
        ),
        (
            SessionListResponse,
            {"schema_version": "1", "sessions": [_session()]},
        ),
        (
            TurnResponse,
            {"schema_version": "1", "turn": _turn().to_dict()},
        ),
        (
            TurnListResponse,
            {"schema_version": "1", "turns": [_turn()]},
        ),
        (
            TurnMutationResponse,
            {
                "schema_version": "1",
                "session": _session().to_dict(),
                "turn": _turn().to_dict(),
            },
        ),
    ),
)
def test_direct_construction_rejects_wire_dicts_and_mutable_lists(
    contract_type,
    values,
) -> None:
    with pytest.raises(ValidationError):
        contract_type(**values)


@pytest.mark.parametrize(
    "contract",
    _public_contracts(),
)
def test_every_public_contract_model_copy_revalidates(contract) -> None:
    copied = contract.model_copy()

    assert copied == contract
    assert copied is not contract
    assert copied.to_dict() == contract.to_dict()

    with pytest.raises(WebAPIContractValidationError) as captured:
        contract.model_copy(
            update={
                "schema_version": 1,
                "unknown": "runtime-secret-marker",
            }
        )

    assert str(captured.value) == "invalid PMQA Web API contract"
    assert "runtime-secret-marker" not in str(captured.value)
    assert captured.value.__cause__ is None


@pytest.mark.parametrize(
    ("contract", "update"),
    (
        (
            CreateSessionRequest(schema_version="1"),
            {"retention_policy": ConversationRetentionPolicy.SEVEN_DAYS},
        ),
        (
            CloseSessionRequest(
                schema_version="1",
                session_id="conversation.session.1",
                expected_revision=1,
            ),
            {"expected_revision": 2},
        ),
        (
            CreateTurnRequest(
                schema_version="1",
                session_id="conversation.session.1",
                expected_revision=1,
                user_message="Analyze",
            ),
            {"user_message": "Analyze again"},
        ),
        (
            SessionResponse(schema_version="1", session=_session()),
            {"session": _session()},
        ),
        (
            TurnResponse(schema_version="1", turn=_turn()),
            {"turn": _turn()},
        ),
    ),
)
def test_valid_model_copy_updates_remain_canonical(contract, update) -> None:
    updated = contract.model_copy(update=update)
    restored = type(updated).from_dict(
        json.loads(json.dumps(updated.to_dict()))
    )

    assert restored == updated


@pytest.mark.parametrize(
    ("contract", "update"),
    (
        (
            HealthResponse(
                schema_version="1",
                api_version="v1",
                readiness="ready",
            ),
            {"readiness": "ready"},
        ),
        (
            WorkflowCatalogResponse(
                schema_version="1",
                workflows=(_workflow(),),
            ),
            {"workflows": (_workflow(),)},
        ),
        (
            SessionListResponse(
                schema_version="1",
                sessions=(_session(),),
            ),
            {"sessions": (_session(),)},
        ),
        (
            TurnListResponse(
                schema_version="1",
                turns=(_turn(),),
            ),
            {"turns": (_turn(),)},
        ),
        (
            TurnMutationResponse(
                schema_version="1",
                session=_session(),
                turn=_turn(),
            ),
            {"session": _session(), "turn": _turn()},
        ),
        (
            DeleteSessionResponse(schema_version="1", deleted=True),
            {"deleted": True},
        ),
    ),
)
def test_remaining_contract_shapes_revalidate_valid_model_copy_updates(
    contract,
    update,
) -> None:
    updated = contract.model_copy(update=update)

    assert type(updated).from_dict(updated.to_dict()) == updated


def test_model_copy_snapshots_caller_owned_nested_domain_objects() -> None:
    session = _session()
    response = SessionResponse(
        schema_version="1",
        session=_session(),
    ).model_copy(update={"session": session})
    session.__dict__["session_id"] = "conversation.session.redirected"

    assert response.session.session_id == "conversation.session.1"


class _DictionarySubclass(dict):
    pass


@pytest.mark.parametrize(
    ("contract_type", "wire"),
    (
        (
            WorkflowCatalogResponse,
            {
                "schema_version": "1",
                "workflows": (_workflow().to_dict(),),
            },
        ),
        (
            SessionResponse,
            {"schema_version": "1", "session": _session()},
        ),
        (
            SessionResponse,
            {
                "schema_version": "1",
                "session": _DictionarySubclass(_session().to_dict()),
            },
        ),
        (
            SessionListResponse,
            {
                "schema_version": "1",
                "sessions": (_session().to_dict(),),
            },
        ),
        (
            TurnResponse,
            {"schema_version": "1", "turn": _turn()},
        ),
        (
            TurnListResponse,
            {
                "schema_version": "1",
                "turns": (_turn().to_dict(),),
            },
        ),
        (
            TurnMutationResponse,
            {
                "schema_version": "1",
                "session": _session().to_dict(),
                "turn": _DictionarySubclass(_turn().to_dict()),
            },
        ),
        (
            SessionResponse,
            {
                "schema_version": "1",
                "session": {
                    **_session().to_dict(),
                    "created_at": "2026-07-25T12:00:00+00:00",
                },
            },
        ),
    ),
)
def test_from_dict_rejects_runtime_objects_and_noncanonical_nested_wire(
    contract_type,
    wire,
) -> None:
    with pytest.raises(WebAPIContractValidationError) as captured:
        contract_type.from_dict(wire)

    assert str(captured.value) == "invalid PMQA Web API contract"
    assert captured.value.__cause__ is None


@pytest.mark.parametrize(
    "invalid_wire",
    (
        (),
        b'{"schema_version":"1"}',
        HealthResponse(
            schema_version="1",
            api_version="v1",
            readiness="ready",
        ),
        {"schema_version": "1", "api_version": "v1"},
        {
            "schema_version": "1",
            "api_version": "v1",
            "readiness": "ready",
            "unknown": "runtime-secret-marker",
        },
    ),
)
def test_from_dict_rejects_noncanonical_wire_inputs(invalid_wire) -> None:
    with pytest.raises(WebAPIContractValidationError) as captured:
        HealthResponse.from_dict(invalid_wire)

    assert "runtime-secret-marker" not in str(captured.value)


@pytest.mark.parametrize(
    "payload",
    (
        b'{"schema_version":"1","schema_version":"1"}',
        b'{"value":NaN}',
        b'{"value":Infinity}',
        b'{"value":-Infinity}',
        b'{"value":1e9999}',
        b'{"value":-1e9999}',
        b'{"nested":{"value":1e9999}}',
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


@pytest.mark.parametrize(
    "failure",
    (MemoryError(), KeyboardInterrupt(), SystemExit(), GeneratorExit()),
)
def test_canonical_json_parser_preserves_resource_and_control_flow(
    monkeypatch,
    failure,
) -> None:
    def raise_failure(*args, **kwargs):
        _ = args, kwargs
        raise failure

    monkeypatch.setattr(web_contracts.json, "loads", raise_failure)

    with pytest.raises(type(failure)) as captured:
        parse_canonical_json_object(b'{"schema_version":"1"}')

    assert captured.value is failure
