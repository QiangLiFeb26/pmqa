# Current Task

Owner: Architect

Task: PMQA Task 5C.4 — Provider-Neutral AI Usage and Cost Contracts

Task ID: `PMQA-5C.4`

Attempt: `1`

Status: Ready for Coder

Branch: `agent/task-5c-1-canonical-run-contract`

Architect reviewed baseline:
`35a6c33d2a72ca4723ac65a3b622962adfbd037e`

Coder starting HEAD: derive and record the latest pushed branch commit that
contains this task publication before changing implementation files.

This is the first live pilot of the full file-driven
Coder → Independent Reviewer → Architect workflow. Repository Markdown and Git
history are authoritative; Chat summaries are informational only.

## Task Objective

Define the small, versioned, provider-neutral domain contract for one AI/model
invocation and its usage/cost evidence.

The new contract must:

- correlate cleanly with the existing PMQA session, run, and runner invocation
  identities;
- distinguish reported, parsed, estimated, subscription-included, and
  unavailable information without fabricating tokens or dollars;
- preserve zero as a real observed value distinct from missing data;
- remain independent from Copilot, Codex, OpenAI, Azure OpenAI, model SDKs,
  CLI output formats, pricing tables, storage, UI, and LangGraph state;
- provide the stable foundation for later collection, pricing, persistence,
  summaries, and optimization.

This checkpoint defines contracts and the pricing lookup boundary only. It
does not implement the full Usage Tracking MVP.

## Background

Task 5C.1–5C.3 established:

- canonical `RunRequest`, `PMQARunContext`, `RunRecord`, and outcome metrics;
- a provider-neutral `PMQARunner` boundary and deterministic `MockRunner`;
- explicit Workflow/Runner Registries and the single-attempt
  `PMQAApplicationService`.

`RunnerInvocationRecord` represents one logical runner attempt. It is not a
model call. A future runner may make zero, one, or many AI/model invocations,
so usage and cost must be separate records correlated to the run and optional
runner invocation rather than embedded in `WorkflowState`, `RunRecord`, or
reasoning traces.

The original Usage/Cost requirement explicitly distinguishes:

- provider-reported usage;
- CLI-parsed usage;
- estimated usage;
- unavailable usage;
- provider-reported cost;
- estimated cost;
- subscription-included execution;
- unavailable cost.

Copilot subscription usage must never be converted into a dollar cost unless a
real pricing source supports that calculation.

## Scope

Implement a new neutral `pmqa.usage` package containing:

1. canonical AI/model invocation usage and cost contracts;
2. small fixed vocabularies for source/type/status and explicit missing-data
   reasons;
3. a pricing-record contract with version/effective-date evidence;
4. a provider-neutral read-only `PricingCatalog` boundary;
5. explicit `to_dict()` / `from_dict()` round trips and revalidated copying;
6. focused contract, security, import-isolation, and packaging tests;
7. concise architecture and roadmap documentation.

The Coder may choose precise class names, but public names must be clear,
stable, and exported only from `pmqa.usage`. Do not export them from top-level
`pmqa`.

## Required Domain Relationships

Use this logical relationship:

```text
PMQA session
  └── RunRecord
      ├── RunnerInvocationRecord
      └── zero or more AI/model invocation records
```

Each AI/model invocation record must carry canonical correlation for:

- its own invocation ID;
- `session_id`;
- PMQA `run_id`;
- optional `runner_invocation_id` when the model call occurred inside a known
  runner attempt;
- provider;
- model, or an explicit reason the model identity is unavailable;
- operation;
- started/completed timestamps and duration;
- terminal success/failure/cancellation status;
- usage evidence;
- cost evidence;
- retry evidence and fallback correlation when reliably known;
- a bounded safe error classification when applicable.

Do not duplicate `RunRecord`, `RunnerInvocationRecord`, `OutcomeMetrics`,
`TraceRecord`, or `WorkflowState`.

Cross-record existence checks belong to a future repository/application
service. This contract must still validate its own local identity,
time/lifecycle, attempt, and predecessor invariants.

## Usage Evidence Requirements

At minimum support these logical token fields:

- input tokens;
- output tokens;
- cached input tokens;
- total tokens.

At minimum support these sources:

- `provider_reported`;
- `parsed_from_cli`;
- `estimated`;
- `unavailable`.

The representation must support complete, partial, and entirely unavailable
usage. For every missing token field, the wire contract must make absence
explicit through a bounded field/reason mechanism. Do not silently turn
missing values into zero.

Required invariants:

- token counts are exact non-negative integers when present;
- `bool`, float, strings, negative numbers, and coercion are rejected;
- zero remains present zero and is not unavailable;
- unavailable fields and present fields cannot contradict one another;
- `source=unavailable` contains no token count and requires a fixed reason;
- non-unavailable sources cannot claim all fields unavailable without an
  explicit, contractually valid explanation;
- do not infer or repair `total_tokens`;
- do not assume whether a provider includes cached input in another count;
- no arithmetic convention may fabricate missing provider data.

