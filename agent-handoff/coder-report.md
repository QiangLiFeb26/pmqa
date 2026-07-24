# Coder Report

Owner: Coder

Task: PMQA Task 5C.4 — Provider-Neutral AI Usage and Cost Contracts

Task ID: `PMQA-5C.4`

Attempt: `1`

Status: Ready for Independent Reviewer

This file is the authoritative Coder handoff for the first live Independent
Reviewer pilot.

## Branch and Starting HEAD

Branch:

`agent/task-5c-1-canonical-run-contract`

Exact Git-derived Coder starting HEAD:

`150c265974eac9f73ffc76b5eb7cd70f94f9cb5c`

The starting commit contained the Architect-owned Task 5C.4 publication. The
worktree and tracking branch were clean before implementation. No prior commit
was amended.

## Implementation Commit

`2252c14736a050e87be6b769f488754a64b144bc`

Commit message:

`add Task 5C.4 usage and cost contracts`

This report is committed separately after the implementation commit. Per the
pilot protocol, the Independent Reviewer derives the report commit from Git;
this report does not include its own SHA.

## Changed Files

Implementation commit:

- `README.md`
- `docs/Roadmap.md`
- `docs/architecture.md`
- `docs/architecture/usage-cost-contracts.md`
- `pmqa/usage/__init__.py`
- `pmqa/usage/contracts.py`
- `pmqa/usage/pricing.py`
- `tests/test_packaging.py`
- `tests/test_usage_contracts.py`
- `tests/test_usage_imports.py`
- `tests/test_usage_pricing.py`

Report-only handoff commit:

- `agent-handoff/coder-report.md`

No Architect- or Reviewer-owned handoff file changed.

## Public Contracts

`pmqa.usage` exports only its explicit neutral surface:

- schema/bound constants:
  - `USAGE_CONTRACT_SCHEMA_VERSION`;
  - `MAX_USAGE_INTEGER`;
- fixed vocabularies:
  - `UsageSource`;
  - `CostType`;
  - `EvidenceUnavailableReason`;
  - `TokenField`;
  - `AIInvocationStatus`;
  - `PricingUnit`;
  - `PricingComponentKind`;
- canonical evidence and correlation records:
  - `TokenFieldAbsence`;
  - `TokenUsageEvidence`;
  - `CostEvidence`;
  - `AIInvocationRecord`;
  - `PricingComponent`;
  - `ModelPricing`;
- boundary/error types:
  - `PricingCatalog`;
  - `UsageContractValidationError`.

Nothing is exported from top-level `pmqa`.

## Usage Evidence Decisions

`TokenUsageEvidence` distinguishes exactly:

- `provider_reported`;
- `parsed_from_cli`;
- `estimated`; and
- `unavailable`.

Input, output, cached-input, and total tokens are independent optional bounded
non-negative integers. Present zero remains integer zero. Every missing field
has one `TokenFieldAbsence` carrying that exact field plus a fixed
`EvidenceUnavailableReason`; mixed missing-field reasons are therefore
representable. Duplicate, omitted, or contradictory absence declarations are
rejected.

An unavailable source contains no counts and declares every field absent. A
non-unavailable source supplies at least one count. The contract never
calculates, repairs, or validates arithmetic equality for `total_tokens` and
makes no cached-token inclusion assumption.

## Cost Evidence Decisions

`CostEvidence` keeps provider-reported, estimated, subscription-included, and
unavailable evidence structurally distinct.

Reported and estimated monetary costs require a bounded canonical
non-negative `Decimal` amount and uppercase three-letter currency. JSON uses a
unique plain decimal string; floats, coercion, exponents, negative values,
non-finite values, and oversized decimals are rejected. A real monetary zero
serializes as `"0"`.

Estimated cost additionally requires a complete pricing source ID, version,
and effective timestamp. When nested in an AI invocation, pricing evidence
cannot take effect after invocation start. Subscription-included and
unavailable evidence carry no amount, currency, or pricing fields;
subscription inclusion does not claim zero marginal cost. Unavailable cost
requires one fixed reason.

