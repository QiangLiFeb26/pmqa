# Architect Review

Owner: Architect

Task: PMQA Task 5C.5 — Provider-Neutral AI Invocation Collector

Task ID: `PMQA-5C.5`

Attempt: `1`

Status: Approved

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed Coder Starting HEAD:
`119330ec2355b2ab8d8f4afa66d23d0af8a06654`

Reviewed Implementation Commit:
`346cc7ccb667ff3be7f58a8282e7fad67a2bcae9`

Derived Coder Report Commit:
`5b8921bf6aa8f4db8cf4f27a453a26bcd3ab9e89`

Derived Reviewer Report Commit:
`efe5ee01ec9ddfa574eef74f333fb98ed46528b2`

The Reviewer report commit was derived from Git with:

```bash
git log -1 --format=%H -- agent-handoff/reviewer-report.md
```

This review does not claim the SHA of its own containing commit. The next
Coder records the publication commit containing this review and the next task
as its starting HEAD.

## Correlation and Ownership Verification

- active branch and upstream are
  `agent/task-5c-1-canonical-run-contract`;
- starting HEAD
  `119330ec2355b2ab8d8f4afa66d23d0af8a06654` is an ancestor of implementation
  commit `346cc7ccb667ff3be7f58a8282e7fad67a2bcae9`;
- implementation commit is an ancestor of Coder report commit
  `5b8921bf6aa8f4db8cf4f27a453a26bcd3ab9e89`;
- Coder report commit is the parent of Reviewer report commit
  `efe5ee01ec9ddfa574eef74f333fb98ed46528b2`;
- the Coder report identifies `PMQA-5C.5`, attempt `1`, and the exact starting
  and implementation commits;
- the Reviewer independently derived the Coder report commit and identifies
  the same task, attempt, branch, and implementation;
- Coder report publication changed only `agent-handoff/coder-report.md`;
- Reviewer publication changed only `agent-handoff/reviewer-report.md`;
- the worktree and local/upstream branch were clean and synchronized before
  this Architect disposition.

## Review Depth Selected

Deep

The Architect independently selected Deep review because the collector adds
opaque runtime ownership, clock containment, evidence snapshots, and
exactly-once terminalization. The Reviewer independently selected Deep and
returned `Pass`.

## Overall Assessment

Task 5C.5 is approved.

The implementation adds a small provider-neutral lifecycle service around the
Task 5C.4 usage/cost contracts without introducing provider parsing, pricing
calculation, persistence, workflow integration, or runtime I/O.

The handle is runtime-only and collector-owned. Metadata is validated before
clock sampling. Caller evidence is reconstructed before ownership transfer.
Ownership is consumed atomically before terminal clocks, producing at most one
canonical record. Expected failures remain fixed and marker-safe, while
resource/control-flow exceptions remain authoritative.

The Task 5C.4 wire schema remains unchanged. Its existing cross-field metadata
policy was extracted into one private helper and reused without semantic
drift.

## Independent Reviewer Result

Reviewer verdict: `Pass`

Blocking findings: None

The Reviewer:

- followed the required independent inspection order;
- read the collector and focused tests in full;
- independently ran every required focused, regression, full, generated,
  compile, and diff check;
- verified handle forgery/mutation/foreign-owner resistance;
- verified retryable pre-consumption validation and terminal post-consumption
  failures;
- verified security, scope, packaging, and import isolation;
- changed only its owned report.

## Architect Findings

No blocking finding remains.

### A1 — Concurrent exactly-once coverage

Disposition: Accepted and independently challenged

The committed tests exercise all sequential first/second terminal method
combinations. The Reviewer noted that they did not create actual competing
threads.

The Architect independently ran 50 iterations with 12 simultaneous contenders
per handle. Every iteration produced exactly one canonical record, eleven
`invalid_handle` failures, and exactly one terminal wall/monotonic sample.

The lock-based ownership transfer is therefore accepted. A focused committed
threaded regression is included as a non-blocking requirement in Task 5C.6 so
this evidence remains durable.

### A2 — Importable handle construction internals

Disposition: Accepted by design

Python module privacy is not a security sandbox. The importable private
sentinel and `_create` method are defense-in-depth only. The authoritative
boundary is collector-owned active-table membership, exact handle type,
collector owner identity, and per-handle integrity identity.

A newly constructed lookalike is absent from the active table and fails
safely. Mutating an owned handle consumes its corrupted state. This is the
intended in-process trust model.

### A3 — Collection error-code vocabulary

Disposition: Accepted as the Task 5C runtime boundary

The eight fixed codes are bounded, provider-neutral, and sufficient for the
current lifecycle. They are a public Task 5C surface but not a stable external
SDK v1 promise. Future changes require explicit compatibility review rather
than provider-specific additions.

## Acceptance Criteria Coverage

- provider-neutral start/complete/fail/cancel interface: Met
- canonical metadata validation reuse: Met
- opaque collector-owned runtime handle: Met
- forged, foreign, subclassed, mutated, and finalized handle rejection: Met
- caller evidence snapshot without fabrication: Met
- exactly-once ownership transfer: Met
- deterministic retryable versus consumed failure policy: Met
- wall/monotonic sampling and duration semantics: Met
- safe expected errors and exact resource/control-flow propagation: Met
- import isolation and wheel inclusion: Met
- no provider/parser/pricing/storage/workflow integration: Met
- Coder and Reviewer write boundaries: Met

## Validation Evidence

Independent Reviewer evidence:

- usage collector/contracts/pricing/import tests: `138 passed`;
- Run/Runner/Application/boundary/packaging regressions: `332 passed`;
- Task 4 orchestration regressions: `98 passed`;
- full default suite: `1699 passed, 5 skipped`;
- generated Playwright regressions: `2 passed`;
- isolated compileall: passed;
- `git diff --check`: passed.

Architect verification:

- complete implementation and relevant contract refactor inspected;
- focused usage collector/contracts/pricing/import tests: `138 passed`;
- 50 × 12-thread terminalization challenge: passed;
- correlation, ancestry, write-boundary, and path-specific report derivation:
  passed;
- implementation-to-Reviewer `git diff --check`: passed.

The Architect did not duplicate the full suite because the Independent
Reviewer already executed it from the exact correlated implementation. This
is the intended value of the independent review stage.

## Required Changes

None.

## Decision

Approved

Task 5C.5 is accepted through implementation commit
`346cc7ccb667ff3be7f58a8282e7fad67a2bcae9`.

## Next Recommended Task

Proceed to PMQA Task 5C.6 — Append-Only Local AI Invocation Repository, defined
in `agent-handoff/current-task.md`.

Task 5C remains in progress and unmerged. Provider/CLI parsing, cost
calculation, summaries, workflow integration, Task 5B, Task 6, and Task 7
remain not started.
