# Current Task

Owner: Architect

Task: PMQA Task 5D.1A — Conversation Session and Retention Foundation

Task ID: `PMQA-5D.1A`

Attempt: `1`

Status: Ready for Coder

Branch: `agent/task-5c-1-canonical-run-contract`

Architect-reviewed baseline Reviewer HEAD:
`115910e2662ce6bd2de6f807dfb3dfddc201a4b3`

Human-approved Architect disposition commit: derive and record the latest
pushed branch commit containing this task publication before changing
implementation files.

Repository Markdown and Git history are authoritative. Chat summaries are
informational only.

## Task Objective

Implement the provider-neutral conversation session, turn lifecycle,
retention policy, application-service, and local SQLite repository foundation
for the future PMQA Web workbench.

This is the first bounded implementation checkpoint inside Task 5D.1. It must
establish canonical records and deterministic local persistence before a Web
server or frontend is introduced.

The completed Task 5D.1 sequence is intentionally decomposed:

1. **5D.1A — Conversation Session and Retention Foundation** (this task);
2. **5D.1B — Secure Loopback Web/API Boundary**; and
3. **5D.1C — Browser Workbench, `pmqa web`, and Distribution Packaging**.

Do not begin 5D.1B or 5D.1C.

## Human Product Decision

The Human approved:

```text
default retention: 30 days after the session's last activity
configurable choices: session-only, 7 days, 30 days, or 90 days
manual deletion: available immediately
indefinite retention: never selected silently
```

This policy applies to future local conversation messages and structured
artifact content. Task 5D.1A implements it for conversation sessions and
turns. Future artifact repositories must reuse the same approved policy.

Task 5C usage records, Task 3 reasoning traces, and future external-execution
receipts retain separate explicit retention policies. Deleting a conversation
must not silently claim to delete or mutate those independent records.

## Background

Task 5D.0 is approved. Its architecture defines:

- arbitrary conversation separately from registered workflows;
- conversation sessions and turns separately from Run, LangGraph,
  reasoning-trace, usage, authorization, and receipt records;
- a local-first Web application with a future hosted migration path;
- no raw credentials or runtime/provider objects in durable records;
- a dedicated conversation/artifact repository rather than reuse of the
  reasoning trace database or usage JSON repository.

The current repository already provides patterns that must be inspected and
reused where appropriate:

- strict immutable contracts in `pmqa/run` and `pmqa/usage`;
- deterministic application boundaries in `pmqa/application`;
- SQLite lifecycle and injection seams in `pmqa/trace`;
- shared security policy in `pmqa/security`;
- reasoning scrub/redaction behavior in `pmqa/reasoning/scrubber.py`;
- import-isolation and real-wheel packaging tests.

Do not broaden `WorkflowState`, `RunRecord`, `TraceRecord`,
`AIInvocationRecord`, `KnowledgeArtifact`, or `RunArtifact` into conversation
storage.

## Required Domain Model

Create a new provider-neutral `pmqa.conversation` package.

The public surface must include strict immutable concepts equivalent to:

- `ConversationRetentionPolicy`;
- `ConversationSessionStatus`;
- `ConversationTurnStatus`;
- `ConversationSession`;
- `ConversationTurn`;
- fixed safe validation/repository/application errors;
- a conversation repository protocol;
- an in-memory repository for deterministic tests and session-only mode;
- a SQLite repository for durable `7`, `30`, and `90` day modes; and
- a deterministic conversation application service.

Names may be refined only when the report explains why the alternative is
clearer and all required semantics remain present.

### Conversation session

A canonical session must contain only the minimum data needed for local
conversation lifecycle, such as:

- schema version;
- session ID;
- monotonic session revision;
- active/closed status;
- retention policy;
- optional future connection-context reference, never credentials;
- ordered turn correlation;
- created, updated, and expiration timestamps.

Required invariants:

