# Coder Report

Owner: Coder

Task: PMQA Task 5D.1C — Local Browser Workbench and Packaged Runtime

Task ID: `PMQA-5D.1C`

Attempt: `1`

Status: Ready for Independent Reviewer

## Branch and Git Correlation

Branch:

`agent/task-5c-1-canonical-run-contract`

Exact Git-derived Coder starting HEAD:

`e2c25273da21bac080a2f29c6abaa2c0517dffac`

That commit is the latest pushed branch commit containing the Architect's
Task 5D.1C publication and Task 5D.1B approval. Before implementation, local
HEAD and `origin/agent/task-5c-1-canonical-run-contract` both equaled that
commit and the worktree was clean. It records approved Task 5D.1B
implementation `8775368fb74ee27425946e4c6ea40e745b475c09` and approved
Reviewer HEAD `d173b54df47f9ea54d82b731680e40e6977ca455`.

No prior Task 5D commit was amended, rebased, or replaced.

## Implementation Commits

`5585812e62f12ac7f8c529769c16048c653d149c`

Commit message:

`add packaged local browser workbench`

`bb25794241e5410afc88032838d6bbb014e2e698`

Commit message:

`document Task 5D.1C workbench status`

This report is committed separately after both implementation commits. The
Independent Reviewer derives the report commit from Git; this report does not
claim its own future commit SHA.

## Changed Files

Runtime, API/static boundary, CLI, and packaging:

- `.gitignore`;
- `pmqa/cli.py`;
- `pmqa/web/__init__.py`;
- `pmqa/web/app.py`;
- `pmqa/web/runtime.py`;
- `pmqa/web/static.py`;
- `pyproject.toml`.

Packaged production assets:

- `pmqa/web/static/index.html`;
- `pmqa/web/static/assets/app.js`;
- `pmqa/web/static/assets/app.css`;
- `pmqa/web/static/asset-integrity.json`.

Frontend source and reproducible tooling:

- `frontend/workbench/index.html`;
- `frontend/workbench/package.json`;
- `frontend/workbench/package-lock.json`;
- `frontend/workbench/tsconfig.json`;
- `frontend/workbench/vite.config.ts`;
- `frontend/workbench/scripts/build.mjs`;
- `frontend/workbench/src/App.tsx`;
- `frontend/workbench/src/api.ts`;
- `frontend/workbench/src/bootstrap.ts`;
- `frontend/workbench/src/main.tsx`;
- `frontend/workbench/src/styles.css`;
- `frontend/workbench/src/api-v1.contract.json`;
- `frontend/workbench/src/test-setup.ts`;
- `frontend/workbench/src/App.test.tsx`;
- `frontend/workbench/src/api.test.ts`;
- `frontend/workbench/src/api-schema.test.ts`;
- `frontend/workbench/src/bootstrap.test.ts`.

Python tests:

- `tests/test_packaging.py`;
- `tests/test_web_frontend_contract_drift.py`;
- `tests/test_web_live_smoke.py`;
- `tests/test_web_runtime.py`;
- `tests/test_web_static.py`.

Documentation:

- `README.md`;
- `docs/Roadmap.md`;
- `docs/architecture.md`;
- `docs/architecture/conversational-workflow-platform.md`.

Report-only handoff:

- `agent-handoff/coder-report.md`.

No conversation, Run, Runner, Application, Usage, reasoning, workflow,
Supervisor, LangGraph, Product Pack, product, provider, ADO, or external-write
behavior changed.

## Runtime Composition and Lifecycle

`run_pmqa_web_workbench` explicitly composes:

- one `InMemoryConversationRepository` for session-only conversations;
- one `SQLiteConversationRepository` at
  `platformdirs.user_data_path("pmqa", "PMQA")`, outside the package;
- the approved `ConversationApplicationService`;
- an explicit empty `WorkflowRegistry`, with no product/pack discovery;
- two fresh `secrets.token_urlsafe(32)` invocation-local tokens;
- the approved `PMQAWebSecurityContext` and FastAPI factory;
- one pre-bound `AF_INET` socket on exact `127.0.0.1` with OS-assigned port;
  and
- programmatic Uvicorn with access logging and configured logging disabled.

Uvicorn receives the already-bound socket, so there is no scan-then-bind
race. It runs in one owned non-daemon thread. Readiness polls Uvicorn's
post-startup `started` state for at most ten seconds before browser launch.
The browser opener is called exactly once after readiness. Normal server
return and interrupt/failure cleanup set `should_exit`, join the owned thread,
and close the socket. Tests inject data location, tokens, socket, server,
browser, monotonic clock, sleep, and thread construction without a live
socket, browser, wall clock, or entropy.

Expected storage, composition, binding, readiness, and browser failures expose
only `PMQAWebRuntimeError("pmqa_web_failed")`. OSError at those owned
operational boundaries is contained. Unexpected `RuntimeError` and
`MemoryError`, `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit` remain
authoritative. Runtime returns `None` and exposes no token, path, repository,
socket, server, or serializable runtime result.

## `pmqa web` CLI

