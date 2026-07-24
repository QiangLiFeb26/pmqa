# Architect Review

Owner: Architect

Task: PMQA Task 5C.3 — Explicit Application Registries and Single-Attempt Run Service

Implementation commit: `41a84d271df00980ffaf84d2df67a3515d9e961c`

Remediation commit: `ad26cfd987526ba9efabc0130458d26df4ca8bcb`

Coder report commit: `307ff706acc445c63880a253df0621dac82afd4d`

Status: Approved

This file is the authoritative Architect review. Chat summaries are
informational only.

## Review Depth Selected

Deep

The Architect accepted the Coder's recommendation because the remediation
changes ownership across workflow-validator and runner trust boundaries and
strengthens the canonical terminal envelope.

## Overall Assessment

Task 5C.3 is approved.

The remediation closes all four blocking findings without redesigning the
registries or expanding Application Service behavior. The service now retains
authoritative canonical objects on its side of every runtime boundary,
dispatches independently reconstructed snapshots, and validates returned data
only against untouched service-owned state.

No new blocking or non-blocking code finding was identified.

## Review Findings

### F1 — Workflow validator isolation

Status: Resolved

- Request and result validators receive fresh canonical snapshots.
- The service retains and later uses only its authoritative `RunRequest` and
  `StructuredResult`.
- Immediate mutation and retained-reference mutation cannot change runner
  selection, result assembly, output, or persisted canonical data.
- Prohibited/runtime-like keys inserted by a validator do not cross the
  boundary.

### F2 — Runner dispatch isolation

Status: Resolved

- The runner receives a fresh reconstructed `RunnerRequest`.
- `validate_runner_response()` uses the untouched authoritative request.
- Mutating request, context, invocation, attempt/predecessor, operation,
  step, and expected-result correlations cannot redirect the run.
- A response correlated only to the mutated dispatch fails with the fixed,
  marker-safe `RUNNER_BOUNDARY_FAILED` error.

### F3 — Single-attempt application invariant

Status: Resolved

`ApplicationRunResult` now enforces the application-owned operation, no step,
attempt number 1, and no retry or fallback predecessor during direct
construction, `from_dict()`, and revalidated copying. The operation constant
has one neutral application-contract definition reused by the service.

### F4 — Live property exception identity

Status: Resolved

- Successfully returned malformed or changed live definition/metadata values
  retain the existing fixed changed-state classification.
- Exceptions raised while reading a live property propagate as the exact
  original object.
- Ordinary, resource, and control-flow exception cases are covered.

## Required Changes

None.

## Independent Validation Evidence

Architect verification at
`307ff706acc445c63880a253df0621dac82afd4d`:

- combined Application, Run, Runner, security, packaging, and Task 4 focused
  suites: `503 passed`;
- full default suite under normal repository build permissions:
  `1561 passed, 5 skipped, 1 existing LangGraph warning`;
- existing generated Playwright regressions: `2 passed`;
- isolated `compileall`: passed;
- remediation `git diff --check`: passed;
- worktree and local/upstream branch were clean and synchronized before this
  review update.

The first sandboxed full-suite run produced one build-metadata permission
failure while attempting to update a source-tree `egg-info` timestamp. The
same full suite passed under normal repository permissions; this was an
Architect execution-environment artifact, not a product or test defect.

## Remaining Risks

The remaining limitations are the intentionally deferred Task 5C scope:
persistence, cross-record correlation, retry/fallback creation, approval
execution, authorization, timeout enforcement, and real workflow/provider
composition. None blocks Task 5C.3.

## Decision

Approved

Task 5C.3 is approved through remediation commit
`ad26cfd987526ba9efabc0130458d26df4ca8bcb`.

## Next Recommended Task

Implement the provider-neutral AI Team Workflow Foundation defined in
`agent-handoff/current-task.md` using the existing
Architect → Coder → Architect process.

After that foundation is approved, PMQA Task 5C.4 will be the first
Coder → Independent Reviewer → Architect pilot. A small stabilization task
will follow the pilot.
