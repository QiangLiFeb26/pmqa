# Current Task

Owner: Architect

Task: PMQA Task 5C.2 — Provider-Neutral Runner Boundary and Deterministic Mock Runner

Status: Coder report required

Branch: `agent/task-5c-1-canonical-run-contract`

Starting HEAD: `a340dfc661d77d53af5f7d8f0b7046a9daf14a71`

This file is the authoritative task handoff. Chat summaries are informational only.

## Task Objective

Add a small, provider-neutral Runner boundary around the canonical Task 5C.1 Run
Contract and validate it with a deterministic in-process `MockRunner`.

The boundary must support future Copilot, Codex, OpenAI, Azure OpenAI, and private
company runners without depending on any provider SDK today.

## Background

Task 5C.1 established the canonical PMQA Run Contract and passed architecture
review at commit `a340dfc661d77d53af5f7d8f0b7046a9daf14a71`.

Implementation commit `502ae0826fffa14310439a8e010c4a2c0bd6408c` has been detected
on the task branch. The implementation is not ready for Architect review until the
Coder completes `agent-handoff/coder-report.md`.

Task 5C.2 is intentionally limited to the Runner boundary. Application Service,
Workflow Registry, provider adapters, and usage/cost tracking remain later work.

## Scope

- Define a provider-neutral `PMQARunner` interface.
- Define strict, frozen, canonical Runner metadata, request, and response contracts.
- Compose the existing `RunRequest`, `PMQARunContext`,
  `RunnerInvocationRecord`, `StructuredResult`, `RunArtifact`, and `RunError`
  contracts rather than duplicating them.
- Enforce complete request/response identity, lifecycle, timestamp, attempt,
  predecessor, and result-schema correlation.
- Add a minimal runtime-only cancellation token/control boundary.
- Add a deterministic in-process `MockRunner`.
- Preserve import isolation and wheel packaging.
- Add focused contract, mock-runner, isolation, and packaging tests.
- Update the relevant architecture and roadmap documentation.

## Allowed Changes

Changes may be made to:

- `pmqa/runners/`
- focused additions to shared Run Contract code only when required by a proven
  Runner-boundary invariant;
- Runner, Run Contract, import-isolation, and packaging tests;
- `README.md`;
- `docs/Roadmap.md`;
- `docs/architecture.md`;
- focused Run Contract or Runner architecture documentation;
- `agent-handoff/coder-report.md`.

## Out of Scope

Do not implement or modify:

- Application Service;
- Workflow Registry or Runner Registry;
- automatic discovery or registration;
- Copilot, Codex, OpenAI, Azure OpenAI, ADO, or other real provider adapters;
- AI usage, cost tracking, pricing, or optimization;
- subprocess, terminal, browser, Node.js, or network execution;
- prompt or response persistence;
- UI, REST API, dashboard, event streaming, or approval workflow;
- WorkflowState, reducer, Supervisor, ToolRegistry, LangGraph, Task 5, or
  Product Pack execution semantics;
- Task 5B, Task 6, or Task 7.

Do not create a PR or merge this task.

## Acceptance Criteria

### Provider-neutral boundary

- `PMQARunner` exposes stable metadata and one execution method.
- The public boundary contains no provider SDK objects, subprocess handles,
  browser objects, environment mappings, credentials, raw prompts, raw
  responses, or terminal output.
- Importing Runner modules performs no registration, discovery, file access,
  environment access, process launch, or `sys.path` mutation.

### Contracts

- Runner wire contracts are strict, frozen, exact-field, deeply immutable, and
  canonical plain JSON.
- Every successfully constructed wire contract satisfies:

  ```python
  wire = contract.to_dict()
  restored = type(contract).from_dict(wire)
  assert restored == contract
  ```

- Construction, `from_dict()`, and `model_copy(update=...)` enforce the same
  invariants.
- The existing shared prohibited-key and canonical-tree policies are reused.
- Request context, invocation, workflow, runner, references, timestamps,
  attempt metadata, and expected result schema are fully correlated.
- Responses are terminal and enforce:
  - succeeded: result required, no errors;
  - partially succeeded: result required, at least one safe error;
  - failed: no result, at least one safe error;
  - cancelled: no result, at least one safe cancellation error.
- Output artifact IDs are unique.
- Validation failures use bounded messages and do not expose invalid values or
  runtime object representations.

### Cancellation

- Cancellation is explicit and idempotent.
- Cancellation/control objects are runtime-only and cannot enter serialized
  contracts, WorkflowState, artifacts, or results.
- There is no global mutable cancellation state.

### MockRunner

- Supports deterministic succeeded, partially succeeded, failed, and
  pre-execution-cancelled outcomes.
- Validates both its input and its returned response.
- Produces exactly one terminal invocation.
- Uses injected timezone-aware wall-clock and monotonic-clock evidence.
- Performs no browser, network, subprocess, sleep, environment, or config-file
  operation.
- Does not fabricate AI usage, cost, retry, fallback, or provider metadata.
- Does not mutate caller-owned objects.

### Compatibility

- Existing Task 4, Task 5, Task 5A, and Task 5C.1 behavior remains unchanged.
- `import pmqa.runners` remains isolated from product, provider, Playwright,
  LangGraph, runtime orchestration, and Product Pack implementation modules.
- The real PMQA wheel contains the intended public Runner modules and no test or
  temporary output.

## Validation Commands

Use the repository environment and report the exact results for:

```bash
python -m pytest tests/test_runner_contracts.py tests/test_mock_runner.py tests/test_runner_imports.py
python -m pytest tests/test_run_contracts.py tests/test_boundary_policy.py tests/test_packaging.py
python -m pytest tests/test_workflow_runtime.py tests/test_workflow_reducer.py tests/test_supervisor_policy.py tests/test_langgraph_workflow.py
python -m pytest
python -m pytest products/demo/generated_tests
python -m compileall -q pmqa products
git diff --check
git status --short
```

If an exact listed test filename does not exist, run the closest existing
focused suite and document the substitution. Do not silently omit a validation.

Tests must not invoke a paid model, browser, network, Node.js, or external CLI,
except for the repository's already established generated Playwright regression
command when explicitly required by the existing suite.

## Expected Deliverables

- Provider-neutral Runner public API.
- Canonical Runner contracts and authoritative response-correlation validation.
- Runtime-only cancellation boundary.
- Deterministic `MockRunner`.
- Focused tests and packaging/import-isolation coverage.
- Concise architecture and roadmap updates.
- New commit or commits on the current task branch, pushed without amending
  Task 5C.1 history.
- Clean worktree synchronized with the remote branch.

## Required Coder Handoff

Before requesting review, the Coder must replace the pending template in
`agent-handoff/coder-report.md` with a complete report for Task 5C.2.

The report must recommend exactly one review depth:

- `Light`
- `Standard`
- `Deep`

The recommendation is advisory. The Architect independently selects the actual
review depth after inspecting the diff and risk boundaries.