- canonical bounded identifiers reuse the existing neutral run-identifier
  policy where compatible rather than introducing a weaker duplicate;
- direct construction, canonical reconstruction, and revalidated copy paths
  enforce the same invariants;
- all timestamps are timezone-aware and serialize canonically as UTC `Z`;
- `created_at <= updated_at`;
- durable policies require exact expiration derived from `updated_at` plus
  `7`, `30`, or `90` days;
- session-only mode has no durable expiration claim and must never be written
  to SQLite;
- no mode represents implicit indefinite retention;
- session revision advances exactly once for each authoritative lifecycle or
  turn change;
- turn IDs and sequence positions are unique and bounded;
- a closed session cannot accept a new turn;
- caller-owned collections are never retained;
- complete canonical-tree depth/item/string bounds apply before persistence.

Choose and document a conservative finite maximum turn count and message size.
The values must support ordinary multi-paragraph QA conversation without
permitting unbounded storage.

### Conversation turn

A turn represents one user message and one canonical application/provider
response lifecycle. It must support:

- pending;
- completed; and
- failed.

Required invariants:

- one immutable turn ID, session ID, and positive sequence number;
- bounded plain-text user content;
- pending turns contain no assistant response, completion time, or error;
- completed turns contain one bounded assistant response and a completion
  timestamp;
- failed turns contain no raw adapter/provider response and expose only a
  fixed safe error code/message;
- terminal completion cannot precede turn creation;
- cross-record session/sequence/time correlation is enforced by the
  application service and repository;
- no provider SDK object, prompt package, raw terminal output, HTML object,
  callable, credential, or runtime handle is serializable;
- ordinary QA text, Unicode, line breaks, Work Item references, and the words
  “password” or “token” in a legitimate testing discussion remain usable.

Do not add citations, workflow suggestions, capability calls, structured
artifacts, approvals, or provider-specific metadata in this checkpoint.
Those require later versioned contracts.

## Canonical Serialization and Immutability

Follow the established Run/Usage contract discipline:

- Pydantic v2 strict models;
- frozen public records;
- `extra="forbid"`;
- hidden invalid inputs and fixed-safe public errors;
- explicit canonical `to_dict()` / `from_dict()`;
- built-in plain JSON wire representation only;
- no coercion-dependent acceptance;
- deep immutable collection snapshots;
- finite numeric values only;
- canonical round trip:

```text
wire = record.to_dict()
restored = type(record).from_dict(wire)
assert restored == record
```

`model_copy(update=...)` or the package's equivalent public copy operation
must fully revalidate and cannot bypass invariants.

Do not add a second prohibited/sensitive-key vocabulary. Reuse the shared
security boundary and existing neutral validation helpers.

## Sensitive Text Ingress

Task 5D.0 requires no credential fields or runtime secrets in conversation
records, but arbitrary user text cannot be mathematically proven secret-free.
Implement an enforceable layered policy rather than an impossible guarantee.

Before a user message or assistant response reaches any repository:

- apply a bounded deterministic sensitive-text inspection;
- reject recognizable Bearer values, Cookie/Set-Cookie values, and
  credential/secret assignments already covered by PMQA's reasoning scrub
  policy;
- expose only a fixed safe rejection code/message;
- do not echo, persist, hash, log, or place the rejected raw value in an
  exception, cause, context, audit record, or test snapshot;
- accept normal QA statements such as “test the password field,” “token usage
  is unavailable,” and `type=password`;
- document that high-confidence pattern handling is defense-in-depth, not a
  claim to detect every arbitrary password.

Do not create an independent regex/list that can drift from the existing
reasoning scrubber. Extract or expose a small neutral security primitive if
needed, then make the reasoning scrubber and conversation boundary reuse it
without changing existing Task 3 behavior.

Resource and control-flow exceptions (`MemoryError`, `KeyboardInterrupt`,
`SystemExit`, `GeneratorExit`) remain authoritative. Expected malformed or
sensitive input failures are contained safely.

