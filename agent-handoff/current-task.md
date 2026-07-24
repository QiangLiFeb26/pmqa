# Current Task

Owner: Architect

Task: PMQA Task 5C.6 — Append-Only Local AI Invocation Repository

Task ID: `PMQA-5C.6`

Attempt: `1`

Status: Ready for Coder

Branch: `agent/task-5c-1-canonical-run-contract`

Architect reviewed baseline:
`efe5ee01ec9ddfa574eef74f333fb98ed46528b2`

Coder starting HEAD: derive and record the latest pushed branch commit that
contains this task publication before changing implementation files.

Repository Markdown and Git history are authoritative. Chat summaries are
informational only. This task uses the adopted
Coder → Independent Reviewer → Architect workflow.

## Task Objective

Add a provider-neutral, append-only local repository for canonical Task 5C.4/
5C.5 `AIInvocationRecord` values.

The repository must persist only canonical metrics and correlation metadata,
never raw prompts, model responses, credentials, provider clients, CLI output,
or runtime handles.

This checkpoint is persistence and deterministic retrieval only. It does not
integrate the collector, aggregate summaries, expose a CLI, parse provider
output, or calculate cost.

## Background

Task 5C.4 established provider-neutral invocation, usage, cost, and pricing
contracts. Task 5C.5 added an exactly-once runtime collector that returns one
canonical terminal `AIInvocationRecord`.

Those records currently remain in memory. Task 5C.6 adds the smallest safe
local persistence boundary needed by later run/session summaries:

```text
AIInvocationRecord
        |
        v
UsageRepository
        |
        v
explicit local JSON repository
```

The existing `StorageProvider` stores generic mutable artifacts and allows
replacement. It is not the correct contract for immutable invocation history.
The existing SQLite reasoning trace store contains prompt/response-oriented
trace semantics and must not be reused or extended for usage records.

Do not introduce a database in this checkpoint.

## Scope

Add:

1. a provider-neutral `UsageRepository` protocol or abstract boundary;
2. fixed safe repository failures;
3. one explicit local JSON implementation using one immutable file per
   invocation;
4. deterministic retrieval by invocation, session, run, and recent order;
5. duplicate-safe and concurrent-writer-safe publication;
6. strict reconstruction and corruption detection;
7. focused persistence, concurrency, security, import, and packaging tests;
8. one durable threaded terminalization regression for the Task 5C.5
   collector;
9. concise architecture/status documentation.

## Repository Interface

Expose a small synchronous interface equivalent to:

```python
class UsageRepository(Protocol):
    def save(self, record: AIInvocationRecord) -> None:
        ...

    def get(self, invocation_id: str) -> AIInvocationRecord:
        ...

    def find_by_session(
        self,
        session_id: str,
        *,
        limit: int = ...,
    ) -> tuple[AIInvocationRecord, ...]:
        ...

    def find_by_run(
        self,
        run_id: str,
        *,
        limit: int = ...,
    ) -> tuple[AIInvocationRecord, ...]:
        ...

    def list_recent(
        self,
        *,
        limit: int = ...,
    ) -> tuple[AIInvocationRecord, ...]:
        ...
```

Exact names may differ if clearer. Do not add update, delete, overwrite,
upsert, raw-query, arbitrary-filter, or mutable registration methods.

Requirements:

- exact canonical identifiers reuse the existing Run/Usage policy;
- limits are exact bounded positive integers and reject `bool`;
- results are immutable tuples of independently reconstructed records;
- ordering is deterministic newest-first by `completed_at`, with one
  documented invocation-ID tie-breaker;
- missing `get` uses a fixed not-found error rather than returning fabricated
  data;
- queries distinguish an empty result from storage failure;
- no method accepts or returns raw dictionaries.

## Local JSON Layout

Use an explicit caller-supplied repository root. There is no implicit
environment variable or current-working-directory discovery.

Recommended layout:

```text
<root>/
  invocations/
    <sha256-of-canonical-invocation-id>.json
```

Requirements:

