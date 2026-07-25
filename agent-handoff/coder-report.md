# Coder Report

Owner: Coder

Task: PMQA Task 5C.7 — Cross-Level Summary Consistency

Task ID: `PMQA-5C.7`

Attempt: `2`

Status: Ready for Independent Reviewer

## Branch and Git Correlation

Branch:

`agent/task-5c-1-canonical-run-contract`

Exact Git-derived Coder starting HEAD:

`370434c4c42c31b3bde573f10bf63e2b503b0c00`

That commit is the latest path-specific publication of
`agent-handoff/current-task.md`, identifies Task `PMQA-5C.7` Attempt `2`, and
was the clean local and tracking-branch HEAD before remediation. The reviewed
Attempt 1 Reviewer HEAD
`569c519c043b3ce97a17dca5d1370ed60a6bc5d9` is its ancestor. No Attempt 1
implementation or report commit was amended.

## Remediation Implementation Commit

`3419a9e5d4460186c2608dbd7f1e26762241c070`

Commit message:

`enforce Task 5C.7 summary consistency`

This report is committed separately after the remediation commit. The
Independent Reviewer derives the report commit from Git; this report does not
claim its own future commit SHA.

## Changed Files

Remediation implementation commit:

- `pmqa/usage/summary.py`
- `tests/test_usage_summary.py`

Report-only handoff commit:

- `agent-handoff/coder-report.md`

No other implementation, test, documentation, packaging, or handoff file
changed.

## Cross-Level Reconciliation

Every `UsageSummary` now runs one contract-owned group roll-up validator after
the existing top-level and nested validations. It reconstructs the complete
top-level metrics exclusively from the canonical
`provider_model_groups` snapshots and compares them to the public top-level
values.

The following counts are independently accumulated with exact bounded integer
addition and must equal the top-level values:

- invocation;
- succeeded, failed, and cancelled invocation;
- retry invocation; and
- fallback invocation.

Group `total_duration_ms` is accumulated with the aggregate integer bound and
must equal top-level duration. Addition checks the remaining bound before each
operation; it does not use float conversion, unchecked `sum`, clamping, or
wrap behavior. Reconciliation overflow is a normal contract `ValueError`, so
persisted `from_dict()` exposes only `UsageSummaryValidationError`.

## Token Reconciliation

For every exact `TokenField`, the validator:

- sums group observed coverage with the record-count bound;
- sums group unavailable coverage with the same bound;
- requires both counts to equal the corresponding top-level counts;
- requires every group total to remain `None` when the top total is `None`;
  and
- otherwise sums all observed group totals with the aggregate integer bound
  and requires exact equality with the top total.

An explicit observed-total flag keeps numeric zero distinct from absence.
Mixed observed/unavailable provider groups remain valid when their counts and
observed totals reconcile. No unavailable group contributes an inferred
numeric value.

## Cost-Bucket Reconciliation

All group buckets are re-aggregated by the existing complete identity:

- cost type;
- currency;
- pricing source ID;
- pricing version;
- pricing effective timestamp; and
- unavailable reason.

Multiple provider/model groups may contribute to one identity. Invocation
counts are merged with the record-count bound. Monetary amounts are merged as
`Decimal` inside a local precision-512 context, then revalidated through the
existing canonical Decimal bound. No float or caller ambient precision is
used. Subscription-included and unavailable buckets retain `amount=None`.

The normalized derived mapping must exactly equal the top-level identity set,
invocation counts, and amounts. Missing, extra, currency/provenance-different,
count-mismatched, and amount-mismatched buckets are rejected. Ordinary Decimal
or bound failures become contract `ValueError`; resource/control-flow
exceptions remain authoritative.

The empty summary remains valid because every bounded roll-up is zero, every
token field has no observed group total, and both cost/group collections are
empty.

## Contract Entry Points

The invariant is enforced by the `UsageSummary` model validator and therefore
applies to:

- direct `UsageSummary(...)` construction;
- fixed-safe `UsageSummary.from_dict(...)`;
- fully revalidated `model_copy(update=...)`; and
- output from `DefaultUsageAggregator.summarize(...)`.

Tests start from real aggregator output and independently mutate canonical
group or top-level wire values. Direct construction and revalidated-copy tests
prove neither alternate public entry point bypasses reconciliation.
`from_dict()` contradictions return only `invalid PMQA usage summary`, without
marker, identifier, provider/model, amount, cause, context, aggregation code,
or underlying arithmetic detail.

## Monetary Assertion Correction

The aggregation loop no longer contains:

```text
assert cost.amount is not None
```

It uses an explicit checked branch. Impossible monetary evidence at that
service boundary raises the existing fixed
`UsageAggregationErrorCode.INVALID_RECORD` without leaking the record or
amount. An automated subprocess regression executes both valid monetary
aggregation and the impossible-evidence branch under `python -O`, proving
behavior does not depend on assertions. Resource/control-flow propagation is
unchanged.