## Repository Contract

Define a provider-neutral repository protocol and two implementations.

The application service must receive an explicit volatile/durable repository
composition or router. Retention mode selects that injected boundary:
session-only state goes only to the in-memory implementation, while `7`,
`30`, and `90` day state goes only to the durable implementation. The service
must not first write session-only content to SQLite and delete it afterward.

### In-memory implementation

Use it for:

- deterministic offline tests;
- injected application-service dependencies; and
- session-only retention.

Session-only records must not be forwarded to a durable repository.

### SQLite implementation

Use Python's existing standard-library SQLite support. Do not introduce an ORM
or a new runtime dependency.

Required behavior:

- explicit caller-supplied database path;
- versioned schema/migration identity;
- foreign-key enforcement;
- atomic session/turn transitions;
- canonical JSON payload or explicit typed-column reconstruction through the
  public domain contracts;
- defensive reconstruction of every stored record;
- fixed-safe corruption errors with no stored payload/path/SQL exposure;
- immutable returned snapshots;
- compare-and-write using expected session revision so stale writers fail
  without partial mutation;
- deterministic ordering;
- bounded reads and lists;
- immediate manual deletion of one session and its conversation turns;
- deterministic purge of sessions whose approved expiration has passed;
- no purge of session-only state because it is never durable;
- no mutation of Task 3 trace or Task 5C usage storage;
- no default database inside the source tree or installed package;
- clean closure and rollback on expected failures;
- no SQL, path, secret marker, or underlying exception details in public
  errors.

The repository must not infer that deleting a conversation also deletes
independent traces, usage, artifacts, authorizations, or receipts.

Use an injected clock at the application/retention boundary. Tests must not
sleep.

## Conversation Application Service

Implement a synchronous provider-neutral service above the repository seam.
It must support the minimum deterministic operations:

- create a session;
- get/list bounded session snapshots;
- start one pending turn;
- complete one pending turn;
- fail one pending turn safely;
- close a session;
- manually delete a session; and
- purge expired durable sessions.

Requirements:

- dependencies are injected;
- clock and ID generation are injectable and validated before side effects;
- each authoritative operation samples time and identifiers only as often as
  explicitly documented and tested;
- input objects and live dependency properties are snapshotted before trust;
- expected session revision prevents lost updates;
- sequence numbers are deterministic and gap-free for successful appends;
- failed operations make no partial repository mutation;
- session `updated_at`, revision, and durable `expires_at` advance together;
- terminal turn timestamps correlate with their session transition;
- manual deletion is idempotent only if explicitly represented as such;
  otherwise a second delete returns one fixed not-found result;
- purge uses one authoritative cutoff and returns only bounded counts or IDs,
  never deleted content;
- application errors remain fixed and marker-safe;
- no reasoning provider, workflow runner, LangGraph graph, Web framework, ADO
  client, or Product Pack is instantiated.

## Retention Semantics

Encode the Human decision exactly:

| Mode | Durable | Expiration |
| --- | --- | --- |
| session-only | No | Process-local only |
| 7 days | Yes | Last authoritative activity + 7 days |
| 30 days | Yes | Last authoritative activity + 30 days |
| 90 days | Yes | Last authoritative activity + 90 days |

The service default is `30 days`.

Clarify and test what counts as authoritative activity. At minimum, successful
turn start, completion/failure, and session close must have deterministic
documented behavior. Read/list operations must not silently extend retention.

Manual deletion is available immediately for any conversation session.
Indefinite retention is not a valid public option.

## Import and Packaging Isolation

`import pmqa.conversation` must not:

- import FastAPI, Uvicorn, React/Node tooling, Playwright, products.demo,
  external Product Packs, LangGraph, orchestration, workflow runtime,
  Supervisor, ADO/provider clients, or reasoning execution;
