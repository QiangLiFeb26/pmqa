# Current Task

Owner: Architect

Task: PMQA Task 5C.7 — Retry/Fallback Aggregate Exclusivity

Task ID: `PMQA-5C.7`

Attempt: `3`

Status: Changes Required

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed Attempt 2 Reviewer HEAD:
`d6b1acd1572bf55de8cb85ed303059b832daa55d`

Coder starting HEAD: derive and record the latest pushed branch commit that
contains this remediation publication before changing implementation files.

Repository Markdown and Git history are authoritative. Chat summaries are
informational only.

## Task Objective

Enforce the final Task 5C.7 predecessor-count invariant:

```text
retry_invocation_count + fallback_invocation_count
    <= invocation_count
```

The invariant must apply to both top-level `UsageSummary` and every
`UsageProviderModelSummary`.

This is a minimal contract correction. Do not change fields, aggregation
output, cross-level reconciliation, or Task 5C.7 architecture.

## Background

Every valid `AIInvocationRecord` permits:

- no predecessor for attempt one; or
- exactly one retry predecessor for a later attempt; or
- exactly one fallback predecessor for a later attempt.

The two predecessor categories are mutually exclusive per invocation.

Task 5C.7 currently validates each aggregate count independently:

```text
retry <= invocation_count
fallback <= invocation_count
```

It therefore accepts this impossible canonical payload:

```text
invocation_count=1
retry_invocation_count=1
fallback_invocation_count=1
```

When the same contradiction is present at top-level and in the sole
provider/model group, cross-level roll-up validation also succeeds.

The complete evidence is in `agent-handoff/architect-review.md`.

## Required Correction

Update the existing shared metrics validator so:

- `retry_invocation_count + fallback_invocation_count` cannot exceed
  `invocation_count`;
- the addition is bounded and cannot wrap or depend on unchecked arithmetic;
- the invariant applies to both `UsageSummary` and
  `UsageProviderModelSummary`;
- direct construction and `model_copy(update=...)` fail through normal
  Pydantic contract validation;
- `UsageSummary.from_dict()` contradictions expose only fixed
  `UsageSummaryValidationError`;
- no identifier, count, provider/model, marker, underlying message, cause, or
  context leaks;
- valid generated summaries remain byte-identical.

Do not require:

```text
retry + fallback == invocation_count
```

Attempt-one invocations legitimately contribute to neither category.

## Required Valid Cases

Retain and test:

- empty summary: invocation `0`, retry `0`, fallback `0`;
- one first attempt: invocation `1`, retry `0`, fallback `0`;
- one retry: invocation `1`, retry `1`, fallback `0`;
- one fallback: invocation `1`, retry `0`, fallback `1`;
- two invocations, one retry and one fallback:
  invocation `2`, retry `1`, fallback `1`;
- mixed first attempts and later attempts where the combined predecessor
  count is less than invocation count;
- multiple provider/model groups whose combined top-level counts remain
  valid.

## Required Rejection Cases

Reject:

- top-level invocation `1`, retry `1`, fallback `1`;
- provider/model group invocation `1`, retry `1`, fallback `1`;
- a canonical wire where top-level and group both contain the same impossible
  overlap and therefore still reconcile cross-level;
- any larger values where combined retry/fallback exceeds invocation count;
- bypass attempts through direct construction, `from_dict()`, or
  `model_copy(update=...)`.

Start from a real `DefaultUsageAggregator` result and mutate only the intended
predecessor counts where practical, so tests reach this invariant rather than
an unrelated nested failure.

## Preserve Existing Behavior

Do not change:

- public fields, enums, schema versions, or error codes;
- record-count, integer, Decimal, or canonical-tree bounds;
- provider/model roll-up reconciliation;
- status, duration, token, or cost semantics;
- empty/zero/partial/unavailable behavior;
- cost-bucket or provider/model ordering;
- canonical serialization;
- `DefaultUsageAggregator` output for valid records;
- repository, collector, pricing, Run, Runner, Application Service,
  WorkflowState, LangGraph, or Product Pack behavior;
- import or packaging isolation.

## Allowed Changes

- `pmqa/usage/summary.py`;
- `tests/test_usage_summary.py`;
- `agent-handoff/coder-report.md`.

No documentation, import, or packaging change is expected.

Do not modify:

- `agent-handoff/README.md`;
- `agent-handoff/current-task.md`;
- `agent-handoff/reviewer-report.md`;
- `agent-handoff/architect-review.md`;
- any other production or test module.

Use one minimal remediation implementation commit and one report-only Coder
handoff commit. Do not amend previous attempts.

## Out of Scope

Do not add:

- any other Task 5C feature;
- new summary fields or aggregate categories;
- repository-backed selection or pagination;
- CLI or Web UI;
- conversation, workflow, capability, artifact, approval, ADO, or Copilot
  integration;
- pricing calculation or provider parsing;
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

- no canonical top-level or provider/model summary can count one invocation
  in both retry and fallback categories;
- valid combinations, including one retry plus one fallback across two
  invocations, remain accepted;
- all public contract entry points enforce the invariant;
- fixed safe errors and exact resource/control-flow behavior remain intact;
- valid aggregator output and canonical serialization remain unchanged;
- existing Task 5C.4–5C.7 and full regressions remain green;
- only allowed files change.

## Expected Deliverables

- one shared predecessor-exclusivity invariant;
- focused valid and adversarial tests;
- one minimal implementation commit;
- one report-only Coder handoff commit;
- clean synchronized branch;
- no PR or merge.

## Required Coder Handoff

Replace `agent-handoff/coder-report.md` with the complete Task 5C.7 Attempt 3
report. Include:

- Task/Attempt, branch, and exact Git-derived starting HEAD;
- remediation implementation commit;
- changed files;
- exact predecessor-count invariant and entry-point behavior;
- focused and full validation results;
- remaining risks and scope confirmation;
- one recommended review depth (`Light`, `Standard`, or `Deep`);
- one-sentence reason;
- 3–6 suggested Reviewer focus areas;
- Human Summary using the mandatory routing and one-sentence Handoff Note.

Do not include the report commit's own SHA. The Independent Reviewer derives
it from Git.
