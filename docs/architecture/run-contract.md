# Canonical PMQA Run Contract

## Status

Task 5C.1 is **Ready for architecture review**. It establishes the local
application/run contract layer before the company-side Task 5B read-only pilot.
It does not start Task 5B, Task 6, or Task 7.

## Boundary

The canonical Run Contract is provider-neutral application-level correlation:

```text
Interface / future CLI
        ↓
Future Application Service
        ↓
Canonical Run Contract
        ↓
Existing LangGraph workflow and future PMQARunner
```

The contracts describe what workflow was requested, one PMQA run and its
lifecycle, safe external references, structured results, logical artifacts,
safe errors, runner invocation attempts, and optional reliable outcome
metrics. They do not execute workflows, launch processes, call providers,
persist usage, calculate cost, access Azure DevOps, or implement a UI.

## Run Contract and WorkflowState

`RunRequest`, `PMQARunContext`, and `RunRecord` are application contracts.
They correlate a user request with a selected workflow and future runner. They
are suitable for future service and persistence boundaries.

LangGraph `WorkflowState` remains checkpoint state for agent routing,
reduction, recovery, and termination. It retains its existing domain-specific
evidence and validation history. Run Contract fields are not added to
`WorkflowState`, and no LangGraph behavior changes in Task 5C.1.

## Run Contract and the future Runner

The Run Contract carries `runner_id` and runner invocation identifiers but
does not define `PMQARunner`, a registry, process configuration, provider
clients, cancellation tokens, or execution behavior. A future Application
Service will validate a `RunRequest`, select registered workflow and runner
implementations, and use the canonical records for correlation.

`RunnerInvocationRecord` describes one logical call to that future runner. Its
attempt number and retry/fallback links describe application execution
correlation only. It is not a model, provider, token-usage, or pricing
invocation. Future usage records may reference the run or invocation without
being embedded in them.

## Run Contract and reasoning traces

`TraceRecord` remains the audit record for the reasoning trust boundary,
including scrubbed request/response material and provider-independent trace
correlation. `RunRecord` instead describes the application outcome. Neither
record replaces the other, and Task 5C.1 does not change reasoning providers
or trace storage.

## Separate operational records

Usage, cost, logs, feedback, and eval data deliberately remain outside
`RunRecord`:

- usage and pricing evolve independently and may aggregate across invocations;
- logs have different volume, retention, and access-control requirements;
- feedback is user-authored data with its own lifecycle;
- eval results compare runs and may be produced after a run completes; and
- outcome metrics contain only optional, reliable product outcomes, not
  inferred usage or cost.

Task 5C.1 therefore defines no `UsageRecord`, `CostSummary`, pricing catalog,
log entry, feedback, or eval model.

## Contract safety

All contracts are frozen Pydantic v2 models with forbidden extra fields and
safe validation output. Persisted reconstruction accepts only bounded,
canonical plain JSON. Dynamic workflow inputs and structured result data use
the shared neutral prohibited-key policy, reject runtime-only fields,
non-finite numbers, cycles, excessive nesting, and mutable container
subclasses, then freeze nested mappings and collections.

Run identifiers use bounded lowercase ASCII segments separated by `.`, `_`,
`-`, or `:`. This supports UUID-style IDs, lowercase names, numeric external
IDs, and safe composed correlation while excluding whitespace, paths, URLs,
shell syntax, Unicode ambiguity, empty segments, and traversal.

Canonical typed fields such as `session_id` and `run_id` are allowed. The
dynamic payload policy is not recursively applied to the contract's own typed
fields. Artifact records contain only logical storage keys and lowercase
SHA-256 digests, never artifact contents or storage implementations.

## Compatibility

The dataclass `pmqa.core.RunContext` remains unchanged as a legacy
compatibility contract. New callers import the application contracts from
`pmqa.run`; they are intentionally not exported from top-level `pmqa`.

No runner, Application Service, Workflow Registry, UI, Copilot integration,
Azure DevOps access, usage/cost tracking, or persistence repository is
implemented. Existing WorkflowState serialization, LangGraph semantics,
reasoning traces, Product Pack behavior, CLI behavior, and generated
Playwright output remain unchanged.