- inspect installed distributions;
- read environment/configuration files;
- open/create a database;
- create files;
- mutate `sys.path`; or
- launch a subprocess.

The real PMQA wheel must contain the new package and no database, conversation
content, cache, test output, or private fixture.

Generic `import pmqa` and `import pmqa.cli` must remain conversation-lazy.

## Documentation

Update only what is necessary to record:

- the approved 30-day default and selectable retention modes;
- Task 5D.1A boundaries and status;
- the 5D.1A/5D.1B/5D.1C decomposition;
- no Web/API/frontend/CLI implementation exists yet;
- no ADO/Copilot integration exists yet.

Do not rewrite Task 5D.0 architecture or mark Task 5D.1 complete.

## Allowed Changes

Expected:

- `pmqa/conversation/__init__.py`;
- conversation contract, security-boundary, repository, and service modules
  under `pmqa/conversation/`;
- a narrowly shared neutral security helper under `pmqa/security/` only if
  needed to prevent drift;
- `pmqa/reasoning/scrubber.py` only if required to reuse that neutral helper
  without behavior change;
- focused tests under `tests/`;
- `tests/test_packaging.py`;
- `README.md`;
- `docs/Roadmap.md`;
- `docs/architecture.md`;
- `docs/architecture/conversational-workflow-platform.md`;
- `agent-handoff/coder-report.md`.

Do not modify:

- `pmqa/cli.py`;
- `pyproject.toml` dependencies or console entry points;
- Task 4 workflow/runtime/orchestration/Supervisor;
- Task 5 product/demo behavior;
- Task 5A Product Pack contracts;
- Task 5C Run, Runner, Application, Usage, or Pricing contracts;
- reasoning models, provider contracts, prompt packages, trace models/store;
- another role's handoff file.

Use one implementation commit and one report-only Coder handoff commit. Do not
amend prior commits.

## Out of Scope

Do not implement:

- FastAPI, Uvicorn, HTTP, REST, SSE, CORS, CSRF, cookies, or session-token
  transport;
- React, TypeScript, Vite, Node, browser UI, or static assets;
- `pmqa web` or another CLI command;
- workflow selection or execution;
- reasoning-provider calls;
- capability registry/gateway;
- ADO reads or writes;
- connection/authentication adapters;
- citations, workflow suggestions, or structured response contracts;
- structured QA artifact schemas/repository;
- approval/authorization;
- external operations or receipts;
- usage UI or provider-session AIC;
- Task 5D.1B, 5D.1C, 5D.2, Task 5B, Task 6, or Task 7;
- PR creation or merge.

## Required Focused Tests

Add direct tests for at least:

### Contracts

- complete session and pending/completed/failed turn records;
- direct construction, revalidated copy, and plain-JSON reconstruction;
- deep immutability and caller-container isolation;
- unknown fields, coercion, invalid identifiers, timestamps, lifecycle,
  revision, sequence, bounds, runtime objects, cyclic/overdeep structures,
  non-finite values, and prohibited fields;
- session-only versus durable expiration invariants;
- observed empty text versus invalid blank text where semantically relevant.

### Sensitive ingress

- recognized Bearer, Cookie, credential assignment, token, password, and
  secret patterns rejected before persistence;
- nested/variant marker values never appear in public errors or stored state;
- no cause/context leak for expected failures;
- ordinary QA discussion of password/token concepts remains accepted;
- existing Task 3 scrubber regressions remain byte/behavior compatible.

### Repository

- in-memory and real SQLite round trips;
- no retained caller references;
- stale expected revision;
- atomic start/complete/fail transitions;
- duplicate IDs/sequences;
- corruption, malformed rows, schema mismatch, and unavailable database;
- deterministic bounded list order;
- manual deletion and second-delete policy;
- expiry boundary immediately before, at, and after cutoff;
- purge never touches unexpired sessions;
- database rollback and clean close;
- separate repositories and no cross-store mutation;
- SQLite tests use pytest temporary directories only.

