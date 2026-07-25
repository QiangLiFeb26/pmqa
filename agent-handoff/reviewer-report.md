# Independent Reviewer Report

Owner: Independent Reviewer

Status: Executed for PMQA Task 5C.7, Attempt 1

## Task Correlation

Task: PMQA Task 5C.7 — Deterministic Usage Summary Contracts and Pure
Aggregation

Task ID: `PMQA-5C.7`

Attempt: `1`

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed Starting HEAD: `4128ef969e1a3dc90297a74c513a6cd2eabf0376`

Reviewed Implementation Commit(s): `eeba9a9dd1d2fac6a007580d4511fbb51722bd15`
("add deterministic usage summaries")

Derived Coder Report Commit: `7b5b577ee369cc9b717d97c723a4ae8a479cec37`
("report Task 5C.7 implementation")

Correlation Verification:

- derived with `git log -1 --format=%H -- agent-handoff/coder-report.md` ->
  `7b5b577ee369cc9b717d97c723a4ae8a479cec37`;
- `git merge-base --is-ancestor 4128ef969e1a3dc90297a74c513a6cd2eabf0376 HEAD`
  succeeds; `4128ef9...` is an ancestor of `eeba9a9...`, and `eeba9a9...` is
  an ancestor of `7b5b577...` (linear sequence
  `4128ef9 -> eeba9a9 -> 7b5b577` on this branch);
- the Task 5C.6 Reviewer baseline named by `current-task.md`,
  `a258ba59b7fdd1edb6e01ab738ea9203610e954b` (this Reviewer's own prior
  Task 5C.6 report commit), is an ancestor of the recorded starting HEAD;
- the correlation header of `coder-report.md` at the derived commit names
  Task ID `PMQA-5C.7`, Attempt `1`, branch
  `agent/task-5c-1-canonical-run-contract`, and starting HEAD
  `4128ef969e1a3dc90297a74c513a6cd2eabf0376`, matching `current-task.md`;
- `git diff --stat eeba9a9..7b5b577` touches only
  `agent-handoff/coder-report.md`, so the derived commit is the report's
  latest authorized change with no later unauthorized replacement.

This Reviewer report does not contain or predict its own commit SHA. The
Architect derives the Reviewer report commit from Git and records it in
`architect-review.md`.

## Independent Review Method

Inspection order completed:

1. `current-task.md` and acceptance criteria;
2. named baseline-to-implementation diff (`4128ef9..eeba9a9`) — full read of
   `pmqa/usage/summary.py` (all 936 lines) and `tests/test_usage_summary.py`
   (all 800 lines);
3. independently selected validation (see Test Evidence);
4. full `coder-report.md` (read only after steps 1-3).

Active-task `architect-review.md` read before publication: No

Prior closed review or architecture material consulted, with reason:
re-verified, via `git diff --stat`, that `pmqa/usage/contracts.py`,
`pricing.py`, `collector.py`, and `repository.py` are byte-identical to the
Task 5C.6 baseline (empty diff), confirming this checkpoint is a pure
additive domain/service layer with no coupling to storage; no closed handoff
report for this task was read.

## Review Depth

Actual Review Depth: Deep

Review Depth Reason: this checkpoint introduces a canonical aggregate
contract whose correctness rests on many interacting, easily-confused
invariants (missing-vs-zero, reported-vs-estimated cost, currency/pricing
provenance, deterministic ordering independent of input order, bounded
overflow arithmetic) that cannot be assessed from test pass/fail counts
alone. I read the entire implementation and test files, traced every
aggregation code path (empty input, token coverage, cost-bucket identity,
provider/model grouping, overflow bounds) against the task's detailed
semantics, and independently executed all listed validation commands. This
matches the Coder's advisory recommendation but was independently selected.

## Overall Assessment

The implementation is a correct, carefully-bounded pure domain/service layer
that satisfies the task's summary-semantics, correlation, and security
requirements. `pmqa/usage/summary.py` adds `UsageSummaryScope`,
`UsageAggregationErrorCode` (5 fixed codes), `UsageAggregationError`,
`UsageSummaryValidationError`, three new strict frozen contracts
(`UsageTokenFieldSummary`, `UsageCostBucket`, `UsageProviderModelSummary`),
the top-level `UsageSummary`, a `runtime_checkable` `UsageAggregator`
protocol, and `DefaultUsageAggregator`. No existing `pmqa/usage/contracts.py`,
`pricing.py`, `collector.py`, or `repository.py` file was touched (confirmed
via an empty `git diff --stat` against those four paths) — this checkpoint
does not read storage, launch providers, or calculate prices, matching the
stated scope exactly.

