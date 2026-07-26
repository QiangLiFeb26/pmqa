# Coder Report

Owner: Coder

Task: PMQA Task 5D.1B — Secure Loopback Web/API Boundary

Task ID: `PMQA-5D.1B`

Attempt: `1`

Status: Ready for Independent Reviewer

## Branch and Git Correlation

Branch:

`agent/task-5c-1-canonical-run-contract`

Exact Git-derived Coder starting HEAD:

`d9fc04c4c02f3ed13b6f91f05ec6fb3912f49029`

That commit was the latest pushed branch commit containing this Task 5D.1B
Attempt 1 publication in `agent-handoff/current-task.md`. Before
implementation, local HEAD and
`origin/agent/task-5c-1-canonical-run-contract` both equaled that commit and
the worktree was clean. The handoff recorded approved Task 5D.1A Reviewer
HEAD `55ea5067e87d502951cd102b40ede17a2d23796f`. No Task 5D.1A or earlier
commit was amended, rebased, or replaced.

## Implementation Commits

`c2ebcad3cbf6d0456ea55deceaebb06e4a37e69b`

Commit message:

`add secure loopback Web API boundary`

`16d34501c1e55afc50cc4006153256e7319d1383`

Commit message:

`enforce Web body bounds before authentication`

The second focused commit moves complete streamed-body bounding ahead of
Host/authentication validation so the required target/body → Host → auth →
Origin/CSRF ordering is explicit. It changes no endpoint, contract, error, or
valid response.

This report is committed separately after the implementation commit. The
Independent Reviewer derives the report commit from Git; this report does not
claim its own future commit SHA.

## Changed Files

Production:

- `pmqa/web/__init__.py`;
- `pmqa/web/app.py`;
- `pmqa/web/contracts.py`;
- `pmqa/web/errors.py`;
- `pmqa/web/security.py`;
- `pyproject.toml`.

Tests:

- `tests/test_web_app.py`;
- `tests/test_web_contracts.py`;
- `tests/test_web_security.py`;
- `tests/test_packaging.py`.

Documentation:

- `README.md`;
- `docs/Roadmap.md`;
- `docs/architecture.md`;
- `docs/architecture/conversational-workflow-platform.md`.

Report-only handoff:

- `agent-handoff/coder-report.md`.

No conversation contract/repository/service, Task 4/5/5A/5C production code,
CLI, Product Pack, workflow runtime, provider, reasoning, usage, frontend,
TypeScript, Node, Uvicorn, or product implementation changed.

## Application Factory and Dependency Direction

`create_pmqa_web_app(...) -> FastAPI` requires exact, already-created:

- `ConversationApplicationService`;
- `WorkflowRegistry`;
- `PMQAWebSecurityContext`.

Invalid factory dependencies fail with one fixed configuration message. The
factory creates no repository, file, environment lookup, socket, process,
browser, credential, provider, runner, or product dependency. It disables
Swagger UI, ReDoc, and OpenAPI exposure and installs no CORS middleware.

The Web endpoints call only public `ConversationApplicationService` and
`WorkflowRegistry` APIs. They do not access repository implementations,
LangGraph, `WorkflowState`, Product Packs, Playwright, provider SDKs, runners,
or product modules. Import tests prove `pmqa.web` performs no filesystem side
effect and does not load Uvicorn, Playwright, products, LangGraph,
orchestration/runtime/supervisor, reasoning, traces, or Product Packs.
Generic `import pmqa` and `import pmqa.cli` remain Web/FastAPI-lazy.

## API v1 Inventory

The only application routes are:

```text
GET    /api/v1/health
GET    /api/v1/workflows
POST   /api/v1/sessions
GET    /api/v1/sessions
GET    /api/v1/sessions/{session_id}
POST   /api/v1/sessions/{session_id}/close
DELETE /api/v1/sessions/{session_id}
POST   /api/v1/sessions/{session_id}/turns
GET    /api/v1/sessions/{session_id}/turns
GET    /api/v1/sessions/{session_id}/turns/{turn_id}
```

Health returns only schema/API identity and `ready`. The workflow catalog
sorts fresh canonical `WorkflowDefinition` snapshots by workflow ID/version
and exposes no adapter or runtime object. Session creation supports the four
existing retention values and the approved 30-day default. Session/turn lists
reuse the existing 1–256 limit. Route-correlated close and pending-turn
requests carry schema version, exact session ID, and expected revision.

Responses contain fresh canonical session/turn/workflow snapshots. No
assistant complete/fail, purge, SQL/storage, command, runner/workflow
execution, provider configuration, credential, arbitrary metadata, or
external-operation endpoint exists.

