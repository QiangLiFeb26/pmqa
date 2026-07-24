# Provider-Neutral Runner Boundary

## Status

Task 5C.1 and Task 5C.2 have passed architecture review. Task 5C.3 is **Ready
for architecture review**. Task 5C remains in progress and unmerged. Task 5B,
Task 6, and Task 7 have not started.

## Responsibility

`pmqa.run` defines stable application correlation and remains independent from
runner implementations. `pmqa.runners` defines the synchronous execution seam:

```text
Explicit Application Service
        |
        v
canonical RunnerRequest
        |
        v
provider-neutral PMQARunner
        |
        v
canonical RunnerResponse
```

`RunnerRequest` composes the existing `RunRequest`, `PMQARunContext`, and one
pending `RunnerInvocationRecord`. It adds only the expected result schema and
a bounded timeout. `RunnerResponse` contains exactly one correlated terminal
invocation, an outcome-appropriate structured result, and logical output
artifact references. The authoritative response validator prevents a runner
from returning a valid but unrelated invocation. Every output artifact is
created no earlier than invocation start and no later than invocation
completion; exact start and completion boundaries are valid.

The interface contains no provider request object, prompt, raw response,
terminal output, environment, credential, browser, subprocess handle, or
mutable callback registry. This keeps future Copilot, Codex, API, private
company, and local deterministic implementations behind the same application
boundary without making any provider part of the contract.

## Runtime-only cancellation

`CancellationToken` and `RunnerControl` are ordinary runtime objects, not
Pydantic or persistence contracts. Cancellation is explicit, idempotent, safe
for ordinary concurrent access, and scoped to one caller-owned control. It
cannot enter Run Contract JSON, WorkflowState, results, artifacts, or logs.
Task 5C.2 adds no pause, resume, approval, progress event, or remote
cancellation behavior.

## Attempts, retry, and fallback

A runner executes exactly the attempt represented by the request's pending
invocation and preserves its attempt number and predecessor classification.
It never creates an implicit retry or fallback. Decisions to create another
attempt, validate cross-record predecessor existence, or apply retry/fallback
policy belong to the future Application Service or policy layer.

## Deterministic MockRunner

`MockRunner` is in-process validation infrastructure, not a production AI
provider. It performs no browser, network, subprocess, configuration,
environment, provider, prompt, usage, or cost work. Injected timezone-aware
wall-clock and monotonic-clock evidence produces deterministic completion and
duration data. Configured success, partial success, and failure outcomes plus
pre-execution cancellation exercise the canonical lifecycle and correlation
rules. Clock call, timezone-awareness, UTC normalization, and duration
conversion failures are contained behind the safe runner boundary while
resource and control-flow exceptions remain authoritative.

Configured output artifacts are exact, independently reconstructed
`RunArtifact` snapshots. Successful, partially successful, and failed
executions may return temporally correlated diagnostic artifacts. A
pre-execution cancellation returns no result and no output artifacts because
the mock did not execute.

## Application Service

Task 5C.2 does not select runners or workflows. Task 5C.3 adds explicit
registry lookup, safe pre-execution approval rejection, one supplied first
attempt, and assembly of the terminal application-level run record. It does
not execute approval-required workflows, create retries or fallbacks, enforce
timeouts, persist records, or add authorization policy. No automatic
discovery, real provider adapter, subprocess runner, Usage/Cost record, UI, or
API is added. See
[Application Service architecture](application-service.md).
