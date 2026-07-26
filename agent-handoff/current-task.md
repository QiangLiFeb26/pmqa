# Current Task

Owner: Architect

Task: PMQA Task 5D.1B — Web Boundary Canonicalization and Token Containment

Task ID: `PMQA-5D.1B`

Attempt: `2`

Status: Changes Required

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed Attempt 1 Reviewer HEAD:
`949a5e39e85024998204858c900a9fb235a3dca0`

Coder starting HEAD: derive and record the latest pushed branch commit that
contains this remediation publication before changing implementation files.

Repository Markdown and Git history are authoritative. Chat summaries are
informational only.

## Task Objective

Close the four Web trust-boundary gaps documented in
`agent-handoff/architect-review.md` while preserving the approved Task 5D.1B
architecture, endpoint inventory, dependency direction, exact valid API
behavior, and Task 5D.1A conversation semantics.

This is a narrow remediation. Do not start Task 5D.1C.

## Accepted Attempt 1 Architecture

Preserve:

- the explicit side-effect-free FastAPI app factory;
- exact injected `ConversationApplicationService`, `WorkflowRegistry`, and
  `PMQAWebSecurityContext`;
- the existing ten `/api/v1` endpoints and no others;
- exact Host and Bearer authentication;
- exact Origin and CSRF enforcement for mutations;
- no cookies, permissive CORS, Swagger/ReDoc/OpenAPI, or arbitrary commands;
- fixed response security headers;
- 64 KiB maximum request body;
- existing conversation error/status mapping;
- no assistant complete/fail, purge, runner, or workflow-execution endpoint;
- FastAPI/httpx dependency bounds, import isolation, and wheel packaging;
- no Uvicorn, CLI, browser, frontend, provider, ADO, or later Task 5D work.

Do not weaken a valid Attempt 1 security check to simplify this remediation.

## Required Change 1 — Runtime Token Containment

The known session and CSRF tokens must be rejected when either token appears
anywhere inside a bounded string, not only when the complete string equals the
token.

Apply containment to every relevant leaf:

- decoded/raw route segment;
- query key and value after canonical decoding;
- nested request JSON key and value;
- nested response/read-model key and value;
- user message;
- workflow catalog text; and
- any other bounded string traversed by the existing token-boundary helper.

Required behavior:

- `prefix<token>suffix` is detected;
- the exact token remains detected;
- unrelated partial prefixes/suffixes are not treated as a full token;
- authentication and CSRF header validation remain exact and timing-safe;
- scanning is bounded and does not use catastrophic/backtracking regex;
- no helper exports or serializes a raw token;
- errors remain fixed and contain no token, candidate string, position, or
  underlying detail.

Incoming embedded tokens must fail before service clock/ID sampling or
repository mutation. Pre-existing embedded tokens found in a response model
must produce only fixed `INTERNAL_FAILED`, with zero token bytes in the HTTP
response.

Directly test both tokens in:

- prefix, suffix, and middle positions;
- route segments;
- query keys and values, including percent-decoded representations;
- nested JSON keys and values;
- valid create-turn `user_message`;
- a pre-existing repository turn;
- a workflow definition string returned by the registry.

Also retain exact-token and ordinary-safe-string tests.

## Required Change 2 — Canonical Public Contract Invariants

Every exported Web contract must satisfy, for every successfully constructed
instance:

```python
wire = contract.to_dict()
restored = type(contract).from_dict(
    json.loads(json.dumps(wire))
)
assert restored == contract
```

This includes:

- health;
- workflow catalog;
- create/close/turn requests;
- session and session-list responses;
- turn, turn-list, and turn-mutation responses; and
- delete response.

Requirements:

- direct construction remains strict and accepts only the intended typed
  nested domain objects and exact tuples;
- explicit `from_dict` accepts only canonical plain-JSON wire dictionaries,
  reconstructs nested `WorkflowDefinition`, `ConversationSession`, and
  `ConversationTurn` through their existing `from_dict` methods, and converts
  wire arrays into fresh immutable tuples;
- direct construction must not silently accept mutable wire dictionaries or
  lists where typed snapshots are required;
- explicit wire reconstruction must not accept tuples, model objects,
  subclasses, bytes, coercive values, missing required fields, unknown fields,
  noncanonical timestamps, or caller-owned mutable/runtime objects;
- only `CreateSessionRequest` retains its explicitly approved default
  insertion;
- caller-owned input is never mutated or retained;
- error messages remain fixed and marker-safe.

Override or otherwise contain Pydantic's unvalidated default
`model_copy(update=...)`. Every public Web contract must:

- fully revalidate valid updates;
- reject unknown fields and invalid/coercive updates;
- preserve canonical wire round trip after a valid update; and
- retain no caller-owned nested object.

Add positive round-trip tests for every exported contract and adversarial
`model_copy` tests across each distinct contract shape.

## Required Change 3 — Finite Canonical JSON

`parse_canonical_json_object` must reject every non-finite number regardless
of JSON spelling or parser path.

Directly reject:

- `NaN`;
- `Infinity` and `-Infinity`;
- positive exponent overflow such as `1e9999`;
- negative exponent overflow such as `-1e9999`; and
- nested variants.

Use an explicit finite-number check for exact floats. Contain decoder
`ValueError`, `OverflowError`, and `RecursionError` only at the JSON parsing
boundary while preserving `MemoryError`, `KeyboardInterrupt`, `SystemExit`,
and `GeneratorExit`.

The public parser must expose only `WebAPIContractValidationError` with the
existing fixed message and no input/parser detail.

## Required Change 4 — Canonical Target and Bounded ASGI Stream

### Decoded/raw target

