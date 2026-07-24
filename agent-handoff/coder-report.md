# Coder Report

Owner: Coder

Task: PMQA Task 5C.2 — Provider-Neutral Runner Boundary and Deterministic Mock Runner

Status: Ready for Architect review

This file is the authoritative Coder-to-Architect handoff for Task 5C.2.

## Branch

`agent/task-5c-1-canonical-run-contract`

## Starting HEAD

`a340dfc661d77d53af5f7d8f0b7046a9daf14a71`

## New Commit SHA

Task 5C.2 implementation:

`502ae0826fffa14310439a8e010c4a2c0bd6408c`

The later `3048612` and `a0e4150` commits add and normalize the file-driven
handoff files; they do not change the reviewed Task 5C.2 implementation.

## Changed Files

- `README.md`
- `docs/Roadmap.md`
- `docs/architecture.md`
- `docs/architecture/run-contract.md`
- `docs/architecture/runner-boundary.md`
- `pmqa/runners/__init__.py`
- `pmqa/runners/base.py`
- `pmqa/runners/contracts.py`
- `pmqa/runners/mock.py`
- `tests/test_mock_runner.py`
- `tests/test_packaging.py`
- `tests/test_runner_contracts.py`
- `tests/test_runner_imports.py`

This Coder handoff additionally updates only
`agent-handoff/coder-report.md`.

## Summary of Changes

Task 5C.2 adds a synchronous provider-neutral `PMQARunner` protocol with stable
`RunnerMetadata`, canonical `RunnerRequest` and `RunnerResponse` contracts, an
authoritative `validate_runner_response()` correlation boundary, runtime-only
`CancellationToken`/`RunnerControl`, and a deterministic in-process
`MockRunner`.

`RunnerRequest` composes the existing Task 5C.1 `RunRequest`,
`PMQARunContext`, and pending `RunnerInvocationRecord` instead of duplicating
their fields. It validates request, session, workflow, runner, reference,
invocation, attempt, predecessor, and timestamp correlations. `RunnerResponse`
accepts only one terminal invocation and enforces the required success,
partial-success, failure, and cancellation result/error combinations plus
unique output artifact identities. The authoritative validator then correlates
the response invocation and result schema back to the exact request.

Cancellation is explicit, idempotent, thread-safe for ordinary concurrent
access, scoped to caller-owned runtime control, and excluded from all
serialization contracts. `MockRunner` supports deterministic success, partial
success, failure, and pre-execution cancellation. It samples an injected wall
clock once and an injected monotonic clock twice, preserves the supplied
attempt/predecessor data, produces one terminal invocation, and validates its
own response before returning.

No provider SDK, subprocess, browser, network, environment/config read,
prompt/response storage, usage/cost fabrication, retry/fallback orchestration,
registry, or Application Service was introduced.

## Validation Results

- Focused tests:
  - `.venv/bin/python -m pytest tests/test_runner_contracts.py tests/test_mock_runner.py tests/test_runner_imports.py`
  - `63 passed`
- Relevant Run Contract/security/packaging regressions:
  - `.venv/bin/python -m pytest tests/test_run_contracts.py tests/test_boundary_policy.py tests/test_packaging.py`
  - `185 passed`
- Task 4 orchestration regressions:
  - `.venv/bin/python -m pytest tests/test_workflow_runtime.py tests/test_workflow_reducer.py tests/test_supervisor_policy.py tests/test_langgraph_workflow.py`
  - `98 passed, 1 existing LangGraph deprecation warning`
- Full default suite:
  - `.venv/bin/python -m pytest`
  - `1402 passed, 5 skipped, 1 existing LangGraph deprecation warning`
- Packaging/import isolation:
  - Real-wheel packaging tests: `3 passed` within the 185-test regression run.
  - Runner import-isolation tests: `2 passed` within the 63-test focused run.
  - The built wheel contains all four `pmqa.runners` modules and excludes
    tests, caches, temporary output, credentials, and generated artifacts.
  - Runner imports do not load product packs, providers, Playwright, LangGraph,
    orchestration, reasoning, trace storage, SQLite, subprocess, or UI modules;
    they perform no registration, file/config/environment/distribution access,
    process launch, or `sys.path` mutation.
- Generated Playwright regressions:
  - `.venv/bin/python -m pytest products/demo/generated_tests`
  - `2 passed`
- Compile/import checks:
  - Isolated `.venv/bin/python -m compileall -q pmqa products`: passed.
  - Import isolation is also covered by the focused runner tests above.
- Markdown relative-link validation:
  - `20 checked, 0 missing`.
- `git diff --check`: passed.
- Final worktree and remote synchronization:
  - The implementation and handoff baseline were clean and synchronized at
    `a0e41503cd620c43981f3ec814a760e4d3cbcc3f` before this report update.
  - This report is the only handoff change; its commit is pushed to the same
    branch and local, tracking, and GitHub branch HEADs are rechecked equal
    before the Human Summary is sent.

All validation was offline and provider-free except the explicitly required
existing generated Playwright regression, which used the locally installed
Chromium browser.

## Remaining Risks / Open Items

- `MockRunner` is validation infrastructure, not a production AI runner.
- Timeout is a bounded request contract value; timeout enforcement and remote
  cancellation remain future execution-policy work.
- Runner/workflow selection, persistence, authorization, approval, retry and
  fallback creation, and cross-record predecessor existence/cycle validation
  remain future Application Service or repository responsibilities.
- Task 5C.2 deliberately provides only a synchronous boundary.
- No known acceptance-criteria defect remains after the reported validation.

## Scope Confirmation

- Changes remain within the allowed Runner package, focused Runner/Run
  Contract/import/packaging tests, documentation, and this Coder handoff.
- Existing `WorkflowState`, reducer, Supervisor, ToolRegistry, LangGraph,
  Task 5, and Product Pack execution semantics were not modified.
- No Application Service, Workflow Registry, Runner Registry, automatic
  discovery, real provider adapter, subprocess/terminal runner, persistence
  repository, Usage/Cost model, UI/API/event system, or approval workflow was
  added.
- Task 5C.3, Task 5B, Task 6, and Task 7 were not started.
- No PR was created and nothing was merged.

## Recommended Review Depth

Recommendation: Deep

## Review Recommendation Reason

Task 5C.2 introduces a new public execution boundary whose canonical lifecycle,
cross-contract correlation, cancellation, clock, and import-isolation
invariants warrant end-to-end architecture inspection.

## Suggested Review Focus

- Confirm `RunnerRequest` composes Task 5C.1 contracts without duplicating or
  weakening their canonical/security policies.
- Inspect every `RunnerResponse` status/result/error combination and the
  authoritative request/response correlation fields.
- Verify attempt and retry/fallback predecessor data are preserved rather than
  orchestrated by the runner.
- Review wall-clock/monotonic sampling, invalid-clock containment, and
  pre-execution cancellation semantics.
- Confirm cancellation/control objects remain runtime-only and no global
  mutable state or serialization path exists.
- Confirm import isolation, real-wheel contents, and the absence of provider,
  subprocess, browser, usage/cost, registry, or Application Service coupling.

The Coder recommendation is advisory and does not approve the task.
