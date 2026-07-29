# Current Task

Owner: Architect

Task: PMQA Task 5D.1C — Local Browser Workbench and Packaged Runtime

Task ID: `PMQA-5D.1C`

Attempt: `1`

Status: Authorized for Coder

Branch: `agent/task-5c-1-canonical-run-contract`

Approved Task 5D.1B implementation:
`8775368fb74ee27425946e4c6ea40e745b475c09`

Approved Task 5D.1B Reviewer HEAD:
`d173b54df47f9ea54d82b731680e40e6977ca455`

Coder starting HEAD: derive and record the latest pushed branch commit that
contains this Architect disposition and task publication before modifying
implementation files.

Repository Markdown and Git history are authoritative. Chat summaries are
informational only.

## Task Objective

Turn the approved Task 5D.1A conversation foundation and Task 5D.1B secure
API into a minimal local browser workbench that an ordinary QA can start with
one `pmqa web` command from an installed PMQA distribution.

This checkpoint provides only local runtime composition, the offline
conversation/workflow-catalog shell, secure browser bootstrap, and packaging.
It must not add AI reasoning, workflow execution, ADO, Copilot, company Skill
Repo integration, authorization, external writes, receipts, or usage UI.

## Background

Task 5D.1B approved:

- an inert, explicitly composed FastAPI application factory;
- exact loopback Host, Bearer, Origin, and CSRF policy;
- strict canonical request/response contracts;
- ten `/api/v1` conversation and workflow-catalog endpoints;
- bounded request bodies, targets, JSON, and ASGI streams;
- fixed-safe errors and security headers; and
- no socket binding, server lifecycle, CLI, browser, or frontend.

Task 5D.1C is the first user-facing shell over that boundary. The Skill Repo
and MDE work continue independently in the company environment. Do not couple
this implementation to either repository or assume their contracts.

## Required Design

### 1. Explicit runtime composition

Add one narrow runtime/application composition layer that:

- creates one volatile in-memory conversation repository;
- opens one durable SQLite conversation repository in a writable user-data
  location, never inside the installed package;
- creates the approved `ConversationApplicationService`;
- creates an explicit `WorkflowRegistry` without product or external-pack
  discovery;
- generates fresh invocation-local session and CSRF tokens with a
  cryptographically secure standard-library generator;
- creates the existing `PMQAWebSecurityContext` and approved FastAPI app;
- binds only `127.0.0.1`;
- obtains an available port through an OS-assigned/pre-bound socket rather
  than a scan-then-bind race;
- starts Uvicorn programmatically with access logging disabled;
- waits for bounded readiness before opening the browser;
- opens the browser exactly once on success and never on failed startup; and
- shuts down cleanly on normal termination or interrupt.

Production defaults may use a small explicit dependency such as
`platformdirs` for a writable OS user-data directory. Runtime collaborators
must have narrow injection seams so default tests do not launch a browser,
bind a real server, or depend on wall-clock/entropy values.

No secret, token, database path, raw exception, socket object, repository
object, or server object may cross into conversation state, API payloads,
CLI output, logs, URLs sent over HTTP, or serializable runtime results.

### 2. `pmqa web` CLI

Add `pmqa web` following the existing CLI style.

Required public behavior:

- no provider, ADO, Copilot, credential, executable, host, arbitrary static
  path, or command arguments;
- no externally reachable bind option;
- success starts the local workbench and returns success only after normal
  shutdown;
- expected configuration, storage, binding, readiness, and browser-launch
  failures return exit code `2` and print only one fixed bounded failure code;
- unexpected programming errors and resource/control-flow exceptions are not
  misclassified as success;
- runtime tokens and internal paths are never printed;
- existing CLI commands remain behaviorally unchanged and product-lazy.

If a test-only runtime seam is needed, keep it private and non-CLI.

### 3. Browser bootstrap and static trust boundary

Serve the frontend only from packaged PMQA resources. Do not accept a
filesystem/static-root argument and do not use the source checkout at
runtime.

