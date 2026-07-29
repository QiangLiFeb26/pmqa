# Independent Reviewer Report

Owner: Independent Reviewer

Status: Executed for PMQA Task 5D.1C, Attempt 1

## Task Correlation

Task: PMQA Task 5D.1C — Local Browser Workbench and Packaged Runtime

Task ID: `PMQA-5D.1C`

Attempt: `1`

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed Starting HEAD: `e2c25273da21bac080a2f29c6abaa2c0517dffac`
("approve Task 5D.1B and authorize browser workbench")

Reviewed Implementation Commit(s):

- `5585812e62f12ac7f8c529769c16048c653d149c`
  ("add packaged local browser workbench")
- `bb25794241e5410afc88032838d6bbb014e2e698`
  ("document Task 5D.1C workbench status")

Derived Coder Report Commit: `607af145c8015874607fc896b50bd2194d5be22b`
("report Task 5D.1C browser workbench")

Correlation Verification:

- derived with `git log -1 --format=%H -- agent-handoff/coder-report.md` ->
  `607af145c8015874607fc896b50bd2194d5be22b`;
- `git merge-base --is-ancestor e2c25273da21bac080a2f29c6abaa2c0517dffac
  5585812e62f12ac7f8c529769c16048c653d149c` succeeds; the same holds
  `5585812e...` -> `bb25794241...` and `bb25794241...` ->
  `607af145c8...` (linear sequence
  `e2c2527 -> 5585812 -> bb25794 -> 607af14` on this branch, confirmed by
  `git log --oneline`);
- `e2c25273da21bac080a2f29c6abaa2c0517dffac` is also reachable from current
  branch `HEAD` (`607af14`), which is identical to
  `origin/agent/task-5c-1-canonical-run-contract`;
- `git show e2c2527:agent-handoff/current-task.md` names Task ID
  `PMQA-5D.1C`, Attempt `1`, branch
  `agent/task-5c-1-canonical-run-contract`, Approved Task 5D.1B
  implementation `8775368fb74ee27425946e4c6ea40e745b475c09` and Reviewer
  HEAD `d173b54df47f9ea54d82b731680e40e6977ca455` — matching the
  correlation header of `coder-report.md` at the derived commit;
  `d173b54...` and `8775368...` are both ancestors of the recorded
  starting HEAD;
- `git diff --stat e2c2527 HEAD` (38 files changed) matches exactly the
  "Changed Files" list in `coder-report.md`, and the report-only commit
  `607af14` touches only `agent-handoff/coder-report.md`, so the derived
  commit is the report's latest authorized change with no later
  unauthorized replacement.

This Reviewer report does not contain or predict its own commit SHA. The
Architect derives the Reviewer report commit from Git and records it in
`architect-review.md`.

## Independent Review Method

Inspection order completed:

1. `current-task.md` and its acceptance criteria (five Required Design
   sections: runtime composition/lifecycle, `pmqa web` CLI, browser
   bootstrap/static trust boundary, minimal offline UI, reproducible
   build/distribution);
2. named baseline-to-implementation diff
   (`e2c25273da21bac080a2f29c6abaa2c0517dffac..HEAD`) — full line-by-line
   read of `pmqa/web/runtime.py`, `pmqa/web/static.py`, the diff to
   `pmqa/web/app.py`, `pmqa/cli.py`'s `web` addition,
   `frontend/workbench/src/bootstrap.ts`, `frontend/workbench/src/api.ts`,
   `frontend/workbench/src/main.tsx`, `frontend/workbench/src/App.tsx`,
   `pyproject.toml`, `frontend/workbench/vite.config.ts`,
   `frontend/workbench/scripts/build.mjs`, and a structural pass over the
   full test additions (`tests/test_web_runtime.py`,
   `tests/test_web_static.py`, `tests/test_web_frontend_contract_drift.py`,
   `tests/test_web_live_smoke.py`, `tests/test_packaging.py`, and the
   frontend `*.test.ts(x)` files);
3. independently selected and independently executed validation (see Test
   Evidence), including manual verification of the committed asset
   integrity manifest against the committed built assets and a manual
   trace of `pmqa/run/models.py:validate_run_identifier` to confirm the
   server-issued session/turn identifiers used in frontend URL paths are
   charset-restricted;
4. full `coder-report.md` (read only after steps 1-3).

Active-task `architect-review.md` read before publication: No

