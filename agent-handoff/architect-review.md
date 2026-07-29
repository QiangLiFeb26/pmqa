# Architect Review

Owner: Architect

Task: PMQA Task 5D.1C — Local Browser Workbench and Packaged Runtime

Task ID: `PMQA-5D.1C`

Attempt: `1`

Status: Needs Revision

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed Starting HEAD:
`e2c25273da21bac080a2f29c6abaa2c0517dffac`

Reviewed Implementation Commits:

- `5585812e62f12ac7f8c529769c16048c653d149c`;
- `bb25794241e5410afc88032838d6bbb014e2e698`.

Derived Coder Report Commit:
`607af145c8015874607fc896b50bd2194d5be22b`

Derived Reviewer Report Commit:
`4a0b0fff32475852374c54e297ee4b22a16bfa62`

The Coder and Reviewer report commits were derived from Git path history.
This review does not predict the SHA of its own containing commit.

## Correlation and Ownership Verification

- the active branch and upstream are
  `agent/task-5c-1-canonical-run-contract`;
- the worktree was clean and local/upstream HEAD both equaled the derived
  Reviewer report commit before this disposition;
- starting HEAD `e2c2527...` is the parent of implementation commit
  `5585812...`;
- implementation commits are linear:
  `5585812... -> bb25794...`;
- documentation commit `bb25794...` is the parent of Coder report commit
  `607af14...`;
- Coder report commit `607af14...` is the parent of Reviewer report commit
  `4a0b0ff...`;
- all reports identify Task `PMQA-5D.1C`, Attempt `1`, the same branch,
  starting HEAD, and implementation commits;
- implementation/documentation changes remain inside the broad areas
  authorized by `current-task.md`;
- Coder and Reviewer report commits each change only their owner-controlled
  report.

## Review Depth

Deep

The Coder recommended Deep review and the Reviewer independently selected
Deep. The Architect also selected Deep because this checkpoint combines the
first real local server lifecycle, public static-resource boundary, browser
secret bootstrap, authenticated mutation API, frontend contracts, and wheel
distribution.

## Independent Reviewer Result

Reviewer verdict: `Pass`

Reviewer blocking findings: none.

Reviewer advisory observations:

1. a non-daemon Uvicorn thread may remain alive beyond the five-second join if
   it does not observe cooperative shutdown promptly;
2. frontend path interpolation does not use `encodeURIComponent`, although
   all currently reachable identifiers are server-issued and satisfy the
   strict run-identifier policy.

The Reviewer performed a legitimate Deep review and independently ran the
major Python/frontend suites. The Architect accepts that evidence for the
paths it covers but overrides the advisory verdict because final review found
one concrete runtime failure-classification defect and one incomplete
contract-drift boundary.

## Overall Assessment

The implementation is strong and preserves the intended architecture:

- exact loopback binding with one pre-bound OS-assigned socket;
- explicit in-memory and user-data SQLite repositories;
- runtime-only cryptographic tokens;
- programmatic Uvicorn with access logs disabled;
- exact public static-route allowlist separated from authenticated
  `/api/v1`;
- fragment-only browser bootstrap removed before rendering or API access;
- module-memory credentials with no cookie or browser-storage persistence;
- a minimal React/strict-TypeScript conversation shell;
- no AI, workflow execution, ADO, Copilot, authorization, receipt, usage UI,
  or external write;
- reproducible frontend assets with packaged digest verification;
- real-wheel and real-browser evidence.

However, a standard-library browser-discovery failure is not contained by the
expected runtime boundary. In addition, the claimed Python-to-TypeScript
contract drift check covers only the outer Web wrapper fields and cannot
detect drift in the nested domain contracts the UI actually reads.

Both findings are local and can be remediated without changing the approved
runtime, API, static-route, bootstrap, or UI architecture.

## Findings

### F1 — Normal browser-launch failure escapes the fixed-safe runtime boundary

Severity: Blocking

Locations:

- `pmqa/web/runtime.py`;
- `run_pmqa_web_workbench`;
- `pmqa/cli.py`;
- `tests/test_web_runtime.py`.

The task requires expected browser-launch failures to return exit code `2`
with only `pmqa_web_failed`. The implementation handles a browser opener that
returns `False` and catches `OSError`, but Python's standard
`webbrowser.open()` can raise `webbrowser.Error` when no runnable browser is
available. `webbrowser.Error` inherits directly from `Exception`, not
`OSError`.

The Architect independently injected the real standard-library exception
type after successful readiness:

```text
browser_open -> webbrowser.Error("secret-path-marker")
```

Observed:

```text
exception type: webbrowser.Error
public message: secret-path-marker
server.should_exit: true
socket close calls: 1
```

Cleanup ran, but the raw expected operational error crossed
`run_pmqa_web_workbench` and would cross `pmqa web` as a traceback instead of
the fixed failure code. A browser executable/path or environment detail can
therefore be disclosed.

Contain only the standard browser-discovery/launch exception at the exact
browser-open boundary. Do not broadly catch every `RuntimeError` or arbitrary
programming exception. Resource/control-flow exceptions remain authoritative.

