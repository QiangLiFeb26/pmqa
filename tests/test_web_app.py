"""Lifecycle, catalog, failure, and import tests for the PMQA Web app."""

from datetime import datetime, timedelta, timezone
import asyncio
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from pmqa.application import WorkflowRegistry
from pmqa.conversation import (
    ConversationApplicationService,
    ConversationRetentionPolicy,
    InMemoryConversationRepository,
)
from pmqa.run import (
    ApprovalMode,
    WorkflowDefinition,
    WorkflowPreviewStep,
)
from pmqa.web import (
    PMQAWebConfigurationError,
    PMQAWebSecurityContext,
    create_pmqa_web_app,
)


NOW = datetime(2026, 7, 25, 12, tzinfo=timezone.utc)
SESSION_TOKEN = "a" * 43
CSRF_TOKEN = "b" * 43
ORIGIN = "http://127.0.0.1:8765"
READ_HEADERS = {"Authorization": f"Bearer {SESSION_TOKEN}"}
MUTATION_HEADERS = {
    **READ_HEADERS,
    "Origin": ORIGIN,
    "X-PMQA-CSRF-Token": CSRF_TOKEN,
}


class Sequence:
    def __init__(self, *values) -> None:
        self.values = list(values)
        self.calls = 0

    def __call__(self):
        value = self.values[self.calls]
        self.calls += 1
        if isinstance(value, BaseException):
            raise value
        return value


class Adapter:
    def __init__(self, definition) -> None:
        self._definition = definition

    @property
    def definition(self):
        return self._definition

    def validate_request(self, request) -> None:
        _ = request

    def validate_result(self, result) -> None:
        _ = result


class ExplodingRepository:
    def __init__(self, failure) -> None:
        self.failure = failure

    def get_session(self, session_id):
        _ = session_id
        raise self.failure


def _definition(workflow_id="workflow.zeta") -> WorkflowDefinition:
    return WorkflowDefinition(
        schema_version="1",
        workflow_id=workflow_id,
        workflow_version="1",
        display_name="Safe workflow",
        description="Bounded workflow catalog metadata.",
        input_schema_id="schema.input",
        input_schema_version="1",
        result_schema_id="schema.result",
        result_schema_version="1",
        preview_steps=(
            WorkflowPreviewStep(
                step_id="step.explore",
                display_name="Explore",
                description="Read-only exploration.",
            ),
        ),
        required_runner_capabilities=("deterministic-execution",),
        approval_mode=ApprovalMode.NONE,
    )


def _components():
    clock = Sequence(
        *tuple(NOW + timedelta(minutes=index) for index in range(20))
    )
    session_ids = Sequence(
        *tuple(
            f"conversation.session.{index}"
            for index in range(1, 10)
        )
    )
    turn_ids = Sequence(
        *tuple(f"conversation.turn.{index}" for index in range(1, 10))
    )
    service = ConversationApplicationService(
        volatile_repository=InMemoryConversationRepository(),
        durable_repository=InMemoryConversationRepository(),
        clock=clock,
        session_id_generator=session_ids,
        turn_id_generator=turn_ids,
    )
    registry = WorkflowRegistry(
        (
            Adapter(_definition("workflow.zeta")),
            Adapter(_definition("workflow.alpha")),
        )
    )
    security = PMQAWebSecurityContext(
        session_token=SESSION_TOKEN,
        csrf_token=CSRF_TOKEN,
        host="127.0.0.1",
        port=8765,
    )
    app = create_pmqa_web_app(
        conversation_service=service,
        workflow_registry=registry,
        security=security,
    )
    return app, service, registry, security, clock


@pytest.fixture
def web_components():
    return _components()


@pytest.fixture
def client(web_components):
    app, _, _, _, _ = web_components
    with TestClient(
        app,
        base_url=ORIGIN,
        raise_server_exceptions=False,
    ) as selected:
        yield selected


def test_authenticated_health_and_catalog_are_bounded_and_ordered(client) -> None:
    health = client.get("/api/v1/health", headers=READ_HEADERS)
    catalog = client.get("/api/v1/workflows", headers=READ_HEADERS)

    assert health.status_code == 200
    assert health.json() == {
        "schema_version": "1",
        "api_version": "v1",
        "readiness": "ready",
    }
    assert catalog.status_code == 200
    definitions = catalog.json()["workflows"]
    assert [item["workflow_id"] for item in definitions] == [
        "workflow.alpha",
        "workflow.zeta",
    ]
    assert definitions[0]["preview_steps"] == [
        {
            "step_id": "step.explore",
            "display_name": "Explore",
            "description": "Read-only exploration.",
        }
    ]
    serialized = catalog.text
    assert "adapter" not in serialized
    assert SESSION_TOKEN not in serialized
    assert CSRF_TOKEN not in serialized