## Pricing Boundary Decisions

`PricingComponent` records a canonical decimal amount with an explicit
`per_token`, `per_1k_tokens`, or `per_1m_tokens` unit.

`ModelPricing` correlates one pricing identity, provider/model, currency,
source/version, effective interval, and independently optional input, output,
and cached-input components. Every absent component is declared, at least one
real component is required, and missing-component evidence cannot contradict
present components. Nested components are canonically reconstructed so the
record retains no caller-owned model instance.

`PricingCatalog` is a runtime-checkable read-only protocol with:

```text
get_price(provider, model, effective_at) -> ModelPricing | None
```

`None` means no applicable pricing and never means zero. The boundary performs
no calculation or mutation. Only test-local fake catalogs exist; no production
catalog or price table was added.

## Invocation Correlation and Lifecycle

`AIInvocationRecord` is separate from `RunnerInvocationRecord`. It carries:

- its own invocation ID;
- session and run IDs;
- optional runner-invocation correlation;
- provider and model or fixed model-unavailable reason;
- operation;
- terminal success/failure/cancellation status;
- canonical UTC start/completion timestamps and monotonic duration evidence;
- attempt number plus retry/fallback predecessor correlation;
- exact usage and cost evidence; and
- optional bounded `RunErrorCategory` classification only.

First attempts have no predecessor. Later attempts have exactly one retry or
fallback predecessor and cannot reference themselves. Success has no error
classification; failure requires a non-cancellation classification;
cancellation requires the cancellation classification.

Cross-record existence and cycle validation remain future
repository/application responsibilities. `RunRecord`,
`RunnerInvocationRecord`, `OutcomeMetrics`, `TraceRecord`, and WorkflowState
were not modified.

## Canonical, Immutability, and Security Decisions

All public records inherit the established strict frozen Pydantic v2 contract
style: forbidden extras, hidden invalid inputs, canonical plain-JSON output,
UTC `Z` timestamps, complete-tree bounds, revalidated copying, and exact
`from_dict()` reconstruction. Usage reconstruction failures use the fixed
`invalid PMQA usage contract` message without input values, cause, or context.

Caller-owned tuples/lists and nested usage, cost, absence, error-classification
and pricing-component values are not retained as mutable caller state.
Adversarial tests cover retained-model mutation through `__dict__` at
construction boundaries.

The package defines no arbitrary metadata or dynamic payload field. Unknown or
prohibited fields, runtime objects, cycles, excessive depth, excessive string
size, non-finite data, coercion, and invalid identifiers fail without exposing
injected markers. The neutral Run validation helpers and shared security
boundary are reused; no sensitive-key list was duplicated.

The contracts contain no prompt/response content, credential/authentication
state, raw CLI output, command/path/environment data, browser evidence,
provider client, callable, subprocess, runtime control, exception message, or
stack trace.

## Import and Packaging Isolation

`import pmqa.usage` performs no I/O, environment/configuration/distribution
inspection, process launch, discovery, registration, provider/product import,
pricing lookup, or runtime integration. Isolation tests prove it does not load
products, external packs, Playwright, LangGraph/orchestration, reasoning
providers, Application Service, runner implementations, storage, SQLite,
subprocess, or UI packages.

The real offline-built PMQA wheel contains only:

- `pmqa/usage/__init__.py`;
- `pmqa/usage/contracts.py`; and
- `pmqa/usage/pricing.py`

for the new package. External-directory wheel import succeeds. No pricing
data, provider fixture, usage artifact, secret, cache, or runtime output was
added.

## Documentation Status

- Task 5C.1–5C.3 are recorded as architecture-review passed.
- Task 5C.4 is recorded as ready for architecture review.
- Usage/cost remains beside, not inside, Run Contract, reasoning traces, or
  LangGraph state.
- The focused architecture document states this is a contracts and
  pricing-boundary checkpoint, not the Usage Tracking MVP.
- Collection, parsing, calculation, persistence, aggregation, summaries,
  budgets, and optimization remain future work.
- Task 5C remains in progress and unmerged; Task 5B, Task 6, and Task 7 remain
  not started.

