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
| Task 5 — Real agent composition | Complete | Checkpoints 5.1–5.9 provide the real workflow, strict verified-artifact handoff, supported SauceDemo demo application/CLI, and retired legacy bypasses; merged through PR #20. |
| Task 5A — Product Pack Adoption Foundation | In progress | Task 5A.1 defines the manifest boundary, Task 5A.2 completes explicit manifest loading, and Task 5A.3 defines Bridge Protocol v1 contracts for architecture review. Runtime bridge work has not started. |

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

Tasks 5.1–5.6 completed the neutral exploration-evidence boundary, the
product-owned Playwright exploration Tool, the real SauceDemo Explorer, and
deterministic Knowledge and Validator behavior with failed-validation recovery.
The product-owned composition API wires the real Tool and all three real agents
through the existing Task 4 graph and supports deterministic offline execution.
Task 5.7 is the strict verified-artifact handoff checkpoint: only the
Validator's independent VERIFIED snapshot may pass through the existing
storage boundary and deterministic test generator. The stored NEW candidate is
never persisted as approved memory. Task 5.8 is the final Task 5 implementation
checkpoint: a product-owned application composes workflow, handoff, storage,
and generation, while the generic CLI dynamically loads it only for
`--product demo`. The command never runs generated tests automatically. The
Task 5.9 checkpoint retires the legacy `explore` and `generate` CLI paths as
static migration stubs. They cannot access product capabilities or knowledge;
only `task5-demo` may create authoritative knowledge or generate new tests.
The underlying Task 2 components remain reusable library/test infrastructure,
and `test-generated` only executes the committed/generated regression tests.
Task 5 passed cumulative architecture review and is complete across checkpoints
5.1 through 5.9. It was merged into `main` through PR #20 from final branch
head `fdba63e3525f055b395a4b40775b42d284541af3`; the merge commit is
`c9167fd4409b22ac89899f0010cda986982e04fe`. `task5-demo` is the
authoritative SauceDemo workflow, while the legacy `explore` and `generate`
commands remain retired. Tasks 6 and 7 have not started.

## Task 5A — Product Pack Adoption Foundation

**Status: In progress.** Task 5A is planned before the existing recommendation
work in Task 6. At a high level, it will:

- establish a reusable Product Pack contract;
- support explicit external/private Product Packs;
- define a safe, versioned TypeScript Playwright bridge;
- provide Product Pack validation and scaffolding; and
- validate the abstraction with SauceDemo before a future MDE pilot.

No stable Product Pack SDK, TypeScript execution bridge, MDE integration, or
new CLI command is implemented by these checkpoints.

Task 5A.1 is the experimental Product Pack manifest and architecture-contract
implementation checkpoint. It defines a frozen, strict, JSON-compatible
manifest with exact version, identity, display-name, and bounded-capability
fields, plus the long-term ownership, dependency, trust-boundary, and adoption
decisions. It is complete on this cumulative Task 5A branch and is not a stable
Product Pack SDK v1. See the
[Product Pack adoption architecture](architecture/product-pack-adoption.md).

Task 5A.2 adds an explicit loader for manifest metadata from one
operator-approved installed distribution. It uses the fixed
`pmqa.product_packs` group, selects the entry-point name matching the expected
`pack_id`, and requires the loaded plain dictionary to equal the complete
expected manifest after safe reconstruction. It performs no global discovery,
arbitrary-path loading, adapter execution, browser execution, or sandboxing;
the selected Python distribution is trusted code. Task 5A.2 is complete on
this cumulative Task 5A branch.

Task 5A.3 defines immutable Bridge Protocol v1 request and response contracts,
safe reconstruction and correlation, and a mechanically verified packaged JSON
schema. It carries only bounded actions and existing structured exploration
evidence; credentials remain inside the future private product execution
boundary. Task 5A.3 is ready for architecture review and is not merged or
complete on `main`. It is not a stable public SDK.

Task 5A.4 will implement the bounded TypeScript/Node execution bridge. No Node,
subprocess, TypeScript, Playwright runner, scaffolding, SauceDemo migration, or
future read-only MDE pilot work has started. Task 6 and Task 7 have not started.
