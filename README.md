# PMQA

PMQA is a reusable Product Memory QA framework. It gives QA workflows a stable
way to combine product-specific knowledge with replaceable reasoning,
execution, and storage providers. A product integrates through a product pack;
product details do not belong in the framework itself.

## Problem

QA automation often mixes orchestration, tool integrations, and knowledge of a
particular product. That makes the automation difficult to reuse and product
knowledge difficult to maintain. PMQA separates those concerns so workflows
can evolve without embedding product configuration in framework code.

## Architecture

- `pmqa/core/` holds the framework's shared runtime types.
- `pmqa/models/` holds JSON-compatible product-knowledge types.
- `pmqa/providers/` defines contracts for reasoning, execution, and storage.
- `pmqa/workflow/` owns orchestration and the executable graph.
- `pmqa/memory/`, `pmqa/graph/`, and `pmqa/storage/` are reserved boundaries
  for future framework capabilities.
- `pmqa/product_pack/` defines the boundary through which products integrate.
- `products/<product>/` contains product-owned configuration and adapters.

See [the architecture guide](docs/architecture.md) for dependency rules and
extension guidance.

## Current scope

Sprint 1 provides foundational models, provider interfaces, and an executable
no-op workflow with these stages:

`initialize -> explore -> generate_tests -> patrol -> finish`

There is intentionally no exploration, AI, Playwright, test generation,
review, verification, or self-healing behavior yet.

## Quick start

PMQA requires Python 3.9 or later.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pmqa.workflow
pytest
```

The workflow command exits after running every no-op stage successfully.

## Future roadmap

Future work can add provider implementations, persistent memory, real workflow
behavior, and enterprise Playwright integration. Each product remains isolated
in its own product pack while the framework stays product-agnostic. These are
extension points, not commitments to a specific implementation.
