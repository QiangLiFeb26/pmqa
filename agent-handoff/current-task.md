# Current Task

Owner: Architect

Task: PMQA Task 5C.6 — Repository Root and Platform Boundary Hardening

Task ID: `PMQA-5C.6`

Attempt: `2`

Status: Changes Required

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed attempt 1 Reviewer HEAD:
`339191498e7b2a2cfcb473483f1f88509f06bc8a`

Coder starting HEAD: derive and record the latest pushed branch commit that
contains this remediation publication before changing implementation files.

Repository Markdown and Git history are authoritative. Chat summaries are
informational only.

## Task Objective

Close three Task 5C.6 persisted-boundary findings without changing repository
layout, public query behavior, canonical invocation schemas, or append-only
publication semantics:

1. reject semantic-root and invalid OS repository paths;
2. contain missing/unsupported platform capabilities behind fixed safe
   failures;
3. contain JSON parser overflow as corrupt persisted data.

## Background

Task 5C.6 attempt 1 implemented a strong per-invocation local JSON repository
and passed Coder and Independent Reviewer validation. Architect review found
three adversarial gaps:

```text
LocalJSONUsageRepository(Path("/tmp/.."))
    -> accepted; target becomes /invocations

LocalJSONUsageRepository(Path("/tmp/runtime\0marker")).save(record)
    -> raw ValueError("embedded null byte")

os.fchmod absent during save
    -> raw AttributeError and private temporary orphan
```

The complete evidence and disposition are in
`agent-handoff/architect-review.md`.

## Scope

- Harden caller-supplied repository root validation.
- Harden optional/unsupported platform-function handling.
- Add parser `OverflowError` containment.
- Add focused adversarial regressions.
- Update the focused usage architecture document only if platform support
  wording needs clarification.
- Replace `agent-handoff/coder-report.md` with the attempt 2 report.

Do not otherwise refactor the repository.

## Required Correction 1 — Repository Root Validation

The constructor must remain side-effect free and require one explicit absolute
non-root `Path`.

Reject before any filesystem effect:

- the filesystem anchor itself;
- any path containing a `..` component;
- any absolute path that could lexically or semantically select the anchor
  after normalization;
- an embedded NUL;
- invalid/unrepresentable path values that would later produce a raw
  `ValueError`, `TypeError`, or platform conversion failure;
- non-`Path`, relative, and existing prohibited cases.

Requirements:

- do not silently rewrite a traversal-containing operator path;
- do not call `resolve()` in a way that follows symlinks and converts an
  existing symlink root into an accepted target;
- retain one private canonical path snapshot not controlled by a mutable
  caller object;
- valid absolute paths, including ordinary spaces, remain supported;
- expected invalid paths raise only
  `UsageRepositoryErrorCode.INVALID_CONFIGURATION`;
- error message, cause, and context expose no path or marker.

Add tests using platform-derived anchors rather than hard-coded POSIX-only
assertions where practical:

- `<anchor>/tmp/..`;
- nested parent traversal that would reach the anchor;
- parent traversal that would select a different directory;
- embedded NUL with a secret marker;
- existing file and symlink roots;
- valid absolute paths with spaces;
- no directory/file creation for every rejected constructor input.

## Required Correction 2 — Platform Capability Boundary

Inventory every OS capability used by publication:

- temporary creation;
- restrictive descriptor mode when supported;
- file synchronization;
- hard-link no-replace publication;
- directory synchronization;
- identity-based cleanup and descriptor release.

Required behavior:

- missing or explicitly not-implemented optional functions must never leak
  `AttributeError` or `NotImplementedError`;
- absence of `os.fchmod` must either:
  - use the secure `mkstemp` result under the documented trusted local
    directory when this is safe for the platform; or
  - fail before target publication through a fixed safe unsupported error;
- absence of `os.link`, or a mandatory hard-link capability that reports
  unsupported, must produce `UNSUPPORTED_PUBLICATION` before a target exists;
- if directory synchronization is mandatory for the claimed durability,
  preflight it before target publication on a platform that cannot perform it;
- if a post-publication synchronization call fails unexpectedly, preserve the
  complete published target and return the existing fixed persistence error;
- Unix restrictive mode checks remain enforced where supported;
- a platform without meaningful Unix mode bits must not leak an exception or
  silently claim a guarantee it did not enforce;
- no fallback may use overwrite, `os.replace`, rename-over-target,
  check-then-write, unlink-and-retry, or a weaker publication primitive;
- no platform-specific runtime dependency may be added.

Full Windows support is not required. A deterministic, documented, fixed safe
unsupported result is acceptable.

Add simulated capability tests that do not depend on the test host:

- `os.fchmod` absent;
- `os.fchmod` reports `NotImplementedError`;
- `os.link` absent;
- hard-link unsupported errno;
- mandatory directory-sync capability unavailable before publication;
- post-publication directory-sync failure preserves the record;
- no raw platform exception or marker leaks;
- descriptors close exactly once;
- only identity-verified owned temporary paths may be removed;
- no target exists for pre-publication unsupported failures.

The Coder must choose and document whether a private orphan is permitted for
each pre-publication failure. Any orphan must remain non-record, restrictive,
and identifier-free.

## Required Correction 3 — Parser Overflow

Contain `OverflowError` raised inside persisted JSON/numeric reconstruction as
fixed `UsageRepositoryErrorCode.CORRUPT_DATA`.

Requirements:

- containment is scoped to `_parse_record`/JSON reconstruction;
- the public error exposes no raw data, marker, parser message, cause, or
  context;
- `MemoryError`, `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit`
  continue to propagate with exact identity;
- valid canonical records remain unchanged.

Add:

- one simulated `json.loads` `OverflowError` regression;
- one real oversized/extreme numeric payload case where the interpreter can
  produce a bounded parser/contract rejection;
- cause/context and marker-leak assertions;
- controls proving resource/control-flow exceptions still propagate.

## Preserve Existing Behavior

Do not change:

- `UsageRepository` public methods;
- file layout or digest naming;
- canonical sorted compact UTF-8 bytes plus trailing newline;
- `AIInvocationRecord` fields or validation;
- duplicate/not-found/query semantics;
- newest-first and invocation-ID tie ordering;
- exact bounded limits;
- atomic hard-link no-replace publication on supported platforms;
- corruption fails whole matching query;
- symlink/non-regular/digest/canonical-byte checks;
- collector implementation or threading behavior;
- import and packaging isolation.

The redundant structural equality check noted by the Reviewer may remain.

## Allowed Changes

- `pmqa/usage/repository.py`;
- `tests/test_usage_repository.py`;
- minimal additive `tests/test_usage_imports.py` or
  `tests/test_packaging.py` only if the correction changes those boundaries;
- `docs/architecture/usage-cost-contracts.md` only if needed to state platform
  capability behavior accurately;
- `agent-handoff/coder-report.md`.

Do not modify:

- `agent-handoff/README.md`;
- `agent-handoff/current-task.md`;
- `agent-handoff/reviewer-report.md`;
- `agent-handoff/architect-review.md`;
- `pmqa/usage/contracts.py`;
- `pmqa/usage/pricing.py`;
- `pmqa/usage/collector.py`;
- `RunRecord`, Runner, Application Service, WorkflowState, LangGraph,
  Supervisor, Task 5, or Product Pack behavior;
- general README, Roadmap, or architecture status.

Use one focused remediation implementation commit and one report-only Coder
handoff commit. Do not amend attempt 1.

## Out of Scope

Do not add:

- a different persistence format or database;
- collector-to-repository wiring;
- aggregation, summaries, CLI, UI, or workflow integration;
- pricing selection or cost calculation;
- provider parsing or adapters;
- retention, deletion, compaction, migration, background work, remote storage,
  authorization, encryption, or key management;
- automatic platform fallbacks that weaken no-replace safety;
- new runtime dependencies;
- Task 5B, Task 6, or Task 7;
- PR creation or merge.

## Required Tests

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

Use an isolated bytecode cache. New tests remain offline and do not invoke a
model, provider CLI, network, browser, Node.js, or external Product Pack.

## Acceptance Criteria

- traversal/root-equivalent paths cannot target an anchor-level repository;
- invalid OS paths fail at construction with fixed safe errors;
- no raw `ValueError`, `AttributeError`, `NotImplementedError`, path, marker,
  or platform message escapes expected boundaries;
- missing/unsupported mandatory capabilities fail safely before publication;
- supported-platform atomic no-replace semantics remain unchanged;
- post-publication failure preserves the target;
- descriptor and temporary ownership remain exactly controlled;
- parser overflow is fixed corrupt-data evidence;
- existing repository, collector, contract, import, package, and orchestration
  regressions remain green;
- only allowed files change.

## Expected Deliverables

- hardened root validation;
- deterministic platform-capability behavior;
- parser overflow containment;
- focused adversarial tests;
- one remediation implementation commit;
- one report-only Coder handoff commit;
- clean synchronized branch;
- no PR or merge.

## Required Coder Handoff

Replace `agent-handoff/coder-report.md` with the complete Task 5C.6 attempt 2
report. Include:

- Task/Attempt, branch, and exact Git-derived starting HEAD;
- remediation implementation commit;
- changed files;
- F1–F3 correction evidence;
- platform capability policy;
- test results;
- remaining risks and scope confirmation;
- one recommended review depth with reason and 3–6 focus areas;
- Human Summary using the required routing and one-sentence Handoff Note.

Do not include the report commit's own SHA. The Independent Reviewer derives
it from Git.