## Contracts and Canonical JSON

API contracts are strict, frozen Pydantic v2 records with exact fields,
forbidden extras, hidden inputs, and no coercion. Schema version is exactly
`1`; identifiers reuse `validate_run_identifier`; revision and list values
reuse existing conversation bounds; user messages reuse the existing message
size/control-character bound. Response validators reconstruct fresh
canonical domain snapshots rather than retaining dependency objects.

The narrow request parser:

- requires a nonempty UTF-8 JSON object for JSON mutations;
- rejects duplicate keys and non-finite numbers;
- rejects invalid UTF-8, surrogate/control ambiguity, wrong roots, excessive
  depth/items/string size, unknown fields, coercion, and schema drift;
- accepts only `application/json` with optional exact UTF-8 charset; and
- never echoes invalid input or parser details.

JSON is parsed only after transport authentication and body bounds and before
any application mutation.

## Runtime Security Context

`PMQAWebSecurityContext` accepts only distinct exact built-in session and CSRF
strings of 43–128 unpadded base64url characters, exact loopback host
`127.0.0.1` or `::1`, and an exact integer port from 1–65535. It derives the
single HTTP Origin and Host authority, including bracketed IPv6.

Tokens are private slotted state, redacted from `repr`, not exported through a
property, and explicitly unavailable to JSON or pickle serialization. Caller
containers are not retained. Authentication and CSRF comparisons use
`hmac.compare_digest`.

Every request requires:

- exactly one configured Host authority;
- exactly one `Authorization: Bearer <session-token>`;
- an exact configured Origin whenever Origin is supplied; and
- for POST/PUT/PATCH/DELETE, exactly one configured Origin and exactly one
  matching `X-PMQA-CSRF-Token`.

Wrong, missing, malformed, non-ASCII, or duplicate security headers fail
closed. Cookies are rejected. Credential-like query keys reuse the shared
`RUN_PAYLOAD_PROHIBITED_KEYS` normalization policy; only protocol-specific
CSRF aliases are added locally. The middleware also rejects the exact runtime
tokens if they appear in route segments or query values. Parsed request and
response trees are compared only against the two known runtime tokens, so an
actual token cannot cross a body/read-model boundary while ordinary strings
are not globally scanned or rejected.

## Request Target, Body Limit, and Side-Effect Ordering

The middleware rejects missing/duplicate/wrong Host, absolute-form or
percent-encoded/backslash/query-bearing raw paths, non-ASCII path ambiguity,
malformed query encoding, and credential-like query keys before routing.

Content-Length must be canonical; conflicting values are rejected. A declared
body over 64 KiB fails before receive. The middleware then buffers and counts
the complete ASGI request stream up to 64 KiB before FastAPI routing and
replays only that bounded stream. This catches omitted or dishonest
Content-Length, multi-chunk overflow, and oversized bodies even for unknown
routes that would not read a body.

For every mutation the order is bounded target/body, Host, authentication,
Origin/CSRF, canonical contract reconstruction, route/body correlation, then
one intended service call. Tests prove wrong security, malformed JSON,
runtime-token placement, oversized/dishonest streams, invalid IDs, and
route/body mismatch leave service clocks and real in-memory repositories
unchanged. No retry, fallback, repair, or cross-repository movement was added.

## Safe Responses and Error Mapping

The stable API error vocabulary is:

- `invalid_request`;
- `authentication_failed`;
- `host_failed`;
- `origin_failed`;
- `csrf_failed`;
- `request_too_large`;
- `resource_not_found`;
- `conversation_failed`;
- `internal_failed`.

Conversation not-found errors map to safe 404, validation to safe 400,
revision/lifecycle/sensitive-ingress conflicts to safe 409, and dependency or
configuration failures to safe 500. Unexpected endpoint/dependency exceptions
are contained by fixed `internal_failed` responses without marker, identifier,
message, header, token, path, SQL, runtime repr, cause, or exception text.
`MemoryError`, `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit` remain
authoritative and propagate from direct ASGI invocation.

Successes and all error paths receive:

- `Cache-Control: no-store`;
- `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`;
- `X-Content-Type-Options: nosniff`;
- `Referrer-Policy: no-referrer`;
- `X-Frame-Options: DENY`;
- `Cross-Origin-Resource-Policy: same-origin`.

The middleware removes wildcard/credential CORS response headers. No body,
Authorization/CSRF header, exception, or credential logging was added.

## Dependency and Packaging Changes

