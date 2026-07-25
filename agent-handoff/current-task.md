# Current Task

Owner: Architect

Task: PMQA Task 5C.7 — Cross-Level Summary Consistency

Task ID: `PMQA-5C.7`

Attempt: `2`

Status: Changes Required

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed Attempt 1 Reviewer HEAD:
`569c519c043b3ce97a17dca5d1370ed60a6bc5d9`

Coder starting HEAD: derive and record the latest pushed branch commit that
contains this remediation publication before changing implementation files.

Repository Markdown and Git history are authoritative. Chat summaries are
informational only.

## Task Objective

Make every successfully constructed `UsageSummary` prove that its top-level
metrics are the exact deterministic roll-up of its
`provider_model_groups`.

Also replace the internal monetary `assert` with an explicit fixed safe
invariant check.

Do not change public fields, aggregation meaning, limits, ordering, or
Task 5C.7 scope.

## Background

Attempt 1 correctly generates internally consistent summaries through
`DefaultUsageAggregator`, but the public contract accepts a contradictory
wire payload as long as group invocation counts add to the top-level count.

The Architect reproduced a `UsageSummary.from_dict()` result where the
top-level claimed:

```text
succeeded=1, duration=100ms, input_tokens=10, cost=USD 0.1
```

while the only provider/model group claimed:

```text
failed=1, duration=999ms, input_tokens=999, cost=USD 999
```

Both nested views were individually valid and `invocation_count` remained
one, so the current validator accepted the impossible aggregate.

The full evidence and disposition are in
`agent-handoff/architect-review.md`.

## Scope

- Add complete top-level/provider-group reconciliation to `UsageSummary`.
- Add focused adversarial contract tests.
- Replace the monetary `assert` with an explicit fixed safe branch.
- Replace `agent-handoff/coder-report.md` with the Attempt 2 report.

No public field, enum, schema version, limit, or aggregation policy changes.

## Required Cross-Level Invariants

For every valid `UsageSummary`, provider/model groups must collectively
reconstruct the exact top-level:

### Invocation and lifecycle counts

The sum across all groups must equal the corresponding top-level value for:

- invocation count;
- succeeded invocation count;
- failed invocation count;
- cancelled invocation count;
- retry invocation count;
- fallback invocation count.

### Duration

The exact bounded sum of group `total_duration_ms` must equal the top-level
`total_duration_ms`.

Use bounded integer arithmetic. Do not allow wrap, clamp, float conversion,
or unchecked sum behavior.

Contract reconciliation failures, including reconciliation overflow, must
surface through normal contract validation (`ValueError` /
`UsageSummaryValidationError` at the applicable public entry point). Do not
let the service-owned `UsageAggregationError` escape from
`UsageSummary.from_dict()`.

### Token fields

For every exact `TokenField`:

- sum of group observed counts equals top-level observed count;
- sum of group unavailable counts equals top-level unavailable count;
- if top-level `total is None`, every group must have `total is None`;
- otherwise, the exact bounded sum of every observed group total equals the
  top-level total;
- observed numeric zero remains zero;
- mixed observed/unavailable group coverage remains valid when it reconciles.

Do not infer values for unavailable groups.

### Cost buckets

Re-aggregate all group cost buckets by the existing complete cost identity:

- cost type;
- currency;
- pricing source ID;
- pricing version;
- pricing effective timestamp;
- unavailable reason.

The normalized group-derived buckets must match the top-level buckets exactly:

- identical identity set;
- exact invocation counts;
- exact monetary amount for monetary buckets;
- no amount for subscription-included or unavailable buckets.

Multiple provider/model groups may legitimately contribute to the same
top-level cost-bucket identity. Merge those contributions using exact bounded
Decimal arithmetic before comparison.

Do not compare Decimal through float conversion or caller ambient precision.
The contract validator must contain Decimal bound failures as contract
validation, not leak `InvalidOperation`, `UsageAggregationError`, or an
underlying arithmetic exception.

### Empty summary

The existing empty summary remains valid:

- no provider/model groups;
- zero lifecycle/duration/predecessor counts;
- every token field has `total=None` and zero coverage;
- no cost buckets.

## Contract Entry Points

The invariant must hold through:

- direct `UsageSummary(...)` construction;
- `UsageSummary.from_dict(...)`;
- `UsageSummary.model_copy(update=...)`;
- `DefaultUsageAggregator.summarize(...)`.

Expected direct construction/copy failures may remain Pydantic
`ValidationError` consistent with existing contract style.

Persisted reconstruction must expose only the fixed
`UsageSummaryValidationError`, with no contradictory identifier, provider,
model, amount, marker, underlying message, cause, or context.

## Monetary Assertion Remediation

Replace:

```python
assert cost.amount is not None
```

with an explicit checked branch.

Requirements:

- do not add a public error code;
- impossible monetary evidence at the aggregation boundary fails with the
  existing fixed `UsageAggregationErrorCode.INVALID_RECORD`;
- do not leak the record, amount, provider/model identity, or underlying
  exception;
- retain exact resource/control-flow propagation;
- valid monetary aggregation remains unchanged under normal and `python -O`
  execution.

## Preserve Existing Behavior

Do not change:

