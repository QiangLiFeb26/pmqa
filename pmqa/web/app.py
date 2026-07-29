"""Side-effect-free FastAPI application factory for the local PMQA API."""

from __future__ import annotations

from typing import Any, Optional, Tuple, Type
from urllib.parse import parse_qsl

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from pmqa.application import WorkflowRegistry
from pmqa.conversation import (
    DEFAULT_CONVERSATION_LIST_LIMIT,
    MAX_CONVERSATION_LIST_LIMIT,
    ConversationApplicationError,
    ConversationApplicationErrorCode,
    ConversationApplicationService,
)
from pmqa.run import validate_run_identifier
from pmqa.security.boundary_policy import (
    RUN_PAYLOAD_PROHIBITED_KEYS,
    is_prohibited_key,
    normalize_boundary_key,
)
from pmqa.web.contracts import (
    CloseSessionRequest,
    CreateSessionRequest,
    CreateTurnRequest,
    DeleteSessionResponse,
    HealthResponse,
    MAX_WEB_REQUEST_BODY_BYTES,
    SessionListResponse,
    SessionResponse,
    TurnListResponse,
    TurnMutationResponse,
    TurnResponse,
    WEB_API_SCHEMA_VERSION,
    WebAPIContractValidationError,
    WorkflowCatalogResponse,
    parse_canonical_json_object,
)
from pmqa.web.errors import (
    WebAPIError,
    WebAPIFailureCode,
    web_error_message,
)
from pmqa.web.security import PMQAWebSecurityContext
from pmqa.web.static import STATIC_ROUTES, load_packaged_web_assets


_RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS = (
    MemoryError,
    KeyboardInterrupt,
    SystemExit,
    GeneratorExit,
)
_STATE_CHANGING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_CSRF_QUERY_KEYS = frozenset(
    {"csrf", "csrf_token", "x_pmqa_csrf_token"}
)
_MAX_QUERY_BYTES = 8 * 1024
_MAX_TARGET_BYTES = 8 * 1024
_SECURITY_HEADERS = (
    (b"cache-control", b"no-store"),
    (
        b"content-security-policy",
        b"default-src 'none'; frame-ancestors 'none'",
    ),
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
    (b"x-frame-options", b"DENY"),
    (b"cross-origin-resource-policy", b"same-origin"),
)
_STATIC_SECURITY_HEADERS = (
    (b"cache-control", b"no-store"),
    (
        b"content-security-policy",
        (
            b"default-src 'none'; script-src 'self'; style-src 'self'; "
            b"connect-src 'self'; base-uri 'none'; form-action 'none'; "
            b"frame-ancestors 'none'"
        ),
    ),
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
    (b"x-frame-options", b"DENY"),
    (b"cross-origin-resource-policy", b"same-origin"),
)
_SECURITY_HEADER_NAMES = frozenset(name for name, _ in _SECURITY_HEADERS)


class PMQAWebConfigurationError(ValueError):
    """Report one fixed invalid application-factory configuration."""

    def __init__(self) -> None:
        super().__init__("invalid PMQA Web application configuration")


class _RequestBoundaryFailure(Exception):
    def __init__(self, code: WebAPIFailureCode, status_code: int) -> None:
        self.code = code
        self.status_code = status_code


