# Current Task

Owner: Architect

Task: PMQA Task 5C.3 — Explicit Application Registries and Single-Attempt Run Service

Status: Ready for Coder

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed implementation baseline:
`0e01d820060d4c3bdc2d5ca342dc12bb7d14f863`

Coder starting HEAD: use the latest pushed branch commit containing this
handoff and record its exact SHA before making changes.

This file is the authoritative task handoff. Chat summaries are informational
only.

## Task Objective

Add the smallest useful application layer above the canonical Run Contract and
provider-neutral Runner boundary.

The application layer must explicitly select a registered workflow and runner,
validate their compatibility, execute exactly one supplied first attempt, and
assemble one canonical `RunRecord` plus its terminal
`RunnerInvocationRecord`.

No persistence, retry, provider integration, or Usage/Cost tracking belongs in
this checkpoint.

## Background

- Task 5C.1 established the canonical application-level Run Contract.
- Task 5C.2 established and hardened the provider-neutral Runner boundary and
  deterministic MockRunner.
- Task 5C.3 connects those two layers without modifying LangGraph or existing
  Task 5/Product Pack execution.

The intended dependency direction is:

```text
caller
  -> explicit PMQA Application Service
      -> explicit Workflow Registry
      -> explicit Runner Registry
      -> PMQARunner.execute()
  -> canonical application execution result
```

Registries are explicit local composition, not discovery systems.

## Scope

- Define a runtime-only workflow adapter boundary carrying:
  - one canonical `WorkflowDefinition`;
  - workflow-specific request validation;
  - workflow-specific result validation.
- Define an explicit immutable Workflow Registry.
- Define an explicit immutable Runner Registry.
- Define safe application failure codes/errors.
- Define a canonical result envelope correlating:
  - one `RunRecord`;
  - exactly one terminal `RunnerInvocationRecord`.
- Implement a synchronous single-attempt `PMQAApplicationService`.
- Validate workflow identity/version and input schema before runner execution.
- Validate runner identity and required capabilities before runner execution.
- Respect `ApprovalMode`; do not execute workflows requiring approval.
- Invoke the selected runner exactly once.
- Validate the returned Runner response and workflow-specific result.
- Assemble a canonical terminal `RunRecord` without fabricating outcome
  metrics.
- Add a deterministic offline vertical slice using a test workflow adapter and
  the existing `MockRunner`.
- Preserve packaging and import isolation.
- Update focused architecture and roadmap documentation.
- Update `agent-handoff/coder-report.md` when complete.

## Allowed Changes

Prefer a focused package such as:

```text
pmqa/application/
    __init__.py
    contracts.py
    registry.py
    service.py
```

Exact file names may differ if a smaller structure is clearer.

Allowed supporting changes:

- minimal additions to `pmqa/run` or `pmqa/runners` only when required by a
  demonstrated application-level invariant;
- focused application, registry, packaging, and import-isolation tests;
- `README.md`;
- `docs/Roadmap.md`;
- `docs/architecture.md`;
- focused application-layer documentation;
- `agent-handoff/coder-report.md`.

Do not amend earlier Task 5C commits.

## Application Boundaries

### Workflow adapter

Define a provider-neutral runtime protocol, for example:

```python
class PMQAWorkflowAdapter(Protocol):
    @property
    def definition(self) -> WorkflowDefinition:
        ...

    def validate_request(self, request: RunRequest) -> None:
        ...

    def validate_result(self, result: StructuredResult) -> None:
        ...
```

The exact method names may change, but responsibilities must stay narrow.

Requirements:

- the adapter does not execute a runner;
- the adapter does not persist state;
- the adapter does not receive provider clients, subprocesses, browsers,
  credentials, raw prompts, or terminal output;
- workflow-specific validators must report only an application-owned fixed
  validation error;
- unexpected programming exceptions must not be silently classified as
  ordinary validation failures;
- resource/control-flow exceptions propagate unchanged.

Do not add a production generic callback-based workflow implementation merely
to fill the protocol. Test fakes may implement the protocol locally.

### Workflow Registry

The Workflow Registry must:

- be constructed explicitly from a bounded immutable collection of workflow
  adapters;
- retain independently validated canonical workflow definitions;
- identify workflows by exact `(workflow_id, workflow_version)`;
- reject duplicate identities;
- reject malformed adapters and definitions safely;
- perform no entry-point discovery, package scanning, filesystem lookup,
  environment lookup, import-path loading, or global registration;
- expose deterministic exact lookup;
- not permit mutable registration after construction.

If an adapter's live definition later differs from its registered snapshot,
execution must fail safely before calling its request validator or any runner.

### Runner Registry

The Runner Registry must:

- be constructed explicitly from a bounded immutable collection of
  `PMQARunner` implementations;
- retain stable validated `RunnerMetadata`;
- identify runners by exact `runner_id`;
- reject duplicate runner IDs;
- reject malformed runners safely;
- not instantiate or discover runners;
- not inspect distributions, files, environment variables, or import paths;
- not expose provider-specific configuration;
- not permit mutable registration after construction.

