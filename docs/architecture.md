# PMQA Architecture

PMQA separates reusable QA orchestration from product knowledge and external
systems. The framework is the stable center; products and provider
implementations change around it.

## Layers

```text
Framework
    ↓ defines contracts and trust boundaries
Providers
    ↓ perform reasoning or execution through
Reasoning
    ↓ persists correlated audit history in
Trace
    ↓ supplies validated results to
Workflow
    ↓ operates with a selected
Product Pack
    ↓ contributes product knowledge to
Memory
```

### Framework

The `pmqa` package owns shared runtime and knowledge models, provider contracts,
and workflow orchestration. Framework modules must not import from `products`.
That rule keeps a demo or enterprise integration from becoming an implicit
framework dependency.

### Providers

Providers isolate external capabilities behind three single-purpose contracts:

- `ReasoningProvider` returns a validated structured reasoning response.
- `ExecutionProvider` executes a task and reports its result.
- `StorageProvider` saves and retrieves artifacts.

Provider implementations are composed at an application boundary rather than
selected through global state. Task 3 includes deterministic, manual Copilot,
and Copilot CLI reasoning providers; product-specific execution remains in its
product pack.

### Reasoning

`pmqa/reasoning/` owns scrubbed request and response contracts, deterministic
Prompt Packages, reasoning providers, and the small execution service that
sequences them. The request validator is the final trust-boundary gate: it
rejects prohibited keys even when a caller constructs a `ReasoningRequest`
directly and bypasses the scrubber.

`pmqa/security/boundary_policy.py` is the neutral, dependency-free home for
prohibited-key policy shared by serializable boundaries. Reasoning uses the
common policy unchanged. Workflow state extends it with `connection`,
`llm_client`, `locator`, and `provider_instance`, which are state-specific
runtime handles. This explicit construction prevents the common subset from
drifting while preserving the stricter workflow boundary.

Capture-time normalization in `pmqa/core/normalization.py` intentionally has a
separate policy because capture and reasoning operate at different trust
boundaries. They should not be unified unless their semantics become identical.

### Trace

`pmqa/trace/` owns provider-independent reasoning history. It stores canonical
requests and responses plus safe Prompt Package and scrub-audit correlation;
it never stores raw pre-scrub input or provider transport state. See
[Task 3 reasoning architecture](task-3-architecture.md) for the complete flow.

### Workflow

`pmqa/workflow/` owns immutable, JSON-compatible workflow state plus typed
agent, tool, capability, and patch contracts. `pmqa/runtime/` validates and
executes exactly one agent invocation, while `pmqa/supervisor/` makes pure,
deterministic routing decisions. Product knowledge and external-system code do
not belong in these layers.

`pmqa/orchestration/` is a thin LangGraph adapter around those contracts:

```text
supervisor -> execute Explorer -> supervisor
           -> execute Knowledge -> supervisor
           -> execute Validator -> supervisor
           -> complete | fail | terminate
```

The supervisor correlates every validation result with completed Validator
history and requires failed-validation recovery to follow Explorer, Knowledge,
and Validator order. `max_iterations` counts Explorer cycles and gates only a
new Explorer invocation. Once the final allowed Explorer cycle begins, its
Knowledge and Validator steps may finish before the terminal decision.

LangGraph owns control flow only. The policy, reducer, runtime validation, and
domain state remain independently testable and do not import LangGraph.
`build_pmqa_graph` and `run_pmqa_workflow` are the active Task 4 graph APIs;
callers must inject Explorer, Knowledge, and Validator agents and a
`ToolRegistry`. The Task 1 no-op graph is retired, and the workflow package is
not a runnable substitute for application composition. Task 5 will provide
real domain agents and tools.

### Product Pack

A product pack is the only home for product-specific configuration, selectors,
rules, and adapters. Add a sibling of `products/demo/` for a new product. A
pack may depend on public framework types; the framework may never depend on a
pack. The demo pack contains the bounded SauceDemo vertical slice.

### Memory

Memory is durable product knowledge represented by the JSON-compatible models
in `pmqa/models/`. Its lifecycle and persistence are future concerns. Keeping
the models independent from storage allows local, database, or enterprise
storage implementations to be introduced without changing workflow contracts.