Require strict ASCII encoding of `scope["path"]` and exact equality with
`raw_path`. Never use `errors="ignore"` or replacement.

Reject before routing:

- any non-ASCII decoded path;
- a decoded/raw path mismatch;
- percent/backslash/query/NUL ambiguity already covered by Attempt 1; and
- embedded runtime tokens covered by Required Change 1.

These failures remain fixed `INVALID_REQUEST` and occur before service calls.

### Stream buffering

Keep the 64 KiB total byte limit, but do not retain an unbounded list of ASGI
message dictionaries.

Required behavior:

- require exact `http.request` messages and exact byte bodies;
- reject non-progressing empty messages when `more_body=True`;
- accumulate at most the bounded body bytes;
- replay one canonical bounded request-body message to FastAPI;
- reject a declared/received mismatch;
- retain the existing oversized-before-authentication ordering;
- preserve resource/control-flow propagation;
- make no mutation on malformed, non-progressing, or oversized input.

Malformed/oversized `Content-Length` parsing must remain deterministic across
supported Python versions. Bound the decimal representation before integer
conversion and contain conversion-limit/overflow failures as fixed
`INVALID_REQUEST` or `REQUEST_TOO_LARGE`, never `INTERNAL_FAILED`.

Directly test:

- mismatched non-ASCII `path`/`raw_path`;
- exact valid ASCII equality;
- empty nonterminal chunks;
- many small valid chunks producing one bounded canonical body;
- non-byte body values;
- honest/dishonest declared lengths;
- extreme digit-length Content-Length;
- overflow by one byte;
- no service mutation on every rejected stream.

## Safe Failure Requirements

All new rejection paths must:

- use only existing fixed `WebAPIFailureCode` values and messages;
- preserve all six required security headers;
- not add permissive CORS;
- expose no token, candidate text, payload, header, path, runtime repr,
  parser detail, cause, or context;
- not log request/response bodies or security headers;
- make no conversation mutation;
- perform no retry, fallback, repository repair, or alternate operation.

`MemoryError`, `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit` remain
authoritative.

## Allowed Changes

Expected:

- `pmqa/web/security.py`;
- `pmqa/web/contracts.py`;
- `pmqa/web/app.py`;
- `tests/test_web_security.py`;
- `tests/test_web_contracts.py`;
- `tests/test_web_app.py`;
- `agent-handoff/coder-report.md`.

If a concise Attempt 1 documentation claim must be corrected, limit changes
to the existing Task 5D Web documentation and explain why. No dependency or
packaging change should be necessary.

Do not modify:

- conversation contracts, repositories, or service;
- Run, Runner, Application, Usage, reasoning, workflow, Product Pack, or
  product code;
- CLI or dependency bounds;
- another role's handoff file.

Use one minimal remediation implementation commit and one separate
report-only Coder handoff commit. Do not amend Attempt 1.

## Out of Scope

Do not implement:

- Uvicorn, socket binding, port selection, readiness, or process lifecycle;
- `pmqa web`, token generation/delivery, browser opening, logout, or cookies;
- React, TypeScript, Vite, npm, Node, static assets, or HTML;
- SSE, WebSockets, polling, reconnect, or cancellation;
- reasoning, assistant-turn completion, runner/workflow execution;
- ADO, Copilot CLI, Azure CLI, provider login, capability, approval,
  operation, receipt, external write, or usage UI;
- new endpoints, error codes, retention modes, or repositories;
- Task 5D.1C, Task 5D.2+, Task 5B, Task 6, or Task 7;
- PR creation or merge.

## Acceptance Criteria

- embedded session/CSRF tokens cannot cross any URL/request/state/response
  string boundary;
- exact auth and CSRF comparison remains timing-safe;
- every public Web contract is strict under direct construction,
  `from_dict`, canonical JSON round trip, and `model_copy(update=...)`;
- canonical JSON parsing rejects every non-finite result;
- decoded/raw targets are exact strict ASCII matches;
- streamed body processing is bounded by bytes and canonicalized without
  unbounded message retention;
- all rejection paths are fixed-safe and mutation-free;
- every valid Attempt 1 endpoint and security behavior remains unchanged;
- Task 5D.1A and unrelated PMQA behavior remain unchanged;
- focused and full regressions pass;
- only allowed files change.

## Validation Commands

Run and report:

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

Use an isolated bytecode cache for compileall. New tests remain offline and
must not bind a socket or use a browser, network, Node, provider, ADO,
external Product Pack, or paid model.

## Expected Deliverables

- corrected runtime-token containment;
- canonical public contract reconstruction and validated copy behavior;
- finite-only JSON parser;
- strict target correlation and bounded canonical stream replay;
- focused adversarial regression tests;
- one minimal remediation implementation commit;
- one separate report-only Coder handoff commit;
- clean synchronized branch;
- no PR or merge.

## Required Coder Handoff

Replace `agent-handoff/coder-report.md` with the complete Task 5D.1B Attempt 2
report. Include:

- Task/Attempt, branch, and exact Git-derived starting HEAD;
- remediation implementation commit;
- changed files;
- exact behavior for all four Required Changes;
- independent evidence that each Architect reproduction now fails safely;
- fixed-safe/no-mutation evidence;
- focused and full validation results;
- remaining risks and scope confirmation;
- one recommended review depth (`Light`, `Standard`, or `Deep`);
- one-sentence reason;
- 3–6 suggested Reviewer focus areas;
- Human Summary using the mandatory routing and one-sentence Handoff Note.

Recommended review depth is advisory. The Architect retains final authority.

Do not include the report commit's own SHA. The Independent Reviewer derives
it from Git.
