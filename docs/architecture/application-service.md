# Explicit PMQA Application Service

## Status

Task 5C.1 and Task 5C.2 have passed architecture review. Task 5C.3 is **Ready
for architecture review**. Task 5C remains in progress and unmerged. Task 5B,
Task 6, and Task 7 have not started.

## Responsibility

The application layer composes the canonical Run Contract and the
provider-neutral Runner boundary without changing either one:

```text
caller
    -> PMQAApplicationService
        -> explicit WorkflowRegistry
        -> explicit RunnerRegistry
        -> PMQARunner.execute()
    -> ApplicationRunResult
```

`PMQAWorkflowAdapter` supplies one canonical `WorkflowDefinition` and narrow
workflow-specific request and result validators. It does not execute runners,
persist state, receive provider clients, or own browser, subprocess,
credential, prompt, or terminal resources.

## Explicit registries, not discovery

`WorkflowRegistry` is constructed from one exact bounded tuple of adapters,
identified by exact `(workflow_id, workflow_version)`.
`RunnerRegistry` is constructed from one exact bounded tuple of runner
instances, identified by exact `runner_id`. Both reject duplicate or malformed
registrations, retain independently reconstructed canonical definition or
metadata snapshots, and expose deterministic exact lookup.

The registries have no mutable registration API. They perform no entry-point
discovery, distribution scan, filesystem or environment lookup, import-path
loading, dynamic import, or global registration. If an adapter's live
definition or a runner's live metadata differs from its registered snapshot,
execution fails safely before the affected validator or runner is called.

## Single-attempt lifecycle

`PMQAApplicationService.execute()` accepts one exact `RunRequest`, caller-owned
run and invocation IDs, and an optional runtime-only `RunnerControl`. An
omitted control creates one invocation-local control. The service creates only
attempt number 1 with no retry or fallback predecessor and uses the stable
`application.execute-workflow` operation.

Before constructing the runner request, the service applies this deterministic
order:

1. reconstruct and validate the exact `RunRequest`;
2. resolve its exact workflow ID and version;
3. verify the request input schema against the registered workflow;
4. verify the adapter's live definition still matches its snapshot;
5. call the workflow request validator;
6. resolve the exact runner ID;
7. verify required workflow capabilities against registered runner metadata;
8. verify live runner metadata still matches its snapshot;
9. reject any approval mode other than `none`;
10. validate the caller-supplied run and invocation IDs and runtime control;
11. sample and validate the application wall clock exactly once; and
12. construct the canonical context, pending invocation, and `RunnerRequest`.

The service calls the selected runner at most once. It canonically reconstructs
and authoritatively validates the `RunnerResponse`. When a structured result is
present, the workflow result validator runs exactly once; failed or cancelled
responses have no result validator call.

## Canonical result

`ApplicationRunResult` is a frozen, versioned canonical envelope containing
the exact canonical request, terminal `RunRecord`, and `RunnerResponse`. Its
single terminal invocation is available through `runner_invocation`. The
contract enforces request, run, session, workflow, version, runner, invocation,
status, timestamp, duration, result, artifact, and error correlations during
construction, reconstruction, and revalidated copying.

The run start, completion, and duration use the runner invocation's validated
evidence. The run creation time remains the request time; update time equals
completion. No current step or fabricated outcome metrics are added.

## Failure policy and deferred work

Expected application failures use a small fixed `ApplicationFailureCode` and
fixed safe messages without request values, registry contents, identifiers,
payloads, paths, prompts, provider data, or underlying exception details.
Expected workflow validation uses only the application-owned
`WorkflowAdapterValidationError`. Expected Runner boundary failures are
translated once at the application boundary. Unexpected programming failures
and resource or control-flow exceptions remain authoritative.

This checkpoint adds no persistence, retry or fallback creation, timeout
enforcement, approval execution, authorization, provider adapter, Usage/Cost
record, discovery, process, browser, network, CLI, UI, or API behavior. It does
not change WorkflowState, LangGraph, Task 5, or Product Pack execution.
