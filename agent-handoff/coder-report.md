# Coder Report

Owner: Coder

Task: PMQA Task 5D.1C — Browser Boundary and Contract Drift Remediation

Task ID: `PMQA-5D.1C`

Attempt: `2`

Status: Ready for Independent Reviewer

## Branch and Git Correlation

Branch:

`agent/task-5c-1-canonical-run-contract`

Exact Git-derived Coder starting HEAD:

`5f0c1413bc0d726592f0e590fc4646fadac5519c`

That commit was the latest pushed branch commit containing the Architect's
Task 5D.1C Attempt 2 publication. Before implementation, local HEAD and
`origin/agent/task-5c-1-canonical-run-contract` both equaled that commit and
the worktree was clean. It records reviewed Attempt 1 Reviewer HEAD
`4a0b0fff32475852374c54e297ee4b22a16bfa62`.

No prior Task 5D commit was amended, rebased, or replaced.

## Remediation Implementation Commit

`da474009bd603e46ce4ffcbdb03de85986094208`

Commit message:

`remediate Task 5D.1C web boundaries`

This report is committed separately after the implementation commit. The
Independent Reviewer derives the report commit from Git; this report does not
claim its own future commit SHA.

## Changed Files

Runtime:

- `pmqa/web/runtime.py`.

Selected frontend contract fixture and focused tests:

- `frontend/workbench/src/api-v1.contract.json`;
- `frontend/workbench/src/api-schema.test.ts`;
- `frontend/workbench/src/api.test.ts`;
- `frontend/workbench/src/App.test.tsx`;
- `tests/test_web_frontend_contract_drift.py`;
- `tests/test_web_runtime.py`.

Report-only handoff:

- `agent-handoff/coder-report.md`.

No production frontend source or packaged static asset changed. No
conversation, Run, Runner, Application, Usage, reasoning, workflow,
Supervisor, LangGraph, Product Pack, product, provider, CLI, API endpoint,
static-route, packaging, ADO, or external-write behavior changed.

## Browser and Thread Boundary Remediation

The exact browser-open call now contains only standard-library
`webbrowser.Error` and a return value other than exact `True` as the existing
fixed `PMQAWebRuntimeError("pmqa_web_failed")`. Conversion occurs outside the
exception handler, leaving both cause and context unset. Tests inject token,
path, and executable markers and prove no detail reaches the exception,
stdout, or stderr.

`MemoryError`, `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit` remain
authoritative at the browser boundary. Unrelated browser `RuntimeError`
continues to propagate unchanged.

The already-constructed owned thread's exact `start()` call now contains its
operational `RuntimeError` as the same fixed-safe runtime error. Thread
construction stays outside that boundary, and server-body failures remain
captured by the owned thread and classified by the existing
`_raise_server_failure` path. Consequently, a programming exception from
`server.run` still propagates rather than being mistaken for a start failure.

Focused tests prove one start/open attempt, no browser before readiness,
server stop signaling, one owned-socket close, no retry or fallback, and
unchanged cleanup for fixed-safe, programming, resource, and control-flow
paths. The existing CLI boundary still emits only `pmqa_web_failed` with exit
code `2` for `PMQAWebRuntimeError`, while unrelated runner failures propagate.

## Selected Frontend Contract Drift

The maintained JSON fixture now records:

- Web API schema version `1`;
- all 11 outer Web response/request contract names and their exact fields;
- all 10 `ConversationSession` fields;
- all 11 `ConversationTurn` fields;
- the five `WorkflowDefinition` fields represented by the TypeScript client;
- all retention-policy, session-status, and turn-status wire values; and
- the complete nine-operation `APIClient` inventory with exact HTTP method
  and path template.

Python drift tests derive outer/nested field order and enum values from the
authoritative Pydantic models and enums. They verify the selected
`WorkflowDefinition` inventory is a subset of the authoritative model, the
fixture schema version equals `WEB_API_SCHEMA_VERSION`, and every declared
operation method/path exists in the composed API routes. TypeScript tests pin
the complete selected fixture and operation inventory. No OpenAPI generator,
new dependency, or duplicate security policy was introduced.

