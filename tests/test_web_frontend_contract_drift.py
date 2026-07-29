"""Authoritative Python-to-frontend API v1 fixture drift check."""

import json
from pathlib import Path

from pmqa.conversation import (
    ConversationRetentionPolicy,
    ConversationSession,
    ConversationSessionStatus,
    ConversationTurn,
    ConversationTurnStatus,
)
from pmqa.run import WorkflowDefinition
from pmqa.web import (
    CloseSessionRequest,
    CreateSessionRequest,
    CreateTurnRequest,
    DeleteSessionResponse,
    HealthResponse,
    SessionListResponse,
    SessionResponse,
    TurnListResponse,
    TurnMutationResponse,
    TurnResponse,
    WEB_API_SCHEMA_VERSION,
    WorkflowCatalogResponse,
)
from test_web_app import _components


def test_frontend_api_fixture_matches_exported_python_contract_fields() -> None:
    root = Path(__file__).resolve().parents[1]
    fixture = json.loads(
        (
            root
            / "frontend"
            / "workbench"
            / "src"
            / "api-v1.contract.json"
        ).read_text(encoding="utf-8")
    )
    contract_types = (
        HealthResponse,
        WorkflowCatalogResponse,
        CreateSessionRequest,
        CloseSessionRequest,
        CreateTurnRequest,
        SessionResponse,
        SessionListResponse,
        TurnResponse,
        TurnListResponse,
        TurnMutationResponse,
        DeleteSessionResponse,
    )

    assert fixture["schema_version"] == "1"
    assert fixture["contracts"] == {
        contract_type.__name__: list(contract_type.model_fields)
        for contract_type in contract_types
    }


def test_frontend_selected_nested_fields_and_enums_match_python() -> None:
    fixture = _fixture()
    selected = fixture["selected_domain_fields"]

    assert selected["ConversationSession"] == list(
        ConversationSession.model_fields
    )
    assert selected["ConversationTurn"] == list(
        ConversationTurn.model_fields
    )
    assert selected["WorkflowDefinition"] == [
        "schema_version",
        "workflow_id",
        "workflow_version",
        "display_name",
        "description",
    ]
    assert set(selected["WorkflowDefinition"]) <= set(
        WorkflowDefinition.model_fields
    )
    assert fixture["enum_values"] == {
        "ConversationRetentionPolicy": [
            item.value for item in ConversationRetentionPolicy
        ],
        "ConversationSessionStatus": [
            item.value for item in ConversationSessionStatus
        ],
        "ConversationTurnStatus": [
            item.value for item in ConversationTurnStatus
        ],
    }


def test_frontend_operation_fixture_matches_real_api_routes() -> None:
    fixture = _fixture()
    app, _, _, _, _ = _components()
    actual_routes = {
        (method, route.path)
        for route in app.routes
        for method in getattr(route, "methods", ())
        if route.path.startswith("/api/v1/")
    }

    assert fixture["schema_version"] == WEB_API_SCHEMA_VERSION
    assert set(fixture["operations"]) == {
        "health",
        "workflows",
        "sessions",
        "session",
        "turns",
        "createSession",
        "createTurn",
        "closeSession",
        "deleteSession",
    }
    assert {
        (operation["method"], operation["path"])
        for operation in fixture["operations"].values()
    } <= actual_routes


def _fixture():
    root = Path(__file__).resolve().parents[1]
    return json.loads(
        (
            root
            / "frontend"
            / "workbench"
            / "src"
            / "api-v1.contract.json"
        ).read_text(encoding="utf-8")
    )
