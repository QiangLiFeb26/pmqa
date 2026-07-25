# Independent Reviewer Report

Owner: Independent Reviewer

Status: Executed for PMQA Task 5C.7, Attempt 2

## Task Correlation

Task: PMQA Task 5C.7 — Cross-Level Summary Consistency

Task ID: `PMQA-5C.7`

Attempt: `2`

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed Starting HEAD: `370434c4c42c31b3bde573f10bf63e2b503b0c00`

Reviewed Implementation Commit(s): `3419a9e5d4460186c2608dbd7f1e26762241c070`
("enforce Task 5C.7 summary consistency")

Derived Coder Report Commit: `71aa76384a628915e170950758f256add9d5eaee`
("report Task 5C.7 consistency remediation")

Correlation Verification:

- derived with `git log -1 --format=%H -- agent-handoff/coder-report.md` ->
  `71aa76384a628915e170950758f256add9d5eaee`;
- `git merge-base --is-ancestor 370434c4c42c31b3bde573f10bf63e2b503b0c00 HEAD`
  succeeds; `370434c...` is an ancestor of `3419a9e...`, and `3419a9e...` is
  an ancestor of `71aa763...` (linear sequence
  `370434c -> 3419a9e -> 71aa763` on this branch);
- the reviewed Attempt 1 Reviewer HEAD named by `current-task.md`,
  `569c519c043b3ce97a17dca5d1370ed60a6bc5d9` (this Reviewer's own prior
  Attempt 1 report commit), is an ancestor of the recorded starting HEAD;
- the correlation header of `coder-report.md` at the derived commit names
  Task ID `PMQA-5C.7`, Attempt `2`, branch
  `agent/task-5c-1-canonical-run-contract`, and starting HEAD
  `370434c4c42c31b3bde573f10bf63e2b503b0c00`, matching `current-task.md`;
- `git diff --stat 3419a9e..71aa763` touches only
  `agent-handoff/coder-report.md`, so the derived commit is the report's
  latest authorized change with no later unauthorized replacement.

This Reviewer report does not contain or predict its own commit SHA. The
Architect derives the Reviewer report commit from Git and records it in
`architect-review.md`.

## Independent Review Method

Inspection order completed:

1. `current-task.md` and acceptance criteria (the Architect's reproduced
   contradictory-summary scenario and the F1/F2-style remediation
   requirements);
2. named baseline-to-implementation diff (`370434c..3419a9e`) — full read of
   the `pmqa/usage/summary.py` diff (`_validate_group_rollup` and the
   monetary-branch replacement) and the added sections of
   `tests/test_usage_summary.py`;
3. independently selected validation (see Test Evidence), including
   reproducing the Architect's exact reported contradictory-summary scenario
   by hand against the remediated code, and independently reproducing the
   monetary-assertion fix under `python -O`, both independent of the
   Coder's own tests;
4. full `coder-report.md` (read only after steps 1-3).

Active-task `architect-review.md` read before publication: No

Prior closed review or architecture material consulted, with reason: this
Reviewer authored the Attempt 1 review of this same task
(`agent-handoff/reviewer-report.md` at commit `569c519`, superseded by this
report), which flagged the monetary `assert` as a non-blocking code-quality
note but did not catch the cross-level reconciliation gap the Architect
found; that prior review context is necessarily part of independently
judging whether this attempt actually closes both gaps, so I compared the
Attempt 1 code (via `git diff 370434c..3419a9e`) directly against my own
recollection of what Attempt 1 validated, rather than re-deriving the gap
from `architect-review.md` (unread, per protocol).

## Review Depth

Actual Review Depth: Deep

