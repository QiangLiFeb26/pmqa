# Current Task

Owner: Architect

Task: PMQA Task 5C.5 — Provider-Neutral AI Invocation Collector

Task ID: `PMQA-5C.5`

Attempt: `1`

Status: Ready for Coder

Branch: `agent/task-5c-1-canonical-run-contract`

Architect reviewed baseline:
`f5a960d359b671c485d70871eecb2e150b9e23d6`

Coder starting HEAD: derive and record the latest pushed branch commit that
contains this task publication before changing implementation files.

Repository Markdown and Git history are authoritative. Chat summaries are
informational only. This task uses the now-adopted
Coder → Independent Reviewer → Architect workflow.

## Task Objective

Implement the first provider-neutral lifecycle service that creates canonical
Task 5C.4 `AIInvocationRecord` values without storing prompts, responses,
credentials, provider clients, or runtime objects.

The service must:

- start one invocation and return an invocation-local runtime handle;
- complete, fail, or cancel that invocation exactly once;
- sample validated wall-clock and monotonic timing through injected clocks;
- accept caller-supplied canonical usage and cost evidence without inventing
  missing data;
- return one fully correlated immutable `AIInvocationRecord`;
- remain independent from provider SDKs, CLI formats, pricing calculation,
  persistence, UI, LangGraph, and current Application Service behavior.

This checkpoint is lifecycle collection only. It does not calculate cost,
parse provider output, persist records, or integrate with a real workflow.

## Background

Task 5C.4 introduced:

- `TokenUsageEvidence`;
- `CostEvidence`;
- `AIInvocationRecord`;
- `ModelPricing`;
- the read-only `PricingCatalog` protocol.

Those contracts describe evidence but do not own runtime timing or
terminalization. A future provider/runner adapter needs a narrow neutral
service equivalent to:

```text
handle = collector.start_invocation(...)

record = collector.complete_invocation(handle, usage, cost)
record = collector.fail_invocation(handle, usage, cost, error_category)
record = collector.cancel_invocation(handle, usage, cost)
```

The API may use different precise names if they are clearer and consistent
with repository style.

## Scope

Add a small collection boundary under `pmqa.usage` containing:

1. a runtime-only invocation handle;
2. a provider-neutral collector interface;
3. one deterministic synchronous default implementation;
4. fixed safe collection failures;
5. focused lifecycle, timing, ownership, security, import, and packaging
   tests;
6. concise Task 5C.5 architecture/status documentation.

Do not change the Task 5C.4 persisted wire schema unless an independently
demonstrated blocking defect makes that unavoidable. If such a defect is
found, stop and report it rather than silently expanding scope.

## Collector Input and Correlation

Starting an invocation must receive only the canonical metadata needed to
eventually construct `AIInvocationRecord`:

- invocation ID;
- session ID;
- PMQA run ID;
- optional runner invocation ID;
- provider;
- model or explicit model-unavailable reason;
- operation;
- attempt number;
- optional retry predecessor;
- optional fallback predecessor.

Reuse Task 5C.4 validation and identifiers. Do not duplicate correlation,
attempt, predecessor, provider/model, or missing-reason policy in a second
independent list.

The collector must validate all caller metadata before sampling any clock or
creating live handle state.

## Runtime Handle Requirements

The handle is runtime-only coordination, not a persisted domain record.

Requirements:

- it is immutable through its public API;
- it contains or privately retains only canonical correlation and timing
  needed by the owning collector;
- it contains no prompt, response, credential, environment, provider client,
  pricing catalog, storage object, browser/process handle, or arbitrary
  metadata;
- it is bound to exactly one collector instance;
- a forged handle, subclass, foreign collector's handle, or mutated internal
  handle is rejected safely;
- it cannot be serialized into `AIInvocationRecord`, `RunRecord`,
  `WorkflowState`, usage artifacts, or logs;
- it does not expose a secret/token-like capability in public output;
- finalization removes or irrevocably marks its active state.

