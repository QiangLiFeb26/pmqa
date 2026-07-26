# Independent Reviewer Report

Owner: Independent Reviewer

Status: Executed for PMQA Task 5C.7, Attempt 3

## Task Correlation

Task: PMQA Task 5C.7 — Retry/Fallback Aggregate Exclusivity

Task ID: `PMQA-5C.7`

Attempt: `3`

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed Starting HEAD: `e18ffd74a5cf1a6d97de3709177af86ac073de46`

Reviewed Implementation Commit(s): `2540acf98be7a1645c252de595be6930c63ab717`
("enforce Task 5C.7 predecessor exclusivity")

Derived Coder Report Commit: `5678d20f239ed40fc8a0cc6749bf98ae1f5e7949`
("report Task 5C.7 predecessor remediation")

Correlation Verification:

- derived with `git log -1 --format=%H -- agent-handoff/coder-report.md` ->
  `5678d20f239ed40fc8a0cc6749bf98ae1f5e7949`;
- `git merge-base --is-ancestor e18ffd74a5cf1a6d97de3709177af86ac073de46 HEAD`
  succeeds; `e18ffd7...` is an ancestor of `2540acf...`, and `2540acf...` is
  an ancestor of `5678d20...` (linear sequence
  `e18ffd7 -> 2540acf -> 5678d20` on this branch);
- the reviewed Attempt 2 Reviewer HEAD named by `current-task.md`,
  `d6b1acd1572bf55de8cb85ed303059b832daa55d` (this Reviewer's own prior
  Attempt 2 report commit), is an ancestor of the recorded starting HEAD;
- the correlation header of `coder-report.md` at the derived commit names
  Task ID `PMQA-5C.7`, Attempt `3`, branch
  `agent/task-5c-1-canonical-run-contract`, and starting HEAD
  `e18ffd74a5cf1a6d97de3709177af86ac073de46`, matching `current-task.md`;
- `git diff --stat 2540acf..5678d20` touches only
  `agent-handoff/coder-report.md`, so the derived commit is the report's
  latest authorized change with no later unauthorized replacement.

This Reviewer report does not contain or predict its own commit SHA. The
Architect derives the Reviewer report commit from Git and records it in
`architect-review.md`.

## Independent Review Method

Inspection order completed:

1. `current-task.md` and acceptance criteria (the Architect's reproduced
   `invocation=1, retry=1, fallback=1` impossible payload and the required
   valid/rejection case lists);
2. named baseline-to-implementation diff (`e18ffd7..2540acf`) — full read of
   the two-line `pmqa/usage/summary.py` change and the entire added section
   of `tests/test_usage_summary.py`;
3. independently selected validation (see Test Evidence), including hand-
   tracing every boundary case of the new inequality and independently
   reproducing the Architect's exact reported scenario against the
   remediated code, both independent of the Coder's own tests;
4. full `coder-report.md` (read only after steps 1-3).

Active-task `architect-review.md` read before publication: No

Prior closed review or architecture material consulted, with reason: this
Reviewer authored the Attempt 1 and Attempt 2 reviews of this same task
(`agent-handoff/reviewer-report.md` at commits `569c519` and `d6b1acd`,
superseded by this report), neither of which caught this specific
retry/fallback-exclusivity gap; that history is directly relevant to how
carefully this attempt needed to be checked, so I compared the Attempt 2
code (via `git diff e18ffd7..2540acf`) directly against my own recollection
of what Attempt 2 validated, rather than re-deriving the gap from
`architect-review.md` (unread, per protocol).

## Review Depth

Actual Review Depth: Deep

Review Depth Reason: although the diff is minimal (a two-line boolean
condition plus tests), this is the third consecutive attempt on Task 5C.7
where a prior attempt's own passing test suite still admitted a real
contradiction the Architect found by direct adversarial construction — the
Coder's own tests are necessarily a weaker signal here than for a typical
checkpoint. I hand-traced the new inequality against every boundary case
(zero, single-category, combined, and over-limit predecessor counts) rather
than only running the provided tests, and independently reproduced the
Architect's exact reported scenario. This is a stricter depth than the
Coder's own "Standard" recommendation, chosen because of this task's
specific track record, not because the diff itself is large or complex.

## Overall Assessment

The remediation is correct, minimal, and precisely scoped. The entire
production change is:

```python
if (
    retry_invocation_count > invocation_count
    or fallback_invocation_count > invocation_count
    or retry_invocation_count
    > invocation_count - fallback_invocation_count
):
    raise ValueError("predecessor counts cannot exceed invocation count")
```

