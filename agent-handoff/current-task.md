# Current Task

Owner: Architect

Task: PMQA Task 5C.3 Architecture Review Remediation — Application Boundary Isolation

Status: Changes Required

Branch: `agent/task-5c-1-canonical-run-contract`

Implementation baseline: `a839154619485b8b19e14bc1ad34cd9b3e97d70b`

Coder starting HEAD: use the latest pushed branch commit containing this
handoff and record its exact SHA before modifying implementation files.

This file is the authoritative task handoff. Chat summaries are informational
only. Full finding evidence is recorded in
`agent-handoff/architect-review.md`.

## Task Objective

Close four blocking Task 5C.3 trust-boundary findings without expanding the
public Application Service scope:

1. isolate service-owned request/result contracts from workflow validators;
2. isolate the authoritative RunnerRequest from the runner dispatch copy;
3. enforce the single-attempt invariant in `ApplicationRunResult`;
4. preserve unexpected live definition/metadata exceptions.

## Background

Task 5C.3 introduced the explicit Workflow Registry, Runner Registry, and
single-attempt Application Service. Existing tests pass, but runtime adapters
and runners currently receive the same Python objects later trusted by the
service.

Pydantic `frozen` prevents ordinary assignment but is not a security boundary
against `__dict__` mutation. The Application Service must use independent
canonical snapshots whenever it crosses a runtime plugin boundary.

## Scope

- Harden workflow request-validator isolation.
- Harden workflow result-validator isolation.
- Harden RunnerRequest dispatch/expected-request isolation.
- Enforce first-attempt application invariants in `ApplicationRunResult`.
- Correct unexpected live definition/metadata exception classification.
- Add focused adversarial regressions.
- Update focused application documentation only if the corrected trust
  boundary needs clarification.
- Replace `agent-handoff/coder-report.md` with the remediation report.

## Allowed Changes

- `pmqa/application/contracts.py`
- `pmqa/application/service.py`
- minimal neutral application constant placement when needed
- `pmqa/application/__init__.py` only if export placement changes
- `tests/test_application_contracts.py`
- `tests/test_application_service.py`
- focused application architecture documentation
- `agent-handoff/coder-report.md`

Do not amend earlier commits. Add one focused implementation commit and one
report-only handoff commit.

## Required Corrections

### 1. Workflow validator isolation

- Keep one authoritative canonical `RunRequest` owned by the service.
- Pass a separately reconstructed canonical request to
  `validate_request()`.
- Do not use the validator-owned object for later workflow/runner selection,
  context construction, dispatch, records, or output.
- Keep the authoritative canonical RunnerResponse/result owned by the service.
- Pass a separately reconstructed canonical `StructuredResult` to
  `validate_result()`.
- Do not use the validator-owned result for RunRecord or output.
- A validator retaining and later mutating its argument must not affect any
  service-owned state.

Add adversarial validators that mutate:

- request ID, session ID, workflow identity/version, runner ID;
- input schema identity/version;
- safe inputs into prohibited/runtime-like fields;
- result schema identity/version;
- result data into prohibited fields;
- retained request/result references after validation.

The output must remain equal to the pre-validation authoritative snapshots.

### 2. Runner dispatch isolation

- Construct one authoritative canonical `RunnerRequest`.
- Construct a separate canonical dispatch snapshot for
  `PMQARunner.execute()`.
- Validate the response against only the untouched authoritative request.
- Do not reuse the runner-owned dispatch object after the call.

Add an adversarial runner that mutates:

- context run/request/session/workflow/runner correlation;
- invocation ID, run ID, runner ID, operation, step, start time;
- attempt number and retry/fallback predecessors;
- embedded RunRequest;
- expected result schema ID/version.

A response correlated only to the mutated dispatch must fail with
`RUNNER_BOUNDARY_FAILED`. The failure must expose no marker, cause, context,
or mutated value. The caller-requested run and invocation identities must
never be replaced.

### 3. ApplicationRunResult single-attempt invariant

The canonical contract must require:

```text
operation == APPLICATION_RUN_OPERATION
step_id is None
attempt_number == 1
retry_of_invocation_id is None
fallback_from_invocation_id is None
```

Keep `APPLICATION_RUN_OPERATION` defined once and reused by service and
contract validation.

Enforce the invariant during:

- direct construction;
- `from_dict()`;
- `model_copy(update=...)`.

