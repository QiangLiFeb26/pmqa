# Independent Reviewer Report

Owner: Independent Reviewer

Status: Executed for PMQA Task 5C.5, Attempt 1

## Task Correlation

Task: PMQA Task 5C.5 — Provider-Neutral AI Invocation Collector

Task ID: `PMQA-5C.5`

Attempt: `1`

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed Starting HEAD: `119330ec2355b2ab8d8f4afa66d23d0af8a06654`

Reviewed Implementation Commit(s): `346cc7ccb667ff3be7f58a8282e7fad67a2bcae9`
("add Task 5C.5 invocation collector")

Derived Coder Report Commit: `5b8921bf6aa8f4db8cf4f27a453a26bcd3ab9e89`
("report Task 5C.5 invocation collector")

Correlation Verification:

- derived with `git log -1 --format=%H -- agent-handoff/coder-report.md` ->
  `5b8921bf6aa8f4db8cf4f27a453a26bcd3ab9e89`;
- `git merge-base --is-ancestor 119330ec2355b2ab8d8f4afa66d23d0af8a06654 HEAD`
  succeeds; `119330ec...` is an ancestor of `346cc7c...`, and `346cc7c...` is
  an ancestor of `5b8921b...` (linear sequence
  `119330e -> 346cc7c -> 5b8921b` on this branch);
- the Task 5C.4 baseline named by `current-task.md`,
  `f5a960d359b671c485d70871eecb2e150b9e23d6`, is an ancestor of the recorded
  starting HEAD;
- the correlation header of `coder-report.md` at the derived commit names
  Task ID `PMQA-5C.5`, Attempt `1`, branch
  `agent/task-5c-1-canonical-run-contract`, and starting HEAD
  `119330ec2355b2ab8d8f4afa66d23d0af8a06654`, matching `current-task.md`;
- `git diff --stat 346cc7c..5b8921b` touches only
  `agent-handoff/coder-report.md`, so the derived commit is the report's
  latest authorized change with no later unauthorized replacement.

This Reviewer report does not contain or predict its own commit SHA. The
Architect derives the Reviewer report commit from Git and records it in
`architect-review.md`.

## Independent Review Method

Inspection order completed:

1. `current-task.md` and acceptance criteria;
2. named baseline-to-implementation diff (`119330e..346cc7c`) and the new/
   modified tests, including a full read of `pmqa/usage/collector.py` and
   `tests/test_usage_collector.py`;
3. independently selected validation (see Test Evidence);
4. full `coder-report.md` (read only after steps 1-3).

Active-task `architect-review.md` read before publication: No

Prior closed review or architecture material consulted, with reason:
re-read the prior Task 5C.4 review context already established in this
session (contracts.py, run/models.py conventions) to confirm the extracted
`_validate_ai_invocation_metadata_values` helper matches the previously
reviewed `AIInvocationRecord` cross-field policy byte-for-byte; no closed
handoff report for this task was read.

## Review Depth

Actual Review Depth: Deep

Review Depth Reason: this checkpoint introduces a security-sensitive opaque
runtime-ownership boundary (handle forgery/mutation/foreign-collector
resistance) and an exactly-once concurrency-lock terminalization policy;
correctness here cannot be assessed from test pass/fail counts alone, so I
read `pmqa/usage/collector.py` in full, traced every lifecycle path
(start / complete / fail / cancel / duplicate / corrupted-handle / evidence-
failure / clock-failure / resource-exception) against the code, and
independently executed all listed validation commands. This matches the
Coder's advisory recommendation but was independently selected.

## Overall Assessment