class _PMQASecurityMiddleware:
    """Validate the transport boundary before FastAPI endpoint processing."""

    def __init__(self, app, security: PMQAWebSecurityContext) -> None:
        self.app = app
        self.security = security

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False
        static_request = scope.get("path") in STATIC_ROUTES

        async def secure_send(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                headers = [
                    (name.lower(), value)
                    for name, value in message.get("headers", ())
                    if name.lower() not in _SECURITY_HEADER_NAMES
                    and name.lower() != b"access-control-allow-origin"
                    and name.lower()
                    != b"access-control-allow-credentials"
                ]
                headers.extend(
                    _STATIC_SECURITY_HEADERS
                    if static_request
                    else _SECURITY_HEADERS
                )
                message = dict(message)
                message["headers"] = headers
            await send(message)

        try:
            declared_length = self._validate_target_and_body(scope)
            received = 0
            body_buffer = bytearray()
            while True:
                message = await receive()
                if (
                    type(message) is not dict
                    or set(message) - {"type", "body", "more_body"}
                    or type(message.get("type")) is not str
                    or message.get("type") != "http.request"
                ):
                    raise _RequestBoundaryFailure(
                        WebAPIFailureCode.INVALID_REQUEST,
                        400,
                    )
                body = message.get("body", b"")
                more_body = message.get("more_body", False)
                if type(body) is not bytes or type(more_body) is not bool:
                    raise _RequestBoundaryFailure(
                        WebAPIFailureCode.INVALID_REQUEST,
                        400,
                    )
                if not body and more_body:
                    raise _RequestBoundaryFailure(
                        WebAPIFailureCode.INVALID_REQUEST,
                        400,
                    )
                received += len(body)
                if received > MAX_WEB_REQUEST_BODY_BYTES:
                    raise _RequestBoundaryFailure(
                        WebAPIFailureCode.REQUEST_TOO_LARGE,
                        413,
                    )
                body_buffer.extend(body)
                if not more_body:
                    break
            if declared_length is not None and received != declared_length:
                raise _RequestBoundaryFailure(
                    WebAPIFailureCode.INVALID_REQUEST,
                    400,
                )
            if static_request:
                self._validate_static_security(scope, received)
            else:
                self._validate_security(scope)
            replayed = False
            canonical_message = {
                "type": "http.request",
                "body": bytes(body_buffer),
                "more_body": False,
            }

            async def replay_receive():
                nonlocal replayed
                if not replayed:
                    replayed = True
                    return canonical_message
                return {"type": "http.disconnect"}

            await self.app(scope, replay_receive, secure_send)
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except _RequestBoundaryFailure as error:
            if response_started:
                raise
            await _send_failure(
                scope,
                receive,
                secure_send,
                error.code,
                error.status_code,
            )
        except Exception:
            if response_started:
                raise
            await _send_failure(
                scope,
                receive,
                secure_send,
                WebAPIFailureCode.INTERNAL_FAILED,
                500,
            )

    def _validate_static_security(self, scope, received: int) -> None:
        headers = tuple(scope.get("headers", ()))
        host_values = _header_values(headers, b"host")
        if (
            len(host_values) != 1
            or _ascii_header(host_values[0]) != self.security.host_authority
        ):
            raise _RequestBoundaryFailure(
                WebAPIFailureCode.HOST_FAILED,
                400,
            )
        if (
            scope.get("method") not in {"GET", "HEAD"}
            or scope.get("query_string", b"") != b""
            or received != 0
            or _header_values(headers, b"cookie")
        ):
            raise _RequestBoundaryFailure(
                WebAPIFailureCode.INVALID_REQUEST,
                400,
            )

    def _validate_target_and_body(self, scope) -> Optional[int]:
        headers = tuple(scope.get("headers", ()))
        raw_path = scope.get("raw_path", b"")
        path = scope.get("path", "")
        if (
            type(raw_path) is not bytes
            or not raw_path.startswith(b"/")
            or len(raw_path) > _MAX_TARGET_BYTES
            or b"://" in raw_path
            or b"%" in raw_path
            or b"\\" in raw_path
            or b"?" in raw_path
            or b"\x00" in raw_path
            or type(path) is not str
            or not path.startswith("/")
            or len(path) > _MAX_TARGET_BYTES
        ):
            raise _RequestBoundaryFailure(
                WebAPIFailureCode.INVALID_REQUEST,
                400,
            )

        try:
            encoded_path = path.encode("ascii", errors="strict")
            path_text = raw_path.decode("ascii", errors="strict")
        except (UnicodeDecodeError, UnicodeEncodeError):
            raise _RequestBoundaryFailure(
                WebAPIFailureCode.INVALID_REQUEST,
                400,
            ) from None
        if encoded_path != raw_path:
            raise _RequestBoundaryFailure(
                WebAPIFailureCode.INVALID_REQUEST,
                400,
            )
        declared_length = _declared_content_length(headers)
        _validate_query(scope.get("query_string", b""), self.security)
        if any(
            self.security.contains_runtime_token(segment)
            for segment in path_text.split("/")
        ):
            raise _RequestBoundaryFailure(
                WebAPIFailureCode.INVALID_REQUEST,
                400,
            )
        return declared_length

    def _validate_security(self, scope) -> None:
        headers = tuple(scope.get("headers", ()))
        host_values = _header_values(headers, b"host")
        if (
            len(host_values) != 1
            or _ascii_header(host_values[0]) != self.security.host_authority
        ):
            raise _RequestBoundaryFailure(
                WebAPIFailureCode.HOST_FAILED,
                400,
            )

        auth_values = _header_values(headers, b"authorization")
        if len(auth_values) != 1:
            raise _RequestBoundaryFailure(
                WebAPIFailureCode.AUTHENTICATION_FAILED,
                401,
            )
        authorization = _ascii_header(auth_values[0])
        if (
            authorization is None
            or not authorization.startswith("Bearer ")
            or authorization.count(" ") != 1
            or not self.security.authenticates(authorization[7:])
        ):
            raise _RequestBoundaryFailure(
                WebAPIFailureCode.AUTHENTICATION_FAILED,
                401,
            )

        origin_values = _header_values(headers, b"origin")
        if len(origin_values) > 1 or (
            origin_values
            and _ascii_header(origin_values[0]) != self.security.origin
        ):
            raise _RequestBoundaryFailure(
                WebAPIFailureCode.ORIGIN_FAILED,
                403,
            )

        method = scope.get("method", "")
        state_changing = method in _STATE_CHANGING_METHODS
        if state_changing and len(origin_values) != 1:
            raise _RequestBoundaryFailure(
                WebAPIFailureCode.ORIGIN_FAILED,
                403,
            )

        csrf_values = _header_values(headers, b"x-pmqa-csrf-token")
        if len(csrf_values) > 1 or (
            csrf_values
            and not self.security.validates_csrf(
                _ascii_header(csrf_values[0])
            )
        ):
            raise _RequestBoundaryFailure(
                WebAPIFailureCode.CSRF_FAILED,
                403,
            )
        if state_changing and len(csrf_values) != 1:
            raise _RequestBoundaryFailure(
                WebAPIFailureCode.CSRF_FAILED,
                403,
            )

        content_types = _header_values(headers, b"content-type")
        if (
            len(content_types) > 1
            or _header_values(headers, b"cookie")
        ):
            raise _RequestBoundaryFailure(
                WebAPIFailureCode.INVALID_REQUEST,
                400,
            )


def create_pmqa_web_app(
    *,
    conversation_service: ConversationApplicationService,
    workflow_registry: WorkflowRegistry,
    security: PMQAWebSecurityContext,
) -> FastAPI:
    """Create one inert, explicitly composed local PMQA ASGI application."""

    if (
        type(conversation_service) is not ConversationApplicationService
        or type(workflow_registry) is not WorkflowRegistry
        or type(security) is not PMQAWebSecurityContext
    ):
        raise PMQAWebConfigurationError() from None

    packaged_assets = load_packaged_web_assets()
    app = FastAPI(
        title="PMQA Local API",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(_PMQASecurityMiddleware, security=security)

    async def static_asset(request: Request):
        content, media_type = packaged_assets[request.url.path]
        return Response(
            content=b"" if request.method == "HEAD" else content,
            media_type=None,
            headers={
                "Content-Type": media_type,
                "X-PMQA-Asset": "packaged",
            },
        )

    for static_route in tuple(sorted(STATIC_ROUTES)):
        app.add_api_route(
            static_route,
            static_asset,
            methods=["GET", "HEAD"],
            include_in_schema=False,
        )

    @app.exception_handler(WebAPIError)
    async def handle_web_error(request: Request, error: WebAPIError):
        _ = request
        return _failure_response(error.code, error.status_code)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        error: RequestValidationError,
    ):
        _ = request, error
        return _failure_response(WebAPIFailureCode.INVALID_REQUEST, 400)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(
        request: Request,
        error: StarletteHTTPException,
    ):
        _ = request
        status_code = 405 if error.status_code == 405 else 404
        return _failure_response(
            WebAPIFailureCode.RESOURCE_NOT_FOUND,
            status_code,
        )

    @app.get("/api/v1/health")
    async def health(request: Request):
        await _require_empty_read(request)
        return _contract_response(
            HealthResponse(
                schema_version=WEB_API_SCHEMA_VERSION,
                api_version="v1",
                readiness="ready",
            ),
            security=security,
        )

    @app.get("/api/v1/workflows")
    async def workflows(request: Request):
        await _require_empty_read(request)
        definitions = workflow_registry.definitions
        ordered = tuple(
            sorted(
                definitions,
                key=lambda item: (
                    item.workflow_id,
                    item.workflow_version,
                ),
            )
        )
        return _contract_response(
            WorkflowCatalogResponse(
                schema_version=WEB_API_SCHEMA_VERSION,
                workflows=ordered,
            ),
            security=security,
        )

    @app.post("/api/v1/sessions")
    async def create_session(request: Request):
        contract = await _request_contract(
            request,
            CreateSessionRequest,
            security,
        )
        try:
            session = conversation_service.create_session(
                contract.retention_policy,
                connection_context_id=contract.connection_context_id,
            )
        except ConversationApplicationError as error:
            raise _mapped_conversation_error(error) from None
        return _contract_response(
            SessionResponse(
                schema_version=WEB_API_SCHEMA_VERSION,
                session=session,
            ),
            status_code=201,
            security=security,
        )

    @app.get("/api/v1/sessions")
    async def list_sessions(request: Request):
        await _require_empty_body(request)
        limit = _query_limit(request)
        try:
            sessions = conversation_service.list_sessions(limit)
        except ConversationApplicationError as error:
            raise _mapped_conversation_error(error) from None
        return _contract_response(
            SessionListResponse(
                schema_version=WEB_API_SCHEMA_VERSION,
                sessions=sessions,
            ),
            security=security,
        )

    @app.get("/api/v1/sessions/{session_id}")
    async def get_session(session_id: str, request: Request):
        await _require_empty_read(request)
        canonical_id = _route_identifier(session_id)
        try:
            session = conversation_service.get_session(canonical_id)
        except ConversationApplicationError as error:
            raise _mapped_conversation_error(error) from None
        return _contract_response(
            SessionResponse(
                schema_version=WEB_API_SCHEMA_VERSION,
                session=session,
            ),
            security=security,
        )

    @app.post("/api/v1/sessions/{session_id}/close")
    async def close_session(session_id: str, request: Request):
        canonical_id = _route_identifier(session_id)
        contract = await _request_contract(
            request,
            CloseSessionRequest,
            security,
        )
        if contract.session_id != canonical_id:
            raise WebAPIError(WebAPIFailureCode.INVALID_REQUEST, 400)
        try:
            session = conversation_service.close_session(
                canonical_id,
                expected_revision=contract.expected_revision,
            )
        except ConversationApplicationError as error:
            raise _mapped_conversation_error(error) from None
        return _contract_response(
            SessionResponse(
                schema_version=WEB_API_SCHEMA_VERSION,
                session=session,
            ),
            security=security,
        )

    @app.delete("/api/v1/sessions/{session_id}")
    async def delete_session(session_id: str, request: Request):
        await _require_empty_read(request)
        canonical_id = _route_identifier(session_id)
        try:
            conversation_service.delete_session(canonical_id)
        except ConversationApplicationError as error:
            raise _mapped_conversation_error(error) from None
        return _contract_response(
            DeleteSessionResponse(
                schema_version=WEB_API_SCHEMA_VERSION,
                deleted=True,
            ),
            security=security,
        )

    @app.post("/api/v1/sessions/{session_id}/turns")
    async def create_turn(session_id: str, request: Request):
        canonical_id = _route_identifier(session_id)
        contract = await _request_contract(
            request,
            CreateTurnRequest,
            security,
        )
        if contract.session_id != canonical_id:
            raise WebAPIError(WebAPIFailureCode.INVALID_REQUEST, 400)
        try:
            session, turn = conversation_service.start_turn(
                canonical_id,
                expected_revision=contract.expected_revision,
                user_message=contract.user_message,
            )
        except ConversationApplicationError as error:
            raise _mapped_conversation_error(error) from None
        return _contract_response(
            TurnMutationResponse(
                schema_version=WEB_API_SCHEMA_VERSION,
                session=session,
                turn=turn,
            ),
            status_code=201,
            security=security,
        )

    @app.get("/api/v1/sessions/{session_id}/turns")
    async def list_turns(session_id: str, request: Request):
        await _require_empty_body(request)
        canonical_id = _route_identifier(session_id)
        limit = _query_limit(request)
        try:
            turns = conversation_service.list_turns(canonical_id, limit)
        except ConversationApplicationError as error:
            raise _mapped_conversation_error(error) from None
        return _contract_response(
            TurnListResponse(
                schema_version=WEB_API_SCHEMA_VERSION,
                turns=turns,
            ),
            security=security,
        )

    @app.get("/api/v1/sessions/{session_id}/turns/{turn_id}")
    async def get_turn(session_id: str, turn_id: str, request: Request):
        await _require_empty_read(request)
        canonical_session_id = _route_identifier(session_id)
        canonical_turn_id = _route_identifier(turn_id)
        try:
            turn = conversation_service.get_turn(
                canonical_session_id,
                canonical_turn_id,
            )
        except ConversationApplicationError as error:
            raise _mapped_conversation_error(error) from None
        return _contract_response(
            TurnResponse(
                schema_version=WEB_API_SCHEMA_VERSION,
                turn=turn,
            ),
            security=security,
        )

    return app


async def _request_contract(
    request: Request,
    contract_type: Type[Any],
    security: PMQAWebSecurityContext,
):
    if request.url.query:
        raise WebAPIError(WebAPIFailureCode.INVALID_REQUEST, 400)
    content_type = request.headers.get("content-type")
    if not _is_json_content_type(content_type):
        raise WebAPIError(WebAPIFailureCode.INVALID_REQUEST, 400)
    try:
        payload = parse_canonical_json_object(await request.body())
        if _contains_runtime_token(payload, security):
            raise WebAPIContractValidationError()
        return contract_type.from_dict(payload)
    except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
        raise
    except (WebAPIContractValidationError, ValueError, TypeError):
        raise WebAPIError(WebAPIFailureCode.INVALID_REQUEST, 400) from None


async def _require_empty_read(request: Request) -> None:
    if request.url.query:
        raise WebAPIError(WebAPIFailureCode.INVALID_REQUEST, 400)
    await _require_empty_body(request)


async def _require_empty_body(request: Request) -> None:
    if await request.body():
        raise WebAPIError(WebAPIFailureCode.INVALID_REQUEST, 400)


def _query_limit(request: Request) -> int:
    items = tuple(request.query_params.multi_items())
    if not items:
        return DEFAULT_CONVERSATION_LIST_LIMIT
    if len(items) != 1 or items[0][0] != "limit":
        raise WebAPIError(WebAPIFailureCode.INVALID_REQUEST, 400)
    value = items[0][1]
    if (
        type(value) is not str
        or not value.isascii()
        or not value.isdigit()
        or (len(value) > 1 and value.startswith("0"))
    ):
        raise WebAPIError(WebAPIFailureCode.INVALID_REQUEST, 400)
    try:
        limit = int(value)
    except ValueError:
        raise WebAPIError(WebAPIFailureCode.INVALID_REQUEST, 400) from None
    if limit < 1 or limit > MAX_CONVERSATION_LIST_LIMIT:
        raise WebAPIError(WebAPIFailureCode.INVALID_REQUEST, 400)
    return limit


def _route_identifier(value: Any) -> str:
    try:
        return validate_run_identifier(value)
    except Exception:
        raise WebAPIError(WebAPIFailureCode.INVALID_REQUEST, 400) from None


def _mapped_conversation_error(
    error: ConversationApplicationError,
) -> WebAPIError:
    if error.code in {
        ConversationApplicationErrorCode.SESSION_NOT_FOUND,
        ConversationApplicationErrorCode.TURN_NOT_FOUND,
    }:
        return WebAPIError(WebAPIFailureCode.RESOURCE_NOT_FOUND, 404)
    if error.code in {
        ConversationApplicationErrorCode.IDENTIFIER_CONFLICT,
        ConversationApplicationErrorCode.REVISION_CONFLICT,
        ConversationApplicationErrorCode.STATE_CONFLICT,
        ConversationApplicationErrorCode.SESSION_CLOSED,
        ConversationApplicationErrorCode.TURN_LIMIT_REACHED,
        ConversationApplicationErrorCode.SENSITIVE_TEXT_REJECTED,
    }:
        return WebAPIError(WebAPIFailureCode.CONVERSATION_FAILED, 409)
    if error.code is ConversationApplicationErrorCode.INVALID_REQUEST:
        return WebAPIError(WebAPIFailureCode.INVALID_REQUEST, 400)
    return WebAPIError(WebAPIFailureCode.INTERNAL_FAILED, 500)


def _contract_response(
    contract,
    status_code: int = 200,
    *,
    security: PMQAWebSecurityContext,
) -> JSONResponse:
    payload = contract.to_dict()
    if _contains_runtime_token(payload, security):
        raise WebAPIError(WebAPIFailureCode.INTERNAL_FAILED, 500)
    return JSONResponse(payload, status_code=status_code)


def _failure_response(
    code: WebAPIFailureCode,
    status_code: int,
) -> JSONResponse:
    return JSONResponse(
        {
            "schema_version": WEB_API_SCHEMA_VERSION,
            "error": {
                "code": code.value,
                "message": web_error_message(code),
            },
        },
        status_code=status_code,
    )


async def _send_failure(
    scope,
    receive,
    send,
    code: WebAPIFailureCode,
    status_code: int,
) -> None:
    await _failure_response(code, status_code)(scope, receive, send)


def _header_values(
    headers: Tuple[Tuple[bytes, bytes], ...],
    name: bytes,
) -> Tuple[bytes, ...]:
    return tuple(
        value
        for header_name, value in headers
        if header_name.lower() == name
    )


def _ascii_header(value: bytes) -> Optional[str]:
    try:
        result = value.decode("ascii", errors="strict")
    except UnicodeDecodeError:
        return None
    if not result or any(ord(character) < 32 for character in result):
        return None
    return result


def _declared_content_length(
    headers: Tuple[Tuple[bytes, bytes], ...],
) -> Optional[int]:
    values = _header_values(headers, b"content-length")
    if not values:
        return None
    decoded = tuple(_ascii_header(value) for value in values)
    if (
        any(value is None or not value.isdigit() for value in decoded)
        or len(set(decoded)) != 1
    ):
        raise _RequestBoundaryFailure(
            WebAPIFailureCode.INVALID_REQUEST,
            400,
        )
    if len(decoded[0]) > len(str(MAX_WEB_REQUEST_BODY_BYTES)):
        raise _RequestBoundaryFailure(
            WebAPIFailureCode.REQUEST_TOO_LARGE,
            413,
        )
    length = int(decoded[0])
    if length > MAX_WEB_REQUEST_BODY_BYTES:
        raise _RequestBoundaryFailure(
            WebAPIFailureCode.REQUEST_TOO_LARGE,
            413,
        )
    return length


def _validate_query(
    raw_query: bytes,
    security: PMQAWebSecurityContext,
) -> None:
    if type(raw_query) is not bytes or len(raw_query) > _MAX_QUERY_BYTES:
        raise _RequestBoundaryFailure(
            WebAPIFailureCode.INVALID_REQUEST,
            400,
        )
    try:
        text = raw_query.decode("ascii", errors="strict")
        for index, character in enumerate(text):
            if character == "%" and (
                index + 2 >= len(text)
                or any(
                    item not in "0123456789abcdefABCDEF"
                    for item in text[index + 1:index + 3]
                )
            ):
                raise ValueError("invalid percent escape")
        pairs = parse_qsl(
            text,
            keep_blank_values=True,
            strict_parsing=True,
            encoding="utf-8",
            errors="strict",
            max_num_fields=8,
        ) if text else ()
    except (UnicodeDecodeError, ValueError):
        raise _RequestBoundaryFailure(
            WebAPIFailureCode.INVALID_REQUEST,
            400,
        ) from None
    for key, value in pairs:
        normalized = normalize_boundary_key(key)
        if (
            is_prohibited_key(key, RUN_PAYLOAD_PROHIBITED_KEYS)
            or normalized in _CSRF_QUERY_KEYS
            or security.contains_runtime_token(key)
            or security.contains_runtime_token(value)
        ):
            raise _RequestBoundaryFailure(
                WebAPIFailureCode.INVALID_REQUEST,
                400,
            )


def _contains_runtime_token(
    value: Any,
    security: PMQAWebSecurityContext,
) -> bool:
    stack = [value]
    while stack:
        current = stack.pop()
        if type(current) is str:
            if security.contains_runtime_token(current):
                return True
        elif type(current) is dict:
            stack.extend(current.keys())
            stack.extend(current.values())
        elif type(current) in {list, tuple}:
            stack.extend(current)
    return False


def _is_json_content_type(value: Optional[str]) -> bool:
    if type(value) is not str:
        return False
    parts = tuple(part.strip().casefold() for part in value.split(";"))
    return parts == ("application/json",) or parts == (
        "application/json",
        "charset=utf-8",
    )


__all__ = [
    "PMQAWebConfigurationError",
    "create_pmqa_web_app",
]
