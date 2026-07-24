# Coder Report

Owner: Coder

Task: PMQA Task 5C.5 — Provider-Neutral AI Invocation Collector

Task ID: `PMQA-5C.5`

Attempt: `1`

Status: Ready for Independent Reviewer

## Branch and Git Correlation

Branch:

`agent/task-5c-1-canonical-run-contract`

Exact Git-derived Coder starting HEAD:

`119330ec2355b2ab8d8f4afa66d23d0af8a06654`

That commit is the latest path-specific publication of
`agent-handoff/current-task.md`, identifies Task `PMQA-5C.5` Attempt `1`, and
was the clean local and tracking-branch HEAD before implementation. It is
reachable from the implementation commit below. The Architect-reviewed Task
5C.4 baseline named by the task,
`f5a960d359b671c485d70871eecb2e150b9e23d6`, is an ancestor of the starting
HEAD. No prior commit was amended.

## Implementation Commit

`346cc7ccb667ff3be7f58a8282e7fad67a2bcae9`

Commit message:

`add Task 5C.5 invocation collector`

This report is committed separately after the implementation commit. The
Independent Reviewer derives the report commit from Git; this report does not
claim its own future commit SHA.

## Changed Files

Implementation commit:

- `README.md`
- `docs/Roadmap.md`
- `docs/architecture.md`
- `docs/architecture/usage-cost-contracts.md`
- `pmqa/usage/__init__.py`
- `pmqa/usage/collector.py`
- `pmqa/usage/contracts.py`
- `tests/test_packaging.py`
- `tests/test_usage_collector.py`
- `tests/test_usage_imports.py`

Report-only handoff commit:

- `agent-handoff/coder-report.md`

No Architect- or Reviewer-owned handoff file changed.

## Public API

`pmqa.usage` now exports:

- `AIInvocationCollector`, a runtime-checkable provider-neutral synchronous
  protocol;
- `DefaultAIInvocationCollector`, the deterministic default implementation;
- `AIInvocationHandle`, an opaque runtime-only ownership value;
- `AIInvocationCollectionErrorCode`, the fixed eight-code failure vocabulary;
  and
- `AIInvocationCollectionError`, the bounded safe boundary exception.

Start accepts only Task 5C.4 correlation fields. Completion, failure, and
cancellation accept exact `TokenUsageEvidence` and `CostEvidence` instances
and return only canonical `AIInvocationRecord` values. No raw dictionary,
arbitrary metadata, provider object, callback, sink, or persistence surface
was introduced.

## Canonical Validation Reuse

The collector calls the existing `AIInvocationRecord` identifier, optional
identifier, and model-unavailable-reason validators before sampling a clock.
The existing cross-field model/predecessor policy was extracted without
semantic change into one private helper used by both `AIInvocationRecord` and
the collector. This avoids a second correlation or predecessor policy while
preserving the Task 5C.4 wire fields, JSON shape, and lifecycle semantics.

All Task 5C.4 contract tests remain green. No persisted wire field was added,
removed, renamed, or reinterpreted.

## Handle Ownership and Terminalization Policy

Each collector owns a private active-handle table and instance identity; there
is no global registry. A handle is exact-type checked, immutable through its
public API, constructor-protected, opaque in `repr`, and non-pickleable. Its
private owner and integrity bindings are checked against collector-owned
state. Foreign, forged, subclassed, finalized, and internally mutated handles
fail with the same bounded error; detected mutation consumes the corrupted
owned state.

Usage and cost are exact-type checked and independently round-tripped before
terminal state changes. Invalid caller evidence or an invalid failure category
therefore leaves the handle active for a corrected attempt. Immediately before
terminal clock sampling, the collector atomically removes the handle. Any
expected clock, duration, or final-record validation failure after that point
is terminal, so a second record cannot be produced. Concurrent contenders are
serialized by the private lock and at most one can consume ownership.

Success has no error category, failure requires a non-cancellation
`RunErrorCategory`, and cancellation always uses
`RunErrorCategory.CANCELLED`. Unavailable evidence remains explicitly
unavailable, and present numeric zero remains zero.

## Clock and Duration Decisions

The constructor validates that both injected clocks are callable without
sampling either. Start validates all metadata, then samples wall clock once
and monotonic clock once. A terminal path validates handle and evidence, then
samples each terminal clock once after consuming ownership.

Wall samples must be exact timezone-aware `datetime` values and are normalized
to UTC. Monotonic samples must be exact finite `int` or `float` values,
excluding `bool`. Terminal wall and monotonic values may not precede their
start values. Duration uses only monotonic evidence, converts through
`Decimal`, and rounds to the nearest millisecond with deterministic
`ROUND_HALF_UP`; zero is preserved and values above `MAX_USAGE_INTEGER` are
rejected. No sample or duration is guessed, clamped, or derived from wall-clock
difference.

