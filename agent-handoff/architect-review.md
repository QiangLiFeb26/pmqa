# Architect Review

Owner: Architect

Task: PMQA Task 5C.2 — Provider-Neutral Runner Boundary and Deterministic Mock Runner

Reviewed implementation commit: `502ae0826fffa14310439a8e010c4a2c0bd6408c`

Coder handoff commit: `17bddd3b75321b206e413082f17f7d242baa43e1`

Status: Needs Revision

This file is the authoritative Architect review. Chat summaries are
informational only.

## Review Depth Selected

Deep

The Coder's Deep recommendation is accepted because this task adds a public
execution contract, cross-contract lifecycle validation, runtime cancellation,
clock handling, and future provider integration seams.

## Overall Assessment

The provider-neutral layering, canonical request/response composition,
attempt/predecessor preservation, cancellation isolation, packaging, and
import isolation are directionally correct. Existing focused and full
regressions pass.

The task is not approved because adversarial review found gaps in clock failure
containment and output-artifact integrity. These gaps allow unsafe exception
detail to cross the MockRunner boundary and allow canonical responses to claim
output artifacts with impossible or pre-execution provenance.

## Review Findings

### F1 — Clock validation can leak provider/runtime exception details

Priority: Blocking

Locations:

- `pmqa/runners/mock.py`, wall-clock validation and UTC conversion
- `pmqa/runners/mock.py`, duration conversion

`_sample_wall_clock()` contains exceptions raised by the clock callable, but
timezone validation and `astimezone()` execute outside that containment. A
`datetime` with a hostile or failing `tzinfo` can therefore raise a raw
exception containing an injected marker.

Separately, two finite monotonic samples can produce a finite elapsed value
whose multiplication by 1000 overflows to infinity. `int(...)` then exposes a
raw `OverflowError` instead of the stable `RunnerBoundaryValidationError`.

The current generic `except Exception` also converts `MemoryError` into an
ordinary boundary error, unlike the established repository policy that
preserves resource/control-flow exceptions.

Required correction:

- contain expected exceptions raised during the complete wall-clock
  validation and UTC-normalization operation;
- contain overflow/value failures during duration calculation;
- expose only the fixed Runner boundary error with no marker, cause, context,
  object representation, or underlying message;
- continue propagating `MemoryError`, `KeyboardInterrupt`, `SystemExit`, and
  `GeneratorExit` unchanged;
- add adversarial tests for hostile `tzinfo`, UTC-conversion failure, extreme
  finite monotonic values, marker leakage, cause/context suppression, and all
  excluded exceptions.

Independent reproduction:

```text
hostile timezone -> ValueError: runtime-secret-marker
finite 0.0 / 1e308 monotonic samples -> raw OverflowError
MemoryError from clock -> RunnerBoundaryValidationError
```

### F2 — Output-artifact timestamps are not correlated to the invocation

Priority: Blocking

Location:

- `pmqa/runners/contracts.py`, `validate_runner_response()`

A `RunnerResponse` currently accepts an output artifact whose `created_at`
precedes invocation start or follows invocation completion. The response is
canonical and passes authoritative request/response validation despite
containing temporally impossible output provenance.

Required correction:

- authoritative response validation must require every output artifact to
  satisfy:

  ```text
  invocation.started_at <= artifact.created_at <= invocation.completed_at
  ```

- validation must use the existing fixed safe boundary error;
- add boundary tests for artifacts before start, exactly at start, exactly at
  completion, and after completion;
- preserve support for valid diagnostic artifacts produced during failed or
  partially successful execution. Pre-existing input artifacts, if needed in
  the future, require a separate explicit request-side contract and must not be
  disguised as output artifacts.

Independent reproduction:

```text
artifact.created_at > invocation.completed_at -> accepted
artifact.created_at < invocation.started_at -> accepted
```

### F3 — MockRunner retains untyped mutable artifact configuration

Priority: Blocking

Location:

- `pmqa/runners/mock.py`, `MockRunner.__init__()`

The constructor validates only that `output_artifacts` is an exact tuple. It
does not validate the item types. A caller can pass a tuple containing a
mutable dictionary, which the runner retains by identity. Mutating that
dictionary after runner construction changes a later execution result.

This weakens the typed public boundary and makes the deterministic MockRunner
externally mutable.

Required correction:

- accept only exact `RunArtifact` items;
- reject dictionaries, model subclasses, mutable artifact-like objects, and
  runtime objects with the fixed safe error;
- retain only an immutable, independently validated snapshot;
- add mutation and marker-leak tests;
- confirm repeated execution is unaffected by later caller-side mutation.

Independent reproduction:

```text
runner._output_artifacts[0] is caller_dictionary -> True
caller mutation changes the later returned artifact ID
```

### F4 — Pre-execution cancellation can return configured output artifacts

Priority: Blocking

Location:

- `pmqa/runners/mock.py`, response assembly

When cancellation is already requested before execution, MockRunner correctly
returns `CANCELLED` but still attaches all configured output artifacts. This
contradicts the documented pre-execution cancellation behavior: the mock did
not execute and therefore cannot have produced its configured outputs.

Required correction:

- a pre-execution-cancelled MockRunner response must contain no output
  artifacts;
- success, partial success, and failure may retain valid configured artifacts
  whose timestamps satisfy F2;
- add a focused regression with a non-empty configured artifact collection.

Independent reproduction:

```text
pre-cancelled MockRunner with one configured artifact -> CANCELLED, 1 artifact
```

## Required Changes

Address F1–F4 in one focused Task 5C.2 remediation. Do not expand the public
Runner API, add provider integrations, or start Application Service work.

The remediation must add tests that fail against
`502ae0826fffa14310439a8e010c4a2c0bd6408c` and pass after the correction.

## Validation Evidence

Independent Architect verification:

- Runner, Run Contract, boundary, import, and packaging suites:
  `248 passed`
- Full default suite:
  `1402 passed, 5 skipped, 1 existing LangGraph warning`
- Existing generated Playwright regressions:
  `2 passed`
- Worktree and local/remote branch were clean and synchronized before this
  review update.

The green existing suite confirms compatibility but does not cover the four
adversarial cases above.

## Decision

Needs Revision

Task 5C.2 is not approved at commit
`502ae0826fffa14310439a8e010c4a2c0bd6408c`.

## Next Recommended Task

Complete the focused Task 5C.2 Runner integrity remediation defined in
`agent-handoff/current-task.md`.

Do not start Task 5C.3, Usage/Cost, Task 5B, Task 6, or Task 7.