## Validation Results

- Focused Task 5C.4 usage/cost/pricing/import tests:
  - `.venv/bin/python -m pytest tests/test_usage_contracts.py tests/test_usage_pricing.py tests/test_usage_imports.py`
  - `68 passed`
- Existing Run, Runner, Application, boundary, and real-wheel packaging
  regressions:
  - `.venv/bin/python -m pytest tests/test_run_contracts.py tests/test_runner_contracts.py tests/test_application_contracts.py tests/test_application_service.py tests/test_boundary_policy.py tests/test_packaging.py`
  - `332 passed`
- Task 4 orchestration regressions:
  - `.venv/bin/python -m pytest tests/test_workflow_runtime.py tests/test_workflow_reducer.py tests/test_supervisor_policy.py tests/test_langgraph_workflow.py`
  - `98 passed, 1 existing LangGraph deprecation warning`
- Full default suite:
  - `.venv/bin/python -m pytest`
  - `1629 passed, 5 skipped, 1 existing LangGraph deprecation warning`
- Existing generated Playwright regressions:
  - `.venv/bin/python -m pytest products/demo/generated_tests`
  - `2 passed`
- Isolated compile check:
  - `PYTHONPYCACHEPREFIX=<temporary-directory> .venv/bin/python -m compileall -q pmqa products`
  - passed
- Markdown relative-link validation:
  - `12 Markdown files validated`
- `git diff --check`:
  - passed before the implementation commit and is rechecked after the
    report-only commit.
- Final worktree and synchronization:
  - rechecked after the report commit and push before the Human Summary.

All new and default tests were offline and provider-free. The only browser
execution was the required existing generated Playwright regression using
locally installed Chromium.

## Remaining Risks and Open Items

- `PricingCatalog` is only a lookup protocol; future implementations must
  independently validate lookup inputs and returned effective intervals.
- Different unavailable reasons are represented per token field; pricing
  components currently share one bounded reason within a `ModelPricing`
  record.
- Cross-record session/run/runner/predecessor existence and cycle checks remain
  future repository/application work.
- Collection, provider/CLI parsing, calculation, persistence, aggregation,
  summaries, budgets, and optimization remain intentionally absent.
- No real pricing source or provider integration has validated the neutral
  contracts yet.

## Scope Confirmation

- Changes are limited to the allowed new usage package, focused tests,
  packaging assertions, four documentation surfaces, and this Coder report.
- Architect- and Reviewer-owned handoff files were not modified.
- No collector, invocation handle, provider adapter/parser, raw provider
  metadata, calculator, estimator service, concrete catalog, pricing table,
  storage, aggregation, CLI, UI, routing, budget, optimization,
  recommendation, feedback, eval, or logging feature was added.
- No Application Service, runner, reasoning provider, Run Contract,
  WorkflowState, LangGraph, Task 5, Product Pack, Supervisor, or existing
  provider behavior changed.
- Task 5B, Task 6, and Task 7 were not started.
- No PR was created and nothing was merged.
- No earlier commit was amended.
- No known blocking finding remains in the Coder implementation.

## Recommended Review Depth

Recommendation: Deep

Reason: Task 5C.4 introduces a new persisted evidence vocabulary whose
missing-data, decimal, correlation, and security invariants will govern future
provider integrations and cost decisions.

## Suggested Reviewer Focus

- Challenge complete, partial, mixed-reason, zero, and unavailable token
  evidence for ambiguity or accidental inference.
- Verify monetary zero, subscription inclusion, unavailable cost, and
  estimated pricing evidence cannot be confused.
- Inspect canonical decimal bounds, effective-time correlation, and
  independent missing pricing components.
- Exercise retry/fallback, model-unavailable, terminal-error, and optional
  runner correlations across all construction paths.
- Recheck deep snapshot isolation, safe errors, import isolation, and actual
  wheel contents.
- Confirm no collection, calculation, persistence, provider, CLI, UI, or
  existing runtime integration entered this checkpoint.

The Coder recommendation is advisory and does not approve the task.