## API Client and Component Regression Coverage

Deterministic API-client tests now cover health, workflow catalog, session
list/read/create, turn list/create, close, and delete. Every operation asserts
its exact path, method, request body, Bearer header, mutation-only CSRF header,
absence of cookies, omitted credentials, no-store caching, and no-referrer
policy.

Deterministic component tests cover session selection and turn rendering, one
pending user turn with no fabricated assistant response, successful close,
confirmed and cancelled deletion, one conflict refresh with zero mutation
retry, not-found, unavailable, and fixed-safe server states. Existing
duplicate-submission and untrusted-text behavior remains covered. Production
React behavior was not expanded.

## Validation Results

- Required Task 5D Web focused group: `225 passed`.
- Web/conversation selection: `399 passed, 1 skipped, 1845 deselected`.
- Packaging regression: `3 passed`.
- Full default Python suite: `2239 passed, 6 skipped`.
- Frontend strict TypeScript typecheck: passed.
- Frontend Vitest suite: `29 passed` across 4 files.
- Frontend production build: passed; committed packaged assets remained
  byte-identical and unchanged.
- Generated SauceDemo Playwright regressions: `2 passed`.
- Isolated `compileall` for `pmqa` and `products`: passed with bytecode outside
  the repository.
- `git diff --check`: passed.

The generated Playwright run could not launch Chromium inside the managed
macOS sandbox because Mach port registration was denied. The required suite
was rerun outside that sandbox and passed `2/2`. No new test accessed a
company system, provider, paid model, external network, or live browser.

## Remaining Risks and Scope Confirmation

The selected frontend fixture remains deliberately maintained rather than
generated. Its Python and TypeScript drift checks now make omission or rename
fail explicitly. The runtime still depends on the standard library browser
launcher and native thread lifecycle; the remediation narrows only their
documented operational failure classification.

Task 5D.2+, Task 5B, Task 6, and Task 7 were not started. No new endpoint,
route, capability, assistant execution, reasoning, workflow execution,
progress transport, hosted binding, ADO/MDE integration, or external write
was added. No PR was created and nothing was merged.

## Recommended Review Depth

**Deep**

Reason: the remediation changes fixed-safe classification at the local
browser/thread trust boundary and expands the cross-language wire-contract
guardrails used to protect that UI.

## Suggested Reviewer Focus

- Inject `webbrowser.Error`, false returns, thread-start `RuntimeError`, and
  control/resource/programming exceptions; verify classification and cleanup.
- Confirm server-body exceptions cannot be reclassified as thread-start
  failures and browser launch remains strictly after readiness.
- Compare every fixture outer/nested field and enum with the authoritative
  Python models, plus all nine API client method/path templates.
- Exercise each API client request for exact body/authentication/CSRF and
  no-cookie behavior.
- Exercise component conflict, close, delete, pending-turn, untrusted-text,
  and fixed-safe failure paths without mutation retries or fabricated output.
- Confirm the diff contains only the seven allowed implementation/test files
  plus this report and that packaged assets remain unchanged.

## Human Summary

Status: PMQA-5D.1C Attempt 2 已完成，等待 Independent Reviewer。
What Changed: 已固定安全地收敛 `webbrowser.Error` 与线程启动失败，并补齐跨语言 contract drift、APIClient 和 UI action 回归覆盖。
Risk: 变更触及浏览器/线程信任边界与手工维护的 wire fixture，建议 Deep review；未新增能力或 endpoint。
Review Result: 聚焦 225 passed、全量 2239 passed / 6 skipped、frontend 29 passed、Playwright 2 passed，所有要求验证通过。
Next Step: Independent Reviewer 从 Git 派生最新 report commit，按 Attempt 2 范围独立复核。
Action Needed From Human: 请将下方 Handoff Note 交给 Independent Reviewer。
Handoff Note: 请读取 agent-handoff/README.md 与 agent-handoff/current-task.md，从 Git 派生最新 coder-report commit，并按独立审查顺序完成 PMQA-5D.1C Attempt 2 review。