- use lowercase SHA-256 of the canonical UTF-8 invocation ID for the filename;
- do not place raw provider, model, session, run, or invocation identifiers in
  filesystem paths;
- each file contains exactly one canonical `AIInvocationRecord.to_dict()`
  JSON object and a trailing newline;
- serialized JSON uses deterministic UTF-8, sorted keys, and compact
  separators;
- the record's schema version remains authoritative;
- no repository-specific metadata is inserted into the domain record;
- read-time validation recomputes the filename digest from the reconstructed
  invocation ID;
- non-record files and private incomplete-publication siblings are never
  treated as records.

Document `artifacts/usage/` as an example operator-selected root, not a hidden
default. Add only the narrow root-level ignore rule needed to prevent that
example runtime output from being committed.

## Append-Only and Publication Semantics

Saving must:

1. require an exact `AIInvocationRecord`;
2. reconstruct an independent canonical snapshot before filesystem effects;
3. serialize and enforce a bounded byte size before publication;
4. create the repository directory safely;
5. publish one complete same-filesystem record without replacing an existing
   target;
6. report an existing target as a fixed duplicate error whether its content
   is identical or different;
7. leave an already published record unchanged on every later failure.

Publication must be atomic and no-replace from the repository reader's point
of view. Concurrent repository instances attempting the same invocation ID
must produce exactly one success and duplicate failures for all losers.

Do not use `os.replace()`, overwrite mode, unlink-and-retry, recursive cleanup,
or a check-then-overwrite sequence.

If the selected platform cannot provide the required safe publication
primitive, fail with a fixed unsupported/IO error before replacing data.

Temporary files:

- must be created in the same private invocation directory;
- use a restrictive file mode where supported;
- must not contain identifiers in their names;
- are not records and are ignored by readers;
- may be left as private orphans after ambiguous publication/cleanup failure;
- must never trigger deletion of an unknown replacement path;
- owned descriptors are closed exactly once;
- no recursive cleanup is allowed.

Keep the implementation proportional to a trusted local repository root. Do
not claim protection against a malicious operating-system administrator.

## Read and Corruption Semantics

Reads must:

- consider only exact lowercase 64-character hexadecimal `.json` record
  names;
- reject symlink/non-regular record entries rather than following them;
- enforce a bounded file size before reading;
- require UTF-8 and one exact JSON object;
- reject duplicate JSON keys, non-finite constants, excessive nesting,
  noncanonical representations, unknown fields, and trailing non-whitespace
  data;
- reconstruct through `AIInvocationRecord.from_dict()`;
- require exact canonical JSON equality with the stored object;
- require filename digest to match reconstructed invocation ID;
- expose corruption only through a fixed safe data error;
- never expose file paths, record IDs, payload values, byte content, parser
  messages, object repr, secret markers, or underlying exceptions.

A corrupt matching record must not be silently skipped by `get`, query, or
recent-list operations. Queries fail safely rather than returning a misleading
partial result.

Resource/control-flow exceptions (`MemoryError`, `KeyboardInterrupt`,
`SystemExit`, `GeneratorExit`) remain authoritative.

## Repository Failure Vocabulary

Define a small fixed vocabulary for:

- invalid repository configuration;
- invalid record or identifier;
- duplicate record;
- record not found;
- persistence failure;
- read failure;
- corrupt/inconsistent stored data;
- unsupported safe publication when needed.

Exact names may vary, but:

- every expected error has a bounded static message;
- no error exposes a root path, filename, identifier, JSON data, marker,
  underlying exception, cause, or context;
- callers can distinguish duplicate, not-found, invalid input, corruption,
  and operational I/O failures;
- unexpected programming errors are not silently mislabeled when they fall
  outside the explicit repository boundary.

## Security and Data-Minimization Requirements

The repository accepts only exact canonical `AIInvocationRecord` values.
Therefore it must never persist:

- prompts or model responses;
- credentials, passwords, PATs, API keys, tokens, cookies, authentication or
  browser storage state;
