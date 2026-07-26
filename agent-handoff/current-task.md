# Current Task

Owner: Architect

Task: PMQA Task 5D.1B — Secure Loopback Web/API Boundary

Task ID: `PMQA-5D.1B`

Attempt: `1`

Status: Authorized

Branch: `agent/task-5c-1-canonical-run-contract`

Approved Task 5D.1A Reviewer HEAD:
`55ea5067e87d502951cd102b40ede17a2d23796f`

Coder starting HEAD: derive and record the latest pushed branch commit that
contains this task publication before changing implementation files.

Repository Markdown and Git history are authoritative. Chat summaries are
informational only.

## Task Objective

Implement the provider-neutral, versioned, secure local ASGI/API boundary for
PMQA's existing conversation service and workflow catalog.

This checkpoint establishes the HTTP trust boundary only. It must be usable by
the future browser workbench, but it must not start a server, open a browser,
ship frontend assets, invoke reasoning, read ADO, or execute a PMQA workflow.

## Background

Task 5D.0 approved the Conversational Workflow Platform architecture:

- a local Python FastAPI boundary;
- versioned REST/JSON under `/api/v1`;
- loopback-only deployment;
- invocation-local authentication;
- strict Host, Origin, and CSRF controls;
- bounded canonical requests and fixed-safe responses; and
- a future React/TypeScript workbench packaged into the PMQA wheel.

Task 5D.1A now provides the approved conversation foundation:

- immutable session and turn contracts;
- session-only and durable repositories;
- SQLite retention and purge;
- optimistic revision transitions;
- shared sensitive-text ingress; and
- repository-result correlation before every read or mutation.

Task 5D.1B puts a narrow HTTP boundary over those existing services. Task
5D.1C will later own Uvicorn startup, `pmqa web`, token delivery to the local
browser, static frontend assets, browser opening, and distribution-level
runtime verification.

## Accepted Architecture Decisions

### Framework and execution boundary

- Use a FastAPI ASGI application factory.
- Add one bounded Python runtime dependency for FastAPI, compatible with the
  repository's supported Python versions and Pydantic v2.
- Do not add or start Uvicorn in this checkpoint.
- Do not use module-level application singletons or import-time dependency
  creation.
- Importing `pmqa.web` must perform no file, environment, network, browser,
  process, discovery, repository, or credential operation.

### Dependency direction

The app factory receives explicit, already-created dependencies:

- one exact `ConversationApplicationService`;
- one exact `WorkflowRegistry`; and
- one validated runtime-only local Web security context.

The Web layer may call only public application-service and registry APIs. It
must not import or access concrete in-memory/SQLite repository internals,
LangGraph, WorkflowState, provider SDKs, Product Packs, Playwright, or product
modules.

### Public API scope

Implement only versioned endpoints needed for the offline local shell:

- authenticated health;
- read-only workflow catalog;
- create, list, get, close, and delete conversation sessions;
- create one pending user turn;
- list and get conversation turns.

Do not expose browser endpoints that complete or fail assistant turns. A
future provider/application orchestration service will own that transition.
Do not expose purge, SQL, storage paths, repository selection, arbitrary
commands, runner execution, or workflow execution.

## Required Public Modules and APIs

Use a small `pmqa/web/` package with names chosen consistently. Expected
surfaces are:

- strict immutable API v1 request/response/read-model contracts;
- a runtime-only local Web security configuration/context;
- `create_pmqa_web_app(...) -> FastAPI`.

The exact module split may differ if it stays small and preserves import
isolation. Export only the APIs needed by future composition and tests.

The runtime security object must:

- be non-serializable into PMQA domain/artifact payloads;
- hide tokens from `repr` and validation errors;
- retain no caller-owned mutable container;
- require session and CSRF tokens to be distinct exact built-in strings,
  43–128 characters long, using only the unpadded base64url alphabet
  (`A-Z`, `a-z`, `0-9`, `-`, `_`); this validates capacity and wire shape,
  while actual cryptographic generation remains Task 5D.1C's responsibility;