The new `web` parser has no options. It accepts no provider, ADO, credential,
executable, host, static path, remote bind, or arbitrary command argument.
The runtime import remains inside the command function.

Expected `PMQAWebRuntimeError` returns exit code `2` and prints only:

```text
pmqa_web_failed
```

Successful normal shutdown returns `0` without printing runtime details.
Unexpected runner errors propagate. Existing commands and product-lazy
dispatch remain unchanged. Editable installation and the installed
`pmqa web --help` command were verified from `/tmp`.

## Static and API Trust Boundaries

Only these unauthenticated packaged routes exist:

```text
GET/HEAD /
GET/HEAD /assets/app.js
GET/HEAD /assets/app.css
```

They use an exact in-memory allowlist loaded through `importlib.resources`.
There is no static-root argument, directory listing, traversal, wildcard,
SPA fallback, arbitrary lookup, or source-map route. Every asset is nonempty,
has a fixed content type, and is verified at app composition against the
packaged SHA-256 integrity manifest.

The static middleware still requires exact loopback Host, strict canonical
raw/decoded target, empty query/body, no cookie, and exact GET/HEAD. It adds
the approved security headers and a static-only CSP:

```text
default-src 'none'; script-src 'self'; style-src 'self';
connect-src 'self'; base-uri 'none'; form-action 'none';
frame-ancestors 'none'
```

All `/api/v1` routes retain the complete approved Task 5D.1B Host, Bearer,
Origin, CSRF, canonical target/body/JSON, fixed-safe error, token-containment,
and response-header behavior. Existing 5D.1B tests remain green. Static
failures mutate no conversation state.

## Secure Browser Bootstrap and Token Non-Persistence

The launched URL contains the two runtime tokens only in this exact fragment:

```text
#session_token=<base64url>&csrf_token=<base64url>
```

The frontend synchronously matches one exact anchored fragment with distinct
43–128 character base64url values, copies the two strings into private
module-memory state, and calls `history.replaceState` before React rendering
or any API request. Invalid, reordered, duplicate, short, or extra fragment
forms are removed and fail closed without constructing an API client.

The API client sends exact Bearer authentication on every request and exact
CSRF on mutations. The browser supplies the same-origin Origin header. Fetch
uses `credentials: "omit"`, no-referrer, and no-store. No token value exists
in HTML, assets, CLI output, server logging, request URL, Referer, database,
cookie, localStorage, sessionStorage, UI text, or console output.

The opt-in real Uvicorn/Chromium smoke proved:

- the fragment was absent before readiness/API rendering completed;
- all network request URLs contained zero token bytes;
- localStorage and sessionStorage remained empty;
- every API request carried exact Bearer authentication;
- a real create-session POST carried exact automatic same-origin Origin and
  exact CSRF;
- no browser console message contained a token; and
- the runtime shut down cleanly after the browser assertion.

## Minimal Offline Workbench

The React UI supports only:

- readiness;
- workflow catalog display;
- bounded session listing;
- explicit session creation with session-only/7/30/90-day retention;
- session selection and inspection;
- bounded turn listing;
- one pending user turn using the selected session revision;
- revision-checked session close; and
- deletion behind explicit browser confirmation.

React renders workflow/domain text through normal text nodes. There is no
`dangerouslySetInnerHTML`, inline script, eval, remote asset/font, analytics,
telemetry, service worker, Markdown/HTML renderer, polling, SSE, WebSocket,
generic JSON executor, or arbitrary endpoint client.

The UI distinguishes loading, empty, closed, conflict, not-found, validation,
unavailable, and fixed-safe server-error states. A synchronous mutation lock
prevents duplicate submissions. A revision conflict performs one bounded
read refresh and never retries the mutation. Labels, semantic headings,
keyboard-native controls, focus-visible styling, a polite status live region,
and bounded inputs are present.

The UI explicitly says AI responses and workflow execution are not enabled.
Pending turns are never imitated or displayed as completed assistant output.

## Frontend Contracts, Build, and Distribution

The frontend uses exact React/Vite/TypeScript/Vitest versions and commits
lockfile version 3. TypeScript is strict. The deliberately maintained
`api-v1.contract.json` fixture is checked by Python against the authoritative
field order of every exported Web v1 contract and by Vitest for the complete
contract inventory.

The build wrapper runs Vite with fixed production filenames, no source maps,
and writes the SHA-256 integrity manifest. Two consecutive clean production
builds produced byte-identical hashes for index, CSS, JavaScript, and
integrity metadata. A clean `npm ci --ignore-scripts` in a temporary directory
installed exactly 162 locked packages.

The real wheel includes:

- all prior PMQA/product modules;
- `pmqa/web/runtime.py` and `pmqa/web/static.py`;
- index, JavaScript, CSS, and integrity manifest; and
- console entry point plus bounded `platformdirs>=4,<5` and
  `uvicorn>=0.30,<1` runtime dependencies.

It excludes frontend source, package/lock files, `node_modules`, source maps,
reports, caches, browser output, databases, tokens, credentials, and temporary
runtime files. From an unrelated temporary directory with repository source
paths removed, the extracted wheel loaded and verified all assets, composed
the runtime through deterministic fakes, created its SQLite database outside
the distribution, and resolved every imported module inside the wheel.