- environment mappings;
- provider clients or SDK objects;
- raw provider metadata;
- CLI stdout/stderr, terminal output, commands, executable paths, working
  directories, or repository paths;
- DOM/HTML, screenshots, traces, selectors, Page/Locator/browser objects;
- `AIInvocationHandle`, collector objects, callables, locks, file handles, or
  arbitrary metadata.

Do not create a second prohibited-key list. Reuse the canonical Usage/Run
contract boundary and reconstruct records on both write and read.

## Collector Concurrency Follow-up

Add one focused durable regression to `tests/test_usage_collector.py`:

- create multiple real threads competing to terminalize the same handle;
- use thread-safe deterministic fake clocks;
- prove exactly one terminal record is returned;
- prove every loser receives the fixed invalid-handle error;
- prove terminal wall and monotonic clocks are each sampled exactly once;
- avoid timing sleeps and probabilistic assertions.

Do not change collector production code unless this deterministic test exposes
a real defect. If it does, stop and report rather than expanding the storage
task silently.

## Import and Dependency Isolation

Importing `pmqa.usage` and the repository modules must not:

- create directories or files;
- inspect environment/configuration/distributions;
- instantiate a repository or collector;
- launch processes, browsers, Node.js, or network calls;
- load products, Product Packs, Playwright, LangGraph, orchestration,
  Supervisor, concrete runners, Application Service, reasoning providers,
  trace storage, SQLite, CLI, or UI.

The local JSON repository may use only the Python standard library and the
neutral usage contracts. No runtime dependency may be added.

The PMQA wheel must include the repository code and exclude usage runtime
output, private temporary files, tests, caches, and generated artifacts.

## Required Tests

At minimum cover:

### Canonical save/load

- successful save/get round trip;
- exact JSON/canonical byte form;
- independent caller snapshot;
- explicit unavailable usage/cost;
- present numeric zero;
- model-unavailable records;
- optional runner invocation correlation;
- retry/fallback records;
- duplicate save with same and different content;
- no overwrite after duplicate or later failure.

### Queries

- deterministic session filtering;
- deterministic run filtering;
- recent ordering;
- tie-break ordering;
- bounded limit;
- empty query result;
- missing get;
- independently reconstructed returned records;
- corrupt matching record fails the whole query.

### Publication and concurrency

- two or more repository instances publishing the same invocation
  concurrently;
- exactly one success and duplicate failures;
- no partial published record;
- private incomplete siblings ignored;
- publication failure preserves existing targets;
- descriptor/resource cleanup policy;
- unsupported safe-publication behavior when applicable.

### Corruption and security

- malformed JSON;
- duplicate keys;
- non-finite constants;
- non-UTF-8 bytes;
- unknown/missing fields;
- noncanonical coercible JSON;
- oversized file;
- filename/content digest mismatch;
- symlink and non-regular record entries;
- marker/path/payload/exception leakage;
- prohibited/runtime values rejected before I/O;
- resource/control-flow exception propagation.

### Compatibility

- threaded Task 5C.5 collector regression;
- import isolation;
- real-wheel inclusion and output exclusion;
- Task 5C.4/5C.5 focused regressions;
- Run/Runner/Application and boundary regressions;
- Task 4 orchestration regressions;
- full default suite.

All new tests must use pytest temporary directories and deterministic fixtures.
They must not use a model, provider CLI, network, browser, Node.js, external
Product Pack, or repository-local runtime output.

## Documentation

Update only what is necessary:

- `docs/Roadmap.md`: mark Task 5C.5 architecture review passed and Task 5C.6
  ready for review after implementation;
- `docs/architecture.md`: separate runtime collection from local persistence;
- extend `docs/architecture/usage-cost-contracts.md`;
- update `README.md` only for concise current status;
- add the narrow root-level ignore rule for the documented example usage
  output.

Document:

- why generic `StorageProvider` and reasoning trace storage are not reused;
- immutable per-invocation files versus JSONL/database trade-off;
- digest filenames and append-only publication;
- trusted local-root boundary;
- corruption behavior;
- collector and repository remain explicitly decoupled;
- deferred aggregation, summaries, CLI, provider parsing, cost calculation,
  workflow integration, retention, compaction, and optimization.

