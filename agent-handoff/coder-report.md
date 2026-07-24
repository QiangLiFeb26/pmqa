# Coder Report

Owner: Coder

Task: PMQA Task 5C.7 — Deterministic Usage Summary Contracts and Pure Aggregation

Task ID: `PMQA-5C.7`

Attempt: `1`

Status: Ready for Independent Reviewer

## Branch and Git Correlation

Branch:

`agent/task-5c-1-canonical-run-contract`

Exact Git-derived Coder starting HEAD:

`4128ef969e1a3dc90297a74c513a6cd2eabf0376`

That commit is the latest path-specific publication of
`agent-handoff/current-task.md`, identifies Task `PMQA-5C.7` Attempt `1`, and
was the clean local and tracking-branch HEAD before implementation. The
Architect-reviewed Task 5C.6 Reviewer baseline
`a258ba59b7fdd1edb6e01ab738ea9203610e954b` is its parent and ancestor. No
Task 5C.6 commit was amended.

## Implementation Commit

`eeba9a9dd1d2fac6a007580d4511fbb51722bd15`

Commit message:

`add deterministic usage summaries`

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
- `pmqa/usage/summary.py`
- `tests/test_packaging.py`
- `tests/test_usage_imports.py`
- `tests/test_usage_summary.py`

Report-only handoff commit:

- `agent-handoff/coder-report.md`

No Architect- or Reviewer-owned handoff file changed.

## Public Contracts and Aggregation API

`pmqa.usage` now exports:

- `UsageSummaryScope` with exact `session` and `run` values;
- strict frozen `UsageTokenFieldSummary`, `UsageCostBucket`,
  `UsageProviderModelSummary`, and `UsageSummary` contracts;
- runtime-checkable synchronous `UsageAggregator`;
- pure stateless `DefaultUsageAggregator`;
- fixed `UsageAggregationErrorCode` and `UsageAggregationError`;
- fixed `UsageSummaryValidationError`; and
- explicit schema, record-count, and aggregate-integer bounds.

The aggregator accepts only a built-in tuple of exact
`AIInvocationRecord` instances, an exact scope enum, and a canonical existing
identifier. It independently reconstructs every invocation, rejects duplicate
IDs and mixed correlation, and returns an independently reconstructed
canonical summary. It retains no caller container or record and has no
repository, clock, provider, pricing, callback, workflow, or CLI dependency.

## Empty, Zero, Partial, and Unavailable Semantics

An empty explicit selection is valid and yields numeric zero for invocation,
status, predecessor, and duration counts; every `TokenField` appears once with
`total=None` and zero observed/unavailable coverage; cost buckets and
provider/model groups are empty. No unavailable invocation is fabricated.

Each non-empty token-field summary records an optional total, observed count,
and unavailable count whose sum equals invocation count. No observation means
`None`; an observed zero remains numeric zero. Partial totals coexist with
explicit unavailable coverage and do not claim to cover missing records.
Unavailable reasons remain on invocation evidence rather than being guessed
or collapsed.

Status counts cover every invocation. Retry and fallback counts use only the
explicit predecessor fields, not `attempt_number`. Duration sums canonical
`duration_ms`, never wall-clock differences. Exact integer overflow fails with
the fixed aggregate-overflow error.

## Cost and Decimal Semantics

Every invocation contributes to exactly one cost bucket. Monetary bucket
identity includes cost type, currency, pricing source ID, pricing version, and
pricing effective timestamp. Provider-reported and estimated evidence,
different currencies, and distinct pricing versions/effective times therefore
never merge.

Subscription-included and unavailable evidence remain non-monetary; unavailable
reasons form distinct buckets. Monetary zero remains a real amount. Decimal
addition uses an explicit high-precision local context, never float or ambient
precision, and the existing canonical Decimal bound is revalidated after each
addition. Aggregate Decimal overflow fails safely.

## Provider/Model Grouping and Determinism

Each exact provider plus known model or exact model-unavailable reason produces
one non-recursive `UsageProviderModelSummary` with the same status,
retry/fallback, duration, token, and cost semantics as the top level. Known
models and unavailable-model reasons cannot merge.

Token fields follow `TokenField` order. Cost buckets follow stable cost-type
and complete-identity order. Provider/model groups sort by provider, known
model before unavailable model, then exact identity. Reversed and arbitrary
input orders produce equal summaries and byte-equivalent canonical JSON
trees. The defined maximum of 64 records is validated with 64 distinct
provider groups and 64 distinct cost buckets, including a complete canonical
round trip.

## Contract, Error, and Security Boundaries

All public records reuse the existing strict frozen Pydantic v2 Run/Usage
boundary: forbidden extras, hidden invalid input, canonical plain-JSON
`to_dict()`/`from_dict()`, fully revalidated `model_copy`, bounded trees and
identifiers, deep immutable tuples, and reconstructed nested contracts.
Summary reconstruction has one fixed safe error; aggregation has five fixed
bounded errors for invalid request, invalid record, correlation mismatch,
duplicate invocation, and aggregate overflow.