Add independent tests for arbitrary operation, non-null step, attempt 2,
retry predecessor, fallback predecessor, and combined changes.

### 4. Unexpected live property exceptions

- Preserve the existing safe changed failure when a live definition or
  metadata value is returned but is malformed or differs from its registered
  snapshot.
- If accessing the live property raises an exception, propagate the exact
  exception object unchanged.
- Preserve `MemoryError`, `KeyboardInterrupt`, `SystemExit`, and
  `GeneratorExit` unchanged.
- Do not change registry-construction handling for malformed objects.

Add tests proving exact exception identity for:

- `RuntimeError`;
- `ValueError`;
- `MemoryError`;
- `KeyboardInterrupt`;
- `SystemExit`;
- `GeneratorExit`.

## Security and Canonical Requirements

- Do not duplicate prohibited-key policy.
- Use existing `to_dict()` / `from_dict()` canonical reconstruction.
- Do not retain mutable caller- or plugin-owned containers.
- Fixed expected application errors must remain bounded and marker-safe.
- Unexpected programming exceptions must not be silently relabeled.
- Do not add prompt, provider, usage, cost, environment, path, browser,
  subprocess, or runtime metadata to canonical contracts.

## Out of Scope

Do not:

- redesign WorkflowRegistry, RunnerRegistry, or PMQAApplicationService;
- add persistence or repositories;
- add retry, fallback, timeout enforcement, or approval execution;
- add real workflow/provider/Product Pack adapters;
- add subprocess, browser, Node.js, network, CLI, UI, or API behavior;
- add Usage/Cost, pricing, logging, feedback, or eval records;
- modify WorkflowState, reducer, Supervisor, ToolRegistry, LangGraph, Task 5,
  or Product Pack behavior;
- implement the Independent Reviewer workflow inside this remediation;
- start PMQA Task 5C.4, Task 5B, Task 6, or Task 7;
- create a PR or merge.

## Required Tests

At minimum cover:

- request-validator mutation cannot change execution or output;
- result-validator mutation cannot change RunRecord or output;
- retained validator references cannot mutate completed results;
- runner dispatch mutation cannot change expected correlation;
- all RunnerRequest correlation fields are protected;
- single-attempt contract invariants at all construction paths;
- live definition/metadata unexpected exception identity;
- existing safe mismatch classifications;
- exactly one runner call remains true;
- caller-owned request/control remain unchanged;
- import isolation and packaging remain unchanged.

New tests must be offline and must not invoke a browser, network, Node.js,
external CLI, or paid model.

## Validation Commands

Run and report:

```bash
.venv/bin/python -m pytest tests/test_application_contracts.py tests/test_application_registry.py tests/test_application_service.py tests/test_application_imports.py
.venv/bin/python -m pytest tests/test_run_contracts.py tests/test_runner_contracts.py tests/test_mock_runner.py tests/test_boundary_policy.py tests/test_packaging.py
.venv/bin/python -m pytest tests/test_workflow_runtime.py tests/test_workflow_reducer.py tests/test_supervisor_policy.py tests/test_langgraph_workflow.py
.venv/bin/python -m pytest
.venv/bin/python -m pytest products/demo/generated_tests
.venv/bin/python -m compileall -q pmqa products
git diff --check
git status --short
```

## Expected Deliverables

- One focused remediation implementation commit.
- One report-only Coder handoff commit.
- Corrected isolation and canonical invariants.
- New adversarial tests.
- Updated `agent-handoff/coder-report.md`.
- Clean worktree with local and remote branch HEADs synchronized.
- No PR and no merge.

## Required Coder Handoff

Replace `agent-handoff/coder-report.md` with the complete remediation report.
Include:

- branch and exact Coder starting HEAD;
- remediation commit SHA;
- changed files;
- correction for F1–F4;
- adversarial test evidence;
- full validation results;
- remaining risks and scope confirmation;
- exactly one recommended review depth: `Light`, `Standard`, or `Deep`;
- one-sentence reason;
- 3–6 suggested review focus areas.

The Coder recommendation is advisory. The Architect independently selects the
actual review depth.

## Planned Workflow Rollout After Approval

After Task 5C.3 is approved:

1. implement the provider-neutral Independent Reviewer file protocol using the
   existing Architect → Coder → Architect workflow;
2. use PMQA Task 5C.4 as the first Coder → Reviewer → Architect pilot;
3. perform one lightweight workflow retrospective and stabilization task.