An opaque identity or collector-owned active-handle table is acceptable. Do
not use a process-global registry.

## Lifecycle Requirements

Support exactly three terminal paths:

- success;
- failure;
- cancellation.

Each successful terminalization returns one independently reconstructed
canonical `AIInvocationRecord`.

Required behavior:

- one handle can terminalize exactly once;
- a second terminalization attempt fails safely and creates no second record;
- finalization status and error category obey Task 5C.4 invariants;
- success has no error category;
- failure requires a caller-supplied non-cancellation `RunErrorCategory`;
- cancellation uses only `RunErrorCategory.CANCELLED`;
- usage and cost evidence are mandatory on every terminal path, but may use
  their explicit unavailable forms;
- caller-owned usage/cost objects are reconstructed and not retained;
- later caller mutation cannot change the returned record;
- no retry, fallback, parser, pricing, or persistence policy is added;
- no callback, event, record sink, or hidden global collection occurs.

If terminal record construction fails because caller evidence is invalid or
correlation was tampered with, the collector must not publish a partial
record. Define and test whether the handle remains retryable or becomes
terminal after each failure category; the policy must be deterministic and
must not permit duplicate successful records.

Recommended default:

- caller-validation failure before terminal clock sampling leaves the handle
  active so corrected evidence may be supplied;
- once terminal clock sampling begins, any expected terminalization failure
  consumes the handle to preserve at-most-once semantics;
- resource/control-flow exceptions remain authoritative and must not be
  silently converted.

If the Coder chooses a different policy, document the exact safety advantage
and test it comprehensively.

## Clock and Duration Requirements

Inject:

- a timezone-aware wall-clock callable;
- a monotonic-clock callable.

Start behavior:

- sample each clock exactly once after input validation;
- wall time must be a timezone-aware `datetime`, normalized to UTC;
- monotonic time must be an exact finite `int` or `float`, excluding `bool`;
- invalid clock objects or returned values fail with fixed safe errors;
- ordinary clock exceptions are contained as fixed safe clock failures;
- `MemoryError`, `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit`
  propagate unchanged;
- a failed start returns no live handle.

Terminal behavior:

- validate handle and caller evidence before sampling terminal clocks;
- sample each terminal clock exactly once;
- terminal wall time cannot precede start;
- terminal monotonic time cannot precede start;
- `duration_ms` is derived only from monotonic evidence;
- conversion uses a documented deterministic rounding policy and remains
  bounded by `MAX_USAGE_INTEGER`;
- wall-clock difference does not overwrite monotonic duration;
- invalid/overflow/non-finite samples fail safely without leaking values;
- no timestamp or duration is guessed, clamped, or fabricated.

Use the existing Runner clock-containment precedent where appropriate, but do
not make the collector depend on a runner implementation.

## Collector Interface Requirements

Expose a provider-neutral interface from `pmqa.usage`.

It must:

- have no provider-specific arguments;
- return only the runtime handle from start and
  `AIInvocationRecord` from a successful terminalization;
- use Task 5C.4 evidence contracts directly;
- not accept raw dictionaries as usage/cost evidence at the runtime method
  boundary unless they are explicitly reconstructed before any state change;
- define a fixed small error-code vocabulary and bounded messages;
- suppress underlying cause/context for expected failures;
- preserve unexpected resource/control-flow exceptions;
- perform no I/O.

An abstract base class or runtime-checkable protocol is acceptable. The default
implementation must satisfy it and be testable with injected clocks.

## Security and Ownership Requirements

The collector must never accept, retain, return, log, or expose:

- prompts or model responses;
- credentials, passwords, API keys, PATs, tokens, cookies, authentication or
  browser storage state;
- environment mappings;
- provider clients or SDK response objects;
- raw CLI stdout/stderr, terminal output, command lines, executable paths,
  working directories, or repository paths;
- DOM/HTML, screenshots, traces, selectors, Page/Locator/browser objects;
- callables other than the two constructor-injected clocks;
- arbitrary metadata or exception text.

