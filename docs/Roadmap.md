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
| Task 5A — Product Pack Adoption Foundation | Complete | Task 5A.1–5A.6 establish the experimental manifest, explicit loading, protocol, bounded transport, scaffolding/conformance, and external SauceDemo architecture-validation slice; merged through PR #22. |
| Task 5C — Local Application and Run Layer | In progress | Task 5C.1 and 5C.2 passed architecture review; Task 5C.3 adds explicit immutable registries and a synchronous single-attempt Application Service and is ready for architecture review. |
| Task 5B — Company-side MDE Read-Only Pilot | Not started | Validate Product Pack assumptions in a company-managed, private, read-only pilot before API v1 stabilization. |

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

**Status: Complete.** Task 5A.1–5A.6 completed cumulative architecture review
and were merged into `main` through PR #22 using a merge commit. The final
implementation branch head was
`b52643067ce0dc01c9204acb10acbacdb51395e1`; the `main` merge commit is
`2a1431e7cd93e059c904e44fc4cc30eafa122a0e`. The Product Pack foundation is
now present on `main`, but the Product Pack API remains experimental and is
not stable SDK v1.

Task 5A precedes the existing recommendation work in Task 6. Across checkpoints
5A.1–5A.6, it provides:

- establish a reusable Product Pack contract;
- support explicit external/private Product Packs;
- define a safe, versioned TypeScript Playwright bridge;
- provide Product Pack validation and scaffolding; and
- validate the abstraction with SauceDemo before a future MDE pilot.

No stable Product Pack SDK, MDE integration, runtime bridge-execution CLI, or
product migration is implemented by these checkpoints.

Task 5A.1 is the experimental Product Pack manifest and architecture-contract
implementation checkpoint. It defines a frozen, strict, JSON-compatible
manifest with exact version, identity, display-name, and bounded-capability
fields, plus the long-term ownership, dependency, trust-boundary, and adoption
decisions. It is complete and is not a stable Product Pack SDK v1. See the
[Product Pack adoption architecture](architecture/product-pack-adoption.md).

Task 5A.2 adds an explicit loader for manifest metadata from one
operator-approved installed distribution. It uses the fixed
`pmqa.product_packs` group, selects the entry-point name matching the expected
`pack_id`, and requires the loaded plain dictionary to equal the complete
expected manifest after safe reconstruction. It performs no global discovery,
arbitrary-path loading, adapter execution, browser execution, or sandboxing;
the selected Python distribution is trusted code. Task 5A.2 is complete.

Task 5A.3 completes immutable Bridge Protocol v1 request and response contracts,
safe reconstruction and correlation, and a mechanically verified packaged JSON
schema. It carries only bounded actions and existing structured exploration
evidence; credentials remain inside the private product execution boundary. It
is complete and is not a stable public SDK.

Task 5A.4 adds bounded transport for one explicitly configured compiled
TypeScript/Node bridge process. The manifest cannot specify commands; canonical
Bridge Protocol v1 JSON travels through stdin/stdout, while bounded stderr and
raw process details remain behind fixed safe errors. Credentials stay in the
inherited private execution environment and are never inspected or serialized
by PMQA. The runner is transport isolation, not a security sandbox. Task 5A.4
is complete.

Task 5A.5 provides a deterministic minimal external Python distribution and
direct TypeScript bridge source scaffold, plus offline source-conformance and
product-neutral CLI commands. It writes only to an explicit operator-selected
target, uses no-replace publication, recommends a separate private Product Pack
source location, and generates a non-operational backend that fails closed.
Protocol and process-boundary files remain scaffold-owned; the consumer-owned
backend implementation may change while preserving a bounded factory contract.
Custom source conformance is not runtime verification. Product Pack SemVer and
Python distribution PEP 440 versions are independent inputs. Consumer
credentials remain in the execution environment. The baseline is an explicitly
versioned, consumer-approved direct TypeScript Playwright dependency;
Playwright MCP remains prohibited. Scaffolding and validation launch no browser
or external Product Pack. The API remains experimental rather than stable SDK
v1. Task 5A.5 is complete.

