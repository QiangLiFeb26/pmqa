# PMQA Architecture

PMQA separates reusable QA orchestration from product knowledge and external
systems. The framework is the stable center; products and provider
implementations change around it.

## Layers

```text
Framework
    ↓ defines contracts
Providers
    ↓ supply external capabilities to
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

- `ReasoningProvider` produces an artifact for a task.
- `ExecutionProvider` executes a task and reports its result.
- `StorageProvider` saves and retrieves artifacts.

Only interfaces exist in Sprint 1. Implementations should be composed into a
workflow at an application boundary rather than selected through global state.

### Workflow

The workflow owns sequencing, not product knowledge or external-system code.
Its initial LangGraph is executable but intentionally does no work:

```text
initialize -> explore -> generate_tests -> patrol -> finish
```

Later node behavior should depend on provider contracts and explicit state.

### Product Pack

A product pack is the only home for product-specific configuration, selectors,
rules, and adapters. Add a sibling of `products/demo/` for a new product. A
pack may depend on public framework types; the framework may never depend on a
pack. The demo pack is deliberately empty in this task.

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
                      workflow
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
| Orchestration and nodes | `pmqa/workflow/` |
| Memory lifecycle | `pmqa/memory/` |
| Knowledge relationships | `pmqa/graph/` |
| Provider implementation for persistence | `pmqa/storage/` |
| Product configuration or adapter | `products/<product>/` |

If ownership is unclear, leave a TODO near the caller until a concrete use case
establishes the correct boundary.