I independently traced the empty-input case by hand against the required
semantics: with zero records, `_aggregate_metrics(())` produces
`duration=0`; for each `TokenField`, `observed=0` so `total=None` (via
`None if observed == 0 else total`), `unavailable_invocation_count =
len(()) - 0 = 0`; `cost_groups` stays empty so `cost_buckets = ()`; and the
per-provider grouping dict stays empty so `provider_model_groups = ()` —
this matches the required "every token field exactly once with total=None,
observed count 0, and unavailable count 0; no cost buckets; no provider/
model groups" precisely, and is confirmed by
`test_empty_summary_has_zero_counts_and_no_fabricated_unavailability`,
which I independently reran.

The cost-bucket grouping key
(`cost_type, currency, pricing_source_id, pricing_version,
pricing_effective_at, unavailable_reason`) is applied identically in both
the aggregator (`_cost_evidence_identity`) and the contract's own
duplicate-rejection validator (`_cost_bucket_identity` inside
`_snapshot_cost_buckets`), so provider-reported and estimated amounts,
different currencies, and distinct pricing provenance can never merge
either through the aggregator or through direct contract construction — I
confirmed this by reading both functions side-by-side and by independently
rerunning `test_cost_buckets_preserve_type_currency_provenance_and_non_money`
and `test_estimated_effective_timestamps_form_distinct_buckets`. The
`unavailable_reason` field is included in the identity even though the
task's cost-bucket grouping-key list only names `cost_type`/`currency`/
`pricing_source_id`/`pricing_version`/`pricing_effective_at`; this is
required separately by the task's own later sentence ("Group non-monetary
evidence separately: ... unavailable evidence, including its exact bounded
unavailable reason"), so this is not scope creep, it is a second explicit
requirement correctly implemented.

Decimal summation correctness is the single most safety-critical piece of
this checkpoint, since a silently-rounded sum would be a real financial
correctness bug. `_bounded_decimal_add` performs the addition inside a
`localcontext(prec=256)` block (well above the default 28-digit precision),
then validates the result through the existing `_canonical_decimal` bound
check (reused from `contracts.py`, not reimplemented) outside that block —
I independently confirmed, by reading `test_decimal_summation_ignores_
ambient_precision_and_never_uses_float` (which wraps the aggregation call in
an ambient `localcontext(prec=5)` set by the *caller* and asserts the full
28-digit exact sum survives) and by rerunning it, that this correctly
isolates the aggregate from both Python's default precision and any
caller-ambient precision setting. The overflow bound is exercised for real
by `test_decimal_aggregate_bound_is_enforced` (summing two 128-nine-digit
amounts, which produces a 129-digit result exceeding the existing 128-char
canonical bound), which I also reran independently.

One minor internal-safety observation, not a defect: in `_aggregate_metrics`,
the monetary summation loop uses a bare `assert cost.amount is not None`
before calling `_bounded_decimal_add`. I traced whether this could ever be
violated by an adversarial or corrupted input and confirmed it cannot: every
record reaching this code has already passed through `_snapshot_record`
(`AIInvocationRecord.from_dict(record.to_dict())`), which recursively
re-validates the nested `cost` field via `CostEvidence`'s own
`model_validator` — and that validator unconditionally rejects a
`PROVIDER_REPORTED`/`ESTIMATED` cost with `amount=None` at reconstruction
time, so a monetary-typed `CostEvidence` with a `None` amount cannot survive
the snapshot step even if the caller mutated a live object via
`object.__setattr__` before calling `summarize()` (I confirmed the general
pattern of this exact attack is caught by the snapshot step via
`test_record_subclass_mutation_and_excess_input_fail_safely`, which mutates
`record.__dict__["provider"]` and gets `INVALID_RECORD`). Because
`assert` statements are stripped under Python's `-O` optimization flag, this
is technically fragile as *written* even though it is currently
unreachable-as-false given the surrounding guarantees — see Suggested
Architect Focus.

All validation commands listed in `current-task.md`, run independently
rather than accepted from the Coder report, pass with no failures, errors,
or unexplained skips.

## Findings