Task 5A.6 validates the abstraction with an explicitly loaded external
SauceDemo Product Pack example. A product-neutral exploration Tool maps the
existing immutable Tool request to one Bridge Protocol v1 request and returns
validated evidence to the existing Explorer. A parallel SauceDemo composition
reuses the existing Knowledge and Validator agents, Task 4 graph, strict
artifact handoff, storage, and generation. The consumer-owned backend uses one
exact direct TypeScript Playwright dependency and child-environment
credentials; it contains no MCP integration. Default verification is offline,
while opt-in temporary builds prove the real Node bridge and live Playwright
workflow. The Product Pack API and Bridge Protocol remain independent version
axes. A separate bounded JSON-only bridge correlation identifier preserves the
established Task 5 domain identities without weakening manifest or action
identifiers. Python and TypeScript use the same canonical key-sorted compact
UTF-8 JSON SHA-256 structural fingerprint; a fixed vector and opt-in live
comparison distinguish offline fake parity from real cross-language parity.
Task 5A.1–5A.6 have completed cumulative architecture review. The public
`pmqa task5-demo --product demo` command and
direct Python SauceDemo implementation remain the authoritative stable Task 5
baseline. The external SauceDemo Product Pack remains an architecture-
validation example outside the PMQA wheel; it does not replace or redirect the
public demo. Task 5A remains experimental and is not a stable Product Pack SDK
v1. API v1 stabilization follows only after evidence from both SauceDemo and
MDE.

## Task 5C — Local Application and Run Layer

**Task 5C.1 status: Architecture review passed. Task 5C.2 status: Architecture
review passed. Task 5C.3 status: Ready for architecture review.** Task 5C exists to
establish the local application/run layer before the company-side Task 5B
pilot. Its first checkpoint defines the versioned, provider-neutral contracts
for requests, workflow metadata, safe run correlation, structured results,
logical artifact references, safe errors, runner invocation lifecycle, and
optional reliable outcome metrics.

The Run Contract is application-level correlation. It does not replace
LangGraph `WorkflowState`, absorb the separate runner boundary, or combine
runner invocations with future model/provider usage records. Usage, cost, logs,
feedback, evals, and reasoning traces remain separate records with independent
retention and trust boundaries. The old `pmqa.core.RunContext` remains a legacy
compatibility contract rather than the new application contract. See the
[Run Contract architecture](architecture/run-contract.md).

Task 5C.2 adds a synchronous `PMQARunner` interface, canonical correlated
runner request/response contracts, runtime-only cancellation, and a
deterministic in-process `MockRunner`. The runner executes only the supplied
attempt. The mock validates the boundary and is not a production AI provider.
See the
[Runner boundary architecture](architecture/runner-boundary.md).

Task 5C.3 adds explicit, bounded, immutable Workflow and Runner Registries and
a synchronous `PMQAApplicationService`. The service performs one deterministic
pre-execution policy sequence, executes only caller-supplied attempt one, and
returns a canonical `RunRecord` correlated with exactly one terminal runner
invocation. The registries are explicit local composition, not discovery.
See the
[Application Service architecture](architecture/application-service.md).

Task 5C remains in progress and unmerged. No automatic discovery, persistence
repository, retry/fallback creation, approval execution, real provider
adapter, subprocess runner, UI, Azure DevOps integration, or usage/cost
tracking has been added.
Task 5B remains Not started; Task 6 and Task 7 remain Not started.

## Task 5B — Company-side MDE Read-Only Pilot

**Status: Not started.** This future pilot will occur in the company-managed
environment, use a private external Product Pack, and connect through the
versioned bridge to the existing TypeScript Playwright E2E capability. It will
begin with read-only exploration and evidence collection to validate Product
Pack assumptions before API v1 stabilization.

The initial pilot will not:

- modify product source;
- modify the existing E2E repository or folder;
- create commits or pull requests;
- write ADO test cases, tasks, or bugs;
- perform destructive browser actions; or
- copy company code, credentials, URLs, selectors, artifacts, or internal
  metadata into the public PMQA repository.

This placeholder does not start or implement the MDE pilot. Task 6 and Task 7
remain Not started.
