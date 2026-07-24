# Coder Report

Owner: Coder

Task: PMQA Task 5C.2 Architecture Review Remediation — Runner Integrity

Status: Ready for Architect re-review

This file is the authoritative Coder-to-Architect remediation handoff.

## Branch

`agent/task-5c-1-canonical-run-contract`

## Starting HEAD

Required remediation starting HEAD:

`17bddd3b75321b206e413082f17f7d242baa43e1`

The Architect handoff commit
`1d9aace3b3d6fec2354554df10252b647af12e45` was already present at execution
time and changed only `agent-handoff/current-task.md` and
`agent-handoff/architect-review.md`. The implementation baseline remained the
required starting commit.

## Remediation Commit SHA

`58d1edb9b765749cb1351e30b3405bc6a6b82247`

Commit message:

`harden Task 5C.2 runner integrity`

The remediation is one focused implementation commit. This report is delivered
in a separate report-only handoff commit so it can record the exact remediation
SHA without amending earlier history.

## Changed Files

Remediation commit:

- `docs/architecture/runner-boundary.md`
- `pmqa/runners/contracts.py`
- `pmqa/runners/mock.py`
- `tests/test_mock_runner.py`
- `tests/test_runner_contracts.py`

Handoff commit:

- `agent-handoff/coder-report.md`

## Correction for Each Architect Finding

### F1 — Clock and duration containment

The complete wall-clock operation now executes inside one containment boundary:
clock invocation, exact `datetime` validation, timezone-awareness evaluation,
`utcoffset()`, and UTC normalization. Monotonic invocation, numeric/finite
validation, float normalization, elapsed calculation, scaling, finite checks,
and integer millisecond conversion are similarly contained.

Expected exceptions are converted to the fixed
`RunnerBoundaryValidationError` outside the active exception handler, leaving
both `__cause__` and `__context__` unset and preventing marker, value, object,
path, or underlying-message disclosure. `MemoryError`, `KeyboardInterrupt`,
`SystemExit`, and `GeneratorExit` propagate unchanged from wall-clock,
timezone-normalization, monotonic, and duration-conversion boundaries. Extreme
finite samples whose scaled duration becomes infinite fail safely. Normal
deterministic clocks and zero duration remain supported.

### F2 — Output-artifact temporal correlation

`validate_runner_response()` now requires every output artifact to satisfy:

```text
invocation.started_at <= artifact.created_at <= invocation.completed_at
```

Artifacts exactly at start or completion are accepted. Artifacts before start
or after completion fail with the fixed safe Runner boundary error. Valid
temporally correlated artifacts remain supported for successful, partially
successful, and failed responses.

### F3 — Typed immutable MockRunner artifact configuration

`MockRunner` now accepts only an exact tuple containing exact `RunArtifact`
instances. Dictionaries, `RunArtifact` subclasses, mutable artifact-like
objects, arbitrary runtime objects, tuple subclasses, and invalid items are
rejected without echoing their values.

Each accepted artifact is serialized and reconstructed through the canonical
`RunArtifact` boundary during construction. The runner therefore retains an
independently validated immutable snapshot rather than the caller's object.
Adversarial caller mutation after construction cannot change subsequent
executions.

### F4 — Pre-execution cancellation artifacts

A cancellation already requested before `execute()` now returns exactly one
canonical `CANCELLED` invocation with the existing safe cancellation error,
`result=None`, and an empty artifact tuple, regardless of configured outputs.
Attempt number and retry/fallback predecessor fields remain unchanged; no new
attempt is created. Executed success, partial-success, and failure outcomes
continue returning valid configured artifacts.

## Adversarial Coverage

Focused tests now cover:

- expected exceptions from `tzinfo.utcoffset()` and from the later UTC
  conversion call;
- fixed safe errors with no cause, context, marker, or underlying message;
- extreme finite monotonic samples causing scaled-duration overflow;
- unchanged propagation of `MemoryError`, `KeyboardInterrupt`, `SystemExit`,
  and `GeneratorExit` from wall callable, timezone operations, monotonic
  callable, and duration conversion;