Runtime dependency:

- `fastapi>=0.115,<1`.

This bounded range supports Python 3.9+, Pydantic v2, and the declared project
Python versions while deferring Uvicorn to Task 5D.1C.

Development dependency:

- `httpx>=0.27,<1`.

This is the direct bounded dependency used by FastAPI/Starlette's in-process
ASGI `TestClient`; tests bind no socket and access no network.

The real-wheel regression now requires all five `pmqa/web` modules and the
FastAPI metadata dependency, imports `pmqa.web` from an extracted wheel in an
unrelated directory, and retains existing runtime-output/cache/credential
exclusions.

## Validation Results

All final implementation commands used the cumulative source state ending at
`16d34501c1e55afc50cc4006153256e7319d1383`:

- Web/conversation focused group: `258 passed`.
- Task 5C Application/Run/Usage regressions: `467 passed`.
- Security/import/real-wheel group: `29 passed`.
- Task 4 runtime/reducer/Supervisor/LangGraph regressions: `98 passed`.
- Full default suite: `2104 passed, 5 skipped`.
- Generated SauceDemo Playwright regressions: `2 passed`.
- Isolated `compileall` for `pmqa` and `products`: passed with bytecode
  outside the repository.
- Tracked Markdown relative-link validation: all `19` files passed.
- Editable install and `pip check`: passed; no broken requirements.
- `git diff --check`: passed.
- Pre-report implementation worktree: clean and implementation commit pushed.

The only observed warnings were the existing local LibreSSL warning and
LangGraph pending-deprecation warning. The five default-suite skips are
existing environment-gated tests. New Web tests are offline/in-process and use
no live socket, browser, network, Node, provider, ADO, external Product Pack,
or paid model.

## Remaining Risks and Scope Confirmation

Task 5D.1B intentionally accepts pre-generated runtime tokens and a selected
loopback authority. Cryptographic token generation, port selection, Uvicorn
startup/readiness, browser delivery, static frontend assets, logout, and
distribution runtime startup belong to Task 5D.1C. This API-only checkpoint
does not claim those composition/runtime guarantees.

Task 5D.1C, Task 5D.2+, Task 5B, Task 6, and Task 7 were not started. No
server/socket/browser lifecycle, frontend, React/TypeScript/Vite/Node, `pmqa
web`, SSE/WebSocket, provider/reasoning call, workflow execution, ADO/Copilot,
capability, approval, operation, receipt, artifact repository, usage UI, or
external write was added. No PR was created and nothing was merged.

## Recommended Review Depth

**Deep**

Reason: this checkpoint creates the HTTP trust root that will receive
browser-originated content and protect local credentials and conversation
mutation in Task 5D.1C.

## Suggested Reviewer Focus

- Attempt Host/Auth/Origin/CSRF duplication, ambiguity, token relocation, raw
  target encoding, cookie/query/body smuggling, and response-token exposure.
- Challenge declared, undeclared, conflicting, dishonest, streamed, and
  unknown-route body sizes plus duplicate/non-finite/deep JSON.
- Verify rejected requests reach no conversation mutation and valid endpoints
  call only the intended public service/registry API once.
- Inspect fixed-safe error mapping/security headers across success, 404/405,
  application conflicts, malformed dependencies, and resource/control flow.
- Confirm import/wheel dependency direction and the absence of Uvicorn,
  frontend, CLI, provider, workflow execution, Product Pack, and later Task
  5D scope.

## Human Summary

PMQA-5D.1B Attempt 1 已完成，Git 派生起点为 `d9fc04c4c02f3ed13b6f91f05ec6fb3912f49029`。
实现提交为 `c2ebcad3cbf6d0456ea55deceaebb06e4a37e69b` 与 `16d34501c1e55afc50cc4006153256e7319d1383`。
新增 side-effect-free FastAPI factory、严格 `/api/v1` contracts、Bearer/Host/Origin/CSRF、64 KiB streamed-body 和 canonical JSON 边界。
所有响应使用固定安全错误与 no-store/security headers，实际 runtime tokens 不得进入 URL、cookie、body、domain read model 或响应。
验证结果：focused 258、Task 5C 467、security/import/wheel 29、Task 4 98、全量 2104 passed / 5 skipped、Playwright 2 passed。
Action Needed From Human: 请将下方 Handoff Note 传递给 Independent Reviewer。
Handoff Note: 请读取 agent-handoff/README.md 与 agent-handoff/current-task.md，从 Git 派生最新 coder-report commit，并按独立审查顺序完成 review。