Review Depth Reason: this remediation touches the mathematical self-
consistency of a persisted multi-level aggregate contract across six count
fields, duration, every `TokenField`, and Decimal-precise cost-bucket
merging — an area where a superficial pass (trusting the Coder's own tests)
would not have caught the original gap either, since Attempt 1 passed all
of its own tests while still admitting the reported contradiction. I traced
`_validate_group_rollup` line-by-line against the required invariants,
independently reproduced the Architect's exact reported scenario and the
`-O` monetary-assertion concern in ad hoc scripts, and independently executed
all listed validation commands. This matches the Coder's advisory
recommendation but was independently selected.

## Overall Assessment

Both remediation targets are correctly and thoroughly closed, with no
regressions to Attempt 1 behavior and no scope creep — the diff touches only
`pmqa/usage/summary.py` and `tests/test_usage_summary.py`, and no public
field, enum, schema version, bound, ordering rule, or aggregation policy
changed (confirmed by re-running every Attempt 1 test unmodified alongside
the new ones).

**Cross-level reconciliation.** `UsageSummary.validate_group_coverage` now
calls a new `_validate_group_rollup(self)` after the existing `_validate_
metrics` check, which independently re-derives every top-level metric
exclusively from `provider_model_groups` and compares it to the public
top-level value:

- the six count fields (`invocation_count`, `succeeded_`/`failed_`/
  `cancelled_invocation_count`, `retry_`/`fallback_invocation_count`) are
  each summed across groups with a bounded-integer add and compared for
  exact equality — I traced this and confirmed it directly closes the
  reported gap, since Attempt 1 only checked `invocation_count`'s total, not
  the other five;
- `total_duration_ms` is summed across groups with the aggregate-integer
  bound and compared for exact equality;
- for every `TokenField`, group `observed_invocation_count` and
  `unavailable_invocation_count` are summed and compared, and an explicit
  `observed_total` flag distinguishes "no group observed this field" (must
  match a top-level `total is None`) from "groups observed it and their sum
  must equal the top-level total" — I confirmed this correctly rejects both
  directions of contradiction: a top `total=None` with some group reporting
  a numeric total, and a top numeric total with either a wrong sum or zero
  groups actually having observed it (the `not observed_total` half of the
  `or` guards against a top-level total that no group actually backs, even
  if it numerically happens to equal the summed value, e.g. both being 0);
- cost buckets are re-aggregated by the exact same six-field identity used
  elsewhere in this module (`_cost_bucket_identity`, not a second
  reimplementation), correctly merging multiple groups that share one
  identity via bounded Decimal addition inside a `localcontext(prec=512)`
  block before revalidating through the existing `_canonical_decimal` bound,
  then compared via a single dict-equality check against the top-level
  bucket set — this catches missing, extra, count-mismatched, and
  amount-mismatched buckets in one comparison, and I confirmed non-monetary
  (subscription-included/unavailable) buckets correctly stay `amount=None`
  through the merge.

I independently reproduced the Architect's exact reported scenario (a
`UsageSummary.from_dict()` wire payload claiming top-level
`succeeded=1, duration=100ms, input_tokens=10, cost=USD 0.1` while the sole
provider/model group claims
`failed=1, duration=999ms, input_tokens=999, cost=USD 999`) directly against
the remediated code in an ad hoc script, independent of the Coder's own
tests, and confirmed it now raises `UsageSummaryValidationError` rather than
being silently accepted.

I also independently confirmed the required exception-type discipline: every
raise inside `_validate_group_rollup` and its two bounded-arithmetic helpers
(`_bounded_summary_integer_add`, `_bounded_summary_decimal_add`) is a plain
`ValueError`, never the service-owned `UsageAggregationError` — this matters
because Pydantic v2 only wraps `ValueError`/`TypeError`/`AssertionError`
raised inside a `model_validator` into its own `ValidationError`; had the
Coder reused `UsageAggregationError` (a `RuntimeError` subclass) here, it
would have leaked unwrapped out of `UsageSummary(...)` construction. I traced
the full chain: a `ValueError` here becomes a Pydantic `ValidationError`
during `model_validate`, which `_RunContract.from_dict()` catches and
converts to `RunContractValidationError`, which `_SummaryContract.from_dict()`
converts to the fixed `UsageSummaryValidationError` — confirmed empirically
by `test_cross_level_from_dict_failure_is_fixed_safe_and_marker_free`
(independently rerun), which explicitly asserts
`not isinstance(captured.value, UsageAggregationError)`.

**Monetary assertion correction.** The bare `assert cost.amount is not None`
in `DefaultUsageAggregator._aggregate_metrics` is replaced with an explicit
`if cost.amount is None: raise UsageAggregationError(INVALID_RECORD) from
None`. I independently reproduced the exact concern I raised in the Attempt
1 review — running under `python -O` (which strips `assert` statements) with
a monkeypatched `_snapshot_record` that returns a record whose `cost.amount`
was corrupted to `None` via `object.__setattr__` — and confirmed the fixed
code now raises `UsageAggregationError(INVALID_RECORD)` correctly, rather
than the raw `TypeError` that a stripped assert would have allowed through
to the unguarded `Decimal + None` addition. The Coder's own test
(`test_monetary_invariant_is_explicit_under_optimized_python`) independently
verifies the identical scenario via a real `python -O` subprocess; I
verified this by reading the test and separately reproducing it myself
rather than only re-running the Coder's version.