- require an exact loopback literal host (`127.0.0.1` or `::1`) and valid
  nonzero port;
- derive or validate one exact `http` Origin and Host authority; and
- reject wildcard, path, URL ambiguity, credentials, query, fragment,
  non-ASCII, control, or non-loopback host configuration.

Token generation and browser delivery are deferred to Task 5D.1C. Tests may
construct deterministic valid tokens explicitly.

## API v1 Endpoints

Use `/api/v1` and exact JSON request/response models. At minimum:

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

Requirements:

- health returns only API/schema identity and bounded readiness state;
- workflow catalog is a stable safe read model projected from canonical
  `WorkflowDefinition` snapshots and never exposes adapters or runners;
- create-session input selects one existing retention policy explicitly or
  uses the approved 30-day default; optional connection-context identity
  remains an identifier, not credentials;
- create-turn input contains schema version, expected revision, and the
  bounded user message;
- close input contains schema version and expected revision;
- session and turn list limits reuse existing canonical bounds;
- mutation responses include the resulting canonical session/turn read model;
- API contracts use exact fields, forbid extras, reject coercion, use
  canonical UTC `Z` timestamps, and do not retain caller-owned containers;
- no endpoint accepts prompts, provider configuration, credentials,
  executable paths, commands, environment mappings, raw HTML/DOM, cookies,
  storage state, or arbitrary free-form metadata.

Do not duplicate domain lifecycle policy in Web models. Reconstruct and
project the existing canonical conversation and workflow contracts.

## Authentication, Origin, Host, and CSRF Policy

Every `/api/v1` endpoint requires an invocation-local session token using one
fixed header scheme. Prefer:

```text
Authorization: Bearer <invocation-local-token>
```

Use timing-safe comparison. Reject missing, malformed, duplicate, or incorrect
authentication with one fixed safe response. Never accept a session or CSRF
token in a URL, query parameter, route value, request body, cookie, log, error,
or response.

Every request must:

- contain the exact configured Host authority;
- reject multiple/ambiguous Host values;
- reject absolute-form or otherwise ambiguous request targets where the ASGI
  surface exposes them; and
- reject credential-like query keys before endpoint processing.

For Origin:

- a supplied Origin on any request must exactly equal the configured local
  Origin;
- every state-changing method must include that exact Origin;
- state-changing methods must also include one exact
  `X-PMQA-CSRF-Token` value matching the runtime CSRF token;
- safe read requests may omit Origin but must still pass Host and
  authentication.

Do not install permissive CORS. Do not return
`Access-Control-Allow-Origin: *`, allow cross-origin credentials, or treat
loopback location alone as authentication.

All API responses, including errors, must apply at least:

- `Cache-Control: no-store`;
- `Content-Security-Policy` suitable for an API-only surface, including
  `default-src 'none'` and `frame-ancestors 'none'`;
- `X-Content-Type-Options: nosniff`;
- `Referrer-Policy: no-referrer`;
- `X-Frame-Options: DENY`; and
- `Cross-Origin-Resource-Policy: same-origin`.

Disable FastAPI Swagger UI, ReDoc, and unauthenticated OpenAPI exposure for
this local runtime boundary.

## Request and Error Boundary

Enforce a fixed maximum request-body size no greater than 64 KiB:

- reject oversized declared `Content-Length` before body parsing;
- count streamed ASGI body bytes so omitted or dishonest Content-Length
  cannot bypass the limit;
- reject malformed Content-Length and multiple conflicting values;
- require JSON content type for JSON mutations;
- reject duplicate JSON keys, non-finite numbers, invalid UTF-8, excessive
  nesting, container cycles/runtime objects where applicable, and
  noncanonical representations;
- do not use broad regular expressions over arbitrary terminal text.

