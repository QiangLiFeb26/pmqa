"""Adversarial transport-boundary tests for the local PMQA API."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from pmqa.web import MAX_WEB_REQUEST_BODY_BYTES
from test_web_app import (
    CSRF_TOKEN,
    MUTATION_HEADERS,
    ORIGIN,
    READ_HEADERS,
    SESSION_TOKEN,
    _components,
)


EXPECTED_SECURITY_HEADERS = {
    "cache-control": "no-store",
    "content-security-policy": (
        "default-src 'none'; frame-ancestors 'none'"
    ),
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "x-frame-options": "DENY",
    "cross-origin-resource-policy": "same-origin",
}


@pytest.fixture
def components():
    return _components()


@pytest.fixture
def client(components):
    app, _, _, _, _ = components
    with TestClient(
        app,
        base_url=ORIGIN,
        raise_server_exceptions=False,
    ) as selected:
        yield selected


def _assert_safe_response(response) -> None:
    for name, value in EXPECTED_SECURITY_HEADERS.items():
        assert response.headers[name] == value
    assert "access-control-allow-origin" not in response.headers
    assert "access-control-allow-credentials" not in response.headers
    assert SESSION_TOKEN not in response.text
    assert CSRF_TOKEN not in response.text


@pytest.mark.parametrize(
    "headers",
    (
        {},
        {"Authorization": "Basic runtime-secret-marker"},
        {"Authorization": "Bearer short"},
        {"Authorization": f"Bearer {'z' * 43}"},
    ),
)
def test_missing_malformed_or_wrong_authentication_is_fixed(
    client,
    headers,
) -> None:
    response = client.get("/api/v1/health", headers=headers)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_failed"
    assert "runtime-secret-marker" not in response.text
    _assert_safe_response(response)


@pytest.mark.parametrize(
    ("headers", "code", "status"),
    (
        (
            {**READ_HEADERS, "Host": "localhost:8765"},
            "host_failed",
            400,
        ),
        (
            {**MUTATION_HEADERS, "Origin": "http://evil.invalid"},
            "origin_failed",
            403,
        ),
        (
            {
                **READ_HEADERS,
                "Origin": "http://evil.invalid",
            },
            "origin_failed",
            403,
        ),
        (
            {
                **MUTATION_HEADERS,
                "X-PMQA-CSRF-Token": "z" * 43,
            },
            "csrf_failed",
            403,
        ),
    ),
)
def test_wrong_host_origin_or_csrf_fails_closed(
    client,
    headers,
    code,
    status,
) -> None:
    method = "post" if "X-PMQA-CSRF-Token" in headers else "get"
    path = "/api/v1/sessions" if method == "post" else "/api/v1/health"
    if method == "post":
        response = client.post(
            path,
            headers=headers,
            json={"schema_version": "1"},
        )
    else:
        response = client.get(path, headers=headers)

    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    _assert_safe_response(response)


@pytest.mark.parametrize(
    ("missing", "code"),
    (
        ("Origin", "origin_failed"),
        ("X-PMQA-CSRF-Token", "csrf_failed"),
    ),
)
def test_mutation_requires_origin_and_csrf(client, missing, code) -> None:
    headers = dict(MUTATION_HEADERS)
    del headers[missing]

    response = client.post(
        "/api/v1/sessions",
        headers=headers,
        json={"schema_version": "1"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == code
    _assert_safe_response(response)


@pytest.mark.parametrize(
    "query",
    (
        "authorization=Bearer%20runtime-secret-marker",
        "token=runtime-secret-marker",
        "csrf_token=runtime-secret-marker",
        "x-pmqa-csrf-token=runtime-secret-marker",
        "credential=runtime-secret-marker",
    ),
)
def test_query_carried_credentials_are_rejected_without_echo(
    client,
    query,
) -> None:
    response = client.get(
        f"/api/v1/health?{query}",
        headers=READ_HEADERS,
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"
    assert "runtime-secret-marker" not in response.text
    _assert_safe_response(response)


def test_runtime_tokens_are_rejected_in_route_cookie_and_body(
    client,
    components,
) -> None:
    _, service, _, _, clock = components
    before = clock.calls
    route = client.get(
        f"/api/v1/sessions/{SESSION_TOKEN}",
        headers=READ_HEADERS,
    )
    cookie = client.get(
        "/api/v1/health",
        headers={**READ_HEADERS, "Cookie": f"session={SESSION_TOKEN}"},
    )
    body = client.post(
        "/api/v1/sessions",
        headers=MUTATION_HEADERS,
        json={
            "schema_version": "1",
            "connection_context_id": None,
            "retention_policy": "30_days",
            "unknown": CSRF_TOKEN,
        },
    )

    for response in (route, cookie, body):
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "invalid_request"
        _assert_safe_response(response)
    assert clock.calls == before
    assert service.list_sessions() == ()


def test_preexisting_runtime_token_is_not_exposed_by_read_model(
    client,
    components,
) -> None:
    _, service, _, _, _ = components
    session = service.create_session()
    current, turn = service.start_turn(
        session.session_id,
        expected_revision=1,
        user_message=SESSION_TOKEN,
    )

    response = client.get(
        f"/api/v1/sessions/{session.session_id}/turns/{turn.turn_id}",
        headers=READ_HEADERS,
    )

    assert current.revision == 2
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_failed"
    _assert_safe_response(response)


@pytest.mark.parametrize(
    ("body", "content_type"),
    (
        ('{"schema_version":"1","schema_version":"1"}', "application/json"),
        ('{"schema_version":"1","value":NaN}', "application/json"),
        ('{"schema_version":"2"}', "application/json"),
        (
            '{"schema_version":"1","unknown":"runtime-secret-marker"}',
            "application/json",
        ),
        ('{"schema_version":"1"}', "text/plain"),
        ("not-json", "application/json"),
    ),
)
def test_malformed_or_noncanonical_json_fails_before_mutation(
    client,
    components,
    body,
    content_type,
) -> None:
    _, service, _, _, clock = components
    before = clock.calls

    response = client.post(
        "/api/v1/sessions",
        headers={**MUTATION_HEADERS, "Content-Type": content_type},
        content=body,
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"
    assert clock.calls == before
    assert service.list_sessions() == ()
    assert "runtime-secret-marker" not in response.text
    _assert_safe_response(response)


def test_auth_and_csrf_in_json_body_are_rejected(client, components) -> None:
    _, service, _, _, clock = components
    before = clock.calls
    for field in ("authorization", "csrf_token"):
        response = client.post(
            "/api/v1/sessions",
            headers=MUTATION_HEADERS,
            json={
                "schema_version": "1",
                field: "runtime-secret-marker",
            },
        )
        assert response.status_code == 400
        assert "runtime-secret-marker" not in response.text
        _assert_safe_response(response)

    assert clock.calls == before
    assert service.list_sessions() == ()


def test_security_headers_cover_success_404_and_405(client) -> None:
    responses = (
        client.get("/api/v1/health", headers=READ_HEADERS),
        client.get("/api/v1/missing", headers=READ_HEADERS),
        client.put(
            "/api/v1/health",
            headers=MUTATION_HEADERS,
            json={"schema_version": "1"},
        ),
    )

    assert [response.status_code for response in responses] == [200, 404, 405]
    for response in responses:
        _assert_safe_response(response)


def test_docs_and_openapi_are_not_exposed(client) -> None:
    for path in ("/docs", "/redoc", "/openapi.json"):
        response = client.get(path, headers=READ_HEADERS)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "resource_not_found"
        _assert_safe_response(response)


def _raw_request(
    app,
    *,
    method="GET",
    path="/api/v1/health",
    raw_path=None,
    query=b"",
    headers=(),
    body_chunks=(b"",),
):
    sent = []
    messages = [
        {
            "type": "http.request",
            "body": chunk,
            "more_body": index < len(body_chunks) - 1,
        }
        for index, chunk in enumerate(body_chunks)
    ]

    async def receive():
        if messages:
            return messages.pop(0)
        return {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": (
            path.encode("ascii") if raw_path is None else raw_path
        ),
        "query_string": query,
        "root_path": "",
        "headers": tuple(headers),
        "client": ("127.0.0.1", 50000),
        "server": ("127.0.0.1", 8765),
    }
    asyncio.run(app(scope, receive, send))
    start = next(item for item in sent if item["type"] == "http.response.start")
    body = b"".join(
        item.get("body", b"")
        for item in sent
        if item["type"] == "http.response.body"
    )
    return start["status"], tuple(start["headers"]), json.loads(body)


def _raw_headers(*extra):
    return (
        (b"host", b"127.0.0.1:8765"),
        (b"authorization", f"Bearer {SESSION_TOKEN}".encode("ascii")),
        *extra,
    )


@pytest.mark.parametrize(
    ("headers", "code"),
    (
        (
            (
                (b"host", b"127.0.0.1:8765"),
                (b"host", b"localhost:8765"),
                (
                    b"authorization",
                    f"Bearer {SESSION_TOKEN}".encode("ascii"),
                ),
            ),
            "host_failed",
        ),
        (
            (
                (b"host", b"127.0.0.1:8765"),
                (
                    b"authorization",
                    f"Bearer {SESSION_TOKEN}".encode("ascii"),
                ),
                (
                    b"authorization",
                    f"Bearer {SESSION_TOKEN}".encode("ascii"),
                ),
            ),
            "authentication_failed",
        ),
    ),
)
def test_duplicate_host_or_auth_headers_are_rejected(
    components,
    headers,
    code,
) -> None:
    app, _, _, _, _ = components
    status, _, payload = _raw_request(app, headers=headers)

    assert status in {400, 401}
    assert payload["error"]["code"] == code


@pytest.mark.parametrize(
    "headers",
    (
        (
            (
                b"authorization",
                f"Bearer {SESSION_TOKEN}".encode("ascii"),
            ),
        ),
        (
            (b"host", b"\xff"),
            (
                b"authorization",
                f"Bearer {SESSION_TOKEN}".encode("ascii"),
            ),
        ),
    ),
)
def test_missing_or_malformed_host_is_rejected(components, headers) -> None:
    app, _, _, _, _ = components
    status, _, payload = _raw_request(app, headers=headers)

    assert status == 400
    assert payload["error"]["code"] == "host_failed"


@pytest.mark.parametrize(
    "raw_path",
    (
        b"http://127.0.0.1:8765/api/v1/health",
        b"/api/v1/%68ealth",
        b"/api/v1\\health",
        b"/api/v1/health?token=value",
    ),
)
def test_ambiguous_request_targets_are_rejected(
    components,
    raw_path,
) -> None:
    app, _, _, _, _ = components
    status, _, payload = _raw_request(
        app,
        headers=_raw_headers(),
        raw_path=raw_path,
    )

    assert status == 400
    assert payload["error"]["code"] == "invalid_request"


@pytest.mark.parametrize(
    ("name", "value", "code"),
    (
        (b"origin", ORIGIN.encode("ascii"), "origin_failed"),
        (
            b"x-pmqa-csrf-token",
            CSRF_TOKEN.encode("ascii"),
            "csrf_failed",
        ),
    ),
)
def test_duplicate_origin_or_csrf_headers_are_rejected(
    components,
    name,
    value,
    code,
) -> None:
    app, _, _, _, _ = components
    headers = _raw_headers(
        (b"origin", ORIGIN.encode("ascii")),
        (b"x-pmqa-csrf-token", CSRF_TOKEN.encode("ascii")),
        (name, value),
        (b"content-type", b"application/json"),
    )
    status, _, payload = _raw_request(
        app,
        method="POST",
        path="/api/v1/sessions",
        headers=headers,
        body_chunks=(b'{"schema_version":"1"}',),
    )

    assert status == 403
    assert payload["error"]["code"] == code


@pytest.mark.parametrize(
    "content_length",
    (b"-1", b"1.5", b"runtime-secret-marker", b"1, 1"),
)
def test_malformed_content_length_is_rejected(
    components,
    content_length,
) -> None:
    app, _, _, _, _ = components
    status, _, payload = _raw_request(
        app,
        headers=_raw_headers((b"content-length", content_length)),
    )

    assert status == 400
    assert payload["error"]["code"] == "invalid_request"
    assert "runtime-secret-marker" not in json.dumps(payload)


def test_conflicting_content_lengths_are_rejected(components) -> None:
    app, _, _, _, _ = components
    status, _, payload = _raw_request(
        app,
        headers=_raw_headers(
            (b"content-length", b"1"),
            (b"content-length", b"2"),
        ),
    )

    assert status == 400
    assert payload["error"]["code"] == "invalid_request"


def test_declared_oversized_body_is_rejected_before_receive(components) -> None:
    app, _, _, _, _ = components
    status, _, payload = _raw_request(
        app,
        headers=_raw_headers(
            (
                b"content-length",
                str(MAX_WEB_REQUEST_BODY_BYTES + 1).encode("ascii"),
            )
        ),
    )

    assert status == 413
    assert payload["error"]["code"] == "request_too_large"


def test_streamed_oversized_and_dishonest_lengths_fail_before_mutation(
    components,
) -> None:
    app, service, _, _, clock = components
    common = (
        (b"origin", ORIGIN.encode("ascii")),
        (b"x-pmqa-csrf-token", CSRF_TOKEN.encode("ascii")),
        (b"content-type", b"application/json"),
    )
    before = clock.calls
    status, _, payload = _raw_request(
        app,
        method="POST",
        path="/api/v1/sessions",
        headers=_raw_headers(*common),
        body_chunks=(
            b"x" * MAX_WEB_REQUEST_BODY_BYTES,
            b"x",
        ),
    )
    assert status == 413
    assert payload["error"]["code"] == "request_too_large"

    status, _, payload = _raw_request(
        app,
        method="POST",
        path="/api/v1/sessions",
        headers=_raw_headers(
            *common,
            (b"content-length", b"1"),
        ),
        body_chunks=(b'{"schema_version":"1"}',),
    )
    assert status == 400
    assert payload["error"]["code"] == "invalid_request"

    status, _, payload = _raw_request(
        app,
        method="POST",
        path="/api/v1/sessions",
        headers=_raw_headers(
            *common,
            (b"content-length", b"1"),
        ),
        body_chunks=(
            b"x" * MAX_WEB_REQUEST_BODY_BYTES,
            b"x",
        ),
    )
    assert status == 413
    assert payload["error"]["code"] == "request_too_large"
    assert clock.calls == before
    assert service.list_sessions() == ()


def test_unknown_route_cannot_bypass_streamed_body_limit(components) -> None:
    app, _, _, _, _ = components
    status, _, payload = _raw_request(
        app,
        method="POST",
        path="/api/v1/missing",
        headers=_raw_headers(
            (b"origin", ORIGIN.encode("ascii")),
            (b"x-pmqa-csrf-token", CSRF_TOKEN.encode("ascii")),
            (b"content-type", b"application/json"),
        ),
        body_chunks=(
            b"x" * MAX_WEB_REQUEST_BODY_BYTES,
            b"x",
        ),
    )

    assert status == 413
    assert payload["error"]["code"] == "request_too_large"