- any public Task 5C.7 field set or enum;
- `USAGE_SUMMARY_SCHEMA_VERSION`;
- `MAX_USAGE_SUMMARY_RECORDS`;
- aggregate integer bounds;
- empty/zero/partial/unavailable semantics;
- cost-bucket identity or ordering;
- provider/model identity or ordering;
- canonical JSON serialization;
- input tuple, exact record, duplicate, and correlation boundaries;
- repository, collector, pricing, Run, Runner, Application Service,
  WorkflowState, LangGraph, or Product Pack behavior;
- import or packaging isolation.

## Required Tests

Add focused tests that independently mutate otherwise canonical summaries and
prove rejection for:

- top-level versus group succeeded/failed/cancelled mismatch;
- retry and fallback mismatch;
- duration mismatch;
- token observed-count mismatch;
- token unavailable-count mismatch;
- token `None` versus observed total mismatch;
- token numeric total mismatch, including zero;
- missing, extra, or different top-level cost-bucket identity;
- monetary cost amount mismatch;
- cost-bucket invocation-count mismatch;
- multiple groups contributing to one compatible top-level monetary bucket;
- multiple groups contributing to subscription/unavailable buckets;
- different currency and pricing-provenance buckets remaining separate;
- empty summary remaining valid;
- `from_dict()` fixed safe failure with marker/cause/context checks;
- `model_copy(update=...)` revalidation;
- input-order-independent canonical aggregator output remaining unchanged;
- exact Decimal behavior under reduced caller ambient precision;
- bounded integer and Decimal reconciliation overflow;
- explicit monetary-invariant failure without relying on `assert`;
- resource/control-flow exception propagation.

Use canonical summaries from the real aggregator as the starting point for
adversarial wire mutations where practical.

Do not weaken a test by creating an object that fails an unrelated nested
contract before reaching cross-level validation.

## Allowed Changes

- `pmqa/usage/summary.py`;
- `tests/test_usage_summary.py`;
- `agent-handoff/coder-report.md`.

Minimal additive changes to `tests/test_usage_imports.py` or
`tests/test_packaging.py` are allowed only if genuinely required by the
remediation; none are expected.

Do not modify:

- `agent-handoff/README.md`;
- `agent-handoff/current-task.md`;
- `agent-handoff/reviewer-report.md`;
- `agent-handoff/architect-review.md`;
- public usage contracts, pricing, collector, or repository;
- README, Roadmap, or architecture documentation;
- RunRecord, Runner, Application Service, WorkflowState, LangGraph,
  Supervisor, Task 5, or Product Pack behavior.

Use one focused remediation implementation commit and one report-only Coder
handoff commit. Do not amend Attempt 1.

## Out of Scope

Do not add:

- new summary fields, enum values, schema versions, or public error codes;
- repository-backed selection, pagination, or completeness claims;
- CLI or Web UI;
- conversation, workflow, capability, artifact, or approval contracts;
- pricing lookup or cost calculation;
- provider/Copilot/ADO integration;
- outcome metrics;
- automatic persistence;
- retention, deletion, migration, database, or remote storage;
- Task 5D, Task 5B, Task 6, or Task 7;
- PR creation or merge.

## Validation Commands

Run and report:

```bash
.venv/bin/python -m pytest tests/test_usage_summary.py tests/test_usage_repository.py tests/test_usage_collector.py tests/test_usage_contracts.py tests/test_usage_pricing.py tests/test_usage_imports.py -q
.venv/bin/python -m pytest tests/test_run_contracts.py tests/test_runner_contracts.py tests/test_application_contracts.py tests/test_application_service.py tests/test_boundary_policy.py tests/test_packaging.py -q
.venv/bin/python -m pytest tests/test_workflow_runtime.py tests/test_workflow_reducer.py tests/test_supervisor_policy.py tests/test_langgraph_workflow.py -q
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest products/demo/generated_tests -q
.venv/bin/python -m compileall -q pmqa products
git diff --check
git status --short
```

Use an isolated bytecode cache for compileall. New tests remain offline.

## Acceptance Criteria

- no public `UsageSummary` can contain contradictory top-level and grouped
  lifecycle, predecessor, duration, token, or cost evidence;
- every contract entry point enforces the invariant;
- exact bounded integer and Decimal semantics remain deterministic;
- monetary aggregation contains no domain `assert`;
- fixed safe errors and exact resource/control-flow propagation remain intact;
- generated aggregator output and canonical wire format remain unchanged;
- existing Task 5C.4–5C.7, application, Task 4, Task 5, Product Pack,
  import, and packaging regressions remain green;
- only allowed files change.

## Expected Deliverables

- complete cross-level summary reconciliation;
- explicit monetary invariant handling;
- focused adversarial tests;
- one remediation implementation commit;
- one report-only Coder handoff commit;
- clean synchronized branch;
- no PR or merge.

## Required Coder Handoff

Replace `agent-handoff/coder-report.md` with the complete Task 5C.7 Attempt 2
report. Include:

- Task/Attempt, branch, and exact Git-derived starting HEAD;
- remediation implementation commit;
- changed files;
- exact cross-level reconciliation semantics;
- monetary assertion correction;
- focused and full validation results;
- remaining risks and scope confirmation;
- one recommended review depth (`Light`, `Standard`, or `Deep`);
- one-sentence reason;
- 3–6 suggested Reviewer focus areas;
- Human Summary using the mandatory routing and one-sentence Handoff Note.

Do not include the report commit's own SHA. The Independent Reviewer derives
it from Git.
