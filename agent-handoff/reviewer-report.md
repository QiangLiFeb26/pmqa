# Independent Reviewer Report

Owner: Independent Reviewer

Status: Executed for PMQA Task 5D.1B, Attempt 1

## Task Correlation

Task: PMQA Task 5D.1B — Secure Loopback Web/API Boundary

Task ID: `PMQA-5D.1B`

Attempt: `1`

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed Starting HEAD: `d9fc04c4c02f3ed13b6f91f05ec6fb3912f49029`

Reviewed Implementation Commit(s):
`c2ebcad3cbf6d0456ea55deceaebb06e4a37e69b` ("add secure loopback Web API
boundary"), `16d34501c1e55afc50cc4006153256e7319d1383` ("enforce Web body
bounds before authentication")

Derived Coder Report Commit: `fbc2810df2475a95b630b6e5f9c6541ec568ae46`
("report Task 5D.1B secure Web API boundary")

Correlation Verification:

- derived with `git log -1 --format=%H -- agent-handoff/coder-report.md` ->
  `fbc2810df2475a95b630b6e5f9c6541ec568ae46`;
- `git merge-base --is-ancestor d9fc04c4c02f3ed13b6f91f05ec6fb3912f49029 HEAD`
  succeeds; `d9fc04c...` is an ancestor of `c2ebcad...`, `c2ebcad...` is an
  ancestor of `16d3450...`, and `16d3450...` is an ancestor of `fbc2810...`
  (linear sequence `d9fc04c -> c2ebcad -> 16d3450 -> fbc2810` on this
  branch);
- the approved Task 5D.1A Reviewer HEAD named by `current-task.md`,
  `55ea5067e87d502951cd102b40ede17a2d23796f` (this Reviewer's own prior
  Task 5D.1A Attempt 2 report commit), is an ancestor of the recorded
  starting HEAD;
- the correlation header of `coder-report.md` at the derived commit names
  Task ID `PMQA-5D.1B`, Attempt `1`, branch
  `agent/task-5c-1-canonical-run-contract`, and starting HEAD
  `d9fc04c4c02f3ed13b6f91f05ec6fb3912f49029`, matching `current-task.md`;
- `git diff --stat 16d3450..fbc2810` touches only
  `agent-handoff/coder-report.md`, so the derived commit is the report's
  latest authorized change with no later unauthorized replacement.

This Reviewer report does not contain or predict its own commit SHA. The
Architect derives the Reviewer report commit from Git and records it in
`architect-review.md`.

## Independent Review Method

Inspection order completed:

1. `current-task.md` and acceptance criteria (the full authentication/Host/
   Origin/CSRF/body-bound/security-header/error-vocabulary requirement
   list);
2. named baseline-to-implementation diff (`d9fc04c..16d3450`) — full line-
   by-line read of all four new production modules
   (`pmqa/web/security.py`, `pmqa/web/contracts.py`, `pmqa/web/errors.py`,
   `pmqa/web/app.py`, the last at 794 lines), `pmqa/web/__init__.py`, the
   `pyproject.toml`/`tests/test_packaging.py` diffs, and a structural pass
   over all three new test files;
3. independently selected validation (see Test Evidence), including eight
   ad hoc adversarial HTTP requests sent through a real
   `fastapi.testclient.TestClient` instance wired to the real application
   factory, independent of the Coder's own test files;
4. full `coder-report.md` (read only after steps 1-3).

Active-task `architect-review.md` read before publication: No

Prior closed review or architecture material consulted, with reason: this
Reviewer's own Task 5D.0 review approved the architecture this checkpoint
implements (FastAPI, versioned `/api/v1`, loopback-only, invocation-local
auth), and the two Task 5D.1A reviews established the
`ConversationApplicationService`/`ConversationRepository` boundary this
checkpoint calls; that context was used only to confirm this
implementation correctly composes those already-reviewed layers rather
than re-deriving their internals, not as a substitute for reading this
attempt's actual code.

## Review Depth

Actual Review Depth: Deep

Review Depth Reason: this is the first network-facing HTTP trust boundary
in the codebase and the security root the future browser workbench
(5D.1C) will depend on entirely — an authentication, CSRF, Origin/Host, or
body-bound gap here would be a directly exploitable local vulnerability,
not a data-integrity bug caught by unit tests alone. I read every
production line by hand (not a sample), traced the full ASGI middleware
control flow for ordering and header-injection correctness, and
independently issued adversarial HTTP requests against a live
`TestClient` instance built from scratch, separate from the Coder's own
test fixtures. This matches the Coder's advisory recommendation but was
independently selected.

## Overall Assessment

The implementation is an exceptionally careful, correct realization of
the required security boundary. `pmqa/web/security.py` adds
`PMQAWebSecurityContext`; `pmqa/web/contracts.py` adds the strict `/api/v1`
request/response contracts plus a narrow bounded JSON parser;
`pmqa/web/errors.py` adds a fixed 9-code failure vocabulary matching the
task's list exactly; `pmqa/web/app.py` adds `create_pmqa_web_app(...)` and
a hand-written ASGI security middleware in front of FastAPI's routing.

**Runtime security context.** `PMQAWebSecurityContext.__init__` validates
token shape via a single strict regex (`^[A-Za-z0-9_-]{43,128}$`), rejects
equal session/CSRF tokens using `hmac.compare_digest` (timing-safe even at
construction time), and constrains `host` to an exact 2-member allowlist
(`{"127.0.0.1", "::1"}`) rather than a blocklist — which structurally
makes wildcard/path/credential/query/fragment/non-ASCII host values
impossible rather than merely filtered. IPv6 is correctly bracketed
(`[::1]:port`) when deriving the Host authority and Origin string, a
detail that is easy to get wrong and would otherwise produce an invalid
URL. All comparisons (`authenticates`, `validates_csrf`,
`contains_runtime_token`) use `hmac.compare_digest` and reject non-`str`
candidates before comparing. `__repr__` is fixed and redacted,
`__reduce_ex__` raises to block pickling, and there is no property or
method that returns a raw token.

**Middleware ordering.** I traced `_PMQASecurityMiddleware.__call__` end
to end: it calls `_validate_target_and_body` (raw-path/query validation
plus declared-`Content-Length` validation) first, then streams and counts
the actual ASGI body bytes — aborting with `REQUEST_TOO_LARGE` the moment
`received > MAX_WEB_REQUEST_BODY_BYTES` regardless of what
`Content-Length` claimed, and separately rejecting a declared/received
mismatch — *before* calling `_validate_security` (Host, then
Authorization/Bearer, then Origin, then CSRF, then Content-Type/Cookie, in
that exact order). This matches the task's required six-step ordering
exactly, and I confirmed via `git diff c2ebcad..16d3450` that the second
implementation commit is a genuinely minimal (9-line) refactor that only
splits one method into two and moves the `_validate_security` call point
— it does not alter any check's logic, matching the Coder's own
description of that commit. Because the middleware buffers and replays
the exact validated ASGI messages to the wrapped FastAPI app via a
`replay_receive` closure, downstream endpoint code calling
`await request.body()` reads only the already-bounded stream, so there is
no second unbounded read path.

**Header injection.** The middleware's `secure_send` wrapper
unconditionally strips any pre-existing security header or
`Access-Control-Allow-Origin`/`Access-Control-Allow-Credentials` header
from every outgoing `http.response.start` message and appends the fixed
six required headers — and because `secure_send` is the literal `send`
callable passed through the entire ASGI chain (including into FastAPI's
own registered exception handlers for `WebAPIError`,
`RequestValidationError`, and `StarletteHTTPException`, and into the
middleware's own `_send_failure` early-rejection path), the six headers
apply uniformly to success responses, 4xx/5xx application errors, and
early transport-layer rejections alike. I independently confirmed this
against a live success response and a live 401 error response (see Test
Evidence) rather than only trusting the code trace.

**Token non-disclosure.** `_request_contract` and `_contract_response`
both call `_contains_runtime_token`, which recursively walks parsed
JSON/dict/list/tuple structures (keys and values) checking each string
against the *actual* configured session/CSRF token values via
`hmac.compare_digest` — not a generic secret-pattern scan, so it cannot
produce false positives against ordinary conversation text, but it does
catch the real token literally appearing in a request or response body.
`_validate_query` applies the same check to every query key/value in
addition to reusing the existing `RUN_PAYLOAD_PROHIBITED_KEYS`/
`is_prohibited_key` policy (no second drifting prohibited-key
vocabulary — only a small local CSRF-alias set was added, matching the
task's explicit allowance). `_validate_target_and_body` separately checks
every decoded path segment against `contains_runtime_token`.

**Endpoint scope.** I confirmed by reading `app.py`'s route table that
exactly the ten required endpoints exist and no others — in particular,
there is no endpoint that completes or fails an assistant turn, no purge/
SQL/storage endpoint, and no workflow-execution endpoint, matching "Do not
expose browser endpoints that complete or fail assistant turns" and the
rest of the out-of-scope list.

All validation commands listed in `current-task.md`, run independently
rather than accepted from the Coder report, pass with no failures, errors,
or unexplained skips.

## Findings

None. This is a large (~2,824 line), security-critical checkpoint reviewed
at full depth with no shortcuts on the highest-risk file
(`pmqa/web/app.py`, read in its entirety), and independently verified
against a live running instance rather than only the Coder's own tests. No
gap was found in authentication, Host/Origin/CSRF enforcement, body-size
bounding, canonical JSON handling, security headers, token non-disclosure,
or endpoint scope.

## Acceptance Criteria Coverage

| Acceptance criterion | Evidence | Result |
| --- | --- | --- |
| Task 5D.1A remains approved and unchanged | `git diff --stat d9fc04c..16d3450` shows zero changes to `pmqa/conversation/*`; all 5D.1A regression tests independently rerun and pass | Met |
| One explicit side-effect-free FastAPI app factory exists | `create_pmqa_web_app(...)` validates exact dependency types, creates no repository/file/socket/process; independently confirmed `import pmqa.web` performs no such side effect via the packaging/import tests | Met |
| The API is versioned under `/api/v1` | All ten routes registered under that prefix, confirmed by reading `app.py`'s route table | Met |
| Only the bounded offline conversation/catalog endpoints exist | Route table read in full; no assistant-completion, purge, SQL, or workflow-execution endpoint present | Met |
| All endpoints require invocation-local authentication | `_validate_security` unconditionally requires exactly one valid `Authorization: Bearer` header for every request; independently reproduced a request with no auth header returning 401 | Met |
| Host, Origin, and CSRF policies fail closed as specified | Traced the exact check ordering and mandatory-vs-optional-per-method logic; independently reproduced wrong Host (400), missing Origin on a mutation (403), missing CSRF on a mutation (403), and wrong Origin (403) | Met |
| Tokens never enter URLs, payloads, domain state, errors, logs, or responses | `contains_runtime_token`/`_contains_runtime_token` traced through path, query, request-body, and response-body checks; independently reproduced a real token placed in a query string being rejected with the token absent from the response body | Met |
| Request bodies and collections are bounded before application mutation | Streamed-byte-counting loop traced and independently reproduced (declared-oversized `Content-Length` -> 413 before receive; real oversized streamed body -> 413 even with a correct declared length) | Met |
| API contracts are strict and canonical | `pmqa/web/contracts.py` read in full: `extra=forbid`, `frozen=True`, `strict=True`, exact tuple-only collections, narrow bounded JSON parser rejecting duplicate keys/non-finite numbers/excess depth | Met |
| Conversation errors and unexpected dependency failures are fixed-safe | `_mapped_conversation_error` traced against every `ConversationApplicationErrorCode`; generic `except Exception` in the middleware maps anything else to fixed `INTERNAL_FAILED`, 500 | Met |
| Valid conversation lifecycle behavior remains canonical | Independently reproduced a full session-creation request returning the expected default 30-day retention and canonical field set | Met |
| Rejected requests cause zero application/repository mutation | Traced that `_validate_security` and body-bounding both run entirely before any `conversation_service.*` call; the Coder's tests use real in-memory repositories to prove this, independently rerun | Met |
| Security headers apply to success and error responses | Independently reproduced identical header sets on a 200 health response and a 401 auth-failure response | Met |
| No permissive CORS, docs UI, arbitrary command, or credential surface exists | Independently reproduced `/docs`, `/redoc`, `/openapi.json` all returning 404, and confirmed no `access-control-allow-origin` header on any response | Met |
| Imports remain isolated and the real wheel packages the Web modules | `tests/test_packaging.py` diff and its independent rerun confirm wheel inclusion and import isolation | Met |
| All focused and full regressions pass | 258 focused Web/conversation + 467 Task 5C + 29 security/import/wheel + 98 Task 4 + 2104/5-skip full suite + 2 Playwright, all independently run, all pass | Met |
| Only allowed files change | `git diff --stat` from starting HEAD to the derived report commit touches exactly the allowed `pmqa/web/*`, test, `pyproject.toml`, and documentation paths plus `agent-handoff/coder-report.md` | Met |

## Test Evidence

### Coder Evidence Reviewed

The Coder report claims: 258 passed for the Web/conversation focused group;
467 passed for Task 5C Application/Run/Usage regressions; 29 passed for the
security/import/real-wheel group; 98 passed for the Task 4 orchestration
set; 2104 passed, 5 skipped for the full default suite; 2 passed for
`products/demo/generated_tests`; Markdown-link validation and an editable
install/`pip check` passed; `compileall` and `git diff --check` clean;
clean worktree. This claimed evidence was read only after independent
execution below and matches it exactly, except the Reviewer did not
independently reproduce the editable-install/`pip check` claim (not part
of the task's listed Validation Commands).

### Independently Run

All commands below were executed by the Reviewer directly, before reading
the Coder's claimed results, from the repository root on the reviewed
branch:

- `.venv/bin/python -m pytest tests/test_web_contracts.py tests/test_web_security.py tests/test_web_app.py tests/test_conversation_service.py tests/test_conversation_repository.py tests/test_conversation_contracts.py -q`
  -> `258 passed`
- `.venv/bin/python -m pytest tests/test_application_contracts.py tests/test_application_service.py tests/test_run_contracts.py tests/test_usage_contracts.py tests/test_usage_repository.py tests/test_usage_summary.py -q`
  -> `467 passed`
- `.venv/bin/python -m pytest tests/test_boundary_policy.py tests/test_scrubber.py tests/test_packaging.py tests/test_conversation_imports.py tests/test_run_imports.py -q`
  -> `29 passed`
- `.venv/bin/python -m pytest tests/test_workflow_runtime.py tests/test_workflow_reducer.py tests/test_supervisor_policy.py tests/test_langgraph_workflow.py -q`
  -> `98 passed, 1 warning` (pre-existing `LangChainPendingDeprecationWarning`,
  unrelated to this change)
- `.venv/bin/python -m pytest -q` (full default suite) -> `2104 passed, 5 skipped, 1 warning`
- `.venv/bin/python -m pytest products/demo/generated_tests -q` -> `2 passed`
- `PYTHONPYCACHEPREFIX=<isolated scratch directory> .venv/bin/python -m compileall -q pmqa products`
  -> exit code `0`, no output
- `git diff --check` -> exit code `0`, no output
- `git status --short` -> empty (clean worktree)

In addition, and independent of the Coder's own test files, I built a real
`ConversationApplicationService` (two `InMemoryConversationRepository`
instances), a real `WorkflowRegistry(())`, and a real
`PMQAWebSecurityContext`, wired them through `create_pmqa_web_app(...)`,
and drove the result with `fastapi.testclient.TestClient` in ad hoc
scripts, independently confirming:

- a `GET /api/v1/health` request with no `Authorization` header returns
  `401` with the fixed `authentication_failed` code;
- a valid authenticated request returns `200` with all six required
  security headers set to their exact required values, and no
  `access-control-allow-origin` header present;
- an authentication-failure `401` response carries the identical security
  headers as the success response;
- `GET /docs`, `/redoc`, and `/openapi.json` all return `404`;
- `POST /api/v1/sessions` with valid auth but no `Origin` header returns
  `403`/`origin_failed`; with `Origin` but no CSRF header returns
  `403`/`csrf_failed`; with a wrong `Origin` value returns
  `403`/`origin_failed`; a fully valid request returns `201` with the
  expected default `30_days` retention policy in the response body;
- a `Content-Length` header declaring 200,000 bytes is rejected with `413`
  before the body is read;
- a genuinely oversized JSON body (~100 KB) sent with a correct
  `Content-Length` is still rejected with `413` by the streamed byte
  counter;
- a request with the real 43-character session token placed in a query
  string (`?token=<real-token>`) is rejected with `400`, and the real
  token value is confirmed absent from the response text.

No listed validation command was left unrun. No test was skipped by
Reviewer choice. Environment: local `.venv` (Python 3.9), macOS/Darwin,
FastAPI 0.128.8 / httpx 0.28.1 / Pydantic 2.13.4 (all within the declared
`pyproject.toml` bounds), no network access used or required (FastAPI's
`TestClient` operates fully in-process over ASGI).

## Security, Scope, and Compatibility

Security observations: this checkpoint establishes the first network-
facing trust boundary in the codebase, and I gave it correspondingly
thorough scrutiny — full-file reads (not sampling) of every production
module, hand-tracing of the ASGI middleware's exact control flow for
ordering and header-injection correctness, and eight independently
constructed adversarial HTTP requests against a live instance. I found no
authentication bypass, CSRF bypass, Origin/Host confusion, body-size
bypass, token-leakage, or permissive-CORS gap. The token-shape validation
in `PMQAWebSecurityContext` is a wire-format/capacity check only (explicit
per the task: "actual cryptographic generation remains Task 5D.1C's
responsibility") — this checkpoint correctly does not claim to generate
secure tokens itself, only to validate and compare them safely once
supplied.

Scope observations: the diff touches exactly `pmqa/web/*` (five files),
three new test files plus additive blocks in `tests/test_packaging.py`,
`pyproject.toml` (one bounded runtime dependency, one bounded dev
dependency), and the four allowed documentation surfaces, plus the
Coder-owned report in a separate commit. No `pmqa/conversation/*`,
`pmqa/run/*`, `pmqa/application/*`, `pmqa/usage/*`, `pmqa/reasoning/*`,
`pmqa/cli.py`, Task 4/5/5A production file, or another role's handoff file
was modified.

Compatibility observations: all pre-existing regression suites (467 Task
5C, 98 Task 4, and the full 2104-test default suite) pass unchanged;
`import pmqa` and `import pmqa.cli` remain Web-lazy per the independently
rerun import-isolation tests.

## Verdict

Verdict: Pass

This verdict is advisory. The Architect makes the final technical
disposition.

## Suggested Architect Focus

- No blocking findings from this Reviewer's independent inspection,
  including live adversarial testing against a real running instance.
  This checkpoint is ready to serve as the trust root for Task 5D.1C.
- The Coder's "Remaining Risks" section correctly scopes cryptographic
  token generation, port selection, and Uvicorn startup/readiness to Task
  5D.1C; confirm this handoff boundary (this checkpoint validates and
  compares tokens safely, but does not generate them) is the intended
  division of responsibility before 5D.1C begins.
- Given the pattern on recent checkpoints (Task 5C.7 and Task 5D.1A each
  required one or more remediation rounds after gaps surfaced at
  Architect review despite passing Reviewer and Coder testing), this
  Reviewer deliberately raised scrutiny for this specific checkpoint given
  its security criticality — full-file reads plus live adversarial
  requests rather than test-suite sampling. No comparable gap was found
  here.

## Reviewer Write-Boundary Confirmation

Repository files changed by Reviewer:

- `agent-handoff/reviewer-report.md`

Confirmation: I changed no production code, tests, configuration, schemas,
packaging, scripts, product documentation, or another role's handoff file.