Ordinary clock, normalization, evidence, and construction failures become
fixed errors raised without cause or context and without values.
`MemoryError`, `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit`
propagate unchanged at every tested clock stage.

## Security, Import, and Packaging Evidence

The handle and collector accept or retain no prompt, response, credential,
environment, provider client, raw process output, executable/path data,
browser state, arbitrary metadata, or exception text. Errors and handle
representations do not include marker values, clock outputs, object identity,
or underlying exception details. Caller-owned evidence is reconstructed twice
across the terminal record boundary; later caller mutation cannot alter the
returned record.

Import-isolation tests prove `import pmqa.usage` performs no clock sampling,
collector construction, I/O, environment/distribution inspection, process or
browser launch, product loading, provider loading, Application Service,
runner, workflow, LangGraph, storage, CLI, or UI import. Top-level `pmqa`
remains usage-lazy. The real-wheel regression asserts
`pmqa/usage/collector.py` is packaged and the external-directory import check
exercises the exported collector protocol and implementation. No dependency
was added.

## Validation Results

- Focused collector plus Task 5C.4 usage/pricing/import tests:
  `138 passed`.
- Run, Runner contract, Application contract/service, boundary-policy, and
  real-wheel packaging regressions: `332 passed`.
- Task 4 runtime, reducer, Supervisor, and LangGraph regressions:
  `98 passed` with one existing LangGraph pending-deprecation warning.
- Full default suite: `1699 passed, 5 skipped` with the same existing warning.
  The skips are existing opt-in live/external environment gates.
- Generated SauceDemo Playwright regressions: `2 passed`. The first
  sandboxed launch was blocked by macOS Chromium Mach-port permissions; the
  required rerun with local browser permission passed.
- Isolated `compileall` for `pmqa` and `products`: passed with bytecode directed
  to `/private/tmp`.
- `git diff --check`: passed.
- Pre-report implementation worktree: clean.

All default, packaging, and collector tests remained offline. No model,
provider CLI, network, Node.js, or external Product Pack was invoked by the
new tests.

## Scope Confirmation

No provider/CLI parser, pricing selection, calculator, catalog implementation,
storage, sink, callback, aggregation, summary, CLI/UI, workflow, runner,
reasoning-provider, or Application Service integration was added. `RunRecord`,
`RunnerInvocationRecord`, `WorkflowState`, LangGraph, Supervisor, Task 5,
Product Pack, and existing provider behavior were not modified. Task 5B,
Task 6, and Task 7 were not started. No PR was created and nothing was merged.

## Remaining Risks and Open Items

- The collector is intentionally process-local and in-memory; persistence and
  recovery across process loss are deferred.
- It records only caller-supplied canonical evidence; provider parsing,
  pricing, and completeness policy remain deferred.
- The runtime API is synchronous; asynchronous adapter composition remains a
  later design decision.

These are explicit task boundaries, not known acceptance blockers.

## Recommended Review Depth

**Deep**

Reason: the new opaque ownership and clock-containment boundary is small but
security- and exactly-once-sensitive, so adversarial lifecycle review is
warranted despite broad regression coverage.

## Suggested Reviewer Focus

- Verify the extracted shared correlation helper is semantically identical to
  the reviewed Task 5C.4 policy and leaves its wire schema unchanged.
- Challenge handle forgery, mutation, collector ownership, duplicate, and
  concurrent terminalization behavior.
- Verify evidence-validation failures stay retryable while all post-consumption
  expected failures remain at-most-once.
- Inspect clock exception containment, exact sampling order, half-up monotonic
  duration, and overflow/backwards-time behavior.
- Confirm import/wheel isolation and absence of provider, persistence, hidden
  sink, global registry, or sensitive runtime data.

## Human Summary

Task 5C.5 Attempt 1 已在指定分支完成，起点为 `119330ec2355b2ab8d8f4afa66d23d0af8a06654`。
实现提交为 `346cc7ccb667ff3be7f58a8282e7fad67a2bcae9`。
新增 provider-neutral collector、opaque runtime handle 与 exactly-once 三种终止路径。
时钟、duration、证据快照、handle 所有权和安全错误边界均有 focused adversarial coverage。
验证结果：focused 138、边界/packaging 332、Task 4 回归 98、全量 1699 passed / 5 skipped、Playwright 2 passed。
未加入 provider、parser、calculator、storage、CLI/workflow integration，也未开始 Task 5B、Task 6 或 Task 7。
Action Needed From Human: 请将下方 Handoff Note 传递给 Independent Reviewer。
Handoff Note: 请读取 agent-handoff/README.md 与 agent-handoff/current-task.md，从 Git 派生最新 coder-report commit，并按独立审查顺序完成 review。