Use a small stable unavailable-reason vocabulary appropriate to this contract,
such as not reported, not supported, parsing failed, or not collected. Do not
store raw parser messages.

## Cost Evidence Requirements

At minimum support these types:

- `provider_reported`;
- `estimated`;
- `subscription_included`;
- `unavailable`.

The cost contract must carry, when applicable:

- non-negative canonical decimal amount;
- uppercase ISO-style three-letter currency code;
- pricing version/source identifier;
- pricing effective date or equivalent version evidence;
- explicit unavailable reason.

Required invariants:

- provider-reported and estimated cost remain distinguishable;
- an estimated cost is valid only with explicit pricing-version/effective-date
  evidence;
- unavailable cost has no amount and requires a fixed reason;
- subscription-included does not automatically mean a zero-dollar marginal
  cost and must not fabricate an amount;
- a real reported or estimated amount of zero remains distinct from
  unavailable or subscription-included;
- floating-point rounding must not determine the canonical amount;
- no price or currency is inferred when it is absent.

Do not include a built-in pricing table.

## Pricing Boundary Requirements

Define a minimal provider-neutral, read-only lookup boundary equivalent to:

```text
PricingCatalog.get_price(provider, model, effective_at)
    -> ModelPricing or None
```

Requirements:

- provider/model/effective date are explicit inputs;
- `None` means no applicable price, never zero price;
- `ModelPricing` is immutable, versioned, and carries its source/version and
  effective interval or effective date;
- input/output/cached pricing components may be unavailable independently;
- prices use canonical decimal representations and explicit units;
- no network, environment, file read, global registry, or provider SDK occurs
  on import;
- no hard-coded production provider prices are added;
- the catalog boundary does not calculate or mutate invocation cost;
- pricing lookup and cost calculation remain separate.

An abstract base class or runtime-checkable protocol is acceptable if it
matches existing repository style. Do not add a concrete production catalog
in this checkpoint.

## Canonical and Security Requirements

All public data contracts must follow the established PMQA contract style:

- Pydantic v2 strict validation;
- frozen/deeply immutable values;
- `extra=forbid`;
- hidden invalid input values in validation errors;
- canonical plain-JSON serialization;
- timezone-aware timestamps normalized to UTC `Z`;
- full revalidation for direct construction, `from_dict()`, and
  `model_copy(update=...)`;
- no retained caller-owned mutable containers;
- bounded complete-tree depth, item count, string length, and identifier
  validation;
- safe fixed wrapper errors without invalid values, runtime repr, cause, or
  context where the existing contract pattern requires them.

Reuse neutral helpers from `pmqa.run` and
`pmqa.security.boundary_policy` where appropriate. Do not create a new
prohibited/sensitive-key list.

The contracts must not contain:

- prompt or response content;
- credentials, tokens, passwords, cookies, authentication/session state, or
  environment mappings;
- raw CLI stdout/stderr or terminal output;
- commands, executable paths, repository paths, storage paths, or working
  directories;
- DOM/HTML, screenshots, traces, selectors, browser/Page/Locator handles;
- provider clients, callables, subprocess objects, runtime controls, or
  arbitrary metadata blobs;
- exception messages or stack traces.

Provider and model identifiers are metadata, not provider-specific SDK
objects. Error information is a bounded safe classification only.

## Import and Dependency Requirements

`import pmqa.usage` must be side-effect free and must not load or inspect:

- `products.demo` or external Product Packs;
- Playwright, browsers, Node.js, or subprocesses;
- LangGraph, `WorkflowState`, Supervisor, or orchestration;
- concrete reasoning providers or Copilot CLI;
- application service, runner implementations, trace storage, SQLite, or
  local artifact storage;
- installed distributions, environment variables, configuration files,
  pricing files, or network resources.

The neutral usage package may depend only on standard-library/Pydantic
contracts and narrowly reused neutral PMQA validation helpers. Avoid circular
imports with `pmqa.run` and `pmqa.runners`.

The real PMQA wheel must include `pmqa.usage` and must not gain provider
fixtures, usage artifacts, pricing data, secrets, or runtime output.

## Required Tests

At minimum cover:

- complete provider-reported usage;
- complete CLI-parsed usage;
- partial usage with explicit missing fields/reason;
- entirely unavailable usage;
- present zero versus unavailable;
- estimated usage remains labeled estimated;
- provider-reported cost;
- estimated cost with pricing evidence;
- estimated cost rejected without pricing evidence;
- subscription-included is not reported or estimated dollar cost;
- unavailable cost;
- real zero cost versus unavailable/subscription-included;
- pricing present and pricing unavailable through a fake catalog;
- independent missing pricing components;
- invocation success, failure, and cancellation lifecycle;
- optional runner correlation;
- retry/fallback local invariants;
- canonical UTC timestamps and duration;
- direct construction, JSON round trip, and revalidated copy;
- deep immutability and caller-container isolation;
- unknown fields and coercion rejection;
- cyclic, oversized, excessive-depth, and non-finite payload rejection where
  applicable;