None. The one internal-safety observation above (a defensively-placed but
currently-unreachable `assert`) is recorded under Suggested Architect Focus
as a code-quality note; it does not represent an exploitable defect given
the current call graph, and does not affect the verdict.

## Acceptance Criteria Coverage

| Acceptance criterion | Evidence | Result |
| --- | --- | --- |
| Summary contracts are strict, immutable, canonical, provider-neutral | All four new contracts extend `_SummaryContract`/`_RunContract` (strict, frozen, `extra=forbid`); `test_public_contract_fields_and_vocabularies_are_exact` independently rerun | Met |
| Empty, zero, partial, and unavailable evidence remain semantically distinct | Traced `_aggregate_metrics` empty-input path and `UsageTokenFieldSummary.validate_coverage`'s `(total is None) != (observed == 0)` invariant by hand; `test_zero_and_unavailable_token_evidence_remain_distinct`, `test_partial_token_totals_status_predecessors_and_duration_are_exact` independently rerun | Met |
| Reported, estimated, subscription-included, unavailable, currency, and pricing provenance never conflated | `_cost_evidence_identity`/`_cost_bucket_identity` traced side-by-side; `UsageCostBucket.validate_identity` enforces the same distinctions at the contract level independent of the aggregator | Met |
| Status, retry/fallback, duration, token, and cost aggregation is exact and bounded | `_bounded_integer_add`/`_bounded_decimal_add` traced by hand; `test_duration_and_token_overflow_fail_safely`, `test_decimal_aggregate_bound_is_enforced` independently rerun | Met |
| Provider/model groups are deterministic and non-recursive | `UsageProviderModelSummary` field list has no nested groups field (confirmed via `test_public_contract_fields_and_vocabularies_are_exact`); `_provider_model_sort_key` enforced in the contract's own `snapshot_provider_model_groups` validator, not just the aggregator | Met |
| Input order cannot change canonical output | Canonical ordering enforced at the *contract* level (`_snapshot_token_fields`, `_snapshot_cost_buckets`, `snapshot_provider_model_groups` all sort deterministically regardless of construction order); `test_input_order_cannot_change_canonical_output` independently rerun, comparing byte-equal canonical JSON | Met |
| Duplicate or mismatched records fail safely rather than being filtered | Duplicate invocation-ID check and correlation-field check both precede aggregation and raise rather than silently drop; `test_duplicate_and_session_mismatch_fail_without_filtering`, `test_run_scope_requires_every_record_to_match` independently rerun | Met |
| No storage, pricing, provider, workflow, or CLI side effect added | Independent grep of `summary.py` for storage/provider/workflow keywords found none; diff confirms zero changes to `repository.py`/`pricing.py`/`collector.py` | Met |
| Import and packaging isolation remain intact | `tests/test_usage_imports.py`/`test_packaging.py` extended and independently rerun as part of the regression sets below | Met |
| Existing usage, application, Task 4, Task 5, and Product Pack behavior unchanged | 245 focused + 332 regression + 98 Task 4 + 1806/5-skip full suite + 2 Playwright, all independently run, all pass | Met |
| Only allowed files changed | `git diff --stat` from starting HEAD to the derived report commit touches only the nine allowed implementation/test/doc paths plus `agent-handoff/coder-report.md`; no Architect/Reviewer file changed | Met |

## Test Evidence

### Coder Evidence Reviewed

The Coder report claims: 245 passed for focused summary + repository +
collector + Task 5C.4 usage/pricing + import tests; 332 passed for the Run/
Runner/Application/boundary/packaging regression set; 98 passed for the
Task 4 orchestration set (one pre-existing LangGraph deprecation warning);
1806 passed, 5 skipped for the full default suite; 2 passed for
`products/demo/generated_tests`; `compileall` and `git diff --check` clean;
clean worktree. This claimed evidence was read only after independent
execution below and matches it exactly, except the Reviewer did not
independently run a Markdown-link validator (not part of the task's listed
Validation Commands).

### Independently Run

All commands below were executed by the Reviewer directly, before reading
the Coder's claimed results, from the repository root on the reviewed
branch:

- `.venv/bin/python -m pytest tests/test_usage_summary.py tests/test_usage_repository.py tests/test_usage_collector.py tests/test_usage_contracts.py tests/test_usage_pricing.py tests/test_usage_imports.py -q`
  -> `245 passed`