Do not introduce a new prohibited-key list. Reuse the existing neutral
contract/security boundary.

Expected errors must not reveal invalid values, runtime repr, markers, clock
output, handle identity, or underlying exceptions.

The collector must not mutate caller-owned inputs, usage/cost evidence, clock
objects, or returned records.

## Import and Dependency Requirements

`import pmqa.usage` must remain side-effect free and must not:

- create a collector instance or global handle registry;
- sample a clock;
- inspect environment/configuration/distributions;
- read or write files;
- launch processes, browsers, Node.js, or network calls;
- load products, Product Packs, Playwright, LangGraph, orchestration,
  Supervisor, concrete runners, Application Service, reasoning providers,
  storage, SQLite, CLI, or UI.

The collector may depend on Task 5C.4 contracts and narrow neutral validation
helpers only. No provider dependency or new runtime dependency may be added.

The PMQA wheel must include the new neutral collector code and no runtime
output or fixture data.

## Required Tests

At minimum cover:

- successful start and completion;
- failed invocation;
- cancelled invocation;
- unavailable usage/cost accepted without fabrication;
- present zero evidence preserved;
- model-unavailable correlation;
- optional runner invocation correlation;
- retry and fallback metadata preserved;
- invalid start metadata rejected before clock sampling;
- start wall-clock and monotonic-clock validation;
- terminal wall-clock and monotonic-clock validation;
- backwards wall and monotonic time;
- non-finite and overflow duration;
- deterministic duration rounding and zero duration;
- ordinary clock exception containment;
- exact propagation of `MemoryError`, `KeyboardInterrupt`, `SystemExit`, and
  `GeneratorExit`;
- each clock sampled exactly once at each applicable stage;
- exactly-once terminalization;
- duplicate completion/fail/cancel combinations rejected;
- foreign, forged, subclassed, and internally mutated handles rejected;
- evidence validation failure and retry/consumption policy;
- retained-reference mutation cannot change returned records;
- no marker, invalid value, handle identity, or exception leakage;
- no global registry or import side effect;
- interface/default implementation conformance;
- package exports, import isolation, and real-wheel inclusion;
- all Task 5C.4, Run, Runner, Application, security, packaging, and Task 4
  regressions.

All new tests must be offline and use deterministic fake clocks. Do not invoke
a model, provider CLI, network, browser, Node.js, or external Product Pack.

## Documentation

Update only what is necessary:

- `docs/Roadmap.md`: mark Task 5C.4 architecture review passed and Task 5C.5
  ready for review after implementation;
- `docs/architecture.md`: add the collector as a runtime lifecycle boundary,
  not storage or provider integration;
- extend the focused usage/cost architecture document;
- update `README.md` only for concise current status.

Document:

- runtime handle versus persisted invocation record;
- exactly-once lifecycle;
- monotonic duration semantics;
- safe missing evidence;
- failure/handle-consumption policy;
- deferred parser, calculator, storage, summary, CLI, workflow integration,
  and optimization work.

## Allowed Changes

- new focused collector/runtime files under `pmqa/usage/`;
- `pmqa/usage/__init__.py` exports;
- focused new tests under `tests/`;
- minimal additive `tests/test_packaging.py` assertions if needed;
- `README.md`;
- `docs/Roadmap.md`;
- `docs/architecture.md`;
- `docs/architecture/usage-cost-contracts.md`;
- `agent-handoff/coder-report.md`.

The Coder must not modify:

- `agent-handoff/README.md`;
- `agent-handoff/current-task.md`;
- `agent-handoff/reviewer-report.md`;
- `agent-handoff/architect-review.md`;
- existing Task 5C.4 wire fields or semantics without stopping for Architect
  direction.

Use one focused implementation commit and one report-only Coder handoff
commit. Do not amend prior commits.

## Out of Scope

Do not implement:

- provider or CLI adapter/parser;
- raw provider metadata;
- pricing selection or cost calculation;
- concrete `PricingCatalog` or pricing table;
- storage, JSONL, SQLite, repository, sink, or callback;
- aggregation, summaries, CLI, UI, logs, feedback, or eval;
- workflow, runner, reasoning-provider, or Application Service integration;
- retry/fallback execution policy;
- timeout enforcement or automatic cancellation;
- budgets, optimization, routing, recommendations, or model selection;
- Task 5B, Task 6, or Task 7;
- PR creation or merge.

Do not modify `RunRecord`, `RunnerInvocationRecord`, `WorkflowState`,
LangGraph, Task 5, Product Pack, Supervisor, or existing provider behavior.

## Acceptance Criteria

The task is complete only if:

- the public collector interface is provider-neutral;
- the runtime handle cannot become persisted domain data;
- lifecycle terminalization is exactly once;
- canonical evidence is snapshotted without fabrication or caller mutation;
- wall and monotonic clocks are injected, bounded, and safely contained;
- duration uses only monotonic evidence;
- failure/status/error correlation is canonical;
- expected failures are fixed, bounded, and marker-safe;
- resource/control-flow exceptions remain authoritative;
- imports remain side-effect free and isolated;
- no provider, parser, calculator, pricing table, storage, CLI, UI, workflow
  integration, or optimization is added;
- all new and existing required tests pass;
- Coder and Reviewer follow their exclusive write boundaries.

## Validation Commands

Run and report:

```bash
.venv/bin/python -m pytest <new collector tests> tests/test_usage_contracts.py tests/test_usage_pricing.py tests/test_usage_imports.py
.venv/bin/python -m pytest tests/test_run_contracts.py tests/test_runner_contracts.py tests/test_application_contracts.py tests/test_application_service.py tests/test_boundary_policy.py tests/test_packaging.py
.venv/bin/python -m pytest tests/test_workflow_runtime.py tests/test_workflow_reducer.py tests/test_supervisor_policy.py tests/test_langgraph_workflow.py
.venv/bin/python -m pytest
.venv/bin/python -m pytest products/demo/generated_tests
.venv/bin/python -m compileall -q pmqa products
git diff --check
git status --short
```

Use an isolated bytecode cache for `compileall`. Browser execution is limited
to the existing generated Playwright regression.

## Expected Deliverables

- provider-neutral collector interface;
- deterministic synchronous default collector;
- runtime-only handle with exactly-once ownership;
- safe clock and terminalization behavior;
- focused adversarial tests;
- import isolation and wheel coverage;
- concise documentation updates;
- one implementation commit;
- one report-only Coder handoff commit;
- clean synchronized branch;
- no PR and no merge.

## Required Coder Handoff

Replace `agent-handoff/coder-report.md` with the complete Task 5C.5 attempt 1
report. Include:

- Task ID, Attempt, branch, and Git-derived Coder starting HEAD;
- implementation commit SHA(s) created before the report;
- changed files and public API;
- handle ownership and terminalization policy;
- clock sampling, duration, and failure decisions;
- security/import/packaging evidence;
- exact validation results;
- remaining risks/open items;
- scope confirmation;
- exactly one recommended review depth: `Light`, `Standard`, or `Deep`;
- one-sentence reason;
- 3–6 suggested Reviewer focus areas.

Do not include the Coder report commit's own SHA. Commit the report separately
after implementation; the Reviewer derives it from Git.

## Handoff After Coder Completion

After the Coder report is committed and pushed:

1. Human wakes the Independent Reviewer without copying report content.
2. Reviewer follows `agent-handoff/README.md`, derives the Coder report commit,
   and reviews independently.
3. Reviewer modifies only `agent-handoff/reviewer-report.md`, commits, pushes,
   and sends the Human Summary.
4. Human then wakes the Architect.
5. Architect derives the Reviewer commit and publishes the final disposition.

The Coder must not modify or reset `reviewer-report.md`.
