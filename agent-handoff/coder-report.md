# Coder Report

Owner: Coder

Task: PMQA Task 5C.6 — Append-Only Local AI Invocation Repository

Task ID: `PMQA-5C.6`

Attempt: `1`

Status: Ready for Independent Reviewer

## Branch and Git Correlation

Branch:

`agent/task-5c-1-canonical-run-contract`

Exact Git-derived Coder starting HEAD:

`ce1334f4a096dd014170a8791d99969b40c4501b`

That commit is the latest path-specific publication of
`agent-handoff/current-task.md`, identifies Task `PMQA-5C.6` Attempt `1`, and
was the clean local and tracking-branch HEAD before implementation. It is
reachable from the implementation commit below. The Architect-reviewed
baseline named by the task,
`efe5ee01ec9ddfa574eef74f333fb98ed46528b2`, is an ancestor of the starting
HEAD. No prior commit was amended.

## Implementation Commit

`08dee16d43c02f42c32591e242b30bc4035033cb`

Commit message:

`add append-only usage repository`

This report is committed separately after the implementation commit. The
Independent Reviewer derives the report commit from Git; this report does not
claim its own future commit SHA.

## Changed Files

Implementation commit:

- `.gitignore`
- `README.md`
- `docs/Roadmap.md`
- `docs/architecture.md`
- `docs/architecture/usage-cost-contracts.md`
- `pmqa/usage/__init__.py`
- `pmqa/usage/repository.py`
- `tests/test_packaging.py`
- `tests/test_usage_collector.py`
- `tests/test_usage_imports.py`
- `tests/test_usage_repository.py`

Report-only handoff commit:

- `agent-handoff/coder-report.md`

No Architect- or Reviewer-owned handoff file changed.

## Repository Public API and Layout

`pmqa.usage` now exports:

- runtime-checkable synchronous `UsageRepository`;
- `LocalJSONUsageRepository`;
- fixed `UsageRepositoryErrorCode` and `UsageRepositoryError`; and
- bounded default/maximum query and record-size constants.

The protocol exposes only `save`, `get`, `find_by_session`, `find_by_run`, and
`list_recent`. It accepts and returns canonical `AIInvocationRecord` values,
never raw dictionaries or mutable query results. The local implementation
requires an explicit absolute non-root `Path` and has no constructor or import
side effects.

Each record is stored at:

```text
<root>/invocations/<lowercase-sha256-of-canonical-invocation-id>.json
```

The file is the exact sorted, compact UTF-8 serialization of
`AIInvocationRecord.to_dict()` followed by one newline. No repository metadata
or raw domain identifier is added to the path or payload.

## Append-Only Publication

Save reconstructs an exact independent record snapshot and enforces the byte
limit before any filesystem effect. It creates a mode-`0600` temporary file in
the private mode-`0700` invocation directory, writes and synchronizes the
complete payload, and publishes with same-directory `os.link()` no-replace
semantics. Existing targets are always fixed duplicate failures; no
check-then-overwrite, replacement, unlink-and-retry, or recursive cleanup path
exists.

Concurrent repository instances have one successful publisher and duplicate
losers. Readers observe either no target or one complete canonical target.
Publication failures leave existing targets unchanged. Unsupported hard-link
publication has a distinct fixed code. Temporary cleanup unlinks only the
captured owned inode, descriptors receive one close attempt, release `OSError`
is suppressed, and resource/control-flow exceptions remain authoritative.
Post-publication synchronization or release failure never removes the
published target.

## Retrieval, Ordering, and Corruption

Only exact lowercase 64-hex `.json` names are record candidates; private
temporary and unrelated files are ignored. Reads reject symlink and
non-regular entries, oversize, identity changes, invalid UTF-8, malformed
JSON, duplicate keys, non-finite constants, excessive nesting, missing or
unknown fields, noncanonical representations, and filename/content digest
mismatch. Reconstruction uses `AIInvocationRecord.from_dict()` and exact
canonical byte equality. A corrupt matching record fails the whole query
rather than returning a partial result.

Session, run, and recent queries return independently reconstructed immutable
tuples. They order newest `completed_at` first and use ascending
`invocation_id` for equal timestamps. Limits are exact bounded positive
integers with `bool` rejected. Missing `get`, empty query, operational read
failure, corruption, duplicate, and invalid input remain distinguishable.

## Security, Import, and Packaging Evidence

The repository accepts only exact canonical `AIInvocationRecord` values, so it
adds no prompt, response, credential, environment, provider object, process
output, browser state, runtime handle, callback, or arbitrary metadata
surface. Invalid values are rejected before I/O. Expected exceptions use
bounded static messages raised without cause or context; tests inject marker
paths, payloads, and underlying exception text and prove none escape.

