# Coder Report

Owner: Coder

Task: PMQA Task 5C.3 Architecture Review Remediation — Application Boundary
Isolation

Status: Ready for Architect re-review

This file is the authoritative Coder-to-Architect remediation handoff.

## Branch and Starting HEAD

Branch:

`agent/task-5c-1-canonical-run-contract`

Exact Coder starting HEAD:

`a5875f2ffce352e4a2aa19a796727e3c520f6430`

The starting commit contained the Architect review and remediation handoff. No
earlier Task 5C commit was amended.

## Remediation Commit

`ad26cfd987526ba9efabc0130458d26df4ca8bcb`

Commit message:

`isolate Task 5C.3 application boundaries`

This report is delivered in a separate report-only handoff commit so it can
record the exact remediation SHA.

## Changed Files

Remediation commit:

- `docs/architecture/application-service.md`
- `pmqa/application/__init__.py`
- `pmqa/application/contracts.py`
- `pmqa/application/service.py`
- `tests/test_application_contracts.py`
- `tests/test_application_service.py`

Report-only handoff commit:

- `agent-handoff/coder-report.md`

## F1 — Workflow Validator Isolation

The service retains its authoritative canonical `RunRequest` and
`StructuredResult`, but never passes either object to workflow code.

Before `validate_request()`, the service reconstructs a fresh canonical
`RunRequest` snapshot. Before `validate_result()`, it reconstructs a fresh
canonical `StructuredResult` snapshot. Each validator-owned snapshot is
discarded after the call. Later runner selection, context construction,
dispatch, record assembly, and output use only the untouched service-owned
objects.

Adversarial tests mutate and retain validator arguments, including request,
session, workflow, version, runner, input-schema and result-schema identities,
safe data changed into prohibited/runtime-like keys, and post-validation
retained references. Execution and output remain byte-for-byte equal to the
pre-validation canonical snapshots, and neither injected markers nor
prohibited keys enter the result.

## F2 — Runner Dispatch Isolation

The service constructs and retains one authoritative canonical
`RunnerRequest`. Immediately before dispatch, it reconstructs a second
canonical `RunnerRequest` and passes only that snapshot to
`PMQARunner.execute()`.

The dispatch object is never reused after the runner call. The canonical
response is validated only against the untouched authoritative request.

Adversarial runners now mutate the complete dispatch correlation:

- embedded request, session, workflow/version, runner, and input schema;
- context run, request, session, workflow/version, runner, and start time;
- invocation ID, run ID, runner ID, operation, step, start time, attempt
  number, and retry or fallback predecessor; and
- expected result schema ID/version.

They return a response correlated only to the rewritten dispatch. The service
rejects it with the fixed `RUNNER_BOUNDARY_FAILED` error, calls the runner
exactly once, preserves caller-owned inputs, and exposes no marker, changed
identity, cause, or context.

## F3 — Single-Attempt Application Contract

`APPLICATION_RUN_OPERATION` now has one definition in the neutral application
contracts module and is reused by both contract validation and the service.

`ApplicationRunResult` requires its terminal invocation to have exactly:

```text
operation == APPLICATION_RUN_OPERATION
step_id is None
attempt_number == 1
retry_of_invocation_id is None
fallback_from_invocation_id is None
```

Tests independently reject an arbitrary operation, non-null step, attempt 2,
retry predecessor, fallback predecessor, and combined mutation through direct
construction, `from_dict()`, and `model_copy(update=...)`. Existing canonical
status, identity, result, artifact, error, timestamp, and duration correlation
remains unchanged.

## F4 — Live Property Exception Identity

Live workflow-definition and runner-metadata property access is no longer
wrapped as an expected changed-state failure. If access raises, the exact
exception object propagates unchanged.

A successfully returned malformed or unequal live value still maps to the
fixed, safe `WORKFLOW_DEFINITION_CHANGED` or `RUNNER_METADATA_CHANGED` error.
Registry-construction containment for malformed registrations is unchanged.

Tests prove exact identity propagation for `RuntimeError`, `ValueError`,
`MemoryError`, `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit` from
both live properties, while existing drift and new malformed-value tests
preserve safe mismatch classification and zero runner calls.

## Adversarial Test Evidence

The focused suite now covers:

