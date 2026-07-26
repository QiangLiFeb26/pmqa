# Coder Report

Owner: Coder

Task: PMQA Task 5D.1A — Conversation Session and Retention Foundation

Task ID: `PMQA-5D.1A`

Attempt: `1`

Status: Ready for Independent Reviewer

## Branch and Git Correlation

Branch:

`agent/task-5c-1-canonical-run-contract`

Exact Git-derived Coder starting HEAD:

`16655cd3a8129599a585b78bcc5336706d595a3b`

That commit was the latest pushed publication of
`agent-handoff/current-task.md`, identified Task `PMQA-5D.1A` Attempt `1`,
and was the clean local and tracking-branch HEAD before implementation
changes. Its Architect-reviewed baseline Reviewer HEAD is
`115910e2662ce6bd2de6f807dfb3dfddc201a4b3`. No prior Task 5C or Task 5D
implementation or handoff commit was amended.

## Implementation Commit

`4ae3893d4f12a4dff1a8f6bf18cbfcc07578be20`

Commit message:

`add conversation session retention foundation`

This report is committed separately after the implementation commit. The
Independent Reviewer derives the report commit from Git; this report does not
claim its own future commit SHA.

## Changed Files

Production:

- `pmqa/conversation/__init__.py`;
- `pmqa/conversation/contracts.py`;
- `pmqa/conversation/repository.py`;
- `pmqa/conversation/service.py`;
- `pmqa/security/sensitive_text.py`;
- `pmqa/security/__init__.py`; and
- `pmqa/reasoning/scrubber.py`.

Tests:

- `tests/test_conversation_contracts.py`;
- `tests/test_conversation_repository.py`;
- `tests/test_conversation_service.py`;
- `tests/test_conversation_imports.py`;
- `tests/test_scrubber.py`; and
- `tests/test_packaging.py`.

Documentation:

- `README.md`;
- `docs/Roadmap.md`;
- `docs/architecture.md`; and
- `docs/architecture/conversational-workflow-platform.md`.

Report-only handoff commit:

- `agent-handoff/coder-report.md`.

No CLI, dependency, packaging configuration, schema outside the new local
repository, Task 4/5/5A/5C contract, reasoning model/provider/trace, Product
Pack, or product implementation changed.

## Public Conversation Contracts

`pmqa.conversation` exports:

- `ConversationRetentionPolicy`;
- `ConversationSessionStatus`;
- `ConversationTurnStatus`;
- `ConversationTurnErrorCode`;
- `ConversationSession`;
- `ConversationTurn`;
- fixed-safe contract, sensitive-text, repository, and application errors;
- `ConversationRepository`;
- `InMemoryConversationRepository`;
- `SQLiteConversationRepository`; and
- `ConversationApplicationService`.

The strict frozen Pydantic v2 records forbid extra fields, hide invalid input,
use exact built-in plain-JSON wires, canonically serialize timestamps as UTC
`Z` with fixed microsecond precision, snapshot caller collections, reject
runtime objects/non-finite/coercive/overdeep/cyclic inputs, and expose exact
`to_dict()` / fixed-safe `from_dict()` / fully revalidated
`model_copy(update=...)` paths.

Identifiers reuse public `pmqa.run.validate_run_identifier`; no weaker
identifier or second prohibited-key policy was added. Session revision is
bounded to signed 64-bit positive range. Sessions permit at most 256 ordered,
unique turns. User and assistant text is bounded to 32 KiB, retains Unicode,
tabs and line breaks, and rejects other control characters. User text must be
nonblank; a completed assistant response may be the observed empty string,
which remains distinct from missing.

`ConversationSession` carries schema version, ID, monotonic revision,
active/closed status, retention policy, optional connection-context
correlation only, ordered turn IDs, and created/updated/expiration timestamps.
It contains no credential or connection object.

`ConversationTurn` carries immutable turn/session IDs, a positive bounded
sequence, pending/completed/failed lifecycle, user text, optional canonical
assistant response, optional fixed failure classification/message, and
creation/completion timestamps. Pending has no terminal fields; completed has
exactly one response and completion time; failed has no provider response and
only the fixed message mapped from its enum code.