Import-isolation coverage proves `import pmqa.usage` performs no filesystem,
environment, distribution, process, browser, product, provider, runner,
Application Service, workflow, LangGraph, storage, SQLite, CLI, or UI work.
Top-level `pmqa` remains usage-lazy. The real-wheel regression includes
`pmqa/usage/repository.py`, exercises the exported repository from outside the
source checkout, and excludes usage output and private temporary files. No
runtime or build dependency was added.

## Collector Concurrency Regression

Eight real threads compete to terminalize one Task 5C.5 handle using
thread-safe deterministic clocks and a barrier, with no sleeps. Exactly one
thread receives the canonical terminal `AIInvocationRecord`; all seven losers
receive the fixed invalid-handle error. Start and terminal wall/monotonic
clocks are each sampled once, for two calls per clock total. No collector
production code changed.

## Validation Results

- Focused repository, collector, Task 5C.4 usage/pricing, and import tests:
  `199 passed`.
- Run, Runner contract, Application contract/service, boundary-policy, and
  real-wheel packaging regressions: `332 passed`.
- Task 4 runtime, reducer, Supervisor, and LangGraph regressions:
  `98 passed` with one existing LangGraph pending-deprecation warning.
- Full default suite: `1760 passed, 5 skipped` with the same existing warning.
  The skips are existing opt-in live/external environment gates.
- Generated SauceDemo Playwright regressions: `2 passed`. The sandboxed
  Chromium launch was denied by macOS Mach-port permissions; the required
  rerun with local browser permission passed.
- Isolated `compileall` for `pmqa`, `products`, and examples: passed with
  bytecode directed to a temporary directory.
- Markdown relative-link validation: passed.
- `git diff --check`: passed.
- Pre-report implementation worktree: clean.

All default, repository, packaging, and collector tests remained offline. The
new tests invoked no model, provider CLI, network, browser, Node.js, or
external Product Pack.

## Scope Confirmation

No collector-to-repository wiring, aggregation, summary model, CLI output,
provider parser, pricing selection, cost calculation, retention, deletion,
compaction, archival, migration, database, background writer, callback,
workflow integration, UI, remote storage, or authorization surface was added.
`RunRecord`, `RunnerInvocationRecord`, WorkflowState, LangGraph, Supervisor,
Task 5, Product Pack, and existing provider behavior were not modified. Task
5B, Task 6, and Task 7 were not started. No PR was created and nothing was
merged.

## Remaining Risks and Open Items

- Hard-link publication is intentionally required; filesystems without the
  primitive fail safely as unsupported rather than weakening no-replace
  semantics.
- The explicit repository root is a trusted local operator boundary; malicious
  operating-system administrators and remote/multi-user storage are outside
  this checkpoint.
- Per-file scans are deliberately simple and deterministic; aggregation,
  indexing, retention, and migration remain deferred.

These are explicit task boundaries, not known acceptance blockers.

## Recommended Review Depth

**Deep**

Reason: append-only filesystem publication, descriptor ownership, concurrent
writers, and adversarial corruption handling form a compact but
security-sensitive durability boundary.

## Suggested Reviewer Focus

- Challenge atomic no-replace behavior across duplicate, concurrent,
  post-publication, unsupported-filesystem, and cleanup-failure paths.
- Verify temporary inode ownership and exactly-once descriptor release under
  active and release-originated resource/control-flow exceptions.
- Inspect read-time symlink, identity, size, canonical-byte, digest, and
  whole-query corruption enforcement.
- Confirm fixed errors cannot leak roots, identifiers, payload markers, or
  underlying exception details and that invalid records fail before I/O.
- Confirm deterministic ordering, exact bounded limits, collector contention,
  import isolation, and real-wheel inclusion/output exclusion.

## Human Summary

Task 5C.6 Attempt 1 已在指定分支完成，起点为 `ce1334f4a096dd014170a8791d99969b40c4501b`。
实现提交为 `08dee16d43c02f42c32591e242b30bc4035033cb`。
新增 provider-neutral append-only usage repository、原子 no-replace 发布、确定性查询与严格损坏检测。
并发发布、descriptor 所有权、固定安全错误、import/wheel 隔离及真实线程 collector 竞争均有专项覆盖。
验证结果：focused 199、边界/packaging 332、Task 4 回归 98、全量 1760 passed / 5 skipped、Playwright 2 passed。
未加入 collector wiring、聚合、CLI、provider parsing、cost calculation，也未开始 Task 5B、Task 6 或 Task 7。
Action Needed From Human: 请将下方 Handoff Note 传递给 Independent Reviewer。
Handoff Note: 请读取 agent-handoff/README.md 与 agent-handoff/current-task.md，从 Git 派生最新 coder-report commit，并按独立审查顺序完成 PMQA-5C.6 review。