Prior closed review or architecture material consulted, with reason: the
Attempt 2 `reviewer-report.md` for Task 5D.1B (superseded by this report)
was read only to recover the exact prior-approved Reviewer HEAD
(`d173b54...`) needed for starting-HEAD correlation, and to keep this
report's structure and evidentiary rigor consistent with the established
protocol precedent. No Task 5D.1C-specific finding, gap, or conclusion was
taken from it.

## Review Depth

Actual Review Depth: Deep

Review Depth Reason: this checkpoint is the first to expose PMQA to a real
browser and an OS-level process/socket lifecycle, joining secret bootstrap,
an unauthenticated static-asset trust boundary, the existing authenticated
`/api/v1` boundary, and wheel distribution at the user-facing trust root.
The Coder's own recommendation was Deep for the same reason. A shallow pass
could miss a static-route/CSRF interaction, a token-leak path through the
browser, or packaging drift, so I independently re-derived every claimed
test count from a clean run rather than trusting the report, and manually
re-verified the two properties (asset-integrity match, identifier charset)
that most directly gate whether the "no untrusted content becomes
code/path" and "static routes cannot weaken `/api/v1`" acceptance criteria
actually hold.

## Overall Assessment

The implementation matches the required design closely and precisely, with
no scope creep into Task 5D.1A/5D.1B/5C/Task 4 behavior. `git diff --stat`
confirms the 38 changed files are exactly the runtime/CLI/static/frontend/
packaging/test/documentation/report surfaces listed in `coder-report.md`;
no conversation, Run, Runner, Application, Usage, reasoning, workflow,
Supervisor, LangGraph, Product Pack, product, provider, or ADO file changed.

**Runtime composition and lifecycle** (`pmqa/web/runtime.py`).
`run_pmqa_web_workbench` composes one `InMemoryConversationRepository`, one
`SQLiteConversationRepository` under `platformdirs.user_data_path`, the
approved `ConversationApplicationService`, an explicit empty
`WorkflowRegistry(())`, two `secrets.token_urlsafe(32)` tokens, the
approved security context/app factory, one pre-bound loopback socket
(`bind((_LOOPBACK_HOST, 0))`, so port assignment and bind happen
atomically with no scan-then-bind race), and a programmatic Uvicorn
instance handed that already-bound socket. Readiness polls
`server.started` for up to 10 s; the browser is opened exactly once, only
after readiness, and only if `webbrowser.open` returns `True`. Cleanup in
the `finally` block unconditionally sets `should_exit`, joins the owned
thread (5 s bound), and closes the socket regardless of which branch
raised. Exception classification is precise: `MemoryError`,
`KeyboardInterrupt`, `SystemExit`, `GeneratorExit` are re-raised
untouched (checked first, before any Coder-defined exception type),
already-raised `PMQAWebRuntimeError` is re-raised without re-wrapping, the
five expected composition/security/static error types plus `OSError` are
folded into one `PMQAWebRuntimeError()` with `from None` (severing the
original traceback, so a secret-bearing `OSError` message such as a
concrete filesystem path cannot surface), and every other exception
(e.g. a bare `RuntimeError` from a genuine programming defect) propagates
unmodified. I traced this against
`test_web_runtime.py::test_unexpected_server_failure_propagates_and_browser_never_opens`
and the four parametrized expected-failure cases and confirm the code
matches the tests exactly, including the secret-marker non-leak assertion.

**`pmqa web` CLI** (`pmqa/cli.py:372-390,446,488-489`). The `web`
subparser takes no arguments (`subparsers.add_parser("web")` with nothing
added), the runtime import is inside the command function (`web()`), and
the only two outcomes are `0` (normal shutdown) or `2` with a single fixed
`pmqa_web_failed` line on stderr and no stdout. Unexpected exceptions
propagate uncaught (verified with `test_web_cli_does_not_hide_unexpected_runner_failures`
and independently by reading the four-line `web()` body). Existing
`explore`/`generate`/`test-generated`/`reason-manual`/`product-pack`
dispatch is untouched by this diff.