All validation commands listed in `current-task.md`, run independently
rather than accepted from the Coder report, pass with no failures, errors,
or unexplained skips.

## Findings

None. Both remediation targets are independently confirmed closed by direct
reproduction outside the Coder's own test suite, and no new gap was found
during this Deep inspection.

## Acceptance Criteria Coverage

| Acceptance criterion | Evidence | Result |
| --- | --- | --- |
| No public `UsageSummary` can contain contradictory top-level and grouped lifecycle, predecessor, duration, token, or cost evidence | `_validate_group_rollup` traced line-by-line; the Architect's exact reported scenario independently reproduced and now rejected | Met |
| Every contract entry point enforces the invariant | Traced that `validate_group_coverage` is a `model_validator(mode="after")`, which Pydantic runs for direct construction, `from_dict`'s `model_validate`, and `model_copy`'s `model_validate`; `test_cross_level_duration_mismatch_rejected_by_all_entry_points` independently rerun, exercising all three entry points in one test | Met |
| Exact bounded integer and Decimal semantics remain deterministic | `_bounded_summary_integer_add`/`_bounded_summary_decimal_add` traced by hand (localcontext prec=512 isolates the merge from ambient precision, then revalidates via the existing canonical-decimal bound); `test_cross_level_decimal_is_independent_of_ambient_precision`, `test_cross_level_integer_and_decimal_overflow_are_contract_failures` independently rerun | Met |
| Monetary aggregation contains no domain `assert` | Read `_aggregate_metrics`: the `assert` line is gone, replaced by an explicit `if`/`raise`; independently reproduced the `-O`-stripped-assert scenario myself and confirmed the fix, separate from the Coder's own subprocess test | Met |
| Fixed safe errors and exact resource/control-flow propagation remain intact | `_validate_group_rollup` and helpers only ever raise `ValueError`, never `UsageAggregationError`; `test_cross_level_from_dict_failure_is_fixed_safe_and_marker_free` and `test_cross_level_decimal_resource_exceptions_propagate_exactly` independently rerun | Met |
| Generated aggregator output and canonical wire format remain unchanged | All Attempt 1 aggregator/ordering/canonical-round-trip tests (e.g. `test_input_order_cannot_change_canonical_output`, `test_maximum_cardinality_supports_distinct_groups_and_cost_buckets`) are untouched in the diff and independently rerun unchanged | Met |
| Existing Task 5C.4-5C.7, application, Task 4, Task 5, Product Pack, import, and packaging regressions remain green | 267 focused + 332 regression + 98 Task 4 + 1828/5-skip full suite + 2 Playwright, all independently run, all pass | Met |
| Only allowed files changed | `git diff --stat 370434c..3419a9e` shows exactly `pmqa/usage/summary.py` and `tests/test_usage_summary.py`; no other usage/run/runner/application/security file touched | Met |

## Test Evidence

### Coder Evidence Reviewed

The Coder report claims: 52 summary-only focused tests; 267 passed for
summary + repository + collector + Task 5C.4 usage/pricing + import tests;
332 passed for the Run/Runner/Application/boundary/packaging regression set;
98 passed for the Task 4 orchestration set (one pre-existing LangGraph
deprecation warning); 1828 passed, 5 skipped for the full default suite; 2
passed for `products/demo/generated_tests`; `compileall` and
`git diff --check` clean; clean worktree. This claimed evidence was read
only after independent execution below and matches it exactly.

### Independently Run

All commands below were executed by the Reviewer directly, before reading
the Coder's claimed results, from the repository root on the reviewed
branch:

- `.venv/bin/python -m pytest tests/test_usage_summary.py tests/test_usage_repository.py tests/test_usage_collector.py tests/test_usage_contracts.py tests/test_usage_pricing.py tests/test_usage_imports.py -q`
  -> `267 passed`
- `.venv/bin/python -m pytest tests/test_run_contracts.py tests/test_runner_contracts.py tests/test_application_contracts.py tests/test_application_service.py tests/test_boundary_policy.py tests/test_packaging.py -q`
  -> `332 passed`
- `.venv/bin/python -m pytest tests/test_workflow_runtime.py tests/test_workflow_reducer.py tests/test_supervisor_policy.py tests/test_langgraph_workflow.py -q`
  -> `98 passed, 1 warning` (pre-existing `LangChainPendingDeprecationWarning`,
  unrelated to this change)
