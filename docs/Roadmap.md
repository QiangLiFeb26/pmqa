# PMQA Roadmap

This document is the authoritative project status and phase roadmap. Product
purpose belongs in [Vision](Vision.md); implementation boundaries belong in
[Architecture](architecture.md).

## Status

| Phase | Status | Outcome |
| --- | --- | --- |
| Task 1 — Foundation and architecture | Complete | Established the reusable framework layout, core knowledge models, provider contracts, product-pack boundary, and initial graph skeleton. |
| Task 2 — SauceDemo vertical slice | Complete | Added bounded Playwright exploration, persisted product knowledge, and deterministic artifact-driven test generation. |
| Task 3 — Reasoning trust boundary | Complete | Added provider-independent reasoning contracts, scrubbing, deterministic/manual/Copilot CLI providers, prompt packages, and SQLite trace storage. |
| Task 4 — Multi-agent runtime | Complete | Added typed state, agent and tool contracts, deterministic reduction and routing, runtime execution, validated recovery, and LangGraph assembly. |
| Task 4.8 — Closure cleanup | Complete | Consolidated prohibited-key policy and retired the misleading Task 1 graph entry point. |
| Task 5 — Real agent composition | In progress | Tasks 5.1–5.5 completed evidence through Validator checkpoints; Task 5.6 adds the product-owned end-to-end workflow composition API for review. |

## Task 4 closure

Task 4 delivered:

- immutable, JSON-compatible workflow-state contracts;
- typed agent contracts and constrained state updates;
- typed tool contracts and deterministic tool registration;
- a deterministic workflow-state reducer;
- a validated one-agent runtime pipeline;
- deterministic supervisor policy;
- failed-validation recovery routing;
- complete validation-history correlation;
- thin LangGraph workflow assembly; and
- final allowed-cycle max-iteration semantics.

The Task 4 implementation checkpoint is
`86214d76d2f12a2b70793b6ca28da4e1e5f3d858`, incorporating PRs #15 and #16.
The documentation-only Task 4 closure commit follows that checkpoint.

Task 4.8 is a narrow closure cleanup. It centralizes the common prohibited-key
policy at a neutral dependency layer, preserves explicit workflow-only runtime
restrictions, and retires the disconnected Task 1 no-op graph and executable
entry point. It does not add agents, tools, or Task 5 behavior.

## Task 5 checkpoints

Tasks 5.1–5.5 completed the neutral exploration-evidence boundary, the
product-owned Playwright exploration Tool, the real SauceDemo Explorer, and
deterministic Knowledge and Validator behavior with failed-validation recovery.
Task 5.6 is the product-owned end-to-end workflow composition checkpoint. It
wires the real Tool and all three real agents through the existing Task 4 graph
and supports deterministic offline execution. CLI integration,
reasoning-provider integration, verified-artifact persistence, and generated-
test handoff remain later checkpoints. Tasks 6 and 7 are outside the current
implementation scope.
