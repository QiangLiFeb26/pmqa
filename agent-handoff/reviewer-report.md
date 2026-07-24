# Independent Reviewer Report

Owner: Independent Reviewer

Status: Executed for PMQA Task 5C.4, Attempt 1

## Task Correlation

Task: PMQA Task 5C.4 — Provider-Neutral AI Usage and Cost Contracts

Task ID: `PMQA-5C.4`

Attempt: `1`

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed Starting HEAD: `150c265974eac9f73ffc76b5eb7cd70f94f9cb5c`

Reviewed Implementation Commit(s): `2252c14736a050e87be6b769f488754a64b144bc`
("add Task 5C.4 usage and cost contracts")

Derived Coder Report Commit: `68953a0999f479a0ffe4ee4c964aa3bb4daa637a`
("report Task 5C.4 usage contracts")

Correlation Verification:

- derived with `git log -1 --format=%H -- agent-handoff/coder-report.md` ->
  `68953a0999f479a0ffe4ee4c964aa3bb4daa637a`;
- `git merge-base --is-ancestor 150c265974eac9f73ffc76b5eb7cd70f94f9cb5c HEAD`
  succeeds, and both `150c265...` and `2252c14...` are ancestors of
  `68953a0...` (`git log --oneline` shows the linear sequence
  `150c265 -> 2252c14 -> 68953a0` on this branch);
- the correlation header of `coder-report.md` at the derived commit names
  Task ID `PMQA-5C.4`, Attempt `1`, branch
  `agent/task-5c-1-canonical-run-contract`, and starting HEAD
  `150c265974eac9f73ffc76b5eb7cd70f94f9cb5c`, matching `current-task.md`;
- `git diff --stat 2252c14..68953a0` touches only
  `agent-handoff/coder-report.md`, so the derived commit is the report's
  latest authorized change with no later unauthorized replacement.

This Reviewer report does not contain or predict its own commit SHA. The
Architect derives the Reviewer report commit from Git and records it in
`architect-review.md`.

## Independent Review Method

Inspection order completed:

1. `current-task.md` and acceptance criteria;
2. named baseline-to-implementation diff (`150c265..2252c14`) and the new/
   modified tests;
3. independently selected validation (see Test Evidence);
4. full `coder-report.md` (read only after steps 1-3).

Active-task `architect-review.md` read before publication: No

Prior closed review or architecture material consulted, with reason: read
`pmqa/run/models.py` and `pmqa/run/__init__.py` (existing, already-merged
architecture) to verify the neutral helpers reused by `pmqa.usage`
(`_RunContract`, `_canonical_timestamp`, `_parse_enum`, `_serialize_timestamp`,
`validate_run_identifier`, `RUN_PAYLOAD_PROHIBITED_KEYS`/`is_prohibited_key`
via inheritance) are applied consistently with established contract
precedent (e.g. `RunReference`, `WorkflowPreviewStep`, `RunArtifact`,
`RunError` field/schema-version conventions). No closed handoff report for
this task was read.

## Review Depth

Actual Review Depth: Deep

Review Depth Reason: this checkpoint defines a new persisted evidence
vocabulary (usage, cost, pricing) with many mutually exclusive/interlocking
invariants (source/type/reason vocabularies, present-zero-vs-unavailable,
estimated-requires-pricing-evidence) that will govern future provider
integrations; a shallow pass could not verify the missing-data and
decimal/currency invariants line by line, so I independently read all three
new implementation files in full, cross-checked every validator against the
acceptance criteria, and independently executed all listed validation
commands rather than accepting the Coder's claimed results. This matches the
Coder's advisory recommendation but was independently selected.

## Overall Assessment

The implementation is a careful, narrowly-scoped extension that satisfies the
task's contract, security, and isolation requirements. `pmqa/usage/contracts.py`
defines `UsageSource`, `CostType`, `EvidenceUnavailableReason`, `TokenField`,
`TokenFieldAbsence`, `TokenUsageEvidence`, `CostEvidence`,
`AIInvocationStatus`, and `AIInvocationRecord`; `pmqa/usage/pricing.py` adds
`PricingUnit`, `PricingComponentKind`, `PricingComponent`, `ModelPricing`, and
a `runtime_checkable` `PricingCatalog` protocol. Both files build on the
existing `_RunContract` base (strict, frozen, `extra=forbid`,
`hide_input_in_errors`, bounded canonical-tree validation) and wrap
reconstruction failures in a new `UsageContractValidationError` that never
leaks input, cause, or context, matching the established Run Contract
pattern. No provider, network, storage, pricing table, or orchestration
coupling was introduced, and `pmqa.usage` is not exported from top-level
`pmqa`.

