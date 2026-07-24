# Architect Review

Owner: Architect

Task: PMQA Task 5C.3 — Explicit Application Registries and Single-Attempt Run Service

Implementation commit: `41a84d271df00980ffaf84d2df67a3515d9e961c`

Coder report commit: `a839154619485b8b19e14bc1ad34cd9b3e97d70b`

Status: Needs Revision

This file is the authoritative Architect review. Chat summaries are
informational only.

## Review Depth Selected

Deep

The Coder's recommendation is accepted because Task 5C.3 introduces the first
application composition boundary across workflow validation, runner execution,
identity correlation, and canonical terminal records.

## Overall Assessment

The explicit registry design, dependency direction, pre-execution ordering,
safe error vocabulary, packaging, and import isolation are directionally
correct. Existing focused and full regressions pass.

Task 5C.3 is not approved because adversarial review found four trust-boundary
defects. Runtime workflow adapters and runners can mutate nominally frozen
Pydantic objects through their underlying Python state. The current service
passes its authoritative objects directly across those runtime boundaries and
then trusts the same mutated objects afterward.

This permits prohibited data and changed run/invocation identities to enter a
valid `ApplicationRunResult`.

## Review Findings

### F1 — Workflow validators can mutate authoritative request and result data

Priority: Blocking

Location:

- `pmqa/application/service.py`
- request and result workflow-validator calls

The service passes its authoritative canonical `RunRequest` and
`StructuredResult` objects directly to workflow validators. A validator can
bypass Pydantic `frozen` through `__dict__`, return normally, and leave the
service using the modified object.

Independent reproductions confirmed:

```text
request validator inserts inputs.provider_client
    -> prohibited field appears in ApplicationRunResult.to_dict()

result validator inserts result.data.provider_client
    -> prohibited field appears in RunRecord and ApplicationRunResult
```

The validator can also change runner selection or request correlation fields
before later service stages.

Required correction:

- retain one authoritative independently reconstructed request/result inside
  the service;
- pass a separate fresh canonical snapshot to each workflow validator;
- discard the validator-owned snapshot after validation;
- validator mutation or later retained-reference mutation must not affect
  runner selection, RunnerRequest construction, RunnerResponse, RunRecord, or
  ApplicationRunResult;
- add tests for mutation of IDs, runner ID, schema IDs, inputs, result schema,
  result data, prohibited keys, and retained references;
- ensure caller-owned and service-owned canonical objects remain unchanged.

### F2 — A runner can rewrite the expected RunnerRequest correlation

Priority: Blocking

Location:

- `pmqa/application/service.py`
- runner dispatch and response validation

The same `RunnerRequest` object is passed to the runner and later used as the
authoritative expected request for `validate_runner_response()`.

A runner can mutate the pending request's context and invocation, return a
response matching the mutated values, and pass authoritative validation.

Independent reproduction:

```text
caller requested run.original / invocation.original
runner rewrites request to run.redirected / invocation.redirected
ApplicationRunResult accepts run.redirected / invocation.redirected
```

Required correction:

- construct and retain an authoritative canonical `RunnerRequest` snapshot;
- pass a separate independently reconstructed dispatch snapshot to the runner;
- validate the returned response only against the untouched authoritative
  snapshot;
- runner mutation of the dispatch snapshot must not alter run ID, invocation
  ID, request correlation, operation, step, attempt, predecessors, expected
  result schema, or final records;
- mutation attempts must produce the fixed safe runner-boundary application
  failure with no marker, cause, context, or mutated value exposure;
- add adversarial mutations covering the complete RunnerRequest correlation.

### F3 — ApplicationRunResult does not enforce the single-attempt contract

Priority: Blocking

Location:

- `pmqa/application/contracts.py`

`ApplicationRunResult` correlates the run and response but does not require
the application-owned operation, attempt number 1, `step_id=None`, or absent
retry/fallback predecessors.

It can therefore be directly constructed, reconstructed, or copied as a valid
Task 5C.3 result containing attempt 2 and an arbitrary operation.

Independent reproduction:

```text
operation=other.operation
attempt_number=2
retry_of_invocation_id=invocation.0
    -> ApplicationRunResult accepted
```

Required correction:

- define the application operation constant in one neutral application module
  and reuse it from contracts and service;
- require exactly:
  - the canonical application operation;
  - `step_id is None`;
  - `attempt_number == 1`;
  - no retry predecessor;
  - no fallback predecessor;
- enforce these rules during direct construction, `from_dict()`, and
  `model_copy(update=...)`;
- add tests for each field independently and in combination.

### F4 — Unexpected live definition/metadata failures are relabeled

Priority: Blocking

Location:

- `pmqa/application/service.py`
- live workflow-definition and runner-metadata checks

The task requires unexpected programming exceptions to propagate. The current
live-property checks catch every ordinary `Exception` and relabel it as
`WORKFLOW_DEFINITION_CHANGED` or `RUNNER_METADATA_CHANGED`.

Independent reproduction:

```text
live workflow definition raises RuntimeError
    -> PMQAApplicationError(WORKFLOW_DEFINITION_CHANGED)

live runner metadata raises RuntimeError
    -> PMQAApplicationError(RUNNER_METADATA_CHANGED)
```

Required correction:

- a successfully returned but unequal or malformed live value may map to the
  existing fixed changed failure;
- an exception raised while reading a previously registered adapter's live
  definition or runner's live metadata is an unexpected runtime/programming
  failure and must propagate unchanged;
- `MemoryError`, `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit`
  continue to propagate unchanged;
- add identity-preserving tests for ordinary and resource/control-flow
  exceptions;
- keep registry-construction malformed-object containment unchanged.

## Required Changes

Address F1–F4 in one focused Task 5C.3 remediation. Do not redesign the
registries or expand application functionality.

The new tests must fail against
`41a84d271df00980ffaf84d2df67a3515d9e961c` and pass after the correction.

Only the Coder may modify implementation, tests, or product documentation.
The Architect has modified only Architect-owned handoff files.

## Validation Evidence

Independent Architect verification:

- Application, Run, Runner, boundary, packaging, and Task 4 focused suites:
  `469 passed`
- Full default suite with normal build metadata access:
  `1527 passed, 5 skipped, 1 existing LangGraph warning`
- Existing generated Playwright regressions:
  `2 passed`
- `git diff --check`: passed
- Worktree and local/remote branch were clean and synchronized before this
  review update.

The existing suite confirms compatibility but does not cover the four
adversarial trust-boundary cases.

## Decision

Needs Revision

Task 5C.3 is not approved at
`41a84d271df00980ffaf84d2df67a3515d9e961c`.

## Next Recommended Task

Complete the focused Task 5C.3 Application Boundary Isolation remediation in
`agent-handoff/current-task.md`.

After Task 5C.3 passes, the next active task will implement the provider-neutral
Independent Reviewer workflow. PMQA Task 5C.4 will then be used as its first
real pilot.
