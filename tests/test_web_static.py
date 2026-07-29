"""Packaged static-route and browser-bootstrap trust-boundary tests."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from test_web_app import ORIGIN, READ_HEADERS, _components


STATIC_CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; "
    "connect-src 'self'; base-uri 'none'; form-action 'none'; "
    "frame-ancestors 'none'"
)


def test_exact_packaged_assets_are_public_read_only_and_fixed_type() -> None:
    app, _, _, _, _ = _components()
    with TestClient(app, base_url=ORIGIN) as client:
        expected = {
            "/": "text/html; charset=utf-8",
            "/assets/app.js": "text/javascript; charset=utf-8",
            "/assets/app.css": "text/css; charset=utf-8",
        }
        for route, content_type in expected.items():
            response = client.get(route)
            head = client.head(route)
            assert response.status_code == 200
            assert response.headers["content-type"] == content_type
            assert response.headers["x-pmqa-asset"] == "packaged"
            assert response.headers["content-security-policy"] == STATIC_CSP
            assert response.headers["cache-control"] == "no-store"
            assert response.content
            assert head.status_code == 200
            assert head.content == b""


def test_static_routes_reject_query_body_cookie_and_non_read_methods() -> None:
    app, service, _, _, clock = _components()
    before = clock.calls
    with TestClient(
        app,
        base_url=ORIGIN,
        raise_server_exceptions=False,
    ) as client:
        responses = (
            client.get("/?safe=value"),
            client.request("GET", "/", content=b"x"),
            client.get("/", headers={"Cookie": "session=value"}),
            client.post("/"),
            client.put("/assets/app.js"),
        )

    assert all(response.status_code == 400 for response in responses)
    assert all(
        response.json()["error"]["code"] == "invalid_request"
        for response in responses
    )
    assert clock.calls == before
    assert service.list_sessions() == ()


def test_static_allowlist_has_no_wildcard_traversal_or_source_maps() -> None:
    app, _, _, _, _ = _components()
    with TestClient(app, base_url=ORIGIN) as client:
        for route in (
            "/assets/missing.js",
            "/assets/app.js.map",
            "/assets/../app.js",
            "/src/main.tsx",
            "/package.json",
        ):
            response = client.get(route, headers=READ_HEADERS)
            assert response.status_code == 404
        assert client.get("/api/v1/health").status_code == 401
        assert (
            client.get("/api/v1/health", headers=READ_HEADERS).status_code
            == 200
        )


def test_built_assets_contain_no_runtime_tokens_or_unsafe_ui_features() -> None:
    app, _, _, _, _ = _components()
    with TestClient(app, base_url=ORIGIN) as client:
        html = client.get("/").text
        script = client.get("/assets/app.js").text
        css = client.get("/assets/app.css").text
    combined = "\n".join((html, script, css))
    source_root = (
        Path(__file__).resolve().parents[1]
        / "frontend"
        / "workbench"
        / "src"
    )
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in source_root.glob("*.tsx")
    )

    assert ("a" * 43) not in combined
    assert ("b" * 43) not in combined
    assert "dangerouslySetInnerHTML" not in source
    assert "eval(" not in source
    assert "localStorage" not in combined
    assert "sessionStorage" not in combined
    assert "serviceWorker" not in combined
    assert "sourceMappingURL" not in combined
    assert "<script type=\"module\"" in html
    assert "https://" not in html
    assert "http://" not in html