I independently traced every stated invariant (present-zero vs. unavailable,
source/type distinctness, estimated-cost-requires-pricing, model-identity XOR,
retry/fallback predecessor arithmetic, pricing-effective-at-not-after-start,
independently-missing pricing components) against the validator code and
found each correctly enforced, with adversarial tests exercising the
corresponding rejection paths. All validation commands listed in
`current-task.md`, run independently rather than accepted from the Coder
report, pass with no failures, errors, or unexplained skips.

## Findings

None.

## Acceptance Criteria Coverage

| Acceptance criterion | Evidence | Result |
| --- | --- | --- |
| Contracts express complete, partial, zero, and unavailable usage without ambiguity | `TokenUsageEvidence.validate_evidence` (`pmqa/usage/contracts.py:277-298`); tests `test_partial_usage_explicitly_identifies_every_missing_field`, `test_entirely_unavailable_usage_has_no_counts`, `test_present_zero_is_not_unavailable` | Met |
| Reported, CLI-parsed, estimated, subscription-included, and unavailable evidence cannot be confused | `UsageSource`/`CostType` enums are structurally distinct fields with mutually exclusive validators (`CostEvidence.validate_evidence`, `pmqa/usage/contracts.py:375-424`); tests `test_complete_reported_and_cli_parsed_usage_remain_distinct`, `test_real_zero_cost_differs_from_unavailable_and_subscription`, `test_subscription_included_does_not_fabricate_money` | Met |
| Cost estimation requires external pricing evidence but no price table is embedded | `CostEvidence.validate_evidence` rejects `ESTIMATED` without complete `pricing_source_id`/`pricing_version`/`pricing_effective_at` (`pmqa/usage/contracts.py:396-400`); no literal price data anywhere in `pmqa/usage/`; grep confirms no provider/pricing constants | Met |
| AI/model invocation correlation remains separate from runner attempts and LangGraph state | `AIInvocationRecord` is a new top-level contract with only an optional `runner_invocation_id` string correlation; `RunRecord`, `RunnerInvocationRecord`, `WorkflowState` untouched (confirmed via diff) | Met |
| All canonical, security, immutability, and import-isolation requirements pass | `tests/test_usage_contracts.py`, `tests/test_usage_pricing.py`, `tests/test_usage_imports.py` (68 tests) independently run and pass; `pmqa/usage` inherits `_RunContract`'s frozen/`extra=forbid`/bounded-tree behavior | Met |
| Existing Run/Runner/Application and Task 4 behavior remain unchanged | `tests/test_run_contracts.py`, `tests/test_runner_contracts.py`, `tests/test_application_contracts.py`, `tests/test_application_service.py`, `tests/test_boundary_policy.py`, `tests/test_packaging.py`, `tests/test_workflow_runtime.py`, `tests/test_workflow_reducer.py`, `tests/test_supervisor_policy.py`, `tests/test_langgraph_workflow.py` independently run and pass unchanged; no non-usage production file in the diff except `tests/test_packaging.py` (additive assertions only) and docs | Met |
| The wheel includes only the intended new package code | `tests/test_packaging.py` extended with `pmqa/usage/__init__.py`, `contracts.py`, `pricing.py` assertions; independently rebuilt wheel via `pytest tests/test_packaging.py` (included in the regression run) passes | Met |
| No real provider, parser, storage, collector, calculator, CLI, UI, or optimization is added | Independent grep of `pmqa/usage/` for provider/orchestration keywords found none; `tests/test_usage_imports.py` subprocess isolation test independently rerun and passes | Met |
| Only the Coder modifies implementation and Coder-owned handoff files | `git diff --stat` between starting HEAD and the derived report commit touches only allowed implementation/test/doc paths plus `agent-handoff/coder-report.md`; no Architect/Reviewer file changed | Met |

## Test Evidence

### Coder Evidence Reviewed

The Coder report (`agent-handoff/coder-report.md`) claims: 68 passed for the
new usage/pricing/import tests; 332 passed for the Run/Runner/Application/
boundary/packaging regression set; 98 passed (1 pre-existing LangGraph
deprecation warning) for the Task 4 orchestration set; 1629 passed, 5 skipped
for the full default suite; 2 passed for `products/demo/generated_tests`;
`compileall` and `git diff --check` clean; clean worktree. This claimed
evidence was read only after independent execution below and matches it
exactly.

### Independently Run

All commands below were executed by the Reviewer directly, before reading the
Coder's claimed results, from the repository root on the reviewed branch:

- `.venv/bin/python -m pytest tests/test_usage_contracts.py tests/test_usage_pricing.py tests/test_usage_imports.py -q`
  -> `68 passed`
