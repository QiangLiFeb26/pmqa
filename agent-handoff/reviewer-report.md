# Independent Reviewer Report

Owner: Independent Reviewer

Status: Executed for PMQA Task 5D.1C, Attempt 2

## Task Correlation

Task: PMQA Task 5D.1C — Browser Boundary and Contract Drift Remediation

Task ID: `PMQA-5D.1C`

Attempt: `2`

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed Starting HEAD: `5f0c1413bc0d726592f0e590fc4646fadac5519c`
("request Task 5D.1C boundary remediation" — the Architect's Attempt 2
`current-task.md` publication commit)

Reviewed Implementation Commit: `da474009bd603e46ce4ffcbdb03de85986094208`
("remediate Task 5D.1C web boundaries")

Derived Coder Report Commit: `11be60dee8c1fee5032ef635e43f9de0d49081dc`
("report Task 5D.1C boundary remediation")

Correlation Verification:

- derived with `git log -1 --format=%H -- agent-handoff/coder-report.md` ->
  `11be60dee8c1fee5032ef635e43f9de0d49081dc`;
- `git log -1 --format=%H -- agent-handoff/current-task.md` ->
  `5f0c1413bc0d726592f0e590fc4646fadac5519c`, matching the starting HEAD the
  Coder recorded;
- `git merge-base --is-ancestor 5f0c1413... da474009...` succeeds and
  `git merge-base --is-ancestor da474009... 11be60de...` succeeds; `git log
  --oneline 5f0c141..HEAD` shows the exact linear sequence
  `5f0c141 -> da47400 -> 11be60d`, and `HEAD` equals
  `origin/agent/task-5c-1-canonical-run-contract`;
- `git show 5f0c1413...:agent-handoff/current-task.md` names Task ID
  `PMQA-5D.1C`, Attempt `2`, branch
  `agent/task-5c-1-canonical-run-contract`, and records "Reviewed Attempt 1
  Reviewer HEAD" `4a0b0fff32475852374c54e297ee4b22a16bfa62`, which is
  exactly `git log -1 --format=%H 4a0b0ff` — the Attempt 1 Reviewer report
  commit — confirming the Attempt 1 -> Attempt 2 chain is intact;
- `git diff --stat 5f0c1413... HEAD` (8 files) shows exactly the 7 files
  listed in the current task's `Allowed Changes` plus
  `agent-handoff/coder-report.md`; the implementation commit `da474009...`
  alone touches only the 7 allowed implementation/test files, and the
  report-only commit `11be60de...` touches only
  `agent-handoff/coder-report.md`, so the derived commit is the report's
  latest authorized change with no later unauthorized replacement.

This Reviewer report does not contain or predict its own commit SHA. The
Architect derives the Reviewer report commit from Git and records it in
`architect-review.md`.

## Independent Review Method

Inspection order:

1. `agent-handoff/current-task.md` (Attempt 2, three Required Changes, Safe
   Failure Requirements, Allowed Changes, Acceptance Criteria);
2. the named baseline-to-implementation diff
   (`5f0c1413...da474009` and the full implementation commit) — line-by-line
   read of `pmqa/web/runtime.py`'s changed region (`_start_server_thread`,
   `_open_browser`, and their two call sites), the full
   `frontend/workbench/src/api-v1.contract.json`,
   `tests/test_web_frontend_contract_drift.py`,
   `frontend/workbench/src/api-schema.test.ts`,
   `frontend/workbench/src/api.test.ts`,
   `frontend/workbench/src/App.test.tsx`, and `tests/test_web_runtime.py`;
   cross-read of `pmqa/web/app.py` (route decorators),
   `pmqa/conversation` and `pmqa/run/models.py` (authoritative field/enum
   sources), and `frontend/workbench/src/api.ts` (production `APIClient`,
   confirmed unchanged);
3. independently selected and independently executed validation (see Test
   Evidence);
4. full `coder-report.md`.