If a concrete runner's live metadata later differs from its registered
snapshot, execution must fail safely before calling the runner.

## Application Service API

Implement one synchronous service method with behavior equivalent to:

```python
execute(
    request: RunRequest,
    *,
    run_id: str,
    invocation_id: str,
    control: RunnerControl | None = None,
) -> ApplicationRunResult
```

The exact name may differ, but do not add parallel sync/async APIs.

For Task 5C.3:

- the application service creates only attempt number 1;
- the operation is one stable application-owned identifier;
- no retry or fallback predecessor is created;
- one Runner is called at most once;
- no random ID generation is required;
- caller-supplied IDs are validated with the existing canonical policy;
- a caller-supplied `RunnerControl` remains runtime-only;
- an omitted control creates one local control for that invocation;
- the caller-owned request and control are not mutated.

## Pre-execution validation order

Before invoking a runner, the service must:

1. validate the exact `RunRequest`;
2. resolve the exact workflow ID and version;
3. confirm request input schema ID/version match the workflow definition;
4. invoke the workflow-specific request validator;
5. resolve the exact runner ID;
6. confirm every required workflow capability is present in registered runner
   metadata;
7. confirm the runner's current metadata still equals the registered snapshot;
8. reject workflows whose approval mode is not `ApprovalMode.NONE`;
9. validate run and invocation IDs;
10. sample and validate the application start clock;
11. construct a canonical `PMQARunContext`, first-attempt pending
    `RunnerInvocationRecord`, and `RunnerRequest`.

Any failure before step 11 must result in zero runner calls.

Use a stable deterministic ordering and document it.

## Runner execution and response handling

- Call `PMQARunner.execute()` exactly once.
- Pass the canonical `RunnerRequest` and the selected runtime-only control.
- Re-run authoritative `validate_runner_response()`.
- If a result is present:
  - schema ID/version must match the selected WorkflowDefinition;
  - invoke the workflow-specific result validator exactly once.
- A terminal failed or cancelled RunnerResponse is a valid application
  execution outcome, not an Application Service exception.
- A safe Runner boundary failure becomes one fixed application-owned failure;
  do not fabricate a successful or terminal runner record.
- Unexpected programming exceptions propagate rather than being silently
  reported as expected application failures.
- `MemoryError`, `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit`
  propagate unchanged.
- Do not retry, fall back, sleep, or enforce the timeout in this checkpoint.

## Canonical ApplicationRunResult

Define a strict frozen canonical envelope, named `ApplicationRunResult` or an
equivalent clear name, containing:

- schema version;
- one terminal `RunRecord`;
- exactly one terminal `RunnerInvocationRecord`.

It must enforce:

- exact run/request/session/workflow/version/runner correlations;
- the RunRecord invocation ID list equals the one contained invocation;
- terminal status mapping:
  - invocation succeeded -> run succeeded;
  - invocation partially succeeded -> run partially succeeded;
  - invocation failed -> run failed;
  - invocation cancelled -> run cancelled;
- result, artifacts, and errors are exactly those returned by the Runner;
- run start equals invocation start;
- run completion equals invocation completion;
- run duration uses the invocation's monotonic duration evidence for this
  single-attempt MVP;
- `created_at` equals the canonical `RunRequest.requested_at`;
- `updated_at` equals runner invocation completion;
- `created_at <= started_at <= completed_at <= updated_at`;
- no `current_step_id` on the terminal record;
- `outcome_metrics` remains `None` unless a reliable workflow-owned value is
  explicitly available. Do not add such metrics merely to populate fields.

The envelope must satisfy canonical JSON round-trip and complete-tree bounds at
construction, `from_dict()`, and `model_copy(update=...)`.

## Application errors

Define a small stable failure-code vocabulary covering only expected
application boundary failures, such as:

- invalid application request;
- workflow not found;
- workflow input schema mismatch;
- workflow input invalid;
- approval required;
- runner not found;
- runner capability mismatch;
- runner metadata changed;
- runner boundary failed;
- workflow result invalid.

Names may be adjusted, but:

- messages are fixed and bounded;
- errors do not expose request values, IDs, registry contents, payloads,
  paths, prompts, provider data, object representations, markers, or
  underlying exception details;
- expected exception chaining is suppressed;
- unknown programming errors are not relabeled as expected failures.

Do not persist these failures in this task.

## Clocks and deterministic behavior

Inject a timezone-aware wall clock into the Application Service.

Requirements:

- callable validation and clock sampling are safely contained;
- invalid, naive, or failing ordinary clock values become a fixed application
  error;
- `MemoryError`, `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit`
  propagate unchanged;
- clock errors expose no cause, context, marker, or object representation;
- sample the application start time exactly once per execution;
- the same sampled start time is used for context, invocation, and RunRecord;
- the sampled start must not precede `RunRequest.requested_at`;
- `RunRequest.requested_at` is reused as RunRecord creation time;
- completion and duration come from the validated Runner response.

