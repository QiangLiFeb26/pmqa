"""Deterministic lifecycle and CLI tests for the local Web workbench."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pmqa import cli
from pmqa.web.runtime import (
    PMQA_WEB_FAILURE_CODE,
    PMQAWebRuntimeError,
    run_pmqa_web_workbench,
)


SESSION_TOKEN = "a" * 43
CSRF_TOKEN = "b" * 43


class _FakeSocket:
    def __init__(self, port=43123) -> None:
        self.port = port
        self.close_calls = 0

    def getsockname(self):
        return ("127.0.0.1", self.port)

    def close(self):
        self.close_calls += 1


class _FakeServer:
    def __init__(self, *, failure=None, starts=True) -> None:
        self.started = False
        self.should_exit = False
        self.failure = failure
        self.starts = starts
        self.run_calls = 0

    def run(self, *, sockets):
        self.run_calls += 1
        assert len(sockets) == 1
        if self.failure is not None:
            raise self.failure
        self.started = self.starts
        while not self.should_exit:
            pass


class _Sequence:
    def __init__(self, *values) -> None:
        self.values = list(values)
        self.calls = 0

    def __call__(self):
        value = self.values[self.calls]
        self.calls += 1
        return value


def _run_values(tmp_path, *, server=None, browser=None):
    selected_server = _FakeServer() if server is None else server
    selected_socket = _FakeSocket()
    captures = {}

    def server_factory(**values):
        captures.update(values)
        return selected_server

    def browser_open(url):
        captures["url"] = url
        selected_server.should_exit = True
        return True

    return (
        {
            "_data_directory_resolver": lambda: tmp_path,
            "_token_factory": _Sequence(SESSION_TOKEN, CSRF_TOKEN),
            "_socket_factory": lambda: selected_socket,
            "_server_factory": server_factory,
            "_browser_open": browser_open if browser is None else browser,
        },
        selected_server,
        selected_socket,
        captures,
    )


def test_runtime_composes_loopback_opens_once_and_shuts_down(tmp_path) -> None:
    values, server, bound_socket, captures = _run_values(tmp_path)

    run_pmqa_web_workbench(**values)

    assert captures["host"] == "127.0.0.1"
    assert captures["port"] == 43123
    assert captures["url"] == (
        "http://127.0.0.1:43123/"
        f"#session_token={SESSION_TOKEN}&csrf_token={CSRF_TOKEN}"
    )
    assert "?" not in captures["url"]
    assert server.run_calls == 1
    assert server.should_exit is True
    assert bound_socket.close_calls == 1
    database = tmp_path / "conversations.sqlite3"
    assert database.exists()
    database_bytes = database.read_bytes()
    assert SESSION_TOKEN.encode() not in database_bytes
    assert CSRF_TOKEN.encode() not in database_bytes
    json.dumps({"started": server.started})


@pytest.mark.parametrize(
    "failure_setup",
    ("data", "binding", "readiness", "browser"),
)
def test_expected_runtime_failures_are_fixed_and_never_leak(
    tmp_path,
    failure_setup,
) -> None:
    server = _FakeServer(starts=failure_setup != "readiness")
    values, _, bound_socket, captures = _run_values(tmp_path, server=server)
    browser_calls = []
    if failure_setup == "data":
        values["_data_directory_resolver"] = lambda: Path("relative")
    elif failure_setup == "binding":
        def fail_binding():
            raise OSError("runtime-secret-marker /tmp/private")

        values["_socket_factory"] = fail_binding
    elif failure_setup == "readiness":
        values["_monotonic"] = _Sequence(0.0, 11.0)
        values["_sleep"] = lambda _: None
    else:
        def fail_browser(url):
            browser_calls.append(url)
            return False

        values["_browser_open"] = fail_browser

    with pytest.raises(PMQAWebRuntimeError) as captured:
        run_pmqa_web_workbench(**values)

    assert str(captured.value) == PMQA_WEB_FAILURE_CODE
    assert "runtime-secret-marker" not in str(captured.value)
    assert "/tmp/private" not in str(captured.value)
    assert captured.value.__cause__ is None
    if failure_setup in {"data", "binding", "readiness"}:
        assert "url" not in captures
        assert browser_calls == []
    if failure_setup not in {"data", "binding"}:
        assert bound_socket.close_calls == 1


def test_unexpected_server_failure_propagates_and_browser_never_opens(
    tmp_path,
) -> None:
    failure = RuntimeError("programming defect")
    values, _, bound_socket, captures = _run_values(
        tmp_path,
        server=_FakeServer(failure=failure),
    )

    with pytest.raises(RuntimeError) as captured:
        run_pmqa_web_workbench(**values)

    assert captured.value is failure
    assert "url" not in captures
    assert bound_socket.close_calls == 1


@pytest.mark.parametrize(
    "failure",
    (MemoryError(), KeyboardInterrupt(), SystemExit(), GeneratorExit()),
)
def test_browser_resource_and_control_flow_remain_authoritative(
    tmp_path,
    failure,
) -> None:
    server = _FakeServer()

    def fail_browser(url):
        _ = url
        raise failure

    values, _, bound_socket, _ = _run_values(
        tmp_path,
        server=server,
        browser=fail_browser,
    )

    with pytest.raises(type(failure)) as captured:
        run_pmqa_web_workbench(**values)

    assert captured.value is failure
    assert server.should_exit is True
    assert bound_socket.close_calls == 1


def test_web_cli_returns_only_fixed_expected_failure(capsys) -> None:
    def fail():
        raise PMQAWebRuntimeError()

    assert cli.web(_runtime_runner=fail) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"{PMQA_WEB_FAILURE_CODE}\n"


@pytest.mark.parametrize(
    "failure",
    (OSError("unexpected"), RuntimeError("unexpected")),
)
def test_web_cli_does_not_hide_unexpected_runner_failures(failure) -> None:
    def fail():
        raise failure

    with pytest.raises(type(failure)) as captured:
        cli.web(_runtime_runner=fail)

    assert captured.value is failure


def test_web_parser_exposes_no_runtime_configuration_arguments(
    monkeypatch,
) -> None:
    calls = []
    monkeypatch.setattr(cli, "web", lambda: calls.append(True) or 0)

    assert cli.main(["web"]) == 0
    assert calls == [True]
    with pytest.raises(SystemExit):
        cli.main(["web", "--host", "0.0.0.0"])
