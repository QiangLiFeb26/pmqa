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
- `pmqa/reasoning/` owns scrubbed reasoning contracts, Prompt Packages,
  providers, and provider-independent execution sequencing.
- `pmqa/trace/` persists canonical reasoning history and audit correlation.
- `pmqa/workflow/` owns serializable workflow, agent, tool, and patch contracts.
- `pmqa/runtime/` executes one validated agent invocation at a time.
- `pmqa/supervisor/` owns deterministic routing and recovery policy.
- `pmqa/orchestration/` adapts those contracts to LangGraph execution.
- `pmqa/memory/`, `pmqa/graph/`, and `pmqa/storage/` are reserved boundaries
  for future framework capabilities.
- `pmqa/product_pack/` defines the boundary through which products integrate.
- `products/<product>/` contains product-owned configuration and adapters.

See [the architecture guide](docs/architecture.md) for dependency rules and
extension guidance.

## Current scope

Task 1 established the reusable framework foundation: runtime and knowledge
models, single-purpose provider interfaces, product-pack isolation, storage
boundaries, and an executable no-op LangGraph skeleton:

`initialize -> explore -> generate_tests -> patrol -> finish`

Task 2 adds the first product-specific vertical slice under `products/demo/`.
It performs bounded SauceDemo exploration with Python Playwright, persists
structured knowledge, and deterministically generates two Playwright tests
from the stored interaction, page, element, and locator relationships.

Task 3 adds the reasoning trust boundary: deterministic scrubbing, canonical
requests and responses, shared Prompt Packages, deterministic/manual
Copilot/Copilot CLI providers, SQLite traces, and a compact execution service.
See [the Task 3 architecture](docs/task-3-architecture.md) for its execution
flow and responsibility boundaries.

Task 4 adds the provider-independent multi-agent runtime foundation: immutable
workflow state, typed agent and tool contracts, deterministic patch reduction,
single-agent runtime execution, supervisor routing, validation-history
correlation, and a thin LangGraph adapter for Explorer, Knowledge, and
Validator cycles. Recovery follows the validated invocation history. The
iteration limit gates only the start of a new Explorer cycle, so Knowledge and
Validator can finish the final allowed cycle before completion or termination.

The Task 2 SauceDemo CLI and Task 3 reasoning service are not yet composed into
the Task 4 multi-agent graph. The graph is an executable framework boundary
with injected agents and tools, not the path used by the demo CLI commands.

## Prerequisites

PMQA requires Python 3.9 or later and network access to SauceDemo. Task 2 uses
Python Playwright with Chromium.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
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
rule-based implementation and records `deterministic-rule-based` provenance in
the artifact. Manual Copilot and Copilot CLI provider boundaries exist, but the
default validation path remains fully offline.

Run the completed Task 3 flow offline with:

```bash
pmqa task3-demo --database /tmp/pmqa-task3.sqlite3
```

Run all offline framework tests separately with:

```bash
pytest tests
```

## Current limitations

Exploration is SauceDemo-specific, headless, capped at four known-safe steps,
and is not a crawler. The normalizer only enforces a basic sensitive-key
boundary; it is not an enterprise PHI scrubber. The Task 4 LangGraph adapter
uses injected contract implementations and is not connected to the Task 2 CLI
or Task 3 reasoning service. Patrol, stale detection, review, self-healing,
prompt repositories, replay, and provider-selection policies remain out of
scope.

## Future roadmap

Task 4 is complete at implementation checkpoint
`86214d76d2f12a2b70793b6ca28da4e1e5f3d858`, which includes supervisor and
recovery routing from PR #15 and LangGraph assembly plus final-cycle iteration
semantics from PR #16. This is the proposed Task 5 starting checkpoint.

Future work can compose real agent implementations with the Task 4 runtime,
add persistent memory, and integrate enterprise Playwright automation. Each
product remains isolated in its own product pack while the framework stays
product-agnostic. These are extension points, not commitments to a specific
implementation.