- prohibited key/runtime object/secret-marker rejection and safe errors;
- import isolation and zero import side effects;
- real-wheel package inclusion;
- existing Run, Runner, Application, security-boundary, and packaging
  regressions.

Tests must use fakes/fixtures only. Do not call a paid model, provider CLI,
network, browser, Node.js, or external Product Pack.

## Documentation

Update only what is necessary:

- `docs/Roadmap.md`: mark Task 5C.3 architecture review passed and Task 5C.4
  ready for review after implementation;
- `docs/architecture.md`: place usage/cost beside, not inside, Run Contract and
  LangGraph state;
- add one focused usage/cost architecture document;
- update `README.md` only for concise current status and links.

Document clearly that:

- this is a contracts/pricing-boundary checkpoint, not the Usage Tracking MVP;
- collection, calculation, persistence, aggregation, CLI summaries, and
  optimization remain future tasks;
- provider-reported, parsed, estimated, subscription-included, and unavailable
  evidence remain distinct;
- raw prompts/responses and secrets are never stored;
- no real provider integration exists.

## Allowed Changes

- new `pmqa/usage/` contract and pricing-boundary files;
- new focused tests under `tests/`;
- minimal packaging assertions/configuration only if needed to include the
  new Python package;
- `README.md`;
- `docs/Roadmap.md`;
- `docs/architecture.md`;
- one focused `docs/architecture/` usage/cost document;
- `agent-handoff/coder-report.md`.

The Coder must not modify:

- `agent-handoff/README.md`;
- `agent-handoff/current-task.md`;
- `agent-handoff/reviewer-report.md`;
- `agent-handoff/architect-review.md`.

Use one focused implementation commit and one report-only Coder handoff
commit. Do not amend prior commits.

## Out of Scope

Do not implement:

- usage collector/service or invocation handle;
- Copilot/Codex/OpenAI/Azure OpenAI adapters or parsers;
- raw provider metadata persistence;
- cost calculator or estimator;
- concrete pricing table/catalog;
- usage/cost storage, JSONL, SQLite, or repository;
- session/run aggregation or summary;
- CLI commands or UI;
- workflow, runner, reasoning-provider, or Application Service integration;
- automatic model routing, budgets, optimization, recommendations, feedback,
  eval, or logging;
- changes to `RunRecord`, `RunnerInvocationRecord`, `WorkflowState`,
  LangGraph, Task 5, Product Pack, Supervisor, or current provider behavior;
- Task 5B, Task 6, or Task 7;
- PR creation or merge.

## Acceptance Criteria

The task is complete only if:

- contracts express complete, partial, zero, and unavailable usage without
  ambiguity;
- reported, CLI-parsed, estimated, subscription-included, and unavailable
  evidence cannot be confused;
- cost estimation requires external pricing evidence but no price table is
  embedded;
- AI/model invocation correlation remains separate from runner attempts and
  LangGraph state;
- all canonical, security, immutability, and import-isolation requirements
  pass;
- existing Run/Runner/Application and Task 4 behavior remain unchanged;
- the wheel includes only the intended new package code;
- no real provider, parser, storage, collector, calculator, CLI, UI, or
  optimization is added;
- only the Coder modifies implementation and Coder-owned handoff files.

## Validation Commands

Run and report exact results for:

```bash
.venv/bin/python -m pytest <new usage tests>
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

- provider-neutral usage/cost invocation contracts;
- pricing record and read-only catalog boundary;
- focused adversarial tests;
- import isolation and real-wheel coverage;
- concise architecture/status documentation;
- one implementation commit;
- one report-only Coder handoff commit;
- clean worktree and synchronized local/upstream branch;
- no PR and no merge.

## Required Coder Handoff

Replace `agent-handoff/coder-report.md` with the complete Task 5C.4 attempt 1
report. It must include:

- Task ID, Attempt, branch, and exact Git-derived Coder starting HEAD;
- implementation commit SHA(s) created before the report commit;
- changed files and public contracts;
- usage, cost, pricing, correlation, lifecycle, and security decisions;
- validation results;
- remaining risks/open items;
- scope confirmation;
- exactly one recommended review depth: `Light`, `Standard`, or `Deep`;
- one-sentence reason;
- 3–6 suggested Reviewer focus areas.

Do not include the Coder report commit's own SHA. Commit the report separately
after the implementation commit; the Independent Reviewer derives it from
Git.

## Pilot Handoff After Coder Completion

After the Coder report is committed and pushed:

1. Human wakes the Independent Reviewer without copying the report.
2. Reviewer reads `agent-handoff/README.md` and follows the required
   independent inspection order.
3. Reviewer derives the Coder report commit from Git.
4. Reviewer replaces only `agent-handoff/reviewer-report.md`, commits, pushes,
   and sends the Human Summary.
5. Human then wakes the Architect.
6. Architect derives the Reviewer report commit, performs final synthesis,
   and publishes the disposition.

The Coder must not prefill, reset, or modify `reviewer-report.md`.