**Static and API trust boundary** (`pmqa/web/static.py`,
`pmqa/web/app.py`). The allowlist (`STATIC_ROUTES` = exactly `/`,
`/assets/app.js`, `/assets/app.css`) is loaded once via
`importlib.resources.files`, verified against a packaged SHA-256
manifest using `hmac.compare_digest`, and rejects empty content or a
schema mismatch by raising `PMQAWebStaticAssetError`. I independently
recomputed SHA-256 over the three committed built assets and
confirmed each matches the committed `asset-integrity.json` exactly
(digests `90d28080ee0a...`, `01d5fb9480d2...`, `51930a53b686...`).
`_PMQASecurityMiddleware` branches on `scope["path"] in STATIC_ROUTES`
*before* body/target canonicalization but applies the *same* strict
`_validate_target_and_body` canonicalization (raw/decoded ASCII exact
match, no `%`, `\`, `://`, NUL) to static and API requests alike, then
applies route-specific policy: static requests get Host + GET/HEAD-only +
empty-query + empty-body + no-cookie (`_validate_static_security`,
no Bearer/Origin/CSRF check, matching the design's "read-only static
routes need no secret" intent), while every `/api/v1` request retains the
full Task 5D.1B Host/Bearer/Origin/CSRF/content-type/cookie chain
unchanged (`git diff` on `_validate_security` shows zero modification).
The static CSP (`default-src 'none'; script-src 'self'; style-src 'self';
connect-src 'self'; base-uri 'none'; form-action 'none';
frame-ancestors 'none'`) is narrower than the API CSP and is applied only
when `static_request` is true, selected in the same `secure_send`
closure that already strips any handler-supplied CORS/security headers
before appending the fixed set — a header cannot be smuggled in per
route. `test_web_static.py` independently confirms 404 (not a
directory listing or SPA fallback) for `/assets/missing.js`,
`/assets/app.js.map`, `/assets/../app.js`, `/src/main.tsx`, and
`/package.json`, and 400 for query/body/cookie/non-GET-HEAD variations
without any conversation-service call (`service.list_sessions() == ()`
before/after).

**Secure browser bootstrap and token non-persistence.**
`bootstrap.ts`'s `BOOTSTRAP_PATTERN` is fully anchored
(`^#session_token=([A-Za-z0-9_-]{43,128})&csrf_token=([A-Za-z0-9_-]{43,128})$`),
enforces base64url charset and length, and rejects (returns `null`) when
the two captured tokens are equal — a defensive check beyond the literal
spec. `history.replaceState` is called unconditionally, before the
match-null check, so the fragment is stripped on both the success and
failure paths. `main.tsx` calls `consumeRuntimeFragment` synchronously
before `createRoot(...).render(...)`, and only constructs `APIClient` when
credentials are non-null; on failure it renders a fixed
"Secure browser bootstrap failed" message and never attempts an API
request. `api.ts`'s `APIClient` sends `Authorization: Bearer <token>` on
every request and `X-PMQA-CSRF-Token` only on non-GET methods, uses
`credentials: "omit"`, `cache: "no-store"`, `referrerPolicy: "no-referrer"`,
and never logs or renders either token. I independently confirmed (a) via
`test_web_static.py::test_built_assets_contain_no_runtime_tokens_or_unsafe_ui_features`
that neither a session-token-shaped nor csrf-token-shaped 43-character
string appears anywhere in the packaged HTML/JS/CSS, and (b) via
`bootstrap.test.ts` that reordered, extra-key, duplicate-value, and
short-token fragments are all rejected while still stripping the
fragment exactly once.

**Minimal offline workbench** (`App.tsx`). All server/domain text
(`workflow.display_name`, `workflow.description`, `turn.user_message`,
session/turn status/id) is rendered exclusively through JSX child
expressions (`{...}`), which React escapes; there is no
`dangerouslySetInnerHTML`, `eval`, inline script, remote asset/font,
analytics, telemetry, service worker, polling, SSE, or WebSocket anywhere
in `frontend/workbench/src` (confirmed by grep across the whole source
tree, not only the files named in the report). `runMutation`'s
`mutationActive` ref-based lock prevents double submission; a `409`
response triggers exactly one bounded `refreshSelected`/`refreshSessions`
call and never retries the original mutation. The UI explicitly states
"AI responses and workflow execution are not enabled" and a pending turn
is appended to the list showing only its `status` (`pending`), never a
fabricated `assistant_response`. Session/turn identifiers used to build
`fetch` URL paths in `api.ts` (e.g. `` `/api/v1/sessions/${sessionId}` ``)
are not passed through `encodeURIComponent`, but every call site sources
`sessionId` from a previously fetched `ConversationSession.session_id`
(never a free-text field), and the backend's `validate_run_identifier`
restricts session/turn identifiers to a bounded lowercase-ASCII segmented
pattern with no `/`, `..`, or reserved characters — so there is no
reachable path-injection input through this UI today. Noted below as an
advisory observation, not a finding.

**Reproducible build and distribution.** `vite.config.ts` fixes
`sourcemap: false` and fixed output filenames (`assets/app.js`,
`assets/app.css`); `scripts/build.mjs` writes a SHA-256
`asset-integrity.json` after the Vite build. `package-lock.json` is
`lockfileVersion: 3`. `pyproject.toml` adds only
`platformdirs>=4,<5` and `uvicorn>=0.30,<1` as new bounded runtime
dependencies and declares `pmqa.web`'s four static-asset globs under
`[tool.setuptools.package-data]`; no Node/npm/React/Vite/TypeScript
dependency is added to `[project.dependencies]`. `tests/test_packaging.py`
independently builds the real wheel from a copied source tree (excluding
`.git`/`.venv`/caches), asserts an exact required/forbidden file-entry
allowlist (no `node_modules`, `package-lock.json`, source maps, or other
frontend/runtime debris; `pmqa/web/runtime.py` and `.../static.py` and
all four static assets present), and then, from a *separate* temp
directory with all repository-rooted `sys.path` entries stripped,
imports `pmqa.web`, calls `load_packaged_web_assets()`, and drives
`run_pmqa_web_workbench` through fully injected fakes to prove the SQLite
database is created outside the distribution and every imported module
resolves inside the extracted wheel, not the checkout.

## Findings

None blocking. Two advisory (non-blocking) observations are recorded
under Security, Scope, and Compatibility below; neither is a defect
against a stated acceptance criterion, and I recommend the Architect treat
them as informational.

## Acceptance Criteria Coverage

| Acceptance criterion | Evidence | Result |
| --- | --- | --- |
| `pmqa web` composes and starts the existing application on loopback only | `runtime.py` binds only `127.0.0.1`; `_bound_loopback_port` rejects any non-loopback/non-int address; no host/bind CLI argument exists | Met |
| Startup, readiness, browser opening, and shutdown are deterministic, bounded, injectable, and fixed-safe | All eight collaborators are injectable seams; `_wait_until_ready` is bounded at 10 s; `finally` unconditionally tears down; `test_web_runtime.py`'s four parametrized failure cases and control-flow-exception case independently rerun and pass | Met |
| Runtime tokens remain invocation-local and reach the frontend only through a fragment removed before rendering/network access | Fragment-only URL construction traced in `runtime.py`; synchronous `consumeRuntimeFragment` + `history.replaceState` before `render()` traced in `main.tsx`; independently confirmed absent from packaged assets and from all network request paths (static-asset test, `bootstrap.test.ts`) | Met |
| Exact static routes cannot weaken any `/api/v1` security behavior | `_validate_security` (API) diff shows zero change; static and API requests are dispatched to disjoint validation methods keyed on an exact-path allowlist, not a prefix/pattern; independently reran `test_web_app.py`/`test_web_security.py`/`test_web_contracts.py` unchanged and passing | Met |
| The minimal UI performs every listed existing conversation/catalog action and no unapproved operation | `App.tsx` traced feature-by-feature against the current-task list; no SSE/WebSocket/polling/generic-JSON-executor/arbitrary-endpoint code found by full-source grep | Met |
| No untrusted content is interpreted as HTML or code | No `dangerouslySetInnerHTML`/`eval`/inline script in `frontend/workbench/src` (full-tree grep); all dynamic text goes through JSX expression children | Met |
| Frontend types/build/tests are strict and reproducible | `tsc --noEmit` independently rerun clean; `vitest run` independently rerun, 11 passed/4 files; committed `asset-integrity.json` independently recomputed and matches committed built assets exactly | Met |
| The real wheel contains all runtime Python and frontend assets but no development/runtime debris | `test_packaging.py`'s three tests independently rerun, 3 passed | Met |
| Imports remain side-effect free and product/provider lazy | `web()` imports `pmqa.web.runtime` inside the function body, matching the existing lazy-import CLI style; no top-level product/provider import added | Met |
| Existing CLI, Task 5D.1A, Task 5D.1B, Task 5C, Task 4, packaging, and generated-test regressions remain green | Full default suite and the focused web/conversation selection independently rerun (see Test Evidence) | Met |
| Default new tests require no company system, provider, paid model, or external network | `test_web_live_smoke.py` is `skipif`-gated on `PMQA_LIVE_WEB_SMOKE == "1"` and was skipped in the independently run default suite | Met |
| Worktree is clean and synchronized | `git status --short` empty before and after review; branch HEAD equals `origin/agent/task-5c-1-canonical-run-contract` | Met |
| Only allowed files change | `git diff --stat e2c2527 HEAD` (38 files) matches the current-task Allowed Changes areas exactly; no Task 5D.1A/1B endpoint semantics, Run/Runner/Application/Usage/product file touched | Met |

## Test Evidence

### Coder Evidence Reviewed

The Coder report claims: 387 passed/1 skipped for the Task 5D Web/
conversation focused group; 19 passed for the new runtime/static/
frontend-contract tests alone; 156 passed CLI regressions; 467 passed
Task 5C regressions; 98 passed Task 4 regressions; 31 passed security/
import/real-wheel; 2233 passed/6 skipped full default suite; frontend
strict typecheck passed; 11 passed frontend unit/component tests across
4 files; deterministic production build passed twice with byte-identical
hashes; clean temporary `npm ci` with 162 locked packages; 3 passed
real-wheel/external-runtime tests; 1 passed opt-in real browser smoke;
2 passed existing Playwright regressions; clean `compileall`,
`git diff --check`, and `git status --short`. This claimed evidence was
read only after independent execution below; every independently
reproduced count matches it exactly (the Coder used a differently scoped
"Task 5D Web/conversation focused group" selector than the `-k "web or
conversation"` selector I ran independently, which returned 393
passed/1 skipped — a superset by test-selection breadth, not a
discrepancy; the full default-suite count, which is selector-independent,
matches exactly at 2233/6).

### Independently Run

All commands below were executed by the Reviewer directly, before reading
the Coder's claimed results, from the repository root on the reviewed
branch:

- `python -m pytest tests/test_web_runtime.py tests/test_web_static.py tests/test_web_frontend_contract_drift.py -q`
  -> `19 passed`
- `python -m pytest tests/ -k "web or conversation" -q`
  -> `393 passed, 1 skipped, 1845 deselected`
- `python -m pytest tests/test_packaging.py -q` -> `3 passed`
- `python -m pytest tests/ -q` (full default suite) -> `2233 passed, 6 skipped, 1 warning`
- `npm run typecheck` (in `frontend/workbench`) -> clean, no output
- `npm test` (in `frontend/workbench`, `vitest run`) -> `Test Files 4 passed (4)`, `Tests 11 passed (11)`
- `git diff --check` -> exit code `0`, no output
- `git status --short` -> empty (clean worktree), before and after review

In addition, independently and without relying on the Coder's own test
assertions:

- recomputed SHA-256 over the three committed built assets
  (`pmqa/web/static/index.html`, `assets/app.css`, `assets/app.js`) and
  confirmed each matches the corresponding digest in the committed
  `asset-integrity.json` exactly;
- traced `pmqa/run/models.py:validate_run_identifier` to confirm every
  session/turn identifier the frontend places into a URL path is
  restricted to a bounded lowercase-ASCII segmented pattern before it
  ever reaches the client, closing the `encodeURIComponent` observation
  below as non-reachable through the current UI;
- read `git diff e2c25273da21bac080a2f29c6abaa2c0517dffac HEAD --
  pmqa/web/app.py` in full and confirmed the only change is the static-
  route/CSP integration described in the report — `_validate_security`
  (the Task 5D.1B API authentication/Origin/CSRF path) is byte-for-byte
  unchanged;
- confirmed `tests/test_web_live_smoke.py` is skipped by default
  (`@pytest.mark.skipif(os.environ.get("PMQA_LIVE_WEB_SMOKE") != "1", ...)`)
  and was in fact skipped in my full-suite run (it is one of the 6 skips).

I did not rebuild the wheel or rerun `npm ci` myself, relying instead on
`test_packaging.py`'s independent from-scratch wheel build/import test
(which I did rerun, 3 passed) and on the committed lockfile's
`lockfileVersion: 3` and single dependency block, since a second full
`npm ci`/wheel rebuild would only re-verify determinism already exercised
by the Coder's reported two-consecutive-build hash comparison and would
not change the trust-boundary conclusions above.

I inadvertently created stray `.pyc` files while spot-checking
`compileall` in-place; these were `git clean -fdx`-removed immediately
and `git status --short` was re-confirmed empty before continuing. No
tracked file was affected.

Environment: local `.venv` (Python 3.9), Node/npm as pinned by
`frontend/workbench/package-lock.json`, macOS/Darwin, no network access
used or required.

## Security, Scope, and Compatibility

Security observations: the two-stage trust boundary (exact-path public
static allowlist vs. fully authenticated `/api/v1`) is cleanly
partitioned at the same middleware layer with no shared code path that
could let one policy leak into the other; the static CSP's
`script-src 'self'` plus the absence of any inline `<script>` in either
`index.html` closes the most likely XSS vector for a locally-served app.
Two non-blocking advisory observations for the Architect:

1. The 5-second `server_thread.join(_SERVER_JOIN_TIMEOUT_SECONDS)` bound
   in `runtime.py`'s `finally` block does not forcibly terminate the
   thread if Uvicorn's real serving loop is slow to observe
   `should_exit`; since the thread is non-daemon, an unusually slow real
   shutdown could keep the CLI process alive past the point
   `run_pmqa_web_workbench` returns or raises. This is inherent to
   Python's cooperative thread model (no forced kill exists) and is
   exercised deterministically in tests via a busy-loop fake server; it
   is not a defect against any stated acceptance criterion and real
   Uvicorn observes `should_exit` on a sub-second poll in practice, but
   is worth the Architect's awareness for a future TLS/reload-heavy
   deployment shape (explicitly out of scope here).
2. `api.ts` builds request paths with unescaped template-literal
   interpolation of `session_id`/`turn_id` rather than
   `encodeURIComponent`. This is not currently reachable as a defect: the
   only source of these identifiers is a previously fetched
   `ConversationSession`/`ConversationTurn` object (no free-text ID entry
   field exists in `App.tsx`), and the backend's
   `validate_run_identifier` restricts the charset before an identifier
   is ever returned to the client. Recommended only as defense-in-depth
   if a future checkpoint adds any client-side-constructed identifier.

Scope observations: `git diff --stat e2c25273da21bac080a2f29c6abaa2c0517dffac HEAD`
shows exactly the 38 files listed in `coder-report.md`'s "Changed Files"
section. No Task 5D.1A conversation contract/repository/lifecycle file,
no Run/Runner/Application/Usage/reasoning/workflow/Supervisor/LangGraph/
Product Pack/product file, and no other role's handoff file changed. The
`pmqa/web/app.py` diff is confined to the static-route/CSP integration
described in the current task; the pre-existing `/api/v1` authentication/
Origin/CSRF/body/error/response-token methods are unchanged.

Compatibility observations: all Task 5D.1A/1B, Task 5C, and Task 4
regression suites continue to pass unchanged; the full default suite
count (2233 passed, 6 skipped) matches the Coder's reported count
exactly, with the 6 skips being the 5 pre-existing environment-gated
tests plus the new opt-in live-browser smoke (confirmed by rerun, not
merely by report).

## Verdict

Verdict: Pass

This verdict is advisory. The Architect makes the final technical
disposition.

## Suggested Architect Focus

- No blocking finding surfaced from this Deep, independently reproduced
  review; the two advisory observations above (non-daemon thread join
  timeout under a real slow shutdown; `api.ts`'s non-percent-encoded
  identifier interpolation, currently non-reachable) are offered for
  awareness only and do not gate approval in this Reviewer's assessment.
- Confirm the Architect is comfortable that the static-route allowlist's
  security posture (no Bearer/Origin/CSRF, relying instead on exact-path
  matching plus the narrowed CSP/CORP headers) is the intended long-term
  shape for any future additional public asset, since it is a slightly
  different trust model from the authenticated `/api/v1` surface it sits
  beside.
- If Task 5D.2+ introduces any client-supplied (not server-echoed)
  identifier into a frontend URL path, revisit observation 2 above
  (`encodeURIComponent`) at that time, since the "currently unreachable"
  reasoning would no longer hold.

## Reviewer Write-Boundary Confirmation

Repository files changed by Reviewer:

- `agent-handoff/reviewer-report.md`

Confirmation: I changed no production code, tests, configuration, schemas,
packaging, scripts, product documentation, or another role's handoff file.