added to the existing shared `_validate_metrics` function, which — as I
confirmed by re-reading its two call sites — is already invoked by both
`UsageSummary.validate_group_coverage` and
`UsageProviderModelSummary.validate_group`, so this single change applies
the invariant at both the top level and every provider/model group without
introducing a second, duplicated policy (matching "the invariant must apply
to both top-level `UsageSummary` and every `UsageProviderModelSummary`").

I hand-traced the third condition's safety: because Python's `or` short-
circuits left-to-right, `retry_invocation_count > invocation_count -
fallback_invocation_count` is only ever evaluated once both preceding
conditions (`retry > invocation_count`, `fallback > invocation_count`) have
already been confirmed `False` — meaning `fallback_invocation_count <=
invocation_count` is guaranteed at the point the subtraction runs, so
`invocation_count - fallback_invocation_count` can never go negative and
there is no underflow/wrap risk. Since `retry_invocation_count`,
`fallback_invocation_count`, and `invocation_count` are already
Pydantic-bounded to `[0, MAX_USAGE_SUMMARY_RECORDS]` by their own field
definitions before this model-level validator ever runs, and Python
integers are arbitrary-precision (no wraparound), the comparison is safe
under every reachable input. I independently verified every boundary the
task's Required Valid/Rejection Cases list names by hand-evaluating the
three-way `or` expression: `(0,0,0)`, `(1,0,0)`, `(1,1,0)`, `(1,0,1)`, and
`(2,1,1)` (invocation, retry, fallback) all evaluate to `False` (accepted);
`(1,1,1)`, `(2,2,1)`, and `(3,2,2)` all evaluate to `True` (rejected) —
matching every case the task and the Coder's tests enumerate.

I independently reproduced the Architect's exact reported scenario — a
`UsageSummary.from_dict()` wire payload with `invocation_count=1,
retry_invocation_count=1, fallback_invocation_count=1` applied
simultaneously at both the top level and the sole `provider_model_groups`
entry, so that Attempt 2's cross-level roll-up reconciliation (added to fix
the prior finding) would have found the two levels "consistent" with each
other despite both being individually impossible — directly against the
remediated code, independent of the Coder's own tests, and confirmed it now
raises `UsageSummaryValidationError` rather than being silently accepted.

The diff is correctly scoped to exactly the two allowed files
(`pmqa/usage/summary.py`, `tests/test_usage_summary.py`); no public field,
enum, schema version, error code, cross-level reconciliation rule, ordering,
canonical serialization, or aggregation output changed — confirmed both by
reading the two-line production diff and by every pre-existing test (from
Attempt 1 and Attempt 2, none modified) continuing to pass unchanged.

All validation commands listed in `current-task.md`, run independently
rather than accepted from the Coder report, pass with no failures, errors,
or unexplained skips.

## Findings

None. The predecessor-exclusivity gap the Architect reported is
independently confirmed closed by direct reproduction and by hand-tracing
the boundary logic, and no new gap surfaced during this Deep inspection.

## Acceptance Criteria Coverage

| Acceptance criterion | Evidence | Result |
| --- | --- | --- |
| No canonical top-level or provider/model summary can count one invocation in both retry and fallback categories | Hand-traced the new inequality's short-circuit safety and boundary cases; independently reproduced the exact Architect-reported `(1,1,1)` payload at both levels simultaneously and confirmed rejection | Met |
| Valid combinations, including one retry plus one fallback across two invocations, remain accepted | Hand-evaluated `(2,1,1)` against the inequality (`False`, accepted); `test_valid_predecessor_aggregate_combinations_remain_canonical` independently rerun across all 7 required valid cases | Met |
| All public contract entry points enforce the invariant | `_validate_metrics` runs inside a `model_validator(mode="after")`, which Pydantic invokes for direct construction, `from_dict`'s `model_validate`, and `model_copy`'s `model_validate`, at both `UsageSummary` and `UsageProviderModelSummary`; `test_top_level_retry_fallback_overlap_is_rejected` and `test_provider_group_retry_fallback_overlap_is_rejected` (each exercising all three entry points) independently rerun | Met |
| Fixed safe errors and exact resource/control-flow behavior remain intact | Reconciled overlap raises plain `ValueError` inside the validator, which the existing `_SummaryContract.from_dict`/`_RunContract.from_dict` chain converts to the fixed `UsageSummaryValidationError`; `test_reconciled_top_and_group_predecessor_overlap_is_rejected_safely` (marker/cause/context checks) independently rerun | Met |
| Valid aggregator output and canonical serialization remain unchanged | No change to `DefaultUsageAggregator`, cross-level reconciliation, ordering, or serialization code; every Attempt 1/2 test (canonical round-trips, input-order independence, maximum-cardinality) is untouched in the diff and independently rerun unchanged | Met |
| Existing Task 5C.4-5C.7 and full regressions remain green | 279 focused + 332 regression + 98 Task 4 + 1840/5-skip full suite + 2 Playwright, all independently run, all pass | Met |
| Only allowed files changed | `git diff --stat e18ffd7..2540acf` shows exactly `pmqa/usage/summary.py` and `tests/test_usage_summary.py`; no documentation, import, or packaging file touched, consistent with the task's explicit "no documentation, import, or packaging change is expected" | Met |

## Test Evidence

### Coder Evidence Reviewed

