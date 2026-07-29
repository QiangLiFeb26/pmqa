"""Opt-in real Uvicorn/Chromium smoke for the packaged local workbench."""

import os
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import sync_playwright

from pmqa.web import runtime as runtime_module


SESSION_TOKEN = "a" * 43
CSRF_TOKEN = "b" * 43


@pytest.mark.skipif(
    os.environ.get("PMQA_LIVE_WEB_SMOKE") != "1",
    reason="set PMQA_LIVE_WEB_SMOKE=1 for real loopback/Chromium smoke",
)
def test_real_loopback_browser_bootstrap_removes_tokens_before_api(
    tmp_path,
) -> None:
    server_holder = {}
    observed_requests = []
    console_messages = []
    browser_origin = []
    tokens = iter((SESSION_TOKEN, CSRF_TOKEN))

    def server_factory(**values):
        server = runtime_module._create_uvicorn_server(**values)
        server_holder["server"] = server
        return server

    def browser_open(url):
        parsed = urlsplit(url)
        browser_origin.append(f"{parsed.scheme}://{parsed.netloc}")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.on(
                "request",
                lambda request: observed_requests.append(
                    (request.url, request.method, request.all_headers())
                ),
            )
            page.on(
                "console",
                lambda message: console_messages.append(message.text),
            )
            page.goto(url)
            page.get_by_role("heading", name="PMQA Workbench").wait_for()
            page.wait_for_function(
                "() => document.querySelector('[role=status]')"
                "?.textContent !== 'Status: loading'"
            )
            page.get_by_role("button", name="Create session").click()
            page.get_by_role("heading", name="Selected session").wait_for()
            assert page.evaluate("window.location.hash") == ""
            assert page.evaluate("window.localStorage.length") == 0
            assert page.evaluate("window.sessionStorage.length") == 0
            browser.close()
        server_holder["server"].should_exit = True
        return True

    runtime_module.run_pmqa_web_workbench(
        _data_directory_resolver=lambda: tmp_path,
        _token_factory=lambda: next(tokens),
        _server_factory=server_factory,
        _browser_open=browser_open,
    )

    assert observed_requests
    assert all(
        SESSION_TOKEN not in url and CSRF_TOKEN not in url
        for url, _, _ in observed_requests
    )
    api_requests = [
        headers
        for url, _, headers in observed_requests
        if "/api/v1/" in url
    ]
    assert api_requests
    assert all(
        headers.get("authorization") == f"Bearer {SESSION_TOKEN}"
        for headers in api_requests
    )
    mutation_headers = [
        headers
        for url, method, headers in observed_requests
        if "/api/v1/" in url and method == "POST"
    ]
    assert len(mutation_headers) == 1
    assert mutation_headers[0].get("origin") == browser_origin[0]
    assert (
        mutation_headers[0].get("x-pmqa-csrf-token") == CSRF_TOKEN
    )
    assert all(
        SESSION_TOKEN not in message and CSRF_TOKEN not in message
        for message in console_messages
    )
