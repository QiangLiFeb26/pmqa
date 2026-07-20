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
- `pmqa/security/` owns dependency-free policies shared by trust boundaries.
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

Project direction and status are maintained separately in the
[product vision](docs/Vision.md) and [roadmap](docs/Roadmap.md). The
[QA workflow loop catalog](docs/architecture/qa-loops.md) describes candidate
memory-backed QA capabilities without assigning implementation status.

## Current scope

Task 1 established the reusable framework foundation: runtime and knowledge
models, single-purpose provider interfaces, product-pack isolation, storage
boundaries, and an initial no-op LangGraph skeleton. That historical skeleton
has been retired and is not an active workflow API.

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

The active Task 4 orchestration APIs are
`pmqa.orchestration.build_pmqa_graph` and
`pmqa.orchestration.run_pmqa_workflow`. They require explicit Explorer,
Knowledge, and Validator agent implementations plus a `ToolRegistry`.
`python -m pmqa.workflow` is intentionally unsupported because silently
constructing placeholder dependencies would misrepresent the active graph.

Task 5 is complete across checkpoints 5.1 through 5.9. The product-owned
`products.demo.application.run_saucedemo_demo` API composes the real SauceDemo
exploration Tool, Explorer, Knowledge agent, Validator, Task 4 graph, strict
verified-artifact handoff, storage, and deterministic test generation. Its
capture-runner seam supports deterministic offline end-to-end execution; using
the default real Playwright capture is an explicit live operation.

The `task5-demo` command is the only supported CLI path that creates verified
SauceDemo knowledge or generates new tests. The legacy Task 2 `explore` and
`generate` names remain recognizable only as retired compatibility stubs; they
cannot capture, persist, load, or generate anything. `test-generated` remains
available only to execute the already generated regression file. Task 3
reasoning providers are not selected by `task5-demo`.

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

## Run the authoritative workflow and tests

Run the complete real Task 5 multi-agent workflow, persist its independently
verified knowledge, and generate the two deterministic Playwright tests:

```bash
pmqa task5-demo --product demo
# equivalent: python -m pmqa.cli task5-demo --product demo
```

The command defaults to headless capture. Pass `--headed` to show the browser,
or use `--workflow-id`, `--product-version`, `--goal`, and `--max-iterations`
to set the bounded workflow inputs explicitly. It writes
`products/demo/artifacts/knowledge.json` and
`products/demo/generated_tests/test_saucedemo_generated.py`. It intentionally
does not run pytest; execute the generated tests separately:

```bash
pmqa test-generated --product demo
```

The retired names return exit code 2 with static guidance to use the
authoritative command:

```bash
pmqa explore --product demo   # retired; performs no capture or persistence
pmqa generate --product demo  # retired; performs no load or generation
```

The Task 2 execution provider, capture implementation, storage provider, and
generator remain reusable library and regression-test infrastructure. They are
not alternate CLI routes around Task 5 validation. The committed generated
test fixture embeds the verified locator inputs used to create it, so
`test-generated` can run in a fresh checkout without a tracked runtime
knowledge artifact.

The public demo uses the `ReasoningProvider` boundary with a deterministic,
rule-based implementation and records `deterministic-rule-based` provenance in
the artifact. Manual Copilot and Copilot CLI provider boundaries exist, but the
default validation path remains fully offline. The `reason-manual` and
`reason-copilot-cli` demonstrations require knowledge produced by a successful
`task5-demo` run first.

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
boundary; it is not an enterprise PHI scrubber. The Task 5 graph does not
invoke the Task 3 reasoning service. Patrol, stale detection, review,
self-healing, prompt repositories, replay, and provider-selection policies
remain out of scope.

## Roadmap checkpoint

Task 4 is complete at implementation checkpoint
`86214d76d2f12a2b70793b6ca28da4e1e5f3d858`, which includes supervisor and
recovery routing from PR #15 and LangGraph assembly plus final-cycle iteration
semantics from PR #16. Task 4.8 closes review findings around shared boundary
policy and the retired Task 1 graph before Task 5.

Task 5.6 provides the real SauceDemo product composition API while keeping the
framework product-agnostic. Task 5.7 adds a strict post-workflow handoff that
persists only the Validator's independent VERIFIED snapshot through the
existing `StorageProvider` boundary and passes that snapshot to the existing
deterministic SauceDemo generator. Task 5.8 adds the product-owned application
composition and supported `task5-demo` CLI. Task 5.9 retires the unvalidated
legacy CLI write/read paths and removes their tracked runtime artifact. The NEW
candidate remains unchanged and is never stored as approved memory.
Reasoning-provider integration remains a future checkpoint; Tasks 6 and 7 have
not started.

Task 5 passed cumulative architecture review and was merged into `main`
through PR #20. Its final branch head was
`fdba63e3525f055b395a4b40775b42d284541af3`, and the merge commit is
`c9167fd4409b22ac89899f0010cda986982e04fe`. `task5-demo` remains the
authoritative SauceDemo workflow, and the legacy `explore` and `generate`
commands remain retired.

Task 5A — Product Pack Adoption Foundation is the next phase before the
existing Task 6 recommendation work and is in progress through Task 5A.4.
Task 5A.1 adds the experimental strict manifest and architecture contract;
Task 5A.2 explicitly loads only manifest metadata from one approved installed
distribution and requires complete equality with an expected manifest. It
does not discover packs globally, load arbitrary paths, run adapters or
browsers, or provide sandboxing. The selected distribution is trusted Python
code. The TypeScript execution bridge, scaffolding, SauceDemo migration, and
future MDE pilot have not started. Task 5A.3 defines only the immutable,
language-neutral Bridge Protocol v1 contracts and packaged JSON schema:
bounded actions cross
the request boundary, and existing structured exploration evidence is the only
product observation returned on success. Credentials remain outside protocol
payloads. Task 5A.4 adds bounded process transport for one explicit
operator-approved executable and compiled bridge artifact. Canonical protocol
JSON travels only through stdin/stdout; stderr and raw process failures remain
behind fixed safe errors, and the manifest cannot specify commands. Credentials
remain in the inherited private execution environment and are not inspected or
serialized by PMQA. The runner is not a security sandbox, and no Playwright
Product Pack, scaffold, SauceDemo migration, or MDE integration exists yet.
This is not a stable Product Pack SDK v1. Task 6 and Task 7 have not started.
See the
[authoritative roadmap](docs/Roadmap.md) for phase status and the
[Product Pack adoption architecture](docs/architecture/product-pack-adoption.md)
for the dependency, ownership, trust-boundary, and versioning decisions.