## Allowed Changes

- focused repository files under `pmqa/usage/`;
- `pmqa/usage/__init__.py`;
- focused new tests under `tests/`;
- one additive threaded regression in `tests/test_usage_collector.py`;
- minimal additive `tests/test_packaging.py` and
  `tests/test_usage_imports.py` coverage;
- `.gitignore`;
- `README.md`;
- `docs/Roadmap.md`;
- `docs/architecture.md`;
- `docs/architecture/usage-cost-contracts.md`;
- `agent-handoff/coder-report.md`.

The Coder must not modify:

- `agent-handoff/README.md`;
- `agent-handoff/current-task.md`;
- `agent-handoff/reviewer-report.md`;
- `agent-handoff/architect-review.md`;
- Task 5C.4 wire fields or semantics;
- collector production behavior unless the required concurrent regression
  proves a defect and the Coder stops for Architect direction.

Use one focused implementation commit and one report-only Coder handoff
commit. Do not amend prior commits.

## Out of Scope

Do not implement:

- collector-to-repository automatic wiring;
- run/session aggregation or summary models;
- CLI commands or output;
- provider or CLI parser;
- pricing selection, cost calculation, or pricing tables;
- retention, deletion, compaction, archival, migration, or schema upgrade;
- SQLite or another database;
- background writer, queue, callback, sink, event bus, watcher, or daemon;
- encryption or key management;
- authorization or multi-user service semantics;
- remote/object/cloud storage;
- UI, API, dashboard, budgets, alerts, or optimization;
- changes to RunRecord, RunnerInvocationRecord, WorkflowState, LangGraph,
  Supervisor, Task 5, Product Pack, or existing provider behavior;
- Task 5B, Task 6, or Task 7;
- PR creation or merge.

## Validation Commands

Run and report:

```bash
.venv/bin/python -m pytest tests/test_usage_repository.py tests/test_usage_collector.py tests/test_usage_contracts.py tests/test_usage_pricing.py tests/test_usage_imports.py -q
.venv/bin/python -m pytest tests/test_run_contracts.py tests/test_runner_contracts.py tests/test_application_contracts.py tests/test_application_service.py tests/test_boundary_policy.py tests/test_packaging.py -q
.venv/bin/python -m pytest tests/test_workflow_runtime.py tests/test_workflow_reducer.py tests/test_supervisor_policy.py tests/test_langgraph_workflow.py -q
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest products/demo/generated_tests -q
.venv/bin/python -m compileall -q pmqa products
git diff --check
git status --short
```

If the chosen repository test filename differs, document the exact
substitution. Do not silently omit a validation.

## Expected Deliverables

- Provider-neutral repository contract and fixed failures.
- Explicit append-only local JSON implementation.
- Canonical duplicate-safe save/get/query behavior.
- Corruption detection and data-minimizing storage.
- Concurrent no-replace publication evidence.
- Durable collector contention regression.
- Import/packaging coverage and concise documentation.
- Updated `agent-handoff/coder-report.md`.
- One implementation commit and one report-only commit.
- Clean synchronized branch.
- No PR, merge, Reviewer implementation, or out-of-scope integration.

## Required Coder Handoff

Replace `agent-handoff/coder-report.md` with the complete Task 5C.6 report.

Include:

- Task/Attempt, branch, and exact Git-derived Coder starting HEAD;
- implementation commit;
- changed files;
- repository public API and layout;
- publication/no-replace strategy;
- query ordering and corruption policy;
- security and import evidence;
- validation results;
- remaining risks and scope confirmation;
- exactly one recommended review depth: `Light`, `Standard`, or `Deep`;
- one-sentence reason;
- 3–6 suggested Reviewer focus areas;
- copy-ready Reviewer Handoff Note in the Human Summary.

The Coder recommendation is advisory. The Independent Reviewer and Architect
independently select their actual review depths.