Define a small stable API failure vocabulary and fixed safe messages for:

- invalid request;
- authentication failure;
- Host failure;
- Origin failure;
- CSRF failure;
- request too large;
- route/resource not found;
- conversation application failure; and
- internal/dependency failure.

Map existing `ConversationApplicationErrorCode` values deliberately without
exposing repository choice, identifiers, user text, payloads, SQL, paths,
tokens, headers, exception text, runtime repr, cause, or context.

Malformed provider/dependency-shaped failures must not crash the application
or leak through an HTTP response. `MemoryError`, `KeyboardInterrupt`,
`SystemExit`, and `GeneratorExit` remain authoritative in direct application
boundaries and must not be deliberately converted into ordinary success.

The API must never log request/response bodies, Authorization/CSRF headers,
user messages, assistant responses, credentials, cookies, or raw exception
text.

## Side-Effect Ordering

Before calling any conversation mutation:

1. validate request target and body bound;
2. validate Host;
3. authenticate;
4. validate Origin and CSRF;
5. reconstruct the exact API contract; and
6. validate route/body correlation.

Any failure in these steps must cause zero conversation-service mutation.

Reads and mutations must call the existing service exactly once per intended
operation. Do not retry, fall back, repair, move repositories, or translate a
failed HTTP request into another service operation.

## Required Tests

Use FastAPI's in-process ASGI test support and real in-memory conversation
repositories. Tests remain offline and must not bind a socket or start a
browser/server.

Directly cover:

- valid authenticated health and workflow catalog;
- exact safe workflow definition projection and deterministic ordering;
- complete valid session/turn create/read/list/close/delete flow;
- 30-day default and explicit session-only/durable retention choices;
- optimistic revision and closed-session errors mapped safely;
- wrong, missing, malformed, duplicated, or query-carried auth tokens;
- wrong, missing, malformed, or duplicate Host;
- wrong/missing Origin on mutations and wrong supplied Origin on reads;
- wrong, missing, duplicated, or query/body-carried CSRF tokens;
- no wildcard CORS and exact security headers on success and every error;
- malformed JSON, duplicate keys, wrong content type, non-finite values,
  unknown fields, coercion, and schema-version mismatch;
- declared, streamed, and dishonestly declared oversized bodies;
- route/body ID mismatch and invalid identifiers;
- 404/405 and unexpected dependency failures produce bounded fixed errors;
- token, header, marker, payload, exception, path, SQL, and runtime repr
  non-disclosure;
- every rejected mutation makes zero service/repository change;
- control/resource exception policy;
- application factory and `pmqa.web` import isolation;
- generic `import pmqa` and `import pmqa.cli` remain Web-lazy;
- real PMQA wheel contains the Web modules but no test/runtime output.

If FastAPI's standard parser cannot enforce a required canonical JSON
invariant, add one narrow boundary parser rather than weakening the invariant.

## Allowed Changes

Expected:

- new `pmqa/web/` modules;
- focused `tests/test_web_*.py` files;
- `pmqa/web/__init__.py`;
- `pyproject.toml` for a bounded FastAPI runtime dependency and a direct
  test-client dev dependency only if required;
- packaging tests;
- concise updates to `README.md`, `docs/Roadmap.md`,
  `docs/architecture.md`, and
  `docs/architecture/conversational-workflow-platform.md`;
- `agent-handoff/coder-report.md`.

An existing neutral security helper may be reused. If it must change, the
change must be additive, generic, separately tested, and explained. Do not
create a second drifting sensitive/prohibited-key vocabulary.

## Out of Scope

Do not implement:

- Uvicorn startup, socket binding, port selection, readiness polling, or
  process lifecycle;
- `pmqa web`, browser opening, cookies, frontend token bootstrap, or logout;
- React, TypeScript, Vite, npm, Node, static assets, HTML pages, or UI
  components;