## Focused Adversarial Coverage

The added tests cover:

- invocation, lifecycle, retry/fallback, and duration contradictions;
- observed/unavailable token coverage, `None`, numeric total, and zero
  contradictions;
- missing, extra, different, count-mismatched, and amount-mismatched cost
  buckets;
- multiple groups merging one monetary, subscription, or unavailable
  identity;
- currency and pricing-provenance separation;
- direct construction, `from_dict`, and `model_copy` enforcement;
- input-order-independent existing aggregator output and empty summary
  preservation;
- reduced ambient Decimal precision;
- integer and Decimal reconciliation overflow;
- fixed marker-safe reconstruction;
- optimized-Python monetary invariant behavior; and
- exact `MemoryError`, `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit`
  propagation from Decimal reconciliation.

No public field, enum, schema version, limit, cost identity, ordering rule,
canonical serialization, or aggregation meaning changed.

## Validation Results

- Summary-only focused tests: `52 passed`.
- Summary, repository, collector, usage contracts, pricing, and usage-import
  tests: `267 passed`.
- Run, Runner contract, Application contract/service, boundary-policy, and
  real-wheel packaging regressions: `332 passed`.
- Task 4 runtime, reducer, Supervisor, and LangGraph regressions:
  `98 passed` with one existing LangGraph pending-deprecation warning.
- Full default suite: `1828 passed, 5 skipped` with the same existing warning.
  The skips are existing opt-in live/external environment gates.
- Generated SauceDemo Playwright regressions: `2 passed`.
- Isolated `compileall` for `pmqa` and `products`: passed with bytecode routed
  to `/private/tmp`.
- `git diff --check`: passed.
- Pre-report implementation worktree: clean.

All focused remediation and default tests remained offline. New tests invoked
no model, provider CLI, network, browser, Node.js, repository output, or
external Product Pack.

## Remaining Risks and Open Items

- A summary still describes only the caller's explicit bounded selection; it
  does not claim repository completeness.
- The public maximum remains 64 records, so larger persisted selections still
  require future pagination/selection policy.
- Provider-reported and estimated amounts are reconciled exactly as evidence;
  reliability and price calculation remain outside this service.

These are preserved Task 5C.7 boundaries, not known remediation blockers.

## Scope Confirmation

No field, enum, schema, public error code, repository integration, pagination,
CLI/UI, pricing lookup, provider adapter, workflow integration, persistence,
retention, database, or runtime dependency was added. Usage contracts,
pricing, collector, repository, Run, Runner, Application Service,
WorkflowState, LangGraph, Supervisor, Task 5, and Product Pack behavior were
not modified. Task 5D, Task 5B, Task 6, and Task 7 were not started. No PR was
created and nothing was merged.

## Recommended Review Depth

**Deep**

Reason: this remediation makes a persisted multi-level aggregate
mathematically self-proving across bounded integers, missing-versus-zero
tokens, complete cost identities, and exact Decimal arithmetic.

## Suggested Reviewer Focus

- Independently mutate each count, duration, and token dimension while
  preserving nested contract validity and confirm cross-level rejection.
- Challenge cost identity merging across currencies, provenance, monetary and
  non-monetary buckets, including multiple contributing groups.
- Verify integer/Decimal overflow is contract validation rather than
  `UsageAggregationError`, `InvalidOperation`, or ambient-context behavior.
- Confirm direct construction, `from_dict`, and revalidated copies all execute
  the same invariant with fixed marker-safe reconstruction.
- Inspect the explicit monetary branch under optimized Python and exact
  resource/control-flow propagation.

## Human Summary

PMQA-5C.7 Attempt 2 已完成，精确起点为 `370434c4c42c31b3bde573f10bf63e2b503b0c00`。
remediation 提交为 `3419a9e5d4460186c2608dbd7f1e26762241c070`。
所有 lifecycle、predecessor、duration、token 与 cost 指标现在必须由 provider/model groups 精确回卷得到。
bounded integer、missing-versus-zero、完整 cost identity 与 Decimal ambient-precision 边界均已覆盖。
monetary aggregation 已移除 domain assert，并通过 `python -O` 回归验证固定 `INVALID_RECORD` 行为。
验证结果：focused 267、边界/packaging 332、Task 4 回归 98、全量 1828 passed / 5 skipped、Playwright 2 passed。
Action Needed From Human: 请将下方 Handoff Note 传递给 Independent Reviewer。
Handoff Note: 请读取 agent-handoff/README.md 与 agent-handoff/current-task.md，从 Git 派生最新 coder-report commit，并按独立审查顺序完成 review。
