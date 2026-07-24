# Coder Report

Owner: Coder

Task: PMQA Task 5C.3 — Explicit Application Registries and Single-Attempt Run
Service

Status: Ready for Architect review

This file is the authoritative Coder-to-Architect handoff.

## Branch and Starting HEAD

Branch:

`agent/task-5c-1-canonical-run-contract`

Exact Coder starting HEAD:

`71fbea740e46c0914564e651e70da9afac67019b`

The starting commit approved Task 5C.2 and supplied the Task 5C.3 handoff. No
earlier Task 5C commit was amended.

## Implementation Commit

`41a84d271df00980ffaf84d2df67a3515d9e961c`

Commit message:

`add Task 5C.3 application service`

This report is delivered in a separate report-only handoff commit so it can
record the exact implementation SHA.

## Changed Files

Implementation commit:

- `README.md`
- `docs/Roadmap.md`
- `docs/architecture.md`
- `docs/architecture/application-service.md`
- `docs/architecture/run-contract.md`
- `docs/architecture/runner-boundary.md`
- `pmqa/application/__init__.py`
- `pmqa/application/contracts.py`
- `pmqa/application/registry.py`
- `pmqa/application/service.py`
- `tests/test_application_contracts.py`
- `tests/test_application_imports.py`
- `tests/test_application_registry.py`
- `tests/test_application_service.py`
- `tests/test_packaging.py`

Report-only handoff commit:

- `agent-handoff/coder-report.md`

## Public Application APIs

`pmqa.application` exports:

- `ApplicationFailureCode`;
- `PMQAApplicationError`;
- `WorkflowAdapterValidationError`;
- `ApplicationRunResult`;
- `PMQAWorkflowAdapter`;
- `WorkflowRegistry`;
- `RunnerRegistry`;
- `PMQAApplicationService`;
- `APPLICATION_CONTRACT_SCHEMA_VERSION`;
- `APPLICATION_RUN_OPERATION`; and
- `MAX_APPLICATION_REGISTRY_ITEMS`.

The package remains an explicit opt-in import and is not re-exported from
top-level `pmqa`.

`ApplicationRunResult` is a frozen canonical envelope containing the canonical
`RunRequest`, terminal `RunRecord`, and exact canonical `RunnerResponse`. Its
single terminal invocation is exposed through the read-only
`runner_invocation` property. Construction, `from_dict()`, and
`model_copy(update=...)` revalidate complete request/run/invocation/status,
timestamp, duration, result, artifact, and error correlations.

## Registry Identity and Immutability

`WorkflowRegistry` accepts only an exact bounded tuple of adapters and indexes
exact `(workflow_id, workflow_version)` identities. `RunnerRegistry` accepts
only an exact bounded tuple of runner instances and indexes exact `runner_id`
identities. Duplicate or malformed entries fail with fixed safe application
errors.

Both registries canonically reconstruct definition or metadata snapshots at
construction. Public listing and resolution return new canonical snapshots, so
caller mutation of original inputs or returned Pydantic internals cannot alter
registry-owned identity. The selected runtime adapter or runner remains the
explicit caller-supplied implementation.

There is no mutable registration API, global registry, entry-point discovery,
package scan, filesystem lookup, environment lookup, import-path loading, or
dynamic import. Live workflow-definition and runner-metadata drift is checked
against the retained snapshot and fails before the affected validator or
runner call.

## Pre-Execution Validation Order

`PMQAApplicationService.execute()` applies this stable order:

1. reconstruct and validate the exact `RunRequest`;
2. resolve the exact workflow ID and version;
3. confirm request input schema ID/version;
4. confirm the adapter's live definition equals its registered snapshot;
5. invoke the workflow-specific request validator;
6. resolve the exact runner ID;
7. confirm every required workflow capability;
8. confirm live runner metadata equals its registered snapshot;
9. reject approval modes other than `ApprovalMode.NONE`;
10. validate caller-supplied run and invocation IDs and runtime control;
11. sample and validate the application clock exactly once; and
12. construct the canonical context, pending first invocation, and
    `RunnerRequest`.

All pre-execution failures produce zero runner calls. The one sampled
timezone-aware UTC application start is shared by context, pending invocation,
and final run start, and cannot precede `RunRequest.requested_at`.

## Execution and Result Lifecycle

The service creates attempt number 1 only, with operation
`application.execute-workflow` and no retry or fallback predecessor. An
omitted control creates one local `RunnerControl`; a supplied control remains
caller-owned and runtime-only.

The selected runner is called at most once. Its response is independently
reconstructed and passed through authoritative `validate_runner_response()`.
A present result must match the selected workflow schema and is passed to the
workflow result validator exactly once. Failed and cancelled terminal
responses are normal execution outcomes and invoke no result validator.