- immediate and retained mutation of request-validator snapshots;
- mutation of every request selection and input-schema identity;
- prohibited/runtime-like input replacement;
- immediate and retained mutation of result-validator snapshots;
- result schema and prohibited/runtime-like result-data replacement;
- exact output equality after validator mutation;
- complete runner dispatch correlation replacement with retry and fallback
  variants;
- fixed marker-safe runner-boundary rejection without cause or context;
- caller run/request/control identity preservation and exactly one runner call;
- all single-attempt fields through all canonical construction paths;
- malformed returned live definition and metadata values; and
- exact ordinary and resource/control-flow exception propagation from both
  live properties.

## Validation Results

- Focused Task 5C.3 application tests:
  - `.venv/bin/python -m pytest tests/test_application_contracts.py tests/test_application_registry.py tests/test_application_service.py tests/test_application_imports.py`
  - `118 passed`
- Task 5C.1/5C.2, security boundary, and real-wheel packaging regressions:
  - `.venv/bin/python -m pytest tests/test_run_contracts.py tests/test_runner_contracts.py tests/test_mock_runner.py tests/test_boundary_policy.py tests/test_packaging.py`
  - `287 passed`
- Task 4 orchestration regressions:
  - `.venv/bin/python -m pytest tests/test_workflow_runtime.py tests/test_workflow_reducer.py tests/test_supervisor_policy.py tests/test_langgraph_workflow.py`
  - `98 passed, 1 existing LangGraph deprecation warning`
- Full default suite:
  - `.venv/bin/python -m pytest`
  - `1561 passed, 5 skipped, 1 existing LangGraph deprecation warning`
- Generated Playwright regressions:
  - `.venv/bin/python -m pytest products/demo/generated_tests`
  - `2 passed`
- Isolated compile check:
  - `.venv/bin/python -m compileall -q pmqa products`
  - passed with `PYTHONPYCACHEPREFIX` directed to a temporary directory
- `git diff --check`: passed before the remediation commit and will be
  rechecked after this report-only commit.
- Final worktree and remote synchronization:
  - the report-only handoff commit is pushed after this report is written;
  - local, tracking, and GitHub branch HEADs are rechecked equal, and the
    worktree is rechecked clean before the Human Summary.

The default and focused suites remained offline and provider-free. The only
browser execution was the explicitly required existing generated Playwright
regression using locally installed Chromium.

## Remaining Risks and Scope Confirmation

- Runtime controls remain intentionally caller-owned runtime objects; this
  remediation isolates only persisted/canonical request and result state.
- Persistence, repository correlation, retry/fallback creation, timeout
  enforcement, approval execution, and authorization remain future work.
- Real provider and workflow adapters remain future explicit composition.
- Usage, cost, logging, feedback, eval, and reliable workflow outcome records
  remain separate future contracts.
- WorkflowRegistry, RunnerRegistry, and the Application Service public shape
  were not redesigned.
- Registry-construction malformed-object containment remains unchanged.
- WorkflowState, reducer, Supervisor, ToolRegistry, LangGraph, Task 5, Product
  Pack, CLI, packaging behavior, and generated tests were not changed.
- No persistence, discovery, provider SDK, subprocess, browser, Node, network,
  UI, API, retry, fallback, approval execution, Usage/Cost, or Independent
  Reviewer capability was added.
- Task 5C.4, Task 5B, Task 6, and Task 7 were not started.
- No PR was created and nothing was merged.
- No earlier commit was amended.
- No known blocking finding remains after this remediation.

## Recommended Review Depth

Recommendation: Deep

Reason: The remediation changes object ownership across both workflow and
runner trust boundaries and strengthens the canonical terminal envelope.

## Suggested Review Focus

- Reproduce validator `__dict__` and retained-reference mutation against
  request and result snapshots.
- Verify the runner receives a dispatch copy while authoritative response
  validation uses an untouched request.
- Inspect all application-owned operation, step, attempt, and predecessor
  invariants across every construction path.
- Confirm exact exception identity from live properties and safe
  classification only for returned mismatches.
- Recheck fixed error secrecy, exactly-one execution, caller immutability, and
  unchanged imports/packaging.

The Coder recommendation is advisory and does not approve the task.