Do not add a second wall-clock sample or a second duration policy.

## Import and dependency isolation

Importing the application package must not:

- import `products.demo`;
- import external Product Packs;
- import Playwright or LangGraph;
- import existing workflow runtime, Supervisor, or orchestration;
- import a provider SDK or reasoning provider;
- inspect installed distributions;
- read files, config, or environment variables;
- create files;
- launch processes;
- mutate `sys.path`;
- create a global registry.

No new runtime dependency should be necessary.

## Required Tests

Add focused tests for:

### Registries

- explicit deterministic workflow lookup;
- exact workflow version selection;
- duplicate workflow rejection;
- explicit deterministic runner lookup;
- duplicate runner rejection;
- independently retained metadata/definition snapshots;
- bounded collections;
- malformed adapter/runner rejection;
- live runner metadata drift;
- no discovery or mutable registration.

### Pre-execution policy

- missing workflow;
- workflow version mismatch;
- input schema mismatch;
- workflow request validation failure;
- approval-required workflow;
- missing runner;
- capability mismatch;
- invalid run/invocation IDs;
- invalid application clock;
- every failure invokes the runner zero times;
- safe messages do not expose injected markers.

### Execution

- succeeded, partially succeeded, failed, and cancelled Runner responses;
- exactly one runner call;
- exactly one result-validator call when a result exists;
- zero result-validator calls when result is absent;
- canonical Runner response is revalidated;
- result-schema mismatch;
- runner metadata drift before execution;
- Runner boundary failure containment;
- unexpected programming exception propagation;
- resource/control-flow exception propagation;
- caller-owned values unchanged.

### ApplicationRunResult

- canonical round-trip;
- status mapping;
- exact result/artifact/error correlation;
- invocation ID correlation;
- timestamp and duration correlation;
- complete-tree bounds;
- `model_copy(update=...)` revalidation;
- zero versus unavailable outcome metrics;
- no runtime objects, prohibited fields, prompt, provider, usage, or cost data.

### Isolation and compatibility

- side-effect-free application imports;
- real wheel contains intended application modules;
- Task 5C.1/5C.2 regressions remain green;
- Task 4 orchestration behavior remains unchanged;
- full default suite remains green.

All new tests must be offline and must not invoke a browser, network, Node.js,
external CLI, or paid model.

## Documentation

Update:

- `README.md`;
- `docs/Roadmap.md`;
- `docs/architecture.md`;
- focused application/run architecture documentation.

Document:

- Run Contract versus Runner versus Application Service responsibility;
- explicit registry behavior and why it is not discovery;
- single-attempt lifecycle;
- pre-execution validation order;
- expected versus unexpected failure policy;
- why persistence, retry, approval execution, provider adapters, and
  Usage/Cost remain later work.

After implementation:

- Task 5C.1: approved;
- Task 5C.2: approved;
- Task 5C.3: ready for architecture review;
- Task 5C remains in progress and unmerged;
- Task 5B, Task 6, and Task 7 remain not started.

## Out of Scope

Do not implement:

- persistence or a Run Repository;
- JSONL/SQLite storage;
- session storage;
- usage, cost, pricing, logs, feedback, or eval records;
- retries, fallbacks, timeout enforcement, or approval execution;
- real provider, Copilot, Codex, OpenAI, Azure OpenAI, ADO, Product Pack, or
  SauceDemo adapters;
- subprocess, terminal, browser, Node.js, or network execution;
- automatic discovery, entry points, path loading, or dynamic imports;
- CLI commands, UI, REST API, dashboard, or events;
- changes to WorkflowState, reducer, Supervisor, ToolRegistry, LangGraph,
  Task 5, or Product Pack semantics;
- Task 5B, Task 6, or Task 7;
- PR creation or merge.

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

If the chosen focused test filenames differ, document the exact substitution.
Do not silently omit a validation.

## Expected Deliverables

- Explicit immutable Workflow and Runner Registries.
- Narrow workflow adapter protocol.
- Safe application error vocabulary.
- Canonical `ApplicationRunResult`.
- Single-attempt synchronous `PMQAApplicationService`.
- Offline deterministic integration through the existing MockRunner.
- Focused tests, packaging/import-isolation coverage, and documentation.
- Updated `agent-handoff/coder-report.md`.
- New commit or commits without amending Task 5C history.
- Pushed branch with clean worktree and synchronized local/remote HEAD.
- No PR and no merge.

## Required Coder Handoff

Replace `agent-handoff/coder-report.md` with the complete Task 5C.3 report.
Include:

- branch and exact Coder starting HEAD;
- implementation commit SHA(s);
- changed files;
- public application APIs;
- registry identity and immutability rules;
- pre-execution validation order;
- execution/result lifecycle;
- safe failure behavior;
- validation results;
- remaining risks and scope confirmation;
- exactly one recommended review depth: `Light`, `Standard`, or `Deep`;
- one-sentence reason;
- 3–6 suggested review focus areas.

The Coder recommendation is advisory. The Architect independently selects the
actual review depth.