Node, npm, React, Vite, TypeScript, and Vitest are build/test dependencies
only; none is a Python runtime dependency.

## Validation Results

Final validation on the cumulative implementation:

- Task 5D Web/conversation focused group: `387 passed, 1 skipped`.
- New runtime/static/frontend-contract focused tests alone: `19 passed`.
- Existing CLI regressions: `156 passed`.
- Task 5C Application/Run/Usage regressions: `467 passed`.
- Task 4 runtime/reducer/Supervisor/LangGraph regressions: `98 passed`.
- Security/import/real-wheel group: `31 passed`.
- Full default Python suite: `2233 passed, 6 skipped`.
- Frontend strict typecheck: passed.
- Frontend unit/component tests: `11 passed` across 4 files.
- Deterministic production build: passed twice with byte-identical hashes.
- Clean temporary `npm ci`: passed, 162 locked packages.
- Real PMQA wheel build/content/external runtime composition: `3 passed`.
- Opt-in real loopback Uvicorn/Chromium workbench smoke: `1 passed`.
- Existing generated SauceDemo Playwright regressions: `2 passed`.
- Editable installation and `pip check`: passed; no broken requirements.
- Isolated `compileall` for `pmqa` and `products`: passed with bytecode
  outside the repository.
- Tracked Markdown relative-link validation: all `19` files passed.
- `git diff --check`: passed.
- Both implementation commits were pushed to the existing remote branch.

The six default-suite skips are five existing environment-gated tests plus
the new opt-in real browser smoke. The smoke passed when explicitly enabled.
The only warnings were the existing local LibreSSL warning, LangGraph
pending-deprecation warning, and npm's transitive `whatwg-encoding`
deprecation notice. No default test accessed a company system, paid model, or
external application.

## Failures, Remaining Risks, and Scope Confirmation

During development, the first live-smoke header assertion used Playwright's
restricted `request.headers` view, which omits browser-managed Origin. The
test was corrected to use `request.all_headers`; the real POST was already
accepted by the strict server, and the final smoke explicitly proves Origin,
Bearer, and CSRF.

The workbench intentionally remains a single-user loopback process that runs
until normal server termination or interrupt. It has no TLS, logout, token
rotation within one invocation, multi-user deployment, progress transport, or
background execution. Those are not claimed by Task 5D.1C.

Assistant completion/failure, reasoning providers, workflow/Runner execution,
ADO/Azure/Copilot/Skill Repo/MDE integration, capabilities, structured QA
artifacts, approvals, authorizations, operations, receipts, usage UI, and
external writes remain absent. Task 5D.2+, Task 5B, Task 6, and Task 7 were
not started. No PR was created and nothing was merged.

## Recommended Review Depth

**Deep**

Reason: this checkpoint joins local process lifecycle, browser secret
bootstrap, unauthenticated packaged assets, authenticated mutation APIs, and
wheel distribution at PMQA's user-facing trust root.

## Suggested Reviewer Focus

- Attempt static-route Host/query/body/cookie/method ambiguity, traversal,
  wildcard lookup, CSP weakening, and `/api/v1` authentication bypass.
- Inspect fragment parsing/removal order, browser request/Referer/storage/
  console behavior, exact Bearer/Origin/CSRF, and invalid-bootstrap fail
  closure.
- Challenge pre-bound socket ownership, readiness timeout, browser-once,
  interrupt/failure shutdown, exception classification, and secret/path/log
  non-disclosure.
- Exercise session/turn/close/delete UI flows, duplicate submission and
  conflict refresh, untrusted text rendering, and explicitly absent
  capabilities.
- Rebuild from the lockfile, compare committed assets/integrity metadata, and
  inspect the real wheel from outside the checkout for included assets and
  excluded debris.
- Confirm all prior Task 5D.1A/1B, CLI, import-isolation, Task 5C, and Task 4
  behavior remains unchanged.

## Human Summary

PMQA-5D.1C Attempt 1 已完成，Git 派生起点为 `e2c25273da21bac080a2f29c6abaa2c0517dffac`。
实现提交为 `5585812e62f12ac7f8c529769c16048c653d149c` 与 `bb25794241e5410afc88032838d6bbb014e2e698`，均已推送。
新增 `pmqa web`、预绑定 loopback/Uvicorn 生命周期、OS user-data SQLite、精确 packaged static allowlist 与 fragment-only token bootstrap。
React/strict-TypeScript workbench 仅支持现有 catalog/session/pending-turn 能力；AI、workflow execution、ADO、external write 均未加入。
验证结果：全量 2233 passed / 6 skipped、frontend 11 passed、real browser smoke 1 passed、Playwright 2 passed、wheel/外部目录验证通过。
Action Needed From Human: 请将下方 Handoff Note 传递给 Independent Reviewer。
Handoff Note: 请读取 agent-handoff/README.md 与 agent-handoff/current-task.md，从 Git 派生最新 coder-report commit，并按独立审查顺序完成 PMQA-5D.1C Attempt 1 review。