def test_complete_session_turn_read_close_delete_lifecycle(
    client,
    web_components,
) -> None:
    _, service, _, _, _ = web_components
    created = client.post(
        "/api/v1/sessions",
        headers=MUTATION_HEADERS,
        json={"schema_version": "1"},
    )
    assert created.status_code == 201
    session = created.json()["session"]
    assert session["retention_policy"] == "30_days"
    assert session["revision"] == 1
    session_id = session["session_id"]

    listed = client.get("/api/v1/sessions?limit=1", headers=READ_HEADERS)
    fetched = client.get(
        f"/api/v1/sessions/{session_id}",
        headers=READ_HEADERS,
    )
    assert listed.json()["sessions"] == [session]
    assert fetched.json()["session"] == session

    started = client.post(
        f"/api/v1/sessions/{session_id}/turns",
        headers=MUTATION_HEADERS,
        json={
            "schema_version": "1",
            "session_id": session_id,
            "expected_revision": 1,
            "user_message": "Analyze this workflow.",
        },
    )
    assert started.status_code == 201
    pending = started.json()["turn"]
    current = started.json()["session"]
    assert pending["status"] == "pending"
    assert current["revision"] == 2

    turns = client.get(
        f"/api/v1/sessions/{session_id}/turns?limit=1",
        headers=READ_HEADERS,
    )
    turn = client.get(
        f"/api/v1/sessions/{session_id}/turns/{pending['turn_id']}",
        headers=READ_HEADERS,
    )
    assert turns.json()["turns"] == [pending]
    assert turn.json()["turn"] == pending

    completed_session, _ = service.complete_turn(
        session_id,
        pending["turn_id"],
        expected_revision=2,
        assistant_response="Bounded result.",
    )
    closed = client.post(
        f"/api/v1/sessions/{session_id}/close",
        headers=MUTATION_HEADERS,
        json={
            "schema_version": "1",
            "session_id": session_id,
            "expected_revision": completed_session.revision,
        },
    )
    assert closed.status_code == 200
    assert closed.json()["session"]["status"] == "closed"

    deleted = client.delete(
        f"/api/v1/sessions/{session_id}",
        headers=MUTATION_HEADERS,
    )
    assert deleted.status_code == 200
    assert deleted.json() == {"schema_version": "1", "deleted": True}
    missing = client.get(
        f"/api/v1/sessions/{session_id}",
        headers=READ_HEADERS,
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "resource_not_found"


@pytest.mark.parametrize(
    "policy",
    (
        ConversationRetentionPolicy.SESSION_ONLY,
        ConversationRetentionPolicy.SEVEN_DAYS,
        ConversationRetentionPolicy.THIRTY_DAYS,
        ConversationRetentionPolicy.NINETY_DAYS,
    ),
)
def test_api_accepts_only_existing_retention_choices(client, policy) -> None:
    response = client.post(
        "/api/v1/sessions",
        headers=MUTATION_HEADERS,
        json={
            "schema_version": "1",
            "retention_policy": policy.value,
            "connection_context_id": None,
        },
    )

    assert response.status_code == 201
    assert response.json()["session"]["retention_policy"] == policy.value


def test_revision_and_closed_session_errors_are_fixed_safe(client) -> None:
    created = client.post(
        "/api/v1/sessions",
        headers=MUTATION_HEADERS,
        json={"schema_version": "1"},
    ).json()["session"]
    session_id = created["session_id"]
    stale = client.post(
        f"/api/v1/sessions/{session_id}/close",
        headers=MUTATION_HEADERS,
        json={
            "schema_version": "1",
            "session_id": session_id,
            "expected_revision": 2,
        },
    )

    assert stale.status_code == 409
    assert stale.json() == {
        "schema_version": "1",
        "error": {
            "code": "conversation_failed",
            "message": "PMQA conversation operation failed",
        },
    }
    assert session_id not in stale.text


def test_route_body_mismatch_fails_before_mutation(
    client,
    web_components,
) -> None:
    _, service, _, _, clock = web_components
    created = client.post(
        "/api/v1/sessions",
        headers=MUTATION_HEADERS,
        json={"schema_version": "1"},
    ).json()["session"]
    before_calls = clock.calls

    rejected = client.post(
        f"/api/v1/sessions/{created['session_id']}/turns",
        headers=MUTATION_HEADERS,
        json={
            "schema_version": "1",
            "session_id": "conversation.session.other",
            "expected_revision": 1,
            "user_message": "Must not persist.",
        },
    )

    assert rejected.status_code == 400
    assert clock.calls == before_calls
    assert service.list_turns(created["session_id"]) == ()


def test_no_assistant_completion_or_workflow_execution_endpoint(client) -> None:
    response = client.post(
        "/api/v1/runs",
        headers=MUTATION_HEADERS,
        json={"schema_version": "1"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "resource_not_found"


def test_invalid_route_identifiers_are_fixed_safe(client) -> None:
    response = client.get(
        "/api/v1/sessions/INVALID",
        headers=READ_HEADERS,
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"
    assert "INVALID" not in response.text


def test_unexpected_dependency_failure_is_fixed_and_non_disclosing(
    web_components,
) -> None:
    app, service, _, _, _ = web_components
    service._durable_repository = ExplodingRepository(
        RuntimeError("runtime-secret-marker /tmp/private SQL SELECT")
    )
    with TestClient(
        app,
        base_url=ORIGIN,
        raise_server_exceptions=False,
    ) as selected:
        response = selected.get(
            "/api/v1/sessions/conversation.session.1",
            headers=READ_HEADERS,
        )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_failed"
    assert "runtime-secret-marker" not in response.text
    assert "/tmp/private" not in response.text
    assert "SELECT" not in response.text
    assert "ExplodingRepository" not in response.text


@pytest.mark.parametrize(
    "failure",
    (MemoryError(), KeyboardInterrupt(), SystemExit(), GeneratorExit()),
)
def test_resource_and_control_flow_errors_remain_authoritative(
    web_components,
    failure,
) -> None:
    app, service, _, _, _ = web_components
    service._durable_repository = ExplodingRepository(failure)

    async def invoke():
        messages = [
            {"type": "http.request", "body": b"", "more_body": False}
        ]

        async def receive():
            return messages.pop(0)

        async def send(message):
            _ = message

        await app(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": "/api/v1/sessions/conversation.session.1",
                "raw_path": (
                    b"/api/v1/sessions/conversation.session.1"
                ),
                "query_string": b"",
                "root_path": "",
                "headers": (
                    (b"host", b"127.0.0.1:8765"),
                    (
                        b"authorization",
                        f"Bearer {SESSION_TOKEN}".encode("ascii"),
                    ),
                ),
                "client": ("127.0.0.1", 50000),
                "server": ("127.0.0.1", 8765),
            },
            receive,
            send,
        )

    with pytest.raises(type(failure)) as captured:
        asyncio.run(invoke())

    assert captured.value is failure


def test_factory_requires_exact_preconstructed_dependencies(
    web_components,
) -> None:
    _, service, registry, security, _ = web_components
    for replacement in (object(), None, "runtime-secret-marker"):
        with pytest.raises(PMQAWebConfigurationError):
            create_pmqa_web_app(
                conversation_service=(
                    replacement if replacement is not None else service
                ),
                workflow_registry=(
                    replacement if replacement is None else registry
                ),
                security=security,
            )


def test_web_import_is_side_effect_free_and_generic_imports_remain_lazy(
    tmp_path,
) -> None:
    web_statement = "\n".join(
        [
            "import pathlib, sys",
            "root = pathlib.Path(sys.argv[1])",
            "before = set(root.iterdir())",
            "import pmqa.web",
            "after = set(root.iterdir())",
            "assert before == after",
            "blocked = ('uvicorn', 'playwright', 'products',",
            " 'pmqa.orchestration', 'pmqa.workflow', 'pmqa.runtime',",
            " 'pmqa.supervisor', 'pmqa.reasoning', 'pmqa.trace',",
            " 'pmqa.product_pack', 'langgraph',",
            " 'tkinter', 'PySide6', 'streamlit', 'node', 'react')",
            "for prefix in blocked:",
            " assert not any(name == prefix or "
            "name.startswith(prefix + '.') "
            "for name in sys.modules), prefix",
        ]
    )
    completed = subprocess.run(
        [sys.executable, "-c", web_statement, str(tmp_path)],
        cwd=tmp_path,
        capture_output=True,
        check=False,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert tuple(tmp_path.iterdir()) == ()

    for statement in ("import pmqa", "import pmqa.cli"):
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                f"{statement}; import sys; "
                "assert 'pmqa.web' not in sys.modules; "
                "assert 'fastapi' not in sys.modules",
            ],
            capture_output=True,
            check=False,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr
