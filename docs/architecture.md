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

`pmqa/reasoning/` owns scrubbed request and response contracts, the canonical
prohibited-key policy, deterministic Prompt Packages, reasoning providers, and
the small execution service that sequences them. The request validator is the
final trust-boundary gate: it rejects prohibited keys even when a caller
constructs a `ReasoningRequest` directly and bypasses the scrubber.

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
| External capability contract | `pmqa/providers/` |
| Reasoning trust boundary and execution | `pmqa/reasoning/` |
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
