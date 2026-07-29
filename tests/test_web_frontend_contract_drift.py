"""Authoritative Python-to-frontend API v1 fixture drift check."""

import json
from pathlib import Path

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
    WorkflowCatalogResponse,
)


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