Exploration evidence is distinct from verified product knowledge. Evidence is
an immutable, runtime-free record of what an external capture tool observed;
it does not carry `Lifecycle` verification state and is not a
`KnowledgeArtifact`. The intended flow is:

```text
external capture tool
    -> immutable exploration evidence
    -> serialized WorkflowState evidence payload
    -> Knowledge agent
    -> existing Page, Element, Locator, Interaction, and KnowledgeArtifact models
```

Task 5.1 defines only the evidence contracts and their explicit workflow
serialization boundary. Concrete Playwright tools belong to product packs;
`products/demo` contains the bounded SauceDemo capture and Tool adapter. All
Browser, Page, Locator, credential, and Playwright objects remain inside that
product-owned capture boundary. Only serialized `ExplorationEvidence` crosses
the Tool boundary into workflow payloads.

The product-owned SauceDemo Explorer depends only on an injected Tool-dispatch
callable. It neither imports nor instantiates Playwright, the concrete Tool, or
the capture implementation. It validates the returned evidence and requests
an append-only serialized evidence update through `AgentResult` and
`WorkflowStatePatch`; the reducer remains the state mutation boundary.

The Tool and Explorer are independently executable through the existing
runtime contracts. The product-owned Knowledge agent consumes exactly one
unprocessed serialized evidence batch and deterministically maps it into the
existing `Page`, `Element`, `Locator`, `Interaction`, and `KnowledgeArtifact`
models. A correlated candidate envelope, rather than a live domain object, is
appended through `WorkflowStatePatch.knowledge_candidates_to_add`.

All mapped candidate items have `ArtifactStatus.NEW` with no verification
timestamp. The product-owned Validator deterministically compares exactly one
unvalidated candidate with the candidate rebuilt from its source evidence. A
matching candidate appends a passed result containing a separate
`KnowledgeArtifact` snapshot whose items are `ArtifactStatus.VERIFIED`; the
stored NEW candidate is not mutated.

A structurally valid candidate mismatch appends a domain-level failed result
with completed Validator history and no fatal workflow error. The unchanged
Supervisor policy therefore starts its existing Explorer, Knowledge,
Validator recovery sequence. Malformed or ambiguous state instead produces a
failed Validator invocation, no validation result, and the stable fatal error
`validator_execution_failed`.

This baseline Validator does not invoke a reasoning provider. Production
composition, persistence, CLI integration, and generated-test integration do
not exist yet.

## Dependency direction

Dependencies point inward toward shared models and contracts:

```text
products ──> pmqa public models/contracts <── provider implementations
                         ↑
               reasoning and workflow
```

Cross-layer behavior should be assembled through composition. Do not add
product checks to framework nodes, provider-specific fields to core models, or
miscellaneous helpers without a concrete shared use case.

## Where new functionality belongs

| New concern | Location |
| --- | --- |
| Runtime coordination data | `pmqa/core/` |
| Product-knowledge schema | `pmqa/models/` |
| Structured exploration-evidence schema | `pmqa/models/exploration.py` |
| External capability contract | `pmqa/providers/` |
| Reasoning trust boundary and execution | `pmqa/reasoning/` |
| Shared serializable-boundary policy | `pmqa/security/` |
| Reasoning trace persistence | `pmqa/trace/` |
| Workflow, agent, tool, and patch contracts | `pmqa/workflow/` |
| Single-agent execution | `pmqa/runtime/` |
| Supervisor routing policy | `pmqa/supervisor/` |
| LangGraph assembly | `pmqa/orchestration/` |
| Memory lifecycle | `pmqa/memory/` |
| Knowledge relationships | `pmqa/graph/` |
| Provider implementation for persistence | `pmqa/storage/` |
| Product configuration or adapter | `products/<product>/` |

If ownership is unclear, leave a TODO near the caller until a concrete use case
establishes the correct boundary.

## Documentation authority

- `README.md` introduces the project, setup, and active entry points.
- `docs/Vision.md` owns long-term product purpose and principles.
- `docs/Roadmap.md` owns phase status and planned work.
- Versioned product specifications own scoped functional behavior when active.
- This guide owns technical boundaries and implementation decisions.
- `notes/prompts/`, if introduced, contains historical, non-authoritative work.

The stable QA-loop catalog is maintained at
`docs/architecture/qa-loops.md`; no root-level duplicate is authoritative.
