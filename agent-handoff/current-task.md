# Current Task

Owner: Architect

Task: PMQA Task 5D.1C — Browser Boundary and Contract Drift Remediation

Task ID: `PMQA-5D.1C`

Attempt: `2`

Status: Changes Required

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed Attempt 1 Reviewer HEAD:
`4a0b0fff32475852374c54e297ee4b22a16bfa62`

Coder starting HEAD: derive and record the latest pushed branch commit that
contains this remediation publication before changing implementation files.

Repository Markdown and Git history are authoritative. Chat summaries are
informational only.

## Task Objective

Close the three bounded Task 5D.1C findings in
`agent-handoff/architect-review.md` while preserving the accepted loopback
runtime, static/API partition, fragment bootstrap, minimal workbench,
distribution, and all prior Task 5D behavior.

This is a narrow remediation. Do not start Task 5D.2.

## Accepted Attempt 1 Architecture

Preserve:

- `pmqa web` with no public options;
- exact `127.0.0.1` binding on one pre-bound OS-assigned socket;
- user-data SQLite plus volatile session-only repository;
- runtime-only session/CSRF tokens;
- programmatic Uvicorn with logs disabled;
- exact public routes `/`, `/assets/app.js`, `/assets/app.css`;
- full Task 5D.1B security for every `/api/v1` route;
- fragment-only browser bootstrap removed before rendering/network access;
- module-memory credentials and no cookies/browser storage;
- the existing minimal React/strict-TypeScript workbench behavior;
- packaged asset integrity and real-wheel external-directory behavior;
- no AI, workflow execution, ADO, Copilot, Skill Repo, authorization,
  receipts, usage UI, or external writes.

Do not weaken an approved security check to simplify remediation.

## Required Change 1 — Expected Runtime Failure Containment

At the exact browser-open boundary:

- contain the standard-library `webbrowser.Error` as
  `PMQAWebRuntimeError`;
- keep a returned value other than exact `True` as the existing expected
  failure;
- expose only `pmqa_web_failed`;
- suppress cause/context and disclose no token, URL, executable, path,
  environment value, or underlying message;
- preserve server stop signaling and owned-socket cleanup;
- preserve `MemoryError`, `KeyboardInterrupt`, `SystemExit`, and
  `GeneratorExit` unchanged;
- preserve propagation of unrelated/programming exceptions.

At thread start:

- contain the normal operational inability to start the already-constructed
  owned server thread as fixed `PMQAWebRuntimeError`;
- preserve thread-construction/programming exception propagation;
- do not reclassify a `RuntimeError` or other programming exception raised
  from inside `server.run`;
- keep readiness, browser-once, cooperative shutdown, and five-second join
  behavior otherwise unchanged.

Directly test:

- `webbrowser.Error` with injected token/path/command markers;
- a false browser return;
- browser control-flow/resource exceptions;
- operational thread-start failure with injected markers;
- unexpected browser programming exception propagation;
- unexpected server-body exception propagation;
- exact CLI stderr/exit behavior and cleanup/no-browser-before-readiness.

Do not introduce a broad catch around the entire runtime.

## Required Change 2 — Complete Selected Frontend Contract Drift

Extend the deliberately maintained frontend contract fixture so it covers the
complete selected wire surface consumed or emitted by the current UI:

- every outer Web contract name and field;
- every `ConversationSession` field used or transmitted;
- every `ConversationTurn` field used or transmitted;
- every `WorkflowDefinition` field represented by the TypeScript client;
- retention-policy, session-status, and turn-status values;
- exact API operation names;
- exact HTTP method and path template for every `APIClient` method; and
- API schema version.

Python tests must derive the authoritative nested field and enum inventory
from the existing Python contracts and fail on drift. TypeScript tests must
verify that its declared selected fixture and operation inventory remain
complete. Do not duplicate security policy or add OpenAPI/code-generation
dependencies.

The TypeScript UI may continue to model only the fields it consumes, but that
selected subset must be explicit and verified as a subset of the authoritative
Python contract with exact names and compatible enum values.

## Required Change 3 — UI Action Regression Coverage

Add fixture-based tests without expanding production behavior.

`APIClient` coverage must verify exact path, method, request body,
authentication, CSRF, and no-cookie policy for:

- health;
- workflow catalog;
- session list/read/create;
- turn list/create;
- close;
- delete.

Component coverage must verify:

- session selection and bounded turn rendering;
- one successful pending user turn with no fabricated assistant response;
- successful close;
- delete only after confirmation;
- cancelled deletion causes no request;
- one revision-conflict refresh and zero automatic mutation retry;
- representative not-found, unavailable, and fixed-safe server states; and
- the existing duplicate-submission and untrusted-text behavior.

Use deterministic fakes. Do not broaden the live browser smoke unless a small
change is necessary to reproduce a remediation boundary.

