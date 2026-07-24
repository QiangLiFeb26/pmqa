# Architect Review

Owner: Architect

Task: PMQA Task 5C.2 — Provider-Neutral Runner Boundary and Deterministic Mock Runner

Original implementation commit: `502ae0826fffa14310439a8e010c4a2c0bd6408c`

Remediation commit: `58d1edb9b765749cb1351e30b3405bc6a6b82247`

Coder remediation handoff: `0e01d820060d4c3bdc2d5ca342dc12bb7d14f863`

Status: Approved

This file is the authoritative Architect review. Chat summaries are
informational only.

## Review Depth Selected

Deep

The Coder's Deep recommendation is accepted because the remediation changes
exception containment and artifact provenance at a public execution boundary.

## Overall Assessment

Task 5C.2 is approved after remediation.

The provider-neutral Runner boundary remains small and isolated. The
remediation closes all four blocking findings without expanding the public
execution API, adding provider behavior, or changing existing workflow
semantics.

## Review Findings

No remaining blocking findings.

### F1 — Clock and duration containment

Resolved.

- Clock invocation, timezone validation, `utcoffset()`, and UTC normalization
  execute inside the safe containment boundary.
- Extreme finite monotonic samples no longer leak conversion exceptions.
- Fixed failures have no underlying message, cause, or context.
- `MemoryError`, `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit`
  propagate unchanged.
- Zero-duration behavior remains valid.

Independent adversarial reproduction now returns:

```text
hostile timezone -> RunnerBoundaryValidationError
scaled monotonic overflow -> RunnerBoundaryValidationError
MemoryError -> propagated unchanged
```

### F2 — Output-artifact temporal correlation

Resolved.

The authoritative validator now requires every output artifact to be created
between invocation start and completion, inclusive. Both exact boundaries are
covered, and impossible timestamps fail with the fixed safe boundary error.

### F3 — MockRunner artifact immutability

Resolved.

MockRunner accepts only exact `RunArtifact` instances in an exact tuple and
stores independently reconstructed canonical snapshots. Dictionaries,
artifact subclasses, mutable lookalikes, and runtime objects are rejected.
Caller-side mutation cannot change later executions.

### F4 — Pre-execution cancellation output

Resolved.

A pre-execution-cancelled MockRunner response contains no result and no output
artifacts while preserving the original attempt and predecessor fields.

## Required Changes

None.

## Validation Evidence

Independent Architect verification:

- Original adversarial reproduction cases: all closed
- Combined Runner, Run Contract, boundary, packaging, and Task 4 regressions:
  `387 passed, 1 existing LangGraph warning`
- Full default suite:
  `1443 passed, 5 skipped, 1 existing LangGraph warning`
- Existing generated Playwright regressions:
  `2 passed`
- `git diff --check`: passed
- The worktree and local/remote task branch were clean and synchronized before
  this review update.

## Decision

Approved

Task 5C.2 is accepted through remediation commit
`58d1edb9b765749cb1351e30b3405bc6a6b82247`.

## Next Recommended Task

Proceed to Task 5C.3 — Explicit Application Registries and Single-Attempt Run
Service, as defined in `agent-handoff/current-task.md`.

Task 5C remains in progress and unmerged. Usage/Cost, Task 5B, Task 6, and Task
7 remain not started.
