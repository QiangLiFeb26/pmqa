"""Explicit loopback runtime composition for the local PMQA workbench."""

from __future__ import annotations

import secrets
import socket
import threading
import time
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urlencode

from platformdirs import user_data_path

from pmqa.application import WorkflowRegistry
from pmqa.conversation import (
    ConversationApplicationError,
    ConversationRepositoryError,
    ConversationApplicationService,
    InMemoryConversationRepository,
    SQLiteConversationRepository,
)
from pmqa.web.app import PMQAWebConfigurationError, create_pmqa_web_app
from pmqa.web.security import (
    PMQAWebSecurityConfigurationError,
    PMQAWebSecurityContext,
)
from pmqa.web.static import PMQAWebStaticAssetError


PMQA_WEB_FAILURE_CODE = "pmqa_web_failed"
_LOOPBACK_HOST = "127.0.0.1"
_READINESS_TIMEOUT_SECONDS = 10.0
_READINESS_POLL_SECONDS = 0.01
_SERVER_JOIN_TIMEOUT_SECONDS = 5.0
_EXPECTED_COMPOSITION_ERRORS = (
    ConversationApplicationError,
    ConversationRepositoryError,
    PMQAWebConfigurationError,
    PMQAWebSecurityConfigurationError,
    PMQAWebStaticAssetError,
)
_RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS = (
    MemoryError,
    KeyboardInterrupt,
    SystemExit,
    GeneratorExit,
)


class PMQAWebRuntimeError(RuntimeError):
    """Report one fixed expected local-workbench startup failure."""

    def __init__(self) -> None:
        super().__init__(PMQA_WEB_FAILURE_CODE)


def run_pmqa_web_workbench(
    *,
    _data_directory_resolver: Optional[Callable[[], Path]] = None,
    _token_factory: Optional[Callable[[], str]] = None,
    _socket_factory: Optional[Callable[[], Any]] = None,
    _server_factory: Optional[Callable[..., Any]] = None,
    _browser_open: Optional[Callable[[str], Any]] = None,
    _monotonic: Optional[Callable[[], float]] = None,
    _sleep: Optional[Callable[[float], None]] = None,
    _thread_factory: Optional[Callable[..., threading.Thread]] = None,
) -> None:
    """Compose, run, and cleanly stop one invocation-local workbench."""

    resolve_data_directory = (
        _default_data_directory
        if _data_directory_resolver is None
        else _data_directory_resolver
    )
    token_factory = (
        _default_runtime_token if _token_factory is None else _token_factory
    )
    socket_factory = (
        _bind_loopback_socket if _socket_factory is None else _socket_factory
    )
    server_factory = (
        _create_uvicorn_server if _server_factory is None else _server_factory
    )
    browser_open = webbrowser.open if _browser_open is None else _browser_open
    monotonic = time.monotonic if _monotonic is None else _monotonic
    sleep = time.sleep if _sleep is None else _sleep
    thread_factory = (
        threading.Thread if _thread_factory is None else _thread_factory
    )
    collaborators = (
        resolve_data_directory,
        token_factory,
        socket_factory,
        server_factory,
        browser_open,
        monotonic,
        sleep,
        thread_factory,
    )
    if any(not callable(item) for item in collaborators):
        raise PMQAWebRuntimeError() from None

    bound_socket = None
    server = None
    server_thread = None
    server_failures = []
    try:
        data_directory = _prepare_data_directory(resolve_data_directory)
        volatile_repository = InMemoryConversationRepository()
        durable_repository = SQLiteConversationRepository(
            str((data_directory / "conversations.sqlite3").resolve())
        )
        service = ConversationApplicationService(
            volatile_repository=volatile_repository,
            durable_repository=durable_repository,
            clock=lambda: datetime.now(timezone.utc),
        )
        registry = WorkflowRegistry(())
        session_token = token_factory()
        csrf_token = token_factory()
        bound_socket = socket_factory()
        port = _bound_loopback_port(bound_socket)
        security = PMQAWebSecurityContext(
            session_token=session_token,
            csrf_token=csrf_token,
            host=_LOOPBACK_HOST,
            port=port,
        )
        app = create_pmqa_web_app(
            conversation_service=service,
            workflow_registry=registry,
            security=security,
        )
        server = server_factory(app=app, host=_LOOPBACK_HOST, port=port)

        def run_server() -> None:
            try:
                server.run(sockets=[bound_socket])
            except BaseException as error:
                server_failures.append(error)

        server_thread = thread_factory(
            target=run_server,
            name="pmqa-web-server",
            daemon=False,
        )
        server_thread.start()
        _wait_until_ready(
            server=server,
            server_thread=server_thread,
            failures=server_failures,
            monotonic=monotonic,
            sleep=sleep,
        )
        fragment = urlencode(
            (
                ("session_token", session_token),
                ("csrf_token", csrf_token),
            )
        )
        opened = browser_open(
            f"http://{_LOOPBACK_HOST}:{port}/#{fragment}"
        )
        if opened is not True:
            raise PMQAWebRuntimeError()
        server_thread.join()
        if server_failures:
            _raise_server_failure(server_failures[0])
    except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
        raise
    except PMQAWebRuntimeError:
        raise
    except _EXPECTED_COMPOSITION_ERRORS:
        raise PMQAWebRuntimeError() from None
    except OSError:
        raise PMQAWebRuntimeError() from None
    finally:
        if server is not None:
            server.should_exit = True
        if (
            server_thread is not None
            and server_thread.is_alive()
            and server_thread is not threading.current_thread()
        ):
            server_thread.join(_SERVER_JOIN_TIMEOUT_SECONDS)
        if bound_socket is not None:
            try:
                bound_socket.close()
            except OSError:
                pass


