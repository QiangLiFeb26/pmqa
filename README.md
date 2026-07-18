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

## Prerequisites

PMQA requires Python 3.9 or later and network access to SauceDemo. Task 2 uses
Python Playwright with Chromium.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m playwright install chromium
```

The demo supports public SauceDemo credentials strictly as explicit demo-only
defaults. Override them without changing files when needed:

```bash
export PMQA_DEMO_USERNAME='standard_user'
export PMQA_DEMO_PASSWORD='secret_sauce'
```

## Explore, generate, and test

Run the bounded deterministic exploration, generate tests from its persisted
knowledge, and execute the generated tests:

```bash
python -m pmqa.cli explore --product demo
python -m pmqa.cli generate --product demo
python -m pmqa.cli test-generated --product demo
```

Exploration writes `products/demo/artifacts/knowledge.json`. Generation writes
`products/demo/generated_tests/test_saucedemo_generated.py`. The generated
tests load their selectors from the stored artifact at runtime.

The public demo uses the `ReasoningProvider` boundary with a deterministic,
rule-based implementation, and records that provenance in the artifact. An
approved adapter boundary exists for future GitHub Copilot reasoning, but no
Copilot or external LLM integration is configured in this task.

Run all offline framework tests separately with:

```bash
pytest tests
```

## Current limitations

Exploration is SauceDemo-specific, headless, capped at four known-safe steps,
and is not a crawler. The normalizer only enforces a basic sensitive-key
boundary; it is not an enterprise PHI scrubber. Patrol, stale detection,
review, self-healing, and external reasoning integrations remain out of scope.

## Future roadmap

Future work can add provider implementations, persistent memory, real workflow
behavior, and enterprise Playwright integration. Each product remains isolated
in its own product pack while the framework stays product-agnostic. These are
extension points, not commitments to a specific implementation.