- `.venv/bin/python -m pytest -q` (full default suite) -> `1828 passed, 5 skipped, 1 warning`
- `.venv/bin/python -m pytest products/demo/generated_tests -q` -> `2 passed`
- `PYTHONPYCACHEPREFIX=<isolated scratch directory> .venv/bin/python -m compileall -q pmqa products`
  -> exit code `0`, no output
- `git diff --check` -> exit code `0`, no output
- `git status --short` -> empty (clean worktree)

In addition, and independent of the Coder's own tests, I directly
reproduced both remediation targets against the remediated code in ad hoc
scripts:

- constructed a summary via the real aggregator, then mutated its wire form
  to the Architect's exact reported contradiction (top-level
  `succeeded=1, duration=100, input_tokens total=10, cost=0.1 USD` vs. the
  sole group claiming
  `failed=1, duration=999, input_tokens total=999, cost=999 USD`) and
  confirmed `UsageSummary.from_dict(wire)` now raises
  `UsageSummaryValidationError` rather than succeeding;
- ran a standalone `python -O` script that corrupts a `CostEvidence.amount`
  to `None` via `object.__setattr__`, bypasses `_snapshot_record` via
  monkeypatching, and confirmed `DefaultUsageAggregator.summarize(...)`
  raises `UsageAggregationError(INVALID_RECORD)` rather than leaking a raw
  `TypeError` from an unguarded `Decimal + None` addition (the exact failure
  mode a stripped `assert` would have permitted).

No listed validation command was left unrun. No test was skipped by
Reviewer choice. Environment: local `.venv` (Python 3.9), macOS/Darwin, no
network access used or required.

## Security, Scope, and Compatibility

Security observations: the new reconciliation logic and the monetary-branch
fix both preserve the existing fixed-error/marker-safety discipline — I
independently confirmed (via the ad hoc reproductions above and by reading
`test_cross_level_from_dict_failure_is_fixed_safe_and_marker_free`) that
reconciliation failures expose only `UsageSummaryValidationError`'s fixed
`"invalid PMQA usage summary"` message with no identifier, provider/model
name, amount, cause, or context, and that the monetary fix exposes only the
existing fixed `UsageAggregationErrorCode.INVALID_RECORD`. No new
prohibited-key list, public field, or error code was introduced.

Scope observations: the diff touches only `pmqa/usage/summary.py` and
`tests/test_usage_summary.py`, plus the Coder-owned report in a separate
commit. No file under `pmqa/run`, `pmqa/runners`, `pmqa/application`,
`pmqa/security`, `pmqa/usage/contracts.py`, `pricing.py`, `collector.py`, or
`repository.py` was modified, and no documentation file changed (consistent
with the task's "do not change README, Roadmap, or architecture
documentation" instruction for this remediation).

Compatibility observations: every Attempt 1 test not directly touching
cross-level consistency continues to pass unmodified, confirming the
legitimate `DefaultUsageAggregator` output (which already partitions every
input record into exactly one group and derives both levels from the same
underlying per-record aggregation) continues to satisfy the new, stricter
validator without any behavioral change to normal aggregation.

## Verdict

Verdict: Pass

This verdict is advisory. The Architect makes the final technical
disposition.

## Suggested Architect Focus

- Both findings from the Attempt 1 Architect review (the cross-level
  reconciliation gap and the fragile monetary `assert`) are independently
  confirmed closed by direct reproduction, not just by re-running the
  Coder's own tests. Nothing further is blocking from this Reviewer's
  independent inspection.
- This is the second consecutive attempt on Task 5C.7 where a real gap
  (first the `assert`, now the missing cross-level reconciliation) was
  caught only by the Architect's own adversarial construction of a
  contradictory wire payload rather than by either the Coder's or this
  Reviewer's Attempt 1 test-driven inspection. Worth noting for the
  Architect's own process calibration: for future Usage/summary-style
  checkpoints where multiple views of the same data must agree, an
  explicit "construct an internally-valid-but-cross-level-contradictory
  wire payload" adversarial step may be worth adding to the Reviewer's
  standing checklist rather than relying on it surfacing only at Architect
  review.

## Reviewer Write-Boundary Confirmation

Repository files changed by Reviewer:

- `agent-handoff/reviewer-report.md`

Confirmation: I changed no production code, tests, configuration, schemas,
packaging, scripts, product documentation, or another role's handoff file.