- `.venv/bin/python -m pytest tests/test_run_contracts.py tests/test_runner_contracts.py tests/test_application_contracts.py tests/test_application_service.py tests/test_boundary_policy.py tests/test_packaging.py -q`
  -> `332 passed`
- `.venv/bin/python -m pytest tests/test_workflow_runtime.py tests/test_workflow_reducer.py tests/test_supervisor_policy.py tests/test_langgraph_workflow.py -q`
  -> `98 passed, 1 warning` (pre-existing `LangChainPendingDeprecationWarning`,
  unrelated to this change)
- `.venv/bin/python -m pytest -q` (full default suite) -> `1629 passed, 5 skipped, 1 warning`
- `.venv/bin/python -m pytest products/demo/generated_tests -q` -> `2 passed`
- `PYTHONPYCACHEPREFIX=<isolated scratch directory> .venv/bin/python -m compileall -q pmqa products`
  -> exit code `0`, no output
- `git diff --check` -> exit code `0`, no output
- `git status --short` -> empty (clean worktree)

No listed validation command was left unrun. No test was skipped by Reviewer
choice. Environment: local `.venv` (Python 3.9), macOS/Darwin, no network
access used or required.

## Security, Scope, and Compatibility

Security observations: the new contracts correctly reuse `_RunContract`'s
`hide_input_in_errors=True`, `extra=forbid`, `strict=True`, and bounded
canonical-tree validation, and add no new payload/metadata field capable of
carrying arbitrary keys, so the existing `RUN_PAYLOAD_PROHIBITED_KEYS` list
did not need duplication. `UsageContractValidationError` is raised with
`from None` and never echoes the invalid value; verified both by reading the
code and by independently running the adversarial tests
(`test_unknown_prohibited_runtime_and_secret_inputs_fail_safely`,
`test_from_dict_rejects_cycles_depth_nonfinite_and_oversized_strings`,
`test_model_pricing_rejects_runtime_and_unknown_wire_data_safely`). No
prompt/response, credential, path, or provider-client field exists anywhere
in `pmqa/usage`.

Scope observations: the diff touches only the allowed new package
(`pmqa/usage/`), three new focused test files, one additive block in
`tests/test_packaging.py`, and the four allowed documentation files, plus the
Coder-owned report in a separate commit. No file under `pmqa/run`,
`pmqa/runners`, `pmqa/application`, `pmqa/security`, or `products/` was
modified.

Compatibility observations: `pmqa.usage` is additive and imports only from
`pmqa.run`/`pmqa.run.models` (one direction; no import of `pmqa.usage` exists
anywhere in `pmqa.run`, so no circular-import risk was introduced). All
pre-existing suites listed in `current-task.md`, plus the full default suite,
pass unchanged.

## Verdict

Verdict: Pass

This verdict is advisory. The Architect makes the final technical
disposition.

## Suggested Architect Focus

- `ModelPricing` shares one `unavailable_reason` across all missing pricing
  components (`input_price`/`output_price`/`cached_input_price`), unlike
  `TokenUsageEvidence`, where every missing token field carries its own
  independent reason. The Coder self-flagged this in "Remaining Risks." The
  task's Pricing Boundary Requirements only require components to be
  independently *present or absent*, not independently *reasoned*, so this
  is acceptance-criteria-compliant as written; confirm this is the intended
  granularity before a future pricing catalog implementation locks it in.
- `AIInvocationRecord.duration_ms` is accepted as an independent field and is
  not derived from, or cross-checked against,
  `completed_at - started_at` (see `test_invocation_timestamps_normalize_to_utc_without_deriving_duration`,
  which asserts a `duration_ms=7` invocation with a 60000ms wall-clock gap
  round-trips unchanged). This appears to be a deliberate choice (provider-
  reported generation duration can legitimately differ from wall-clock gap,
  e.g. queueing time), consistent with "do not fabricate/derive" evidence
  elsewhere in the task, but confirm this matches the intended semantics for
  future collectors.
- `pmqa/usage/contracts.py` and `pmqa/usage/pricing.py` import private
  underscore-prefixed helpers directly from `pmqa.run.models`
  (`_RunContract`, `_canonical_timestamp`, `_parse_enum`,
  `_serialize_timestamp`) rather than only the public `pmqa.run` surface.
  This was explicitly permitted by "reuse neutral helpers from `pmqa.run`"
  and avoids duplicating validation logic, but it is a tighter coupling to
  `pmqa.run`'s private internals than the public-API boundary implies; worth
  a one-line architecture note if this reuse pattern should be repeated by
  future packages.

## Reviewer Write-Boundary Confirmation

Repository files changed by Reviewer:

- `agent-handoff/reviewer-report.md`

Confirmation: I changed no production code, tests, configuration, schemas,
packaging, scripts, product documentation, or another role's handoff file.