Tests inject unknown prohibited keys, runtime objects, invalid identifiers,
mutated records, and marker-bearing values. Expected failures expose no
identifier, provider/model, amount, payload, object representation, cause, or
context. `MemoryError`, `KeyboardInterrupt`, `SystemExit`, and
`GeneratorExit` propagate with exact identity. No second prohibited-key list
was added.

## Import and Packaging Isolation

Import coverage proves the expanded `pmqa.usage` surface performs no
filesystem, environment, distribution, process, browser, product, Product
Pack, provider, runner, Application Service, workflow, LangGraph, storage,
SQLite, pricing lookup, CLI, or UI work. Top-level `pmqa` remains usage-lazy.
The real-wheel regression explicitly includes `pmqa/usage/summary.py` and
imports the summary protocol/default implementation from an unrelated
directory. No runtime or build dependency was added.

## Documentation

The four allowed status/architecture surfaces now record that Task 5C.6 passed
architecture review and Task 5C.7 is ready for review. They document explicit
bounded caller selection, zero/partial/unavailable meaning, cost type/currency/
provenance separation, deterministic grouping, and the absence of repository
completeness claims. Repository-backed selection, CLI rendering,
outcome-metric joining, pricing calculation, provider integration, retention,
and optimization remain deferred. Task 5C remains in progress and unmerged;
Task 5B, Task 6, and Task 7 remain not started.

## Validation Results

- Focused summary, repository, collector, usage contracts, pricing, and import
  tests: `245 passed`.
- Run, Runner contract, Application contract/service, boundary-policy, and
  real-wheel packaging regressions: `332 passed`.
- Task 4 runtime, reducer, Supervisor, and LangGraph regressions:
  `98 passed` with one existing LangGraph pending-deprecation warning.
- Full default suite: `1806 passed, 5 skipped` with the same existing warning.
  The skips are existing opt-in live/external environment gates.
- Generated SauceDemo Playwright regressions: `2 passed`.
- Isolated `compileall` for `pmqa` and `products`: passed with bytecode routed
  to a temporary directory.
- Markdown relative-link validation: passed.
- `git diff --check`: passed.
- Pre-report implementation worktree: clean.

All new and default summary tests remained offline. They invoked no model,
provider CLI, network, browser, Node.js, external Product Pack, or repository
runtime output.

## Scope Confirmation

No repository read/write or completeness logic, pagination, CLI command or
rendering, outcome-metric join, price lookup or calculation, provider parser
or SDK, collector persistence, workflow/Application Service/Runner
integration, retry/fallback execution policy, retention, database, background
work, remote storage, budget, optimization, model routing, or quality scoring
was added. Existing usage contracts, pricing, collector, repository, Run,
Runner, Application Service, WorkflowState, LangGraph, Supervisor, Task 5,
and Product Pack behavior were not modified. Task 5B, Task 6, and Task 7 were
not started. No PR was created and nothing was merged.

## Remaining Risks and Open Items

- A summary describes only the caller's explicit bounded selection and cannot
  prove repository completeness; that integration remains deferred.
- The conservative 64-record limit is intentional for canonical tree bounds;
  pagination and larger repository-backed reporting remain future policy.
- Provider-reported and estimated amounts are aggregated exactly as supplied;
  evidence reliability, price calculation, and outcome interpretation remain
  outside this pure domain service.

These are explicit task boundaries, not known acceptance blockers.

## Recommended Review Depth

**Deep**

Reason: the new canonical aggregate tree encodes subtle missing-versus-zero,
cost-provenance, overflow, and input-order invariants that warrant adversarial
contract review despite broad focused coverage.

## Suggested Reviewer Focus

- Challenge empty, zero, partial, unavailable, status, predecessor, and
  overflow invariants at both top-level and provider/model-group contracts.
- Verify reported/estimated, currency, pricing provenance,
  subscription-included, unavailable reason, and Decimal identities never
  merge incorrectly.
- Confirm all ordering is input-independent and public contract round trips or
  revalidated copies cannot admit noncanonical nested collections.
- Exercise exact tuple/record boundaries, duplicate and correlation rejection,
  fixed marker-safe errors, and resource/control-flow propagation.
- Confirm import/wheel isolation and absence of repository, pricing,
  provider, workflow, CLI, or new dependency coupling.

## Human Summary

Task 5C.7 Attempt 1 已在指定分支完成，精确起点为 `4128ef969e1a3dc90297a74c513a6cd2eabf0376`。
实现提交为 `eeba9a9dd1d2fac6a007580d4511fbb51722bd15`。
新增严格 usage summary contracts 与纯聚合器，保持 zero/partial/unavailable、cost provenance 和 provider/model 分组语义。
输入顺序、Decimal、overflow、correlation、canonical round-trip、import/wheel 隔离均有专项验证。
验证结果：focused 245、边界/packaging 332、Task 4 回归 98、全量 1806 passed / 5 skipped、Playwright 2 passed。
未接入 repository、CLI、pricing/provider/workflow，也未开始 Task 5B、Task 6 或 Task 7。
Action Needed From Human: 请将下方 Handoff Note 传递给 Independent Reviewer。
Handoff Note: 请读取 agent-handoff/README.md 与 agent-handoff/current-task.md，从 Git 派生最新 coder-report commit，并按独立审查顺序完成 PMQA-5C.7 review。
