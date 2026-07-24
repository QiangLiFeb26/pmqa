# Architect Review

Owner: Architect

Task: PMQA Task 5C.4 — Provider-Neutral AI Usage and Cost Contracts

Task ID: `PMQA-5C.4`

Attempt: `1`

Status: Approved

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed Coder Starting HEAD:
`150c265974eac9f73ffc76b5eb7cd70f94f9cb5c`

Reviewed Implementation Commit:
`2252c14736a050e87be6b769f488754a64b144bc`

Derived Coder Report Commit:
`68953a0999f479a0ffe4ee4c964aa3bb4daa637a`

Derived Reviewer Report Commit:
`f5a960d359b671c485d70871eecb2e150b9e23d6`

The Reviewer report commit was derived from Git with:

```bash
git log -1 --format=%H -- agent-handoff/reviewer-report.md
```

This Architect review does not claim the SHA of its own containing commit. The
next Coder records the publication commit containing this review and the next
task as its starting HEAD.

## Correlation and Ownership Verification

- active branch and upstream:
  `agent/task-5c-1-canonical-run-contract`;
- starting HEAD
  `150c265974eac9f73ffc76b5eb7cd70f94f9cb5c` is an ancestor of implementation
  commit `2252c14736a050e87be6b769f488754a64b144bc`;
- implementation commit is an ancestor of Coder report commit
  `68953a0999f479a0ffe4ee4c964aa3bb4daa637a`;
- Coder report commit is an ancestor of Reviewer report commit
  `f5a960d359b671c485d70871eecb2e150b9e23d6`;
- the Coder report identifies `PMQA-5C.4`, attempt `1`, and the exact starting
  and implementation commits;
- the Reviewer report independently derived the Coder report commit and
  identifies the same task, attempt, branch, and implementation;
- the Reviewer commit changed only
  `agent-handoff/reviewer-report.md`;
- the Reviewer did not modify `architect-review.md`, production code, tests,
  configuration, schemas, packaging, scripts, or product documentation.

## Review Depth Selected

Deep

The Architect independently selected Deep review because these versioned
contracts establish the persisted semantics for missing usage, monetary
evidence, pricing, and future provider integration. The Reviewer also selected
Deep independently and returned `Pass`.

## Overall Assessment

Task 5C.4 is approved.

The implementation establishes a small provider-neutral usage/cost vocabulary
without coupling it to providers, CLI output, pricing data, storage, UI,
LangGraph, or existing runner/application behavior.

The contracts clearly separate:

- provider-reported, CLI-parsed, estimated, and unavailable usage;
- provider-reported, estimated, subscription-included, and unavailable cost;
- present zero from missing data;
- one AI/model invocation from one logical runner invocation;
- pricing lookup evidence from cost calculation.

No token count, total, currency, amount, price, provider identity, or model
identity is fabricated.

## Independent Reviewer Result

Reviewer verdict: `Pass`

Reviewer findings: None

The Reviewer independently:

- inspected the task, diff, implementation, and tests before reading the full
  Coder report;
- ran the focused, regression, full, generated-test, compile, and diff checks;
- confirmed security, package scope, import isolation, and write ownership;
- changed only its owned report.

This successfully completes the first live
Coder → Independent Reviewer → Architect pilot.

## Architect Findings

No blocking finding remains.

### A1 — Missing pricing-component reason granularity

Disposition: Accepted current scope; future design checkpoint

`ModelPricing` allows each component to be independently present or absent but
uses one shared bounded reason for all absent components. This meets Task 5C.4
because independent presence/absence was required and no concrete pricing
catalog exists yet.

Before a real catalog or stable public SDK freezes the schema, the future
pricing/calculation task must validate whether mixed per-component reasons are
needed. Do not silently infer a shared reason from heterogeneous provider
evidence.

### A2 — Duration versus wall-clock interval

Disposition: Accepted by design

`duration_ms` is independent monotonic timing evidence and is not derived from
`completed_at - started_at`. This matches the existing Runner contract,
supports queueing/wall-clock changes, and avoids fabricating timing. Future
collectors must sample it from an injected monotonic clock and document that
semantics.

### A3 — Reuse of private Run Contract helpers

Disposition: Accepted internal dependency; monitor

`pmqa.usage` reuses `_RunContract` and canonical validation helpers from
`pmqa.run.models`. Within the same package and repository this avoids
duplicating security and persistence policy, and it was explicitly allowed by
the task.

These helpers are not a public extension API. If a third independent domain
package needs the same base, move the shared contract machinery to a neutral
internal module in a separately reviewed task rather than expanding ad hoc
private imports.

## Acceptance Criteria Coverage

- complete, partial, zero, and unavailable usage: Met;
- all required usage/cost provenance types remain distinct: Met;
- estimated cost requires external pricing evidence: Met;
- no embedded pricing table: Met;
- AI invocation remains separate from runner and LangGraph state: Met;
- strict canonical reconstruction and revalidated copying: Met;
- safe decimal, currency, time, lifecycle, and predecessor invariants: Met;
- security boundary and marker-safe failures: Met;
- import isolation and real-wheel inclusion: Met;
- existing Run/Runner/Application/Task 4 behavior unchanged: Met;
- no collector, parser, calculator, storage, CLI, UI, or provider integration:
  Met;
- Coder and Reviewer ownership boundaries: Met.

## Validation Evidence

Independent Reviewer evidence:

- new usage/pricing/import tests: `68 passed`;
- Run/Runner/Application/boundary/packaging regressions: `332 passed`;
- Task 4 orchestration regressions: `98 passed`;
- full default suite: `1629 passed, 5 skipped`;
- generated Playwright regressions: `2 passed`;
- isolated compileall: passed;
- `git diff --check`: passed.

Architect verification:

- full implementation and tests inspected;
- new usage/pricing/import tests: `68 passed`;
- Run/Runner/Application/boundary regressions:
  `329 passed`;
- correlation and ancestry checks: passed;
- implementation-to-Reviewer `git diff --check`: passed;
- worktree and local/upstream branch were clean and synchronized before
  Architect-owned disposition edits.

The Architect did not duplicate the full suite because the Independent
Reviewer had already run it from the exact correlated implementation and
reported complete evidence. This is the intended value of the new review
stage.

## Required Changes

None.

## Decision

Approved

Task 5C.4 is accepted through implementation commit
`2252c14736a050e87be6b769f488754a64b144bc`.

## Workflow Pilot Retrospective

The first pilot succeeded:

- Human did not copy the task or Coder report to the Reviewer;
- Reviewer derived the report commit from Git;
- Reviewer followed the independent inspection order;
- Reviewer changed only its owned file;
- Architect derived the Reviewer commit and performed final synthesis;
- provider choice did not affect the protocol.

No protocol or template defect was observed. The Human's Chat message named
`architect-review.md`, but Git proved that the Reviewer correctly published
`reviewer-report.md`; no repository or role-boundary failure occurred.

The planned lightweight stabilization is therefore complete with no protocol
change. Normal PMQA development now continues under the adopted workflow.

## Next Recommended Task

Proceed to PMQA Task 5C.5 — Provider-Neutral AI Invocation Collector, defined
in `agent-handoff/current-task.md`.