- zero-duration monotonic evidence;
- output artifacts before start, exactly at start, exactly at completion, and
  after completion;
- valid artifacts on success, partial success, and failure;
- dictionary, mutable artifact-like object, runtime object, and
  `RunArtifact` subclass rejection;
- independently reconstructed artifacts surviving caller-side mutation;
- pre-execution cancellation with configured output artifacts.

## Validation Results

- Focused Runner remediation:
  - `.venv/bin/python -m pytest tests/test_runner_contracts.py tests/test_mock_runner.py tests/test_runner_imports.py`
  - `104 passed`
- Run Contract, security boundary, and real-wheel packaging:
  - `.venv/bin/python -m pytest tests/test_run_contracts.py tests/test_boundary_policy.py tests/test_packaging.py`
  - `185 passed`
- Task 4 orchestration regressions:
  - `.venv/bin/python -m pytest tests/test_workflow_runtime.py tests/test_workflow_reducer.py tests/test_supervisor_policy.py tests/test_langgraph_workflow.py`
  - `98 passed, 1 existing LangGraph deprecation warning`
- Full default suite:
  - `.venv/bin/python -m pytest`
  - `1443 passed, 5 skipped, 1 existing LangGraph deprecation warning`
- Generated Playwright regressions:
  - `.venv/bin/python -m pytest products/demo/generated_tests`
  - `2 passed`
- Isolated compile check:
  - `.venv/bin/python -m compileall -q pmqa products`
  - passed with `PYTHONPYCACHEPREFIX` directed to a temporary directory
- `git diff --check`: passed
- Final worktree and remote synchronization:
  - The report-only handoff commit is pushed after this report is written.
  - Local, tracking, and GitHub branch HEADs are rechecked equal, and the
    worktree is rechecked clean before the Human Summary is sent.

The default and focused suites remained offline and provider-free. The only
browser execution was the explicitly required existing generated Playwright
regression using locally installed Chromium.

## Remaining Risks / Open Items

- Timeout enforcement and in-flight or remote cancellation remain future
  execution-policy work.
- Input artifacts still require a future explicit request-side contract and
  are not represented as output artifacts.
- Runner/workflow selection, persistence, authorization, approval,
  retry/fallback creation, and cross-record predecessor validation remain
  future Application Service or repository responsibilities.
- `MockRunner` remains deterministic validation infrastructure rather than a
  production provider.
- No known blocking finding remains after the reported remediation.

## Scope Confirmation

- Changes are limited to the allowed Runner contracts, MockRunner, focused
  tests, focused Runner documentation, and this Coder handoff.
- The public `PMQARunner`, `RunnerRequest`, and `RunnerResponse` architecture
  was not redesigned or expanded.
- No input-artifact support, timeout enforcement, in-flight cancellation,
  retry, fallback, registry, discovery, persistence, provider, subprocess,
  terminal, browser, network, usage/cost, UI, API, or ADO behavior was added.
- Existing WorkflowState, reducer, Supervisor, ToolRegistry, LangGraph, Task 5,
  and Product Pack semantics were not modified.
- Task 5C.3, Task 5B, Task 6, and Task 7 were not started.
- No PR was created and nothing was merged.
- No earlier commit was amended.

## Recommended Review Depth

Recommendation: Deep

## Review Recommendation Reason

The remediation closes adversarial exception-containment and artifact-provenance
gaps at a public execution boundary, so the corrected invariants warrant
end-to-end reinspection.

## Suggested Review Focus

- Exercise hostile timezone behavior and verify safe errors have neither cause
  nor context while resource/control-flow exceptions remain unchanged.
- Inspect finite-to-infinite duration scaling and zero-duration behavior.
- Verify artifact timestamp boundaries for every supported terminal outcome.
- Confirm exact artifact typing and canonical reconstruction eliminate
  caller-owned mutable configuration.
- Confirm pre-execution cancellation cannot return configured artifacts or
  create retry/fallback state.
- Recheck that the remediation introduces no provider, runtime orchestration,
  registry, persistence, Usage/Cost, or public API expansion.

The Coder recommendation is advisory and does not approve the task.