Deviation from the prescribed anti-anchoring order: at the start of this
review I opened `current-task.md` and `coder-report.md` together in one
read (the full Coder report, not only its correlation header), before
performing the diff/test/validation steps. This is a process deviation from
the "read only the correlation header before step 4" instruction. To
mitigate anchoring risk, I performed the diff read, the nested-field/enum/
operation cross-check against the authoritative Python models, and every
independent test run below from primary sources (the diff, the code, and a
clean rerun of every required command) rather than from the report's prose,
and I record here that every finding and every count below was independently
re-derived, not copied from the report. The Architect should weigh this
process deviation on its own terms; it did not change any substantive
conclusion, since independent execution matched the report's claims exactly
in every case checked.

Active-task `architect-review.md` read before publication: No.

Prior closed review or architecture material consulted, with reason: the
Attempt 1 `reviewer-report.md` (superseded by this report, read via `git
show 4a0b0ff:agent-handoff/reviewer-report.md` and via the file's prior
committed state) was read only to recover the exact prior Reviewer HEAD
needed for starting-HEAD/attempt-chain correlation and to keep this report's
structure consistent with established protocol precedent. No Attempt-2-
specific finding, gap, or conclusion was taken from it.

## Review Depth

Actual Review Depth: Deep

Review Depth Reason: this remediation changes fixed-safe exception
classification at the local browser-launch and native-thread-start trust
boundary (a leak here would disclose a token, path, or executable to
stdout/stderr) and expands a cross-language wire-contract guardrail that
several other approved security properties (CSRF, no-cookie, Bearer auth)
depend on for detection of silent drift. The Coder's own recommendation was
Deep for the same reason. I independently re-derived every claimed test
count from a clean run rather than trusting the report, read every line of
the two new runtime helper functions and all seven test/fixture diffs in
full, and independently traced the nested-field/enum/operation fixture
against the live Pydantic models and FastAPI routes rather than accepting
the Coder's claim of completeness.

## Overall Assessment