The initial browser document and immutable assets may be fetched without the
Bearer token only through an exact allowlist of read-only static routes. Those
routes must still enforce:

- loopback Host;
- GET/HEAD only;
- empty query and request body;
- no cookies;
- strict target canonicalization;
- fixed content types;
- no directory listing, traversal, SPA wildcard, arbitrary file lookup, or
  source maps; and
- the approved security headers with a CSP narrowed to packaged same-origin
  scripts, styles, and API connections.

Every `/api/v1` route retains the complete approved Task 5D.1B authentication,
Origin, CSRF, body, error, and response-token policy.

Deliver the two invocation-local tokens to the launched browser only in the
URL fragment, never in the scheme, authority, path, query, HTTP request,
Referer, HTML, asset, server log, CLI output, file, cookie, localStorage, or
sessionStorage. The frontend must synchronously:

1. validate the exact fragment shape;
2. copy the tokens only into module-memory state;
3. remove the complete fragment with `history.replaceState` before rendering
   or making any request; and
4. fail closed without an API request if bootstrap validation fails.

The browser API client sends exact Bearer authentication on every API request
and the exact CSRF header on mutations. It must never display or log either
token.

### 4. Minimal offline browser workbench

Use the approved React + strict TypeScript + Vite direction. Keep the UI
deliberately small.

It must support only the existing API capabilities:

- readiness;
- workflow catalog display;
- bounded session list;
- create a session with an explicit approved retention choice;
- select and inspect one session;
- bounded turn list;
- create one user turn using expected revision;
- close a session using expected revision; and
- delete a session with explicit confirmation.

The UI must clearly say that AI responses and workflow execution are not yet
enabled. It must not imitate a completed assistant response.

Required UI behavior:

- all server/domain/provider-like text renders as text, never executable HTML;
- no `dangerouslySetInnerHTML`, inline script, `eval`, remote asset, remote
  font, analytics, telemetry, service worker, or external network request;
- loading, empty, closed, conflict, not-found, validation, unavailable, and
  fixed-safe server-error states are distinct;
- mutation controls prevent accidental double submission;
- revision conflicts trigger a bounded refresh rather than an automatic
  retry;
- basic keyboard navigation, labels, focus visibility, and status
  announcements are present;
- the frontend consumes versioned API types and has an explicit drift check
  against the authoritative Python contracts or a deliberately maintained
  canonical schema fixture.

Do not add SSE, WebSockets, polling, background workflow execution, Markdown
or HTML rendering, a generic JSON executor, or arbitrary endpoint access.

### 5. Reproducible build and distribution

- commit the frontend source, package manifest, and deterministic lockfile;
- keep TypeScript strict and provide explicit typecheck, unit-test, and build
  commands;
- commit only the intentional production build assets required by the Python
  wheel, if the selected packaging strategy requires committed assets;
- exclude `node_modules`, caches, reports, source maps, browser output, local
  databases, tokens, and temporary runtime files;
- package all required static assets in the real PMQA wheel;
- prove the wheel can load the assets and compose the runtime from an
  unrelated directory with repository source paths removed;
- Node/npm/Vite/TypeScript/React are build-time dependencies only, not Python
  runtime requirements;
- add only the minimum bounded Python runtime dependencies required by the
  approved design.

## Allowed Changes

Expected implementation areas:

- `pmqa/web/` runtime, static serving, and package resources;
- a bounded CLI addition in `pmqa/cli.py`;
- frontend source and its build/test configuration in one clearly named
  repository directory;
- `pyproject.toml`, lockfiles, packaging assertions, and `.gitignore` where
  necessary;
- focused Python, TypeScript/component, runtime, CLI, security, and packaging
  tests;
- concise README, Roadmap, and existing Task 5D architecture status updates;
- `agent-handoff/coder-report.md`.

Do not modify:

- Task 5D.1A conversation contracts, repositories, or lifecycle semantics;
- Run, Runner, Application, Usage, reasoning, workflow, Supervisor,
  LangGraph, Product Pack, or product behavior;
- Task 5D.1B API endpoint semantics except the exact static-route and CSP
  integration needed by this task;
- another role's handoff file.

Use bounded implementation commits followed by one separate report-only Coder
handoff commit. Do not amend previously reviewed commits.

## Out of Scope

Do not implement:

- assistant turn completion/failure;
- reasoning providers or provider login;
- ADO, Azure CLI, Copilot CLI, Skill Repo, or MDE integration;
- workflow/Runner execution;
- capabilities, artifacts, approvals, authorizations, operations, receipts,
  or usage/cost UI;
- SSE, WebSockets, polling, reconnect, multi-user hosting, TLS, remote bind,
  or deployment;
- arbitrary commands, paths, plugins, Product Pack discovery, or external
  assets;
- Task 5D.2+, Task 5B, Task 6, or Task 7;
- PR creation or merge.

## Acceptance Criteria

- `pmqa web` composes and starts the existing application on loopback only;
- startup, readiness, browser opening, and shutdown are deterministic,
  bounded, injectable, and fixed-safe;
- runtime tokens remain invocation-local and reach the frontend only through
  a fragment that is removed before rendering or network access;
- exact static routes cannot weaken any `/api/v1` security behavior;
- the minimal UI performs every listed existing conversation/catalog action
  and no unapproved operation;
- no untrusted content is interpreted as HTML or code;
- frontend types/build/tests are strict and reproducible;
- the real wheel contains all runtime Python and frontend assets but no
  development/runtime debris;
- imports remain side-effect free and product/provider lazy;
- existing CLI, Task 5D.1A, Task 5D.1B, Task 5C, Task 4, packaging, and
  generated-test regressions remain green;
- default new tests require no company system, provider, paid model, or
  external network;
- worktree is clean and synchronized;
- only allowed files change.

## Validation Requirements

The Coder must identify and run the repository's exact applicable commands.
At minimum report:

- focused Python runtime/CLI/static-security/API tests;
- all existing Task 5D conversation/Web tests;
- frontend strict typecheck;
- frontend unit/component tests;
- deterministic production frontend build;
- packaged-asset drift or integrity check;
- real PMQA wheel build and external-directory asset/runtime import test;
- existing CLI regressions;
- Task 5C and Task 4 regressions;
- full default Python suite;
- existing generated SauceDemo Playwright regressions;
- one opt-in local browser workbench smoke if a real browser is required;
- isolated `compileall`;
- `git diff --check`;
- final `git status --short`.

Tests must use fixtures/fakes for entropy, browser opening, readiness, server
lifecycle, storage location, and time. No test may print or persist runtime
tokens.

## Expected Deliverables

- explicit local Web runtime composition;
- `pmqa web`;
- secure browser bootstrap;
- minimal React/TypeScript workbench;
- packaged static assets and reproducible frontend build;
- focused security, lifecycle, UI, and packaging tests;
- concise documentation status updates;
- one complete Coder report;
- no PR or merge.

## Required Coder Handoff

Replace `agent-handoff/coder-report.md` with the complete Task 5D.1C report.
Include:

- Task/Attempt, branch, and exact Git-derived starting HEAD;
- every implementation commit and changed file;
- runtime composition and lifecycle;
- exact static/API trust-boundary behavior;
- token bootstrap and non-persistence evidence;
- implemented UI capabilities and explicit absent capabilities;
- frontend build/type/test and Python validation results;
- real-wheel/external-directory evidence;
- failures, remaining risks, and scope confirmation;
- one recommended review depth (`Light`, `Standard`, or `Deep`);
- one-sentence reason;
- 3–6 suggested Reviewer focus areas;
- Human Summary using the mandatory routing and one-sentence Handoff Note.

Recommended review depth is advisory. The Architect retains final authority.
Do not include the report commit's own SHA; the Reviewer derives it from Git.
