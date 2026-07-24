# Current Task

Owner: Architect

Task: PMQA Task 5C.2 Architecture Review Remediation — Runner Integrity

Status: Changes Required

Branch: `agent/task-5c-1-canonical-run-contract`

Starting HEAD: `17bddd3b75321b206e413082f17f7d242baa43e1`

This file is the authoritative task handoff. Chat summaries are informational
only. The complete review evidence is in `agent-handoff/architect-review.md`.

## Task Objective

Close the four blocking Runner integrity findings from the Task 5C.2 Deep
architecture review without expanding scope or redesigning the provider-neutral
Runner API.

## Background

Task 5C.2 implementation commit
`502ae0826fffa14310439a8e010c4a2c0bd6408c` introduced the provider-neutral
Runner boundary and passed the existing test suite. Deep adversarial review
found four uncovered defects:

1. clock validation and duration conversion can expose raw exceptions;
2. output-artifact timestamps are not correlated to invocation time;
3. MockRunner retains untyped mutable artifact configuration;
4. pre-execution cancellation can return configured output artifacts.

Task 5C.2 remains unapproved until these findings are remediated and reviewed.

## Scope

- Harden MockRunner clock sampling, timezone normalization, and duration
  conversion.
- Preserve resource/control-flow exception propagation.
- Correlate every output artifact timestamp with the terminal invocation.
- Enforce exact typed, immutable MockRunner output-artifact configuration.
- Remove configured output artifacts from pre-execution-cancelled mock results.
- Add focused adversarial regression tests.
- Update Runner documentation only if the corrected invariant needs explicit
  documentation.
- Replace `agent-handoff/coder-report.md` with the remediation completion
  report.

## Allowed Changes

- `pmqa/runners/contracts.py`
- `pmqa/runners/mock.py`
- `tests/test_runner_contracts.py`
- `tests/test_mock_runner.py`
- focused Runner documentation when required
- `agent-handoff/coder-report.md`

Do not modify the previous implementation or handoff commits. Add a new
remediation commit.

## Out of Scope

Do not:

- change the overall `PMQARunner`, `RunnerRequest`, or `RunnerResponse`
  architecture;
- add input-artifact support;
- implement timeout enforcement, in-flight cancellation, retry, or fallback;
- add Application Service, Workflow Registry, Runner Registry, discovery, or
  persistence;
- add real provider, subprocess, terminal, browser, Node.js, network, usage,
  cost, pricing, UI, API, or ADO behavior;
- modify WorkflowState, reducer, Supervisor, ToolRegistry, LangGraph, Task 5,
  or Product Pack semantics;
- start Task 5C.3, Task 5B, Task 6, or Task 7;
- create a PR or merge.

## Acceptance Criteria

### Clock and duration containment

- The complete wall-clock operation is contained, including:
  - callable execution;
  - timezone-awareness validation;
  - `utcoffset()` evaluation;
  - UTC conversion.
- Expected clock/normalization failures become only the fixed
  `RunnerBoundaryValidationError`.
- Extreme finite monotonic samples cannot leak raw `OverflowError` or
  `ValueError` during millisecond conversion.
- Errors do not expose marker text, clock values, object representations,
  paths, cause, context, or underlying messages.
- `MemoryError`, `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit`
  propagate unchanged from wall clock, timezone operations, monotonic clock,
  and duration conversion wherever applicable.
- Normal deterministic wall/monotonic behavior and zero duration remain
  unchanged.

### Output-artifact temporal correlation

- `validate_runner_response()` requires every output artifact to satisfy:

  ```text
  invocation.started_at <= artifact.created_at <= invocation.completed_at
  ```

- Artifacts at either exact boundary are accepted.
- Artifacts before start or after completion fail with the fixed safe Runner
  boundary error.
- Valid artifacts remain supported for success, partial success, and failure.

### Typed immutable MockRunner configuration

- `output_artifacts` must be an exact tuple of exact `RunArtifact` objects.
- Dictionaries, `RunArtifact` subclasses, mutable artifact-like objects,
  runtime objects, and invalid items are rejected safely.
- MockRunner retains an independently validated immutable snapshot rather than
  a mutable caller-owned object.
- Repeated execution cannot be changed by later caller mutation.

### Pre-execution cancellation

- A cancellation requested before `execute()` returns one canonical
  `CANCELLED` response with the existing safe cancellation error.
- Its `result` is `None`.
- Its output artifact collection is empty even when the runner was configured
  with valid artifacts.
- The runner does not create a retry or fallback.

### Compatibility

- All existing Runner request/response and MockRunner behavior outside these
  corrections remains unchanged.
- Public imports and wheel contents remain unchanged.
- Task 4, Task 5, Task 5A, and Task 5C.1 regressions remain green.

## Required Adversarial Tests

At minimum add tests for:

- `tzinfo.utcoffset()` raising an expected exception with a secret marker;
- UTC conversion raising an expected exception;
- extreme finite monotonic samples causing scaled-duration overflow;
- `MemoryError`, `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit`
  propagation from the clock/normalization boundary;
- suppressed exception cause/context and marker leakage;
- artifacts before invocation start;
- artifacts exactly at invocation start;
- artifacts exactly at invocation completion;
- artifacts after invocation completion;
- dictionary and `RunArtifact` subclass configuration rejection;
- caller mutation after MockRunner construction;
- pre-execution cancellation with configured artifacts.

Use fixtures only. Do not invoke a paid model, browser, network, Node.js, or
external CLI in the new tests.

## Validation Commands

Run and report:

```bash
.venv/bin/python -m pytest tests/test_runner_contracts.py tests/test_mock_runner.py tests/test_runner_imports.py
.venv/bin/python -m pytest tests/test_run_contracts.py tests/test_boundary_policy.py tests/test_packaging.py
.venv/bin/python -m pytest tests/test_workflow_runtime.py tests/test_workflow_reducer.py tests/test_supervisor_policy.py tests/test_langgraph_workflow.py
.venv/bin/python -m pytest
.venv/bin/python -m pytest products/demo/generated_tests
.venv/bin/python -m compileall -q pmqa products
git diff --check
git status --short
```

## Expected Deliverables

- One new focused remediation commit; do not amend earlier commits.
- Corrected Runner integrity behavior and adversarial tests.
- Updated `agent-handoff/coder-report.md`.
- Pushed branch with local, tracking, and GitHub HEADs equal.
- Clean worktree.
- No PR and no merge.

## Required Coder Handoff

Replace `agent-handoff/coder-report.md` with the complete remediation report.
Include:

- branch and exact starting HEAD;
- remediation commit SHA;
- changed files;
- correction for each Architect finding;
- adversarial and full validation results;
- remaining risks;
- scope confirmation;
- exactly one recommended review depth: `Light`, `Standard`, or `Deep`;
- one-sentence reason;
- 3–6 suggested review focus areas.

The Coder's review-depth recommendation is advisory. The Architect retains the
final review-depth decision.