## Safe Failure Requirements

New runtime rejection paths must:

- expose only the existing fixed `PMQAWebRuntimeError`;
- reach the CLI as only `pmqa_web_failed`, exit code `2`;
- suppress expected exception cause/context;
- print or persist no token, URL, path, executable, environment, static
  content, or runtime-object detail;
- close the owned socket exactly once and signal an already-created server to
  stop;
- never open a browser before readiness;
- perform no retry, fallback, alternate browser, repository repair, or
  alternate operation.

Resource/control-flow exceptions remain authoritative.

## Allowed Changes

Expected:

- `pmqa/web/runtime.py`;
- `frontend/workbench/src/api-v1.contract.json`;
- `frontend/workbench/src/api-schema.test.ts`;
- `frontend/workbench/src/api.test.ts`;
- `frontend/workbench/src/App.test.tsx`;
- `tests/test_web_frontend_contract_drift.py`;
- `tests/test_web_runtime.py`;
- regenerated packaged frontend assets and integrity manifest only if
  production frontend source changes;
- `agent-handoff/coder-report.md`.

If a concise Attempt 1 documentation claim must be corrected, limit changes
to the existing Task 5D documentation and explain why.

Do not modify:

- conversation, Run, Runner, Application, Usage, reasoning, workflow,
  Product Pack, product, Supervisor, or LangGraph behavior;
- Task 5D.1B API endpoint or static-route security semantics;
- CLI command inventory or dependency bounds;
- another role's handoff file.

Use one minimal remediation implementation commit and one separate report-only
Coder handoff commit. Do not amend Attempt 1.

## Out of Scope

Do not implement:

- new runtime configuration or CLI options;
- new static or API routes;
- assistant completion/failure;
- reasoning, workflow/Runner execution;
- ADO, Azure CLI, Copilot CLI, Skill Repo, MDE integration;
- capability, artifact, approval, authorization, operation, receipt, usage
  UI, or external write;
- SSE, WebSocket, polling, remote binding, hosted deployment, or TLS;
- Task 5D.2+, Task 5B, Task 6, or Task 7;
- PR creation or merge.

## Acceptance Criteria

- ordinary browser-discovery/launch and thread-start operational failures are
  fixed-safe and fully contained;
- unrelated programming exceptions and resource/control-flow exceptions
  preserve their approved propagation;
- cleanup and browser-before-readiness invariants remain unchanged;
- frontend contract drift checks cover the complete selected nested and
  operation surface;
- every existing UI/API-client action has bounded focused regression
  coverage;
- no production capability or endpoint is added;
- exact Task 5D.1A/1B/runtime/static/bootstrap/package behavior remains
  unchanged;
- focused/frontend/full regressions pass;
- generated assets remain consistent if touched;
- only allowed files change;
- worktree is clean and synchronized.

## Validation Commands

Run and report at minimum:

```bash
.venv/bin/python -m pytest tests/test_web_runtime.py tests/test_web_frontend_contract_drift.py tests/test_web_static.py tests/test_web_app.py tests/test_web_security.py tests/test_web_contracts.py -q
.venv/bin/python -m pytest tests/ -k "web or conversation" -q
.venv/bin/python -m pytest tests/test_packaging.py -q
.venv/bin/python -m pytest -q
cd frontend/workbench && npm run typecheck
cd frontend/workbench && npm test
cd frontend/workbench && npm run build
.venv/bin/python -m pytest products/demo/generated_tests -q
.venv/bin/python -m compileall -q pmqa products
git diff --check
git status --short
```

Use an isolated bytecode cache for compileall. The new tests remain offline
and use no company system, provider, paid model, external network, or real
browser.

## Expected Deliverables

- fixed-safe browser/thread startup failure containment;
- complete selected nested/operation drift fixture and checks;
- focused API-client/component action coverage;
- preserved runtime, security, bootstrap, UI, and packaging behavior;
- one minimal remediation implementation commit;
- one separate report-only Coder handoff commit;
- clean synchronized branch;
- no PR or merge.

## Required Coder Handoff

Replace `agent-handoff/coder-report.md` with the complete Task 5D.1C Attempt 2
report. Include:

- Task/Attempt, branch, and exact Git-derived starting HEAD;
- remediation implementation commit;
- changed files;
- browser/thread failure classification and cleanup evidence;
- nested contract/enum/operation drift evidence;
- focused UI action coverage;
- focused, frontend, packaging, full, and generated-test validation;
- remaining risks and scope confirmation;
- one recommended review depth (`Light`, `Standard`, or `Deep`);
- one-sentence reason;
- 3–6 suggested Reviewer focus areas;
- Human Summary using the mandatory routing and one-sentence Handoff Note.

Recommended review depth is advisory. The Architect retains final authority.
Do not include the report commit's own SHA; the Reviewer derives it from Git.