- `.venv/bin/python -m pytest tests/test_run_contracts.py tests/test_runner_contracts.py tests/test_application_contracts.py tests/test_application_service.py tests/test_boundary_policy.py tests/test_packaging.py -q`
  -> `332 passed`
- `.venv/bin/python -m pytest tests/test_workflow_runtime.py tests/test_workflow_reducer.py tests/test_supervisor_policy.py tests/test_langgraph_workflow.py -q`
  -> `98 passed, 1 warning` (pre-existing `LangChainPendingDeprecationWarning`,
  unrelated to this change)
- `.venv/bin/python -m pytest -q` (full default suite) -> `1806 passed, 5 skipped, 1 warning`
- `.venv/bin/python -m pytest products/demo/generated_tests -q` -> `2 passed`
- `PYTHONPYCACHEPREFIX=<isolated scratch directory> .venv/bin/python -m compileall -q pmqa products`
  -> exit code `0`, no output
- `git diff --check` -> exit code `0`, no output
- `git status --short` -> empty (clean worktree)

No listed validation command was left unrun. No test was skipped by
Reviewer choice. Environment: local `.venv` (Python 3.9), macOS/Darwin, no
network access used or required.

## Security, Scope, and Compatibility

Security observations: the aggregator accepts and returns only exact
`AIInvocationRecord`/`UsageSummary` contract instances (never raw dicts),
independently reconstructs every input record before use, and retains no
caller-owned container — confirmed by
`test_summary_round_trip_copy_freezing_and_independent_snapshot`, which
mutates the caller's original record/usage objects after summarization and
confirms the returned summary is unaffected. All five expected-error paths
use bounded static messages, suppress cause/context, and were independently
confirmed (via a `"runtime-secret-marker"` canary threaded through
identifiers, payloads, and a runtime object's `__repr__`) to never leak
provider/model names, amounts, identifiers, or object representations. No
new prohibited-key list was introduced; the summary contracts reuse
`validate_run_identifier`, `_canonical_currency`, `_canonical_decimal`, and
the inherited `_RunContract` bounded-tree/security boundary from
`pmqa.run`/`pmqa.usage.contracts` rather than duplicating policy.

Scope observations: the diff touches only `pmqa/usage/summary.py` (new),
`pmqa/usage/__init__.py` exports, one new focused test file, small additive
blocks in `tests/test_packaging.py` and `tests/test_usage_imports.py`, and
the four allowed documentation files, plus the Coder-owned report in a
separate commit. `pmqa/usage/contracts.py`, `pricing.py`, `collector.py`,
and `repository.py` are byte-identical to the Task 5C.6 baseline, and no
file under `pmqa/run`, `pmqa/runners`, `pmqa/application`, `pmqa/security`,
or `products/` was modified.

Compatibility observations: `pmqa.usage` still imports only from `pmqa.run`/
`pmqa.run.models` and `pmqa.usage.contracts` plus the standard library; no
new runtime dependency was added. All pre-existing suites listed in
`current-task.md`, plus the full default suite, pass unchanged.

## Verdict

Verdict: Pass

This verdict is advisory. The Architect makes the final technical
disposition.

## Suggested Architect Focus

- `_aggregate_metrics` in `pmqa/usage/summary.py` (around the monetary
  summation loop) uses a bare `assert cost.amount is not None` rather than
  an explicit checked branch that raises `UsageAggregationError`. I traced
  this and confirmed it is currently unreachable-as-false given that
  `_snapshot_record` fully re-validates every record (including its nested
  `cost`) before this code runs, so no defect exists today. However,
  `assert` statements are removed entirely when Python runs with `-O`, so if
  this invariant were ever violated by a future refactor that changes call
  order, the failure mode would become an unhandled `TypeError` rather than
  a fixed safe `UsageAggregationError`. Consider replacing the `assert` with
  an explicit check, purely for defense-in-depth against future changes, not
  because of any currently-exploitable gap.
- No other findings surfaced from this Reviewer's independent inspection.
  This checkpoint is a clean, well-isolated addition on top of an unchanged
  Task 5C.4-5C.6 foundation.

## Reviewer Write-Boundary Confirmation

Repository files changed by Reviewer:

- `agent-handoff/reviewer-report.md`

Confirmation: I changed no production code, tests, configuration, schemas,
packaging, scripts, product documentation, or another role's handoff file.