The Coder report claims: 64 summary-only focused tests; 279 passed for
summary + repository + collector + Task 5C.4 usage/pricing + import tests;
332 passed for the Run/Runner/Application/boundary/packaging regression set;
98 passed for the Task 4 orchestration set (one pre-existing LangGraph
deprecation warning); 1840 passed, 5 skipped for the full default suite; 2
passed for `products/demo/generated_tests`; `compileall` and
`git diff --check` clean; clean worktree. This claimed evidence was read
only after independent execution below and matches it exactly.

### Independently Run

All commands below were executed by the Reviewer directly, before reading
the Coder's claimed results, from the repository root on the reviewed
branch:

- `.venv/bin/python -m pytest tests/test_usage_summary.py tests/test_usage_repository.py tests/test_usage_collector.py tests/test_usage_contracts.py tests/test_usage_pricing.py tests/test_usage_imports.py -q`
  -> `279 passed`
- `.venv/bin/python -m pytest tests/test_run_contracts.py tests/test_runner_contracts.py tests/test_application_contracts.py tests/test_application_service.py tests/test_boundary_policy.py tests/test_packaging.py -q`
  -> `332 passed`
- `.venv/bin/python -m pytest tests/test_workflow_runtime.py tests/test_workflow_reducer.py tests/test_supervisor_policy.py tests/test_langgraph_workflow.py -q`
  -> `98 passed, 1 warning` (pre-existing `LangChainPendingDeprecationWarning`,
  unrelated to this change)
- `.venv/bin/python -m pytest -q` (full default suite) -> `1840 passed, 5 skipped, 1 warning`
- `.venv/bin/python -m pytest products/demo/generated_tests -q` -> `2 passed`
- `PYTHONPYCACHEPREFIX=<isolated scratch directory> .venv/bin/python -m compileall -q pmqa products`
  -> exit code `0`, no output
- `git diff --check` -> exit code `0`, no output
- `git status --short` -> empty (clean worktree)

In addition, and independent of the Coder's own tests, I directly
reproduced the Architect's exact reported scenario against the remediated
code in an ad hoc script: constructed a summary via the real aggregator,
then set `retry_invocation_count=1` and `fallback_invocation_count=1` on
both the top-level wire and its sole `provider_model_groups` entry
(`invocation_count=1` throughout, so the individual per-category bounds and
Attempt 2's cross-level roll-up both "pass" while the aggregate is still
impossible), and confirmed `UsageSummary.from_dict(wire)` now raises
`UsageSummaryValidationError` rather than succeeding.

No listed validation command was left unrun. No test was skipped by
Reviewer choice. Environment: local `.venv` (Python 3.9), macOS/Darwin, no
network access used or required.

## Security, Scope, and Compatibility

Security observations: the new invariant fails through the same fixed,
marker-safe path as every other Task 5C.7 contract failure — a plain
`ValueError` inside the shared `model_validator`, converted by the existing
`_SummaryContract.from_dict` chain into the fixed `UsageSummaryValidationError`
with no cause, context, count, identifier, provider/model, or marker leaked.
No new error code, public field, or prohibited-key surface was introduced.

Scope observations: the diff touches only `pmqa/usage/summary.py` and
`tests/test_usage_summary.py`, plus the Coder-owned report in a separate
commit. No documentation, import-isolation, or packaging file changed,
matching the task's explicit expectation that none would be needed.

Compatibility observations: every Attempt 1 and Attempt 2 test not directly
touching predecessor-count boundaries continues to pass unmodified,
confirming legitimate `DefaultUsageAggregator` output (which by construction
never produces an invocation double-counted as both retry and fallback,
since each `AIInvocationRecord`'s own `attempt_number`/predecessor
invariants already enforce at-most-one predecessor per invocation) continues
to satisfy the new, stricter validator without any behavioral change to
normal aggregation.

## Verdict

Verdict: Pass

This verdict is advisory. The Architect makes the final technical
disposition.

## Suggested Architect Focus

- The reported gap is independently confirmed closed by direct reproduction
  and by hand-tracing the boundary logic, not just by re-running the
  Coder's own tests. Nothing further is blocking from this Reviewer's
  independent inspection.
- This is the third consecutive attempt on Task 5C.7 where a genuine
  cross-field or cross-level contract gap was caught only by the
  Architect's own adversarial construction, not by the Coder's or this
  Reviewer's own testing at the prior attempt. I flagged this pattern in
  the Attempt 2 report as well; repeating it here because the underlying
  cause seems consistent across all three instances: each attempt's tests
  verified the fields being changed, but not the *interaction* between a
  new/existing invariant and a sibling invariant already present elsewhere
  in the same contract (Attempt 1: per-field aggregate bounds without
  cross-level rollup; Attempt 2: cross-level rollup without predecessor
  mutual exclusivity). If Task 5C.7 is now feature-complete, it may be
  worth a short final adversarial pass enumerating *pairs* of already-
  individually-valid nested contradictions before moving to the next
  checkpoint, rather than continuing to find them one at a time.

## Reviewer Write-Boundary Confirmation

Repository files changed by Reviewer:

- `agent-handoff/reviewer-report.md`

Confirmation: I changed no production code, tests, configuration, schemas,
packaging, scripts, product documentation, or another role's handoff file.