def _default_data_directory() -> Path:
    return Path(user_data_path("pmqa", "PMQA", ensure_exists=False))


def _prepare_data_directory(resolver: Callable[[], Path]) -> Path:
    try:
        selected = resolver()
        if not isinstance(selected, Path) or not selected.is_absolute():
            raise PMQAWebRuntimeError()
        selected.mkdir(mode=0o700, parents=True, exist_ok=True)
        return selected
    except PMQAWebRuntimeError:
        raise
    except OSError:
        raise PMQAWebRuntimeError() from None


def _default_runtime_token() -> str:
    return secrets.token_urlsafe(32)


def _bind_loopback_socket():
    selected = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        selected.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        selected.bind((_LOOPBACK_HOST, 0))
        selected.listen(128)
        return selected
    except OSError:
        selected.close()
        raise


def _bound_loopback_port(bound_socket: Any) -> int:
    try:
        address = bound_socket.getsockname()
    except OSError:
        raise PMQAWebRuntimeError() from None
    if (
        type(address) is not tuple
        or len(address) < 2
        or address[0] != _LOOPBACK_HOST
        or type(address[1]) is not int
        or not 1 <= address[1] <= 65535
    ):
        raise PMQAWebRuntimeError() from None
    return address[1]


def _create_uvicorn_server(*, app, host: str, port: int):
    import uvicorn

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        access_log=False,
        log_config=None,
        log_level="critical",
    )
    return uvicorn.Server(config)


def _wait_until_ready(
    *,
    server: Any,
    server_thread: Any,
    failures,
    monotonic: Callable[[], float],
    sleep: Callable[[float], None],
) -> None:
    started_at = monotonic()
    while not bool(getattr(server, "started", False)):
        if failures:
            _raise_server_failure(failures[0])
        if not server_thread.is_alive():
            raise PMQAWebRuntimeError()
        if monotonic() - started_at >= _READINESS_TIMEOUT_SECONDS:
            raise PMQAWebRuntimeError()
        sleep(_READINESS_POLL_SECONDS)


def _raise_server_failure(error: BaseException) -> None:
    if isinstance(error, _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS):
        raise error
    if isinstance(error, OSError):
        raise PMQAWebRuntimeError() from None
    raise error


__all__ = [
    "PMQA_WEB_FAILURE_CODE",
    "PMQAWebRuntimeError",
    "run_pmqa_web_workbench",
]