The same focused audit must classify a normal thread-start resource failure
separately from a programming failure raised inside `server.run`. A production
`threading.Thread.start()` can raise the operational
`RuntimeError("can't start new thread")`; it should not expose a traceback as
a normal startup failure. Thread-construction/programming errors and a
`RuntimeError` emitted by the server body must continue to propagate.

### F2 — Frontend drift guard omits the nested contracts consumed by the UI

Severity: Blocking

Locations:

- `frontend/workbench/src/api-v1.contract.json`;
- `frontend/workbench/src/api.ts`;
- `tests/test_web_frontend_contract_drift.py`;
- `frontend/workbench/src/api-schema.test.ts`.

The current fixture and Python test compare only the field names of the eleven
outer Web contracts. For example:

```json
"SessionResponse": ["schema_version", "session"]
```

They do not describe or compare:

- `ConversationSession`;
- `ConversationTurn`;
- the `WorkflowDefinition` fields consumed by the UI;
- retention/status enum values; or
- the endpoint method/path mapping used by `APIClient`.

The TypeScript `WorkflowDefinition` intentionally models only a subset of the
server object. That is acceptable for rendering, but the current drift test
would still pass if a nested field used by the UI were renamed, removed, or
changed incompatibly. The outer wrapper would remain
`{"schema_version", "session"}`.

Expand the canonical fixture and drift tests to cover every nested field and
enum value the frontend depends upon, plus the exact method/path inventory.
The implementation need not introduce OpenAPI or a new code-generation
dependency. A small deliberately maintained canonical fixture is sufficient
if both Python and TypeScript verify its complete selected surface.

### F3 — Declared UI operations lack focused behavioral regression coverage

Severity: Required test follow-up

Locations:

- `frontend/workbench/src/App.test.tsx`;
- `frontend/workbench/src/api.test.ts`;
- `tests/test_web_live_smoke.py`.

Production code contains the required turn, close, delete, and conflict
refresh paths, and the Architect found no direct implementation defect in
them. But the frontend tests cover only escaped catalog text, duplicate
session submission, one authenticated read, and create-session headers. The
live smoke creates only a session.

No focused test currently locks:

- exact API method/path/body/headers for create-turn, close, and delete;
- session selection and turn display;
- successful pending-turn creation without fake assistant output;
- close behavior;
- confirmed deletion and cancelled deletion;
- one bounded refresh without mutation retry on revision conflict; or
- representative not-found/server/unavailable rendering.

Add bounded fixture-based coverage for these already-declared capabilities.
This does not authorize new UI behavior or broaden the live smoke.

## Acceptance Criteria Disposition

| Acceptance criterion | Result |
| --- | --- |
| Loopback-only packaged runtime composition | Met |
| Deterministic/fixed-safe startup and browser launch | Not met |
| Fragment-only token bootstrap and non-persistence | Met |
| Static routes preserve `/api/v1` security | Met |
| Minimal UI implements only approved capabilities | Met by inspection |
| Untrusted content renders only as text | Met |
| Strict frontend build and complete API drift protection | Partially met |
| Real wheel contains exact runtime assets and excludes debris | Met |
| Import/product/provider isolation | Met |
| Existing Python/frontend/browser regressions | Met |
| Focused tests lock every declared UI action | Not met |
| Scope and ownership | Met |

## Architect Validation

Independently executed:

- Task 5D Web/conversation focused group: `387 passed`;
- full default suite: first run had one environment-only wheel-build failure
  because the current review mount prohibited an existing egg-info timestamp
  update; the identical suite under normal repository permissions passed
  `2233 passed, 6 skipped, 1` existing LangGraph warning;
- frontend typecheck: passed;
- frontend unit/component tests: `11 passed` across four files after allowing
  Vitest its temporary Vite cache;
- opt-in real loopback Uvicorn/Chromium smoke: `1 passed`;
- existing generated SauceDemo Playwright regressions: `2 passed`;
- Git correlation and diff scope: passed;
- browser `webbrowser.Error` reproduction: failed the required fixed-safe
  invariant.

The six default skips are five existing environment-gated tests and the
opt-in workbench smoke, which passed separately.

## Required Changes

Complete one narrow Task 5D.1C Attempt 2 remediation:

1. contain normal browser-discovery/launch and thread-start operational
   failures as `PMQAWebRuntimeError` with no cause, context, token, URL, path,
   or underlying detail;
2. preserve propagation of resource/control-flow and genuine server-body
   programming exceptions;
3. extend the frontend contract fixture/drift checks across all nested fields,
   enums, and endpoint method/path shapes used by the UI;
4. add focused API-client and component tests for every already-implemented
   UI operation and conflict behavior;
5. preserve exact runtime, static/API, bootstrap, package, and scope behavior.

Do not start Task 5D.2 or add any new capability.

## Final Disposition

**Needs Revision**

Task 5D.1C is not approved at implementation commits
`5585812e62f12ac7f8c529769c16048c653d149c` and
`bb25794241e5410afc88032838d6bbb014e2e698`.

## Next Recommended Task

Complete Task 5D.1C Attempt 2 — Browser Failure Containment, Complete Contract
Drift, and UI Action Regression Coverage, as defined in
`agent-handoff/current-task.md`.