## Retention and Activity Semantics

The Human decision is encoded exactly:

| Policy | Repository | Expiration |
| --- | --- | --- |
| `session_only` | injected volatile/in-memory repository only | `None` |
| `7_days` | injected durable repository | `updated_at + 7 days` |
| `30_days` | injected durable repository | `updated_at + 30 days` |
| `90_days` | injected durable repository | `updated_at + 90 days` |

The application default is `30_days`. No enum value represents indefinite
retention. A session-only contract rejects any expiration, while each durable
contract requires its exact derived expiration.

Successful session creation starts at revision 1. Successful turn start,
turn completion/failure, and session close each advance revision exactly once
and set session `updated_at` and durable `expires_at` from the same authoritative
clock sample. Turn creation equals the start transition time; terminal turn
completion equals its session transition time. Reads and lists sample no clock
and never extend expiration.

Static malformed/sensitive input is rejected before clock, identifier, or
repository activity. After that validation, each attempted create, turn start,
terminalization, close, or purge samples the injected clock exactly once.
Create and turn start sample their respective injected ID generator exactly
once; other operations sample no ID. Successful sequence numbers are gap-free.

Manual deletion is immediate and deletes the session/turns only from the
repository that owns the session. A second delete returns fixed
`session_not_found`; it is not silently idempotent. Purge samples one cutoff,
calls only the durable repository, deletes `expires_at <= cutoff` in
deterministic expiration/ID order, returns only bounded IDs, and never touches
session-only state.

Conversation deletion does not access or claim deletion of reasoning traces,
Task 5C usage, product artifacts, authorization, or receipts.

## Sensitive-Text Ingress

The Task 3 Bearer, Cookie, and credential-assignment patterns were extracted
from the reasoning scrubber into dependency-free
`pmqa.security.sensitive_text`. The shared primitive handles:

- Bearer values;
- Cookie and Set-Cookie header values; and
- API key, password/passwd, access/refresh token, token, secret, and
  credential assignments.

`DeterministicReasoningScrubber` uses the primitive to preserve its existing
redacted output, rule names, counts, and report behavior. Conversation
contracts and the application service use the same primitive to reject before
persistence rather than redact user/assistant records. No raw match is echoed,
persisted, hashed, logged, placed in a snapshot, or exposed through exception
cause/context.

Normal QA text such as “test the password field,” “token usage is
unavailable,” and `type=password` remains valid. The documentation explicitly
describes this as deterministic high-confidence defense in depth, not perfect
detection of arbitrary passwords.

## Repository APIs and Transition Enforcement

`ConversationRepository` defines:

- `create_session`;
- `get_session` / bounded `list_sessions`;
- `get_turn` / bounded `list_turns`;
- atomic `append_turn`;
- atomic `replace_turn`;
- revision-checked `close_session`;
- `delete_session`; and
- bounded `purge_expired`.

All input/output records cross canonical reconstruction. Both implementations
return independent immutable snapshots. Repository errors use stable codes and
messages; boundary wrappers recreate expected errors outside caught exception
contexts so public cause/context does not retain SQLite or caller details.
Resource/control-flow exceptions remain authoritative.

Repository transition validators enforce:

- exact expected revision before mutation;
- revision increments of exactly one;
- unchanged session identity, policy, connection reference, creation time,
  and existing turn order;
- active-session requirement;
- append-only next sequence and matching turn/session time;
- pending-to-one-terminal-state replacement only;
- unchanged turn identity, sequence, user text, and creation time;
- terminal turn/session timestamp correlation; and
- no close while a turn is pending.

Session turn IDs must exactly equal repository turn rows in sequence order.
Reads, writes, close, manual delete, and purge validate that cross-record index
before trusting or deleting data, so corruption cannot be hidden through
cleanup.

## In-Memory and SQLite Behavior

`InMemoryConversationRepository` stores canonical wire snapshots behind an
instance lock. It supports all policies for deterministic tests and is the
only repository selected for session-only service state. It retains no caller
collection or model reference.

`SQLiteConversationRepository` requires one explicit absolute caller-selected
database path and introduces no default. Its schema identity is:

```text
schema_name = pmqa.conversation
schema_version = 1
```

The database contains versioned metadata, `conversation_sessions`, and
`conversation_turns`; turn rows have a foreign key with delete cascade and a
unique `(session_id, sequence_number)`. Initialization validates exact table
columns and the foreign-key definition, not only the metadata version.
Session-only contracts are rejected before SQL.

Every connection enables and verifies foreign keys. Writes use
`BEGIN IMMEDIATE`, canonical compact sorted UTF-8 JSON payloads, typed
revision/time/index columns, expected-revision `UPDATE`, commit on complete
success, rollback on any expected failure, and deterministic close. Reads
defensively reconstruct public contracts, require canonical JSON, reject
duplicate keys/non-finite values/oversize payloads, cross-check typed columns,
and validate session/turn correlation. Schema drift, corruption, unavailable
database, duplicate, stale revision, and state conflict expose only fixed safe
errors without database path, SQL, payload, marker, or underlying context.

Manual delete and purge reconstruct and validate the selected records before
deletion. Tests prove corruption causes rollback and preserves the row rather
than silently erasing it.

## Conversation Application Service APIs

`ConversationApplicationService` receives explicit distinct volatile and
durable repositories, clock, and optional session/turn ID generators. It
provides:

- `create_session`;
- `get_session` / `list_sessions`;
- `get_turn` / `list_turns`;
- `start_turn`;
- `complete_turn`;
- `fail_turn`;
- `close_session`;
- `delete_session`; and
- `purge_expired`.

The service routes creation by exact retention policy and never writes
session-only content to the durable repository. Lookup resolves the owning
repository without transferring records. It snapshots dependency results,
rejects duplicate identities across repositories, validates bounded ordering
and correlations, and maps expected repository failures to fixed application
codes.

Invalid clocks and generated IDs fail before repository writes. Repository
write failure, stale revision, closed session, pending-close conflict,
sensitive response, and identifier collision leave existing state unchanged.
No reasoning provider, workflow/runner, LangGraph graph, Web framework, ADO
client, Product Pack, or external process is instantiated.

## Import and Packaging Isolation

`import pmqa.conversation` imports no FastAPI, Uvicorn, Playwright, product,
Product Pack, LangGraph, orchestration, workflow runtime, Supervisor,
reasoning execution, trace, application runner, provider client, Node, or UI
tooling. It performs no database connection, filesystem creation, discovery,
environment/config read, subprocess launch, or `sys.path` mutation.

Generic `import pmqa` and `import pmqa.cli` remain conversation-lazy. The real
wheel built from copied source in a pytest temporary directory includes all
four conversation modules plus the neutral security primitive. The wheel is
extracted and imports `pmqa.conversation` from an unrelated directory outside
the source checkout. Existing wheel exclusions reject `.sqlite`, `.sqlite3`,
runtime content, caches, generated tests, credentials, and unrelated files.
No packaging configuration or dependency change was required because existing
`pmqa*` discovery already includes the package and SQLite is standard library.

## Documentation Status

README, Roadmap, the architecture index, and the approved platform architecture
now record:

- Task 5D.0 passed architecture review;
- Task 5D.1A is ready for architecture review;
- Task 5D.1 is decomposed into 5D.1A persistence, 5D.1B secure loopback API,
  and 5D.1C workbench/CLI/packaging;
- the approved 30-day default and session-only/7/30/90 choices;
- immediate manual deletion and no silent indefinite retention;
- separate trace, usage, and receipt retention; and
- no Web/API/frontend/CLI/ADO/Copilot implementation in 5D.1A.

Stale-status search found no statement that Task 5D.0 remains awaiting review
or that 5D.1A is not started. 5D.1B and 5D.1C remain explicitly not started.

## Validation Results

- Task 5D.1A conversation, shared scrubber/boundary, import-isolation, and
  real-wheel packaging focused group: `151 passed`.
- Task 5C Run/Application/Usage regressions: `467 passed`.
- Task 4 runtime/reducer/Supervisor/LangGraph regressions: `98 passed` with
  one existing LangGraph pending-deprecation warning.
