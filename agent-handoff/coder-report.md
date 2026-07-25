# Coder Report

Owner: Coder

Task: PMQA Task 5C.7 — Retry/Fallback Aggregate Exclusivity

Task ID: `PMQA-5C.7`

Attempt: `3`

Status: Ready for Independent Reviewer

## Branch and Git Correlation

Branch:

`agent/task-5c-1-canonical-run-contract`

Exact Git-derived Coder starting HEAD:

`e18ffd74a5cf1a6d97de3709177af86ac073de46`

That commit was the latest pushed publication of
`agent-handoff/current-task.md`, identified Task `PMQA-5C.7` Attempt `3`, and
was the clean local and tracking-branch HEAD before implementation changes.
The reviewed Attempt 2 Reviewer HEAD
`d6b1acd1572bf55de8cb85ed303059b832daa55d` is its ancestor. No prior
implementation or report commit was amended.

## Remediation Implementation Commit

`2540acf98be7a1645c252de595be6930c63ab717`

Commit message:

`enforce Task 5C.7 predecessor exclusivity`

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

## Predecessor-Count Invariant

The existing shared `_validate_metrics` validator now enforces:

```text
retry_invocation_count + fallback_invocation_count
    <= invocation_count
```

The implementation avoids unchecked addition. It first retains the individual
upper-bound checks and then, using short-circuit evaluation, compares retry
count with `invocation_count - fallback_invocation_count`. The subtraction is
therefore reached only after fallback count is known not to exceed invocation
count. It does not wrap, clamp, or rely on unbounded aggregate arithmetic.

The invariant deliberately does not require equality. Attempt-one invocations
remain valid because they contribute to neither predecessor category.

## Contract Entry Points

Both `UsageSummary` and `UsageProviderModelSummary` already use the shared
metrics validator, so the new invariant applies at the top level and to every
provider/model group without duplicating policy.

Tests prove rejection through:

- direct Pydantic construction;
- fully revalidated `model_copy(update=...)`; and
- fixed-safe `from_dict()` reconstruction.

Contradictory persisted summaries expose only
`UsageSummaryValidationError("invalid PMQA usage summary")`. Tests verify that
an injected marker and underlying validation details do not appear, and that
cause and context remain suppressed.

## Valid and Adversarial Coverage

Valid canonical aggregator output remains accepted for:

- an empty summary;
- one first attempt;
- one retry;
- one fallback;
- two invocations containing one retry and one fallback;
- mixed first and later attempts whose predecessor total is below invocation
  count; and
- multiple provider/model groups with valid combined top-level counts.

Every valid case round-trips through `to_dict()` and `from_dict()` with an
identical canonical payload.

Adversarial tests reject:

- top-level invocation `1`, retry `1`, fallback `1`;
- provider/model invocation `1`, retry `1`, fallback `1`;
- direct construction, `from_dict()`, and revalidated-copy bypass attempts;
- larger overlaps `(2, 2, 1)` and `(3, 2, 2)`; and
- canonical wires whose top-level and sole group contain the same impossible
  overlap and therefore still reconcile cross-level.

The adversarial wires begin with real `DefaultUsageAggregator` output and
mutate only the intended predecessor counts. Existing valid aggregation and
serialization bytes were not changed.

## Validation Results

- Summary-only focused tests: `64 passed`.
- Summary, repository, collector, usage contracts, pricing, and usage-import
  tests: `279 passed`.
- Run, Runner contract, Application contract/service, boundary-policy, and
  real-wheel packaging regressions: `332 passed`.
- Task 4 runtime, reducer, Supervisor, and LangGraph regressions:
  `98 passed` with one existing LangGraph pending-deprecation warning.
- Full default suite: `1840 passed, 5 skipped` with the same existing warning.
  The skips are existing opt-in live/external environment gates.
- Generated SauceDemo Playwright regressions: `2 passed`.
- Isolated `compileall` for `pmqa` and `products`: passed with bytecode routed
  to `/private/tmp`.
- `git diff --check`: passed.
- Pre-report implementation worktree: clean.

All focused remediation and default tests remained offline. The generated
Playwright regressions used the existing local browser fixture and passed.
New tests invoked no model, provider CLI, network, browser, Node.js, repository
output, or external Product Pack.

## Remaining Risks and Open Items

- A usage summary still represents only the caller's explicit bounded
  selection and does not claim repository completeness.
- The public maximum remains 64 records; future pagination and selection
  policy remain outside this task.
- Provider-reported and estimated costs remain evidence rather than a pricing
  calculation service.

These are preserved Task 5C.7 boundaries, not known remediation blockers.

## Scope Confirmation

No public field, enum, schema version, error code, aggregation output,
cross-level reconciliation rule, canonical ordering, serialization format, or
repository behavior changed. Collector, pricing, Run, Runner, Application
Service, WorkflowState, LangGraph, Supervisor, Task 5, and Product Pack
behavior were not modified. No documentation, import, or packaging file
changed. Task 5D, Task 5B, Task 6, and Task 7 were not started. No PR was
created and nothing was merged.

## Recommended Review Depth

**Standard**

Reason: the correction is a narrow shared-validator invariant with focused
entry-point, safe-error, and canonical-aggregation regression coverage.

## Suggested Reviewer Focus

- Confirm the subtraction check is reached only after the individual fallback
  bound and therefore cannot underflow or bypass the aggregate invariant.
- Exercise the same contradiction at top-level and group level through direct
  construction, `from_dict()`, and `model_copy(update=...)`.
- Verify cross-level-consistent but aggregate-impossible wires are rejected
  before they can become canonical summaries.
- Confirm valid mixed first/retry/fallback records and multiple provider groups
  retain byte-identical canonical serialization.
- Inspect fixed-error reconstruction for marker, cause, context, count, and
  provider/model leakage.

## Human Summary

PMQA-5C.7 Attempt 3 已完成，Git 派生起点为 `e18ffd74a5cf1a6d97de3709177af86ac073de46`。
实现提交为 `2540acf98be7a1645c252de595be6930c63ab717`。
共享 metrics validator 现同时约束顶层与每个 provider/model group 的 retry/fallback 总量不超过 invocation count。
direct construction、`model_copy` 与固定安全 `from_dict` 边界均有回归覆盖。
验证结果：usage 279、边界/packaging 332、Task 4 回归 98、全量 1840 passed / 5 skipped、Playwright 2 passed。
Action Needed From Human: 请将下方 Handoff Note 传递给 Independent Reviewer。
Handoff Note: 请读取 agent-handoff/README.md 与 agent-handoff/current-task.md，从 Git 派生最新 coder-report commit，并按独立审查顺序完成 review。
