# Current Task

Owner: Architect

Task: PMQA Task 5D.1 — Local Web Foundation and Session State

Task ID: `PMQA-5D.1`

Attempt: `0`

Status: Awaiting Human Decision

Branch: `agent/task-5c-1-canonical-run-contract`

Architect-reviewed Reviewer HEAD:
`115910e2662ce6bd2de6f807dfb3dfddc201a4b3`

Repository Markdown and Git history are authoritative. Chat summaries are
informational only.

## Current Disposition

PMQA Task 5D.0 passed final architecture review.

Task 5D.1 is the next implementation checkpoint, but no Coder task is
authorized yet. The Human must first choose the default retention policy for
local conversation messages and structured artifact revisions.

Only the Architect may replace this holding state with the executable
Task 5D.1 Attempt 1 handoff after the Human decision.

## Decision Required From Human

Choose the default local retention behavior for conversation and structured
artifact content.

Architect recommendation:

```text
default: 30 days after the session's last activity
manual deletion: available immediately
configurable choices: session-only, 7 days, 30 days, or 90 days
indefinite retention: never silently selected
```

This setting does not implicitly delete or redefine:

- Task 5C AI invocation usage records;
- Task 3 reasoning traces; or
- future external-execution receipts.

Those records require separate explicit retention policy because their audit,
correlation, and recovery semantics differ.

## Why the Decision Is Required Now

Task 5D.1 establishes the local repository seam and lifecycle. Choosing
session-only storage versus durable multi-day retention changes:

- persistence behavior;
- deletion and expiry semantics;
- startup recovery;
- UI status and settings;
- test cases;
- migration design; and
- privacy expectations.

The Architect will not infer this product choice.

## Coder Instruction

Do not start Task 5D.1 while this file has:

```text
Attempt: 0
Status: Awaiting Human Decision
```

Do not modify code, tests, dependencies, configuration, product
documentation, or handoff files for this holding state.

## Next Step

After the Human answers, the Architect will publish the complete Task 5D.1
Attempt 1 objective, allowed changes, acceptance criteria, validation
commands, and Coder deliverables.