### Service

- approved 30-day default;
- session-only, 7, 30, and 90 day modes;
- successful activity extends durable expiration exactly;
- reads do not extend expiration;
- injected clock/ID validation before repository effects;
- sampling counts;
- closed session rejection;
- turn ordering and cross-record timestamp correlation;
- fixed-safe failure paths;
- resource/control-flow propagation;
- no partial changes after dependency or repository failure.

### Isolation and packaging

- import side-effect and forbidden-module assertions;
- real wheel contains required conversation modules;
- real wheel contains no SQLite/runtime content;
- current CLI and all existing commands remain unchanged.

New default tests must be offline and require no browser, network, Node,
external provider, ADO identity, or Product Pack installation.

## Validation Commands

Run and report:

```bash
.venv/bin/python -m pytest tests/test_conversation_contracts.py tests/test_conversation_repository.py tests/test_conversation_service.py tests/test_conversation_imports.py tests/test_scrubber.py tests/test_boundary_policy.py tests/test_packaging.py -q
.venv/bin/python -m pytest tests/test_run_contracts.py tests/test_application_contracts.py tests/test_application_service.py tests/test_usage_contracts.py tests/test_usage_repository.py tests/test_usage_summary.py -q
.venv/bin/python -m pytest tests/test_workflow_runtime.py tests/test_workflow_reducer.py tests/test_supervisor_policy.py tests/test_langgraph_workflow.py -q
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest products/demo/generated_tests -q
.venv/bin/python -m compileall -q pmqa products
git diff --check
git status --short
```

Use an isolated bytecode cache for compileall. Also run repository Markdown
relative-link validation and real-wheel inspection from outside the source
checkout.

## Acceptance Criteria

- canonical provider-neutral conversation session and turn records exist;
- 30-day retention is the default and only session-only/7/30/90 are valid;
- session-only content never reaches SQLite;
- durable activity and expiration are deterministic;
- immediate manual deletion and expiry purge are implemented;
- repository writes are atomic and stale revisions cannot overwrite;
- sensitive ingress uses shared non-drifting rules and rejects before
  persistence without marker leaks;
- arbitrary QA text remains usable and the implementation does not claim
  perfect arbitrary-password detection;
- no credentials, runtime objects, raw provider/process output, or
  unrestricted dynamic payload enters records; only the validated canonical
  assistant response may enter a completed turn;
- SQLite corruption and operational failures are contained safely;
- public imports are side-effect free and existing generic imports stay lazy;
- existing workflows, application/run/usage layers, CLI, packaging, and tests
  remain compatible;
- no Web/API/frontend/ADO/Copilot implementation is started;
- only allowed files change.

## Expected Deliverables

- canonical conversation/retention contracts;
- neutral sensitive-text ingress boundary;
- repository protocol;
- deterministic in-memory implementation;
- real SQLite implementation;
- deterministic application service;
- focused adversarial tests;
- minimal documentation/status updates;
- one implementation commit;
- one report-only Coder handoff commit;
- clean synchronized branch;
- no PR or merge.

## Required Coder Handoff

Replace `agent-handoff/coder-report.md` with the complete Task 5D.1A Attempt 1
report. Include:

- Task/Attempt, branch, and exact Git-derived starting HEAD;
- implementation commit;
- changed files;
- exact public contracts and repository/service APIs;
- retention and expiry semantics;
- sensitive-ingress reuse and safe-failure behavior;
- SQLite schema/migration/transaction behavior;
- focused and full validation results;
- remaining risks and scope confirmation;
- one recommended review depth (`Light`, `Standard`, or `Deep`);
- one-sentence reason;
- 3–6 suggested Reviewer focus areas;
- Human Summary using the mandatory routing and one-sentence Handoff Note.

Recommended review depth is advisory. The Architect retains final authority.

Do not include the report commit's own SHA. The Independent Reviewer derives
it from Git.