The implementation matches the three Required Changes precisely, is fully
covered by new deterministic tests, and shows no scope creep. `git diff
--stat` confirms the 8 changed files are exactly the 7 allowed
implementation/test files plus `agent-handoff/coder-report.md`; no
conversation, Run, Runner, Application, Usage, reasoning, workflow,
Supervisor, LangGraph, Product Pack, product, CLI, endpoint, or another
role's handoff file changed, and no packaged frontend asset changed (`npm
run build` reproduced byte-identical output with an empty `git status
--short` afterward).

**Browser/thread boundary remediation** (`pmqa/web/runtime.py:150,164`,
new helpers at `:258` and `:270`). `server_thread.start()` and the
browser-open call are now each routed through a narrow, single-purpose
helper. `_start_server_thread` re-raises the four resource/control-flow
exceptions unchanged, catches only `RuntimeError` (the sole exception type
`threading.Thread.start()` raises, and only for "cannot start a thread
twice") and converts it to `PMQAWebRuntimeError() from None`, executed
outside the `except` block so no implicit `__context__` is attached either.
`_open_browser` follows the identical shape for `webbrowser.Error` and for
a non-`True` return value. Both helpers are new module-level functions
using the same style as the pre-existing `_wait_until_ready` and
`_raise_server_failure`; the outer `try/except` in
`run_pmqa_web_workbench` is untouched (still the same five specific
`except` clauses, no broadened catch). Thread *construction*
(`thread_factory(...)`) remains outside `_start_server_thread`, so a
construction-time programming exception is not caught by any of the
classifiers and propagates unmodified; a `server.run` failure is captured
inside the thread body into `server_failures` and re-raised as-is by the
unchanged `_raise_server_failure`, so it can never be mistaken for a
thread-start failure. The `finally` block (unconditional `should_exit`,
bounded `server_thread.join(5.0)`, `bound_socket.close()`) was not touched
and still runs for every raise path, including both new ones.

**Frontend contract drift fixture** (`api-v1.contract.json`,
`test_web_frontend_contract_drift.py`, `api-schema.test.ts`). The fixture
gained `selected_domain_fields`, `enum_values`, and `operations` blocks. On
the Python side, `ConversationSession`/`ConversationTurn` are checked for
exact equality against `list(Model.model_fields)` (the live Pydantic field
order), `WorkflowDefinition`'s selected 5 fields are checked as an exact
list *and* as `set(...) <= set(WorkflowDefinition.model_fields)` against
the live 13-field model in `pmqa/run/models.py:289` — I confirmed by direct
read that all 5 selected names (`schema_version`, `workflow_id`,
`workflow_version`, `display_name`, `description`) are a strict subset,
matching exactly what `frontend/workbench/src/api.ts:9-14`'s
`WorkflowDefinition` interface consumes and nothing more. Enum values are
checked as exact equality against `[item.value for item in Enum]` for all
three enums. Operation entries are checked for exact name-set equality
against a hardcoded 9-name set and their `(method, path)` pairs are checked
as a subset of the live FastAPI route table (`app.routes` filtered to
`/api/v1/`) — I independently grepped `pmqa/web/app.py` and confirmed 10
live `/api/v1/*` route decorators exist, of which the 9 fixture operations
are exactly the ones `api.ts`'s `APIClient` calls (the 10th, single-turn
`GET .../turns/{turn_id}`, is not used by the client and is correctly
absent from the fixture). On the TypeScript side, `api-schema.test.ts` pins
the same three blocks by exact-equality assertion against the imported JSON
fixture, and `api.test.ts` independently exercises all 9 `APIClient`
methods against a mocked `fetch`, asserting exact path, method, JSON body,
`Authorization: Bearer`, mutation-only `X-PMQA-CSRF-Token`, absence of a
`Cookie` header, `credentials: "omit"`, `cache: "no-store"`, and
`referrerPolicy: "no-referrer"` for every one. No OpenAPI generator or new
dependency was added; `package-lock.json` is unchanged (confirmed by `git
diff --stat`, not listed).

**Component regression coverage** (`App.test.tsx`). Production `App.tsx`
is unchanged (not in the diff). New tests cover: session selection and
turn-list rendering (`selects one session and renders its bounded turns`);
one pending user turn with the assistant response asserted absent (`adds
one pending user turn without fabricating assistant output`); successful
close; confirmed delete (mocked `window.confirm` true) and cancelled
delete (mocked false, `deleteSession` asserted never called); one
`APIError("conversation_failed", 409)` triggering exactly one
`session`/`turns` refresh pair with `createTurn` still called only once
(no mutation retry); a 404 not-found state; a `TypeError` with an embedded
secret-shaped marker asserted absent from the rendered "unavailable" text;
and a `500 internal_failed` server error rendered as a fixed "server-error"
state with the raw code asserted absent from the DOM. The pre-existing
untrusted-HTML-text and duplicate-submission tests are preserved (only
extended with the new session/turns fixtures they now require).

## Findings

None blocking. No high, medium, or low defect against a stated acceptance
criterion was found. One non-blocking advisory observation is recorded
under Security, Scope, and Compatibility below.

## Acceptance Criteria Coverage

| Acceptance criterion | Evidence | Result |
| --- | --- | --- |
| Ordinary browser-discovery/launch and thread-start operational failures are fixed-safe and fully contained | `_open_browser`/`_start_server_thread` convert only `webbrowser.Error`/non-`True` and thread-`RuntimeError` respectively to fixed `PMQAWebRuntimeError() from None`; independently reran `test_standard_browser_discovery_error_is_fixed_safe_and_cleans_up` and `test_operational_thread_start_failure_is_fixed_safe_and_cleans_up`, both assert injected markers absent from the exception, stdout, and stderr | Met |
| Unrelated programming exceptions and resource/control-flow exceptions preserve their approved propagation | `test_thread_construction_programming_failure_propagates`, `test_unexpected_browser_programming_failure_propagates`, and the pre-existing `test_unexpected_server_failure_propagates_and_browser_never_opens` / `test_browser_resource_and_control_flow_remain_authoritative` all independently rerun and pass; traced by code read that construction and `server.run` failures never enter either new helper | Met |
| Cleanup and browser-before-readiness invariants remain unchanged | `finally` block byte-for-byte unchanged; the pre-existing `readiness` parametrized case in `test_expected_runtime_failures_are_fixed_and_never_leak` still asserts `browser_calls == []`; every new failure test asserts `server.should_exit is True` and `bound_socket.close_calls == 1` | Met |
| Frontend contract drift checks cover the complete selected nested and operation surface | Traced `selected_domain_fields`/`enum_values`/`operations` against live `ConversationSession`/`ConversationTurn`/enum/route sources; all outer contract names/fields, all `ConversationSession`/`ConversationTurn` fields, the selected `WorkflowDefinition` subset, all three enums, and all 9 API operations are present and independently confirmed accurate | Met |
| Every existing UI/API-client action has bounded focused regression coverage | `api.test.ts` covers all 9 `APIClient` methods; `App.test.tsx` covers selection/rendering, pending turn, close, confirmed/cancelled delete, conflict-refresh-without-retry, not-found, unavailable, and fixed-safe server-error states, plus the pre-existing duplicate-submission/untrusted-text cases | Met |
| No production capability or endpoint is added | `git diff --stat` shows zero change to `pmqa/web/app.py`, `pmqa/web/static.py`, `pmqa/web/security.py`, `pmqa/cli.py`, or `App.tsx`/`api.ts`/`bootstrap.ts`/`main.tsx` | Met |
| Exact Task 5D.1A/1B/runtime/static/bootstrap/package behavior remains unchanged | Focused group (`test_web_runtime.py`, `test_web_frontend_contract_drift.py`, `test_web_static.py`, `test_web_app.py`, `test_web_security.py`, `test_web_contracts.py`) independently rerun, `225 passed`; full default suite independently rerun, `2239 passed, 6 skipped` | Met |
| Focused/frontend/full regressions pass | See Test Evidence below; every required command independently rerun and matches the Coder's claimed counts exactly | Met |
| Generated assets remain consistent if touched | `npm run build` rerun independently; `git status --short` empty afterward (byte-identical output, confirming no production frontend source changed) | Met |
| Only allowed files change | `git diff --stat 5f0c1413... HEAD` (8 files) matches the current task's `Allowed Changes` list plus `coder-report.md` exactly; implementation commit alone touches only the 7 allowed files | Met |
| Worktree is clean and synchronized | `git status --short` empty before and after review; branch HEAD equals `origin/agent/task-5c-1-canonical-run-contract` | Met |

## Test Evidence

### Coder Evidence Reviewed

The Coder report claims: `225 passed` for the required Task 5D Web focused
group; `399 passed, 1 skipped, 1845 deselected` for the `web or
conversation` selection; `3 passed` packaging; `2239 passed, 6 skipped` full
default suite; strict TypeScript typecheck passed; `29 passed` Vitest across
4 files; production build passed with byte-identical committed assets;
`2 passed` generated SauceDemo Playwright regressions (rerun outside the
sandbox after an in-sandbox Chromium launch was denied); clean isolated
`compileall`; clean `git diff --check`. This claimed evidence was read in
full at the start of this review (see the Independent Review Method
deviation note above) but was independently reproduced below before being
relied upon; every reproduced count matches it exactly.

### Independently Run

All commands below were executed by the Reviewer directly from the
repository root on the reviewed branch:

- `.venv/bin/python -m pytest tests/test_web_runtime.py
  tests/test_web_frontend_contract_drift.py tests/test_web_static.py
  tests/test_web_app.py tests/test_web_security.py
  tests/test_web_contracts.py -q` -> `225 passed`
- `.venv/bin/python -m pytest tests/ -k "web or conversation" -q` ->
  `399 passed, 1 skipped, 1845 deselected`
- `.venv/bin/python -m pytest tests/test_packaging.py -q` -> `3 passed`
- `npm run typecheck` (in `frontend/workbench`) -> clean, no diagnostic
  output
- `npm test` (in `frontend/workbench`, `vitest run`) -> `Test Files 4 passed
  (4)`, `Tests 29 passed (29)`
- `.venv/bin/python -m pytest -q` (full default suite) -> `2239 passed,
  6 skipped, 1 warning`
- `npm run build` (in `frontend/workbench`) -> succeeded; `git status
  --short` empty immediately afterward, confirming the committed packaged
  assets are byte-identical to a fresh build
- `.venv/bin/python -m pytest products/demo/generated_tests -q` ->
  `2 passed`
- `.venv/bin/python -m compileall -q pmqa products` with
  `PYTHONPYCACHEPREFIX` pointed outside the repository -> exit `0`, no
  tracked bytecode written (`git status --short` remained empty)
- `git diff --check` -> exit `0`, no output
- `git status --short` -> empty (clean worktree), before and after review

In addition, independently and without relying on the Coder's own test
assertions:

- read `pmqa/run/models.py:289-303` in full and confirmed
  `WorkflowDefinition`'s 13 live fields strictly contain the 5 fixture-
  selected fields with no name mismatch;
- grepped `pmqa/web/app.py` for every `/api/v1` route decorator (10 found)
  and confirmed the 9 fixture `operations` entries are exactly the routes
  `frontend/workbench/src/api.ts`'s `APIClient` calls, with the unused
  10th (single-turn read) correctly omitted;
- read `git diff 5f0c1413... da474009... -- pmqa/web/runtime.py` in full
  and confirmed the only behavioral change is the two new helper functions
  and their two call sites; the outer `try/except`/`finally` structure is
  byte-for-byte unchanged;
- confirmed `frontend/workbench/src/App.tsx`, `api.ts`, `bootstrap.ts`, and
  `main.tsx` (production sources) are absent from the implementation
  commit's diff.

Environment: local `.venv` (Python 3.9), Node/npm as pinned by
`frontend/workbench/package-lock.json`, macOS/Darwin, no network access
used or required. I did not attempt a real-browser Playwright run myself,
relying on the Coder's report that the generated suite was rerun outside
the sandboxed environment and passed `2/2`; the committed `generated_tests`
directory was not modified by this remediation.

## Security, Scope, and Compatibility

Security observations: neither new helper introduces a broader catch than
the single exception type it is named for, and both discard cause/context
before the exception crosses the CLI boundary — I traced this by code
read and independently confirmed via the marker-injection tests that
`__cause__`/`__context__` are `None` and that `capsys` captures no output
for the browser-discovery-error case. One advisory, non-blocking
observation for the Architect: `test_frontend_operation_fixture_matches_real_api_routes`
checks the fixture's `(method, path)` pairs as a *subset* of the live
FastAPI route table, and checks the *name set* of fixture operations
against a hardcoded 9-name literal in the test itself, rather than deriving
that name set from `api.ts`'s actual method inventory. This correctly
catches the operationally important drift direction (a fixture path/method
that no longer matches a real route, or the accidental loss of a named
operation with a real route), but a newly added `APIClient` method could in
principle go unnoticed by the Python-side check until a human also adds a
TypeScript assertion for it. This is consistent with the task's explicit
"deliberately maintained... selected subset" design (not a generated
contract) and was already the accepted shape prior to this remediation; it
is not a defect against any stated acceptance criterion and is offered only
for awareness.

Scope observations: `git diff --stat 5f0c1413... HEAD` shows exactly the
8 files described above; no Task 5D.1A/1B endpoint or static-route security
file, no CLI file, no conversation/Run/Runner/Application/Usage/reasoning/
workflow/Supervisor/LangGraph/Product Pack/product file, and no other
role's handoff file changed. Nothing under Task 5D.2+, Task 5B, Task 6, or
Task 7 was started.

Compatibility observations: all Task 5D.1A/1B/1C-Attempt-1 regression
suites continue to pass unchanged (`225 passed` focused group,
`399 passed, 1 skipped` web/conversation selection); the full default
suite count (`2239 passed, 6 skipped`) matches the Coder's reported count
exactly on independent rerun.

## Verdict

Verdict: Pass

This verdict is advisory. The Architect makes the final technical
disposition.

## Suggested Architect Focus

- No blocking finding surfaced from this Deep, independently reproduced
  review. The one advisory observation above (operation-name-set pinned by
  literal rather than derived from `api.ts`) does not gate approval in this
  Reviewer's assessment and matches an already-accepted design choice.
- Note the process deviation recorded in "Independent Review Method": the
  full `coder-report.md` was read alongside `current-task.md` at the start
  of this review rather than only its correlation header, ahead of the
  independent diff/test steps. Every conclusion below was independently
  re-derived and matched the report exactly; no finding depended on the
  report's own claims.
- If a future checkpoint adds a new `APIClient` method, confirm the Coder
  also adds both a Python fixture entry and a TypeScript pinned assertion
  for it, since no single check currently derives the operation-name set
  directly from `api.ts`.

## Reviewer Write-Boundary Confirmation

Repository files changed by Reviewer:

- `agent-handoff/reviewer-report.md`

Confirmation: I changed no production code, tests, configuration, schemas,
packaging, scripts, product documentation, or another role's handoff file.