- Full default suite: `1970 passed, 5 skipped` with the same existing warning.
  The skips are existing opt-in live/external environment gates.
- Generated SauceDemo Playwright regressions: `2 passed`.
- Isolated `compileall` for `pmqa` and `products`: passed with bytecode routed
  to `/private/tmp`.
- Real PMQA wheel construction, content exclusions, external-directory
  import, and product config load: passed inside the focused packaging tests.
- Repository Markdown relative-link validation: all `19` files passed.
- Stale Task 5D status search: passed.
- `git diff --check`: passed.
- Pre-report implementation worktree: clean.

All new default tests are offline. SQLite tests use only pytest temporary
directories and no sleep. No browser, network, Node, provider, ADO identity,
or external Product Pack is required by the new tests.

## Remaining Risks and Open Items

- Sensitive-text inspection intentionally detects high-confidence recognizable
  shapes; arbitrary secrets without those shapes remain impossible to prove
  absent.
- Conversation deletion does not yet coordinate a future artifact repository;
  that repository must reuse the approved policy without conflating
  trace/usage/receipt retention.
- The synchronous repository/service boundary is local single-user
  foundation. Multi-user authorization, hosted concurrency, migrations beyond
  schema version 1, and backup/restore policy remain future work.
- Session/turn APIs carry only plain conversation lifecycle. Citations,
  workflow suggestions, capabilities, structured artifacts, approvals, and
  receipts remain intentionally absent.

These are documented scope boundaries, not known Task 5D.1A blockers.

## Scope Confirmation

Task 5D.1B, 5D.1C, 5D.2, Task 5B, Task 6, and Task 7 were not started. No
FastAPI/Uvicorn/HTTP/REST/SSE/CORS/CSRF/cookie/session-token transport, React /
TypeScript/Vite/Node/browser UI, `pmqa web`, CLI change, reasoning-provider
call, workflow execution, capability registry, ADO connection, structured QA
artifact, authorization, external operation, receipt, usage UI, or
provider-session AIC was added. No PR was created and nothing was merged.

## Recommended Review Depth

**Deep**

Reason: this checkpoint establishes persisted user-text, retention, revision,
SQLite transaction, deletion, corruption, and safe-ingress boundaries that
the future local Web trust boundary will depend on.

## Suggested Reviewer Focus

- Challenge direct construction, canonical reconstruction, revalidated copies,
  text bounds, sensitive patterns, and lifecycle/expiration invariants for
  bypass or marker leakage.
- Exercise two repository instances, stale expected revisions, duplicate
  IDs/sequences, malformed schema/rows, cross-record turn-index corruption,
  rollback, deletion, and exact purge cutoff behavior.
- Verify service sampling order/counts, volatile-versus-durable routing,
  gap-free successful sequence, closed/pending conflicts, dependency
  snapshots, and zero partial mutation on failures.
- Confirm the shared sensitive-text primitive preserves Task 3 scrubber output
  while accepting ordinary password/token QA discussion and making no perfect
  secret-detection claim.
- Inspect public error cause/context containment and exact propagation of
  `MemoryError`, `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit`.
- Verify import/wheel isolation and confirm no Web/API/frontend/CLI/ADO/Copilot
  implementation or runtime content entered the distribution.

## Human Summary

PMQA-5D.1A Attempt 1 已完成，Git 派生起点为 `16655cd3a8129599a585b78bcc5336706d595a3b`。
实现提交为 `4ae3893d4f12a4dff1a8f6bf18cbfcc07578be20`。
新增严格 conversation session/turn contracts、30 天默认 retention、内存与 SQLite repositories、revision CAS、manual delete/purge 和同步 application service。
敏感文本 ingress 与 Task 3 scrubber 共用同一 neutral primitive，固定安全拒绝且不泄露 marker。
验证结果：focused 151、Task 5C 回归 467、Task 4 回归 98、全量 1970 passed / 5 skipped、Playwright 2 passed。
Action Needed From Human: 请将下方 Handoff Note 传递给 Independent Reviewer。
Handoff Note: 请读取 agent-handoff/README.md 与 agent-handoff/current-task.md，从 Git 派生最新 coder-report commit，并按独立审查顺序完成 review。