- SSE, WebSockets, polling orchestration, live progress, reconnect, or
  cancellation;
- reasoning-provider execution or assistant-turn completion;
- workflow/runner execution;
- ADO, Copilot CLI, Azure CLI, provider login, capabilities, approvals,
  operations, receipts, or external writes;
- usage/cost UI or new usage collection;
- repository migrations, new retention modes, or artifact repositories;
- Task 5D.1C, Task 5D.2+, Task 5B, Task 6, or Task 7;
- PR creation or merge.

## Acceptance Criteria

- Task 5D.1A remains approved and unchanged;
- one explicit side-effect-free FastAPI app factory exists;
- the API is versioned under `/api/v1`;
- only the bounded offline conversation/catalog endpoints exist;
- all endpoints require invocation-local authentication;
- Host, Origin, and CSRF policies fail closed as specified;
- tokens never enter URLs, payloads, domain state, errors, logs, or responses;
- request bodies and collections are bounded before application mutation;
- API contracts are strict and canonical;
- conversation errors and unexpected dependency failures are fixed-safe;
- valid conversation lifecycle behavior remains canonical;
- rejected requests cause zero application/repository mutation;
- security headers apply to success and error responses;
- no permissive CORS, docs UI, arbitrary command, or credential surface exists;
- imports remain isolated and the real wheel packages the Web modules;
- all focused and full regressions pass;
- only allowed files change.

## Validation Commands

Run and report at minimum:

```bash
.venv/bin/python -m pytest tests/test_web_contracts.py tests/test_web_security.py tests/test_web_app.py tests/test_conversation_service.py tests/test_conversation_repository.py tests/test_conversation_contracts.py -q
.venv/bin/python -m pytest tests/test_application_contracts.py tests/test_application_service.py tests/test_run_contracts.py tests/test_usage_contracts.py tests/test_usage_repository.py tests/test_usage_summary.py -q
.venv/bin/python -m pytest tests/test_boundary_policy.py tests/test_scrubber.py tests/test_packaging.py tests/test_conversation_imports.py tests/test_run_imports.py -q
.venv/bin/python -m pytest tests/test_workflow_runtime.py tests/test_workflow_reducer.py tests/test_supervisor_policy.py tests/test_langgraph_workflow.py -q
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest products/demo/generated_tests -q
.venv/bin/python -m compileall -q pmqa products
git diff --check
git status --short
```

Adjust only the three focused Web test filenames if the implementation uses a
smaller equivalent split. Use an isolated bytecode cache for compileall.

New tests must use no network, browser, live socket, Node, provider, ADO,
external Product Pack, or paid model.

## Expected Deliverables

- secure runtime-only local Web security context;
- strict API v1 contracts and safe errors;
- authenticated FastAPI app factory over existing application APIs;
- focused adversarial security and lifecycle tests;
- real-wheel and import-isolation coverage;
- concise architecture/status documentation;
- one or more intentional implementation commits;
- one separate report-only Coder handoff commit;
- clean synchronized branch;
- no PR or merge.

## Required Coder Handoff

Replace `agent-handoff/coder-report.md` with the complete Task 5D.1B Attempt 1
report. Include:

- Task/Attempt, branch, and exact Git-derived starting HEAD;
- implementation commit(s);
- changed files;
- exact API endpoint and contract inventory;
- authentication, Host, Origin, CSRF, body-limit, canonical-JSON, security
  header, and safe-error behavior;
- side-effect ordering evidence;
- dependency and packaging changes with compatibility rationale;
- focused and full validation results;
- remaining risks and scope confirmation;
- one recommended review depth (`Light`, `Standard`, or `Deep`);
- one-sentence reason;
- 3–6 suggested Reviewer focus areas;
- Human Summary using the mandatory routing and one-sentence Handoff Note.

Recommended review depth is advisory. The Architect retains final authority.

Do not include the report commit's own SHA. The Independent Reviewer derives
it from Git.