The terminal `RunRecord` maps the exact runner status, result, artifacts,
errors, timestamps, and duration. Creation time is the request timestamp,
update time is invocation completion, `current_step_id` is absent, and
`outcome_metrics` remains `None` rather than being fabricated.

No persistence, retry, fallback, timeout enforcement, approval execution, or
provider operation occurs.

## Safe Failure Behavior

Expected application failures use a bounded enum and fixed messages that do
not expose requests, IDs, registry contents, payloads, paths, prompts, provider
data, runtime objects, injected markers, or underlying exception details.
Expected exception chaining is suppressed.

Workflow adapters signal expected validation rejection only with
`WorkflowAdapterValidationError`. Runner-owned
`RunnerBoundaryValidationError` becomes the fixed
`RUNNER_BOUNDARY_FAILED` application error. Unexpected programming exceptions
are not relabeled. `MemoryError`, `KeyboardInterrupt`, `SystemExit`, and
`GeneratorExit` propagate unchanged across registry, workflow, clock, and
runner boundaries.

Application imports remain side-effect-free and do not load products,
external Product Packs, Playwright, LangGraph, existing orchestration/runtime,
reasoning providers, storage, subprocesses, or UI packages.

## Validation Results

- Focused Task 5C.3 application tests:
  - `.venv/bin/python -m pytest tests/test_application_contracts.py tests/test_application_registry.py tests/test_application_service.py tests/test_application_imports.py`
  - `84 passed`
- Task 5C.1/5C.2, security boundary, and real-wheel packaging regressions:
  - `.venv/bin/python -m pytest tests/test_run_contracts.py tests/test_runner_contracts.py tests/test_mock_runner.py tests/test_boundary_policy.py tests/test_packaging.py`
  - `287 passed`
- Task 4 orchestration regressions:
  - `.venv/bin/python -m pytest tests/test_workflow_runtime.py tests/test_workflow_reducer.py tests/test_supervisor_policy.py tests/test_langgraph_workflow.py`
  - `98 passed, 1 existing LangGraph deprecation warning`
- Full default suite:
  - `.venv/bin/python -m pytest`
  - `1527 passed, 5 skipped, 1 existing LangGraph deprecation warning`
- Generated Playwright regressions:
  - `.venv/bin/python -m pytest products/demo/generated_tests`
  - `2 passed`
- Isolated compile check:
  - `.venv/bin/python -m compileall -q pmqa products`
  - passed with `PYTHONPYCACHEPREFIX` directed to a temporary directory
- Markdown relative-link validation:
  - `11 Markdown files validated`
- `git diff --check`: passed before the implementation commit and will be
  rechecked after this report-only commit.
- Final worktree and remote synchronization:
  - the report-only handoff commit is pushed after this report is written;
  - local, tracking, and GitHub branch HEADs are rechecked equal, and the
    worktree is rechecked clean before the Human Summary.

The default and focused suites remained offline and provider-free. The only
browser execution was the explicitly required existing generated Playwright
regression using locally installed Chromium.

## Remaining Risks and Scope Confirmation

- Persistence and repository-level cross-run validation remain future work.
- Retry/fallback creation, timeout enforcement, approval execution, and
  authorization remain future application-policy work.
- Real provider and workflow adapters remain future explicit composition.
- Usage, cost, logs, feedback, evals, and reliable workflow-owned outcome
  metrics remain separate future records.
- `MockRunner` remains deterministic boundary infrastructure, not a production
  provider.
- Task 5C remains in progress and unmerged.
- Task 5B, Task 6, and Task 7 were not started.
- WorkflowState, reducer, Supervisor, ToolRegistry, LangGraph, Task 5, Product
  Pack, CLI, and generated-test behavior were not changed.
- No persistence, discovery, provider SDK, subprocess, browser, Node, network,
  UI, API, retry, fallback, approval execution, usage, or cost capability was
  added.
- No PR was created and nothing was merged.
- No earlier commit was amended.
- No known blocking finding remains in the implementation.

## Recommended Review Depth

Recommendation: Deep

Reason: Task 5C.3 introduces the first public composition boundary that
correlates workflow policy, runner execution, and canonical terminal records.

## Suggested Review Focus

- Verify registry snapshots cannot be changed through caller-owned or returned
  model objects and that no discovery surface exists.
- Check the documented pre-execution order and zero-runner-call guarantees.
- Reinspect expected versus unexpected exception classification across
  workflow, runner, and clock boundaries.
- Verify exactly-one runner execution and exact canonical response/result
  correlation for every terminal outcome.
- Confirm application imports and wheel contents preserve product, provider,
  browser, orchestration, and runtime isolation.
- Confirm no persistence, retry/fallback, approval execution, Usage/Cost, or
  existing workflow semantics entered this checkpoint.

The Coder recommendation is advisory and does not approve the task.