The implementation is a tightly-scoped, careful addition that satisfies the
task's lifecycle, ownership, clock, and security requirements. `pmqa/usage/
collector.py` adds `AIInvocationCollectionErrorCode`,
`AIInvocationCollectionError`, an opaque constructor-protected
`AIInvocationHandle`, a `runtime_checkable` `AIInvocationCollector` protocol,
and `DefaultAIInvocationCollector`. The one change to `pmqa/usage/
contracts.py` is a pure refactor: the existing `AIInvocationRecord` cross-
field model/predecessor validation was extracted verbatim into a private
`_validate_ai_invocation_metadata_values` function so the collector can reuse
it; I diffed the extracted logic against the original inline block and
confirmed it is unchanged (only reindented and parameterized), so the Task
5C.4 wire schema and semantics are unmodified.

I independently traced the handle-ownership design: handles are exact-type
checked (`type(handle) is AIInvocationHandle`, rejecting subclasses),
constructor-protected (`__init__` always raises; only `_create` with a
private module-level sentinel can build one), bound to one collector
instance via a private `owner` marker plus a per-invocation `integrity`
token, and looked up by identity in a per-instance `dict`. A forged handle
built by directly calling the private `_create` classmethod (even with the
correct sentinel, which is importable since Python has no true privacy)
still fails safely because it was never registered as a key in any
collector's active-invocation table. An internally mutated handle (its
private `owner`/`integrity` slot overwritten via `object.__setattr__`,
bypassing the class's own `__setattr__` override) is detected because the
stored `_ActiveInvocation.integrity` no longer matches, and the corrupted
entry is deleted rather than left retryable. All of this is exercised by
`test_foreign_forged_subclassed_and_mutated_handles_are_rejected` and
`test_handle_is_opaque_immutable_and_not_serializable`, which I read and ran.

The at-most-once terminalization policy matches the task's recommended
default exactly: `_snapshot_evidence` (which independently reconstructs
caller-supplied `TokenUsageEvidence`/`CostEvidence` via `from_dict(to_dict())`
and rejects non-instances, including raw dicts) runs *before* the handle is
removed from the active table, so evidence or failure-category validation
failures leave the handle retryable; ownership is then consumed atomically
under a `Lock` immediately before terminal clock sampling, so any expected
failure afterward (bad clock value, backwards time, non-finite/overflow
duration, or a final `AIInvocationRecord` construction failure such as
pricing-effective-at-in-the-future) permanently consumes the handle. This is
independently verified by
`test_invalid_evidence_and_failure_category_leave_handle_retryable`,
`test_mutated_evidence_is_rejected_before_clocks_and_can_be_corrected`,
`test_invalid_terminal_clock_consumes_handle`,
`test_backwards_and_overflow_terminal_timing_fail_safely`, and
`test_pricing_correlation_failure_after_clock_sampling_consumes_handle`, all
of which I read and ran. Duration is derived only from monotonic samples
converted through `Decimal` (using `str()` conversion for floats to avoid
binary-float imprecision) and rounded with `ROUND_HALF_UP`; wall-clock
values are used only for the `started_at`/`completed_at` fields and the
backwards-time invariant, never for duration, matching
`test_duration_rounding_is_deterministic` and
`test_successful_lifecycle_preserves_correlation_zero_and_duration`.
`MemoryError`, `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit` are
re-raised unchanged (identity-checked, not just type-checked) at every clock
stage in both the collector code and
`test_resource_and_control_flow_exceptions_propagate_exactly`.

All validation commands listed in `current-task.md`, run independently rather
than accepted from the Coder report, pass with no failures, errors, or
unexplained skips.

## Findings

None blocking. One non-blocking observation is recorded under Suggested
Architect Focus: the "concurrent contenders are serialized by the private
lock" claim in the Coder report is correct by code inspection (the
`with self._lock: if self._active.get(handle) is not active: raise ... del
self._active[handle]` block in `_terminalize` is the sole ownership-transfer
point), but no test in `tests/test_usage_collector.py` exercises this with
actual concurrent threads — coverage is sequential/single-threaded only. This
does not block Pass because the task's Required Tests list asks for
"exactly-once terminalization" and "duplicate completion/fail/cancel
combinations rejected," both of which are covered sequentially, and does not
explicitly require a multi-threaded stress test.

## Acceptance Criteria Coverage

| Acceptance criterion | Evidence | Result |
| --- | --- | --- |
| The public collector interface is provider-neutral | `AIInvocationCollector` Protocol (`pmqa/usage/collector.py:148-192`) takes only canonical correlation, `TokenUsageEvidence`, `CostEvidence`, `RunErrorCategory`; no provider-specific parameter anywhere | Met |
| The runtime handle cannot become persisted domain data | `AIInvocationHandle.__reduce__` raises `TypeError`; no `to_dict`/serialization method exists; `test_handle_is_opaque_immutable_and_not_serializable` confirms `pickle.dumps`/`json.dumps` both raise | Met |
| Lifecycle terminalization is exactly once | Lock-guarded atomic removal in `_terminalize` (`pmqa/usage/collector.py:401-406`); `test_every_terminal_combination_is_exactly_once` exercises all 9 first/second method combinations | Met |
| Canonical evidence is snapshotted without fabrication or caller mutation | `_snapshot_evidence` uses `from_dict(to_dict())` round trip, exact-type-checks instances; `test_returned_record_does_not_retain_caller_evidence` mutates the caller's original objects post-hoc and confirms no effect | Met |
| Wall and monotonic clocks are injected, bounded, and safely contained | `_sample_wall_clock`/`_sample_monotonic_clock` validate type/timezone/finiteness and wrap ordinary exceptions; `test_invalid_start_clock_values_fail_safely`/`test_ordinary_clock_exception_is_contained` independently run and pass | Met |
| Duration uses only monotonic evidence | `_duration_milliseconds(started, completed)` takes only `Decimal` monotonic samples; wall-clock difference never enters the calculation | Met |
| Failure/status/error correlation is canonical | `fail_invocation` rejects non-`RunErrorCategory`/`CANCELLED`; `cancel_invocation` hard-codes `RunErrorCategory.CANCELLED`; `complete_invocation` passes `error_category=None`, all enforced again by the reused `AIInvocationRecord` validators | Met |
| Expected failures are fixed, bounded, and marker-safe | All 11 `AIInvocationCollectionError` raises use `from None`; fixed 8-code vocabulary with static messages; `_assert_safe_error` helper independently verified across all collector tests | Met |
| Resource/control-flow exceptions remain authoritative | `_RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS` re-raised verbatim (identity-checked) at every try/except in `collector.py`; `test_resource_and_control_flow_exceptions_propagate_exactly` independently run and passes | Met |
| Imports remain side-effect free and isolated | `tests/test_usage_imports.py` extended with `AIInvocationCollector`/`DefaultAIInvocationCollector` assertions and independently rerun; no collector instance or clock sampling occurs at import time | Met |
| No provider, parser, calculator, pricing table, storage, CLI, UI, workflow integration, or optimization is added | Independent grep of `pmqa/usage/collector.py` for provider/orchestration keywords found none; diff confirms only additive test/doc/package changes elsewhere | Met |
| All new and existing required tests pass | 138 focused + 332 regression + 98 Task 4 + 1699/5-skip full suite + 2 Playwright, all independently run, all pass | Met |
| Coder and Reviewer follow their exclusive write boundaries | `git diff --stat` from starting HEAD to the derived report commit touches only allowed implementation/test/doc paths plus `agent-handoff/coder-report.md`; no Architect/Reviewer file changed | Met |

## Test Evidence

### Coder Evidence Reviewed

The Coder report claims: 138 passed for focused collector + Task 5C.4 usage/
pricing/import tests; 332 passed for the Run/Runner/Application/boundary/
packaging regression set; 98 passed for the Task 4 orchestration set (one
pre-existing LangGraph deprecation warning); 1699 passed, 5 skipped for the
full default suite; 2 passed for `products/demo/generated_tests` (noting a
transient macOS Chromium sandbox permission issue on first launch, resolved
on rerun); `compileall` and `git diff --check` clean; clean worktree. This
claimed evidence was read only after independent execution below and matches
it exactly, except the Reviewer's environment did not encounter the noted
transient Chromium permission issue.

### Independently Run

All commands below were executed by the Reviewer directly, before reading
the Coder's claimed results, from the repository root on the reviewed
branch:

- `.venv/bin/python -m pytest tests/test_usage_collector.py tests/test_usage_contracts.py tests/test_usage_pricing.py tests/test_usage_imports.py -q`
  -> `138 passed`
- `.venv/bin/python -m pytest tests/test_run_contracts.py tests/test_runner_contracts.py tests/test_application_contracts.py tests/test_application_service.py tests/test_boundary_policy.py tests/test_packaging.py -q`
  -> `332 passed`
- `.venv/bin/python -m pytest tests/test_workflow_runtime.py tests/test_workflow_reducer.py tests/test_supervisor_policy.py tests/test_langgraph_workflow.py -q`
  -> `98 passed, 1 warning` (pre-existing `LangChainPendingDeprecationWarning`,
  unrelated to this change)
- `.venv/bin/python -m pytest -q` (full default suite) -> `1699 passed, 5 skipped, 1 warning`
- `.venv/bin/python -m pytest products/demo/generated_tests -q` -> `2 passed`
- `PYTHONPYCACHEPREFIX=<isolated scratch directory> .venv/bin/python -m compileall -q pmqa products`
  -> exit code `0`, no output
- `git diff --check` -> exit code `0`, no output
- `git status --short` -> empty (clean worktree)

No listed validation command was left unrun. No test was skipped by Reviewer
choice. Environment: local `.venv` (Python 3.9), macOS/Darwin, no network
access used or required.

## Security, Scope, and Compatibility

Security observations: the collector and handle retain no prompt, response,
credential, environment, provider client, or arbitrary metadata — confirmed
by reading `pmqa/usage/collector.py` in full and by
`test_handle_is_opaque_immutable_and_not_serializable`. All expected error
paths raise the fixed `AIInvocationCollectionError` with `from None` and a
static per-code message, never echoing caller input, clock output, or handle
identity; `_assert_safe_error` independently verified this across the full
parametrized test matrix (including a `"runtime-secret-marker"` canary value
threaded through metadata, clock, and evidence inputs). The handle-ownership
model correctly resists forged, foreign-collector, subclassed, and
internally-mutated handles as detailed in Overall Assessment.

Scope observations: the diff touches only `pmqa/usage/collector.py` (new),
one small refactor-only hunk in `pmqa/usage/contracts.py`, `pmqa/usage/
__init__.py` exports, one new focused test file, small additive blocks in
`tests/test_packaging.py` and `tests/test_usage_imports.py`, and the four
allowed documentation files, plus the Coder-owned report in a separate
commit. No file under `pmqa/run`, `pmqa/runners`, `pmqa/application`,
`pmqa/security`, or `products/` was modified, and no `RunRecord`/
`RunnerInvocationRecord`/`WorkflowState` field was touched.

Compatibility observations: the `pmqa/usage/contracts.py` change is a
verified pure refactor (identical validation logic relocated into a shared
private function) with no wire-schema or behavioral change — all pre-
existing Task 5C.4 contract tests pass unchanged. `pmqa.usage` still imports
only from `pmqa.run`/`pmqa.run.models` plus the standard library
(`dataclasses`, `datetime`, `decimal`, `enum`, `math`, `threading`, `time`,
`typing`); no new runtime dependency was added.

## Verdict

Verdict: Pass

This verdict is advisory. The Architect makes the final technical
disposition.

## Suggested Architect Focus

- No test exercises the lock-based exactly-once guarantee under actual
  concurrent (multi-threaded) contention; the guarantee is correct by code
  inspection (single atomic `Lock`-guarded check-and-delete), but coverage is
  sequential only. Not a blocking gap against the stated Required Tests list,
  but worth a follow-up test if the collector is ever expected to run under
  real thread-level concurrency rather than single-threaded async/await
  usage.
- The private `_HANDLE_FACTORY_KEY` sentinel and `AIInvocationHandle._create`
  classmethod are technically importable/callable by a determined caller
  (Python has no true privacy), so "forged" handles are only rejected
  because they were never registered in a collector's active-invocation
  table, not because `_create` itself is unreachable. This is sufficient
  (verified) but relies on dict-membership as the actual security boundary
  rather than construction-time gating; worth confirming this is the
  intended defense-in-depth layering for future review.
- Confirm the `AIInvocationCollectionErrorCode` vocabulary (8 fixed codes) is
  the intended stable public surface, since a future provider/runner adapter
  will likely branch on these codes.

## Reviewer Write-Boundary Confirmation

Repository files changed by Reviewer:

- `agent-handoff/reviewer-report.md`

Confirmation: I changed no production code, tests, configuration, schemas,
packaging, scripts, product documentation, or another role's handoff file.
