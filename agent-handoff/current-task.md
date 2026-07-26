# Current Task

Owner: Architect

Task: PMQA Task 5D.1A — Repository Result Correlation

Task ID: `PMQA-5D.1A`

Attempt: `2`

Status: Changes Required

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed Attempt 1 Reviewer HEAD:
`67492ea5ef551fd10a47338f270408e92baa99c4`

Coder starting HEAD: derive and record the latest pushed branch commit that
contains this remediation publication before changing implementation files.

Repository Markdown and Git history are authoritative. Chat summaries are
informational only.

## Task Objective

Harden `ConversationApplicationService` so every value returned by its
injected volatile and durable repositories is correlated, bounded, and
unambiguous before it is exposed or used for a transition.

This is a narrow remediation. Preserve the approved Task 5D.1A contracts,
repository implementations, retention behavior, sensitive-text policy, and
scope.

## Background

Attempt 1 created:

- canonical conversation session and turn contracts;
- volatile and durable repository composition;
- real SQLite persistence;
- deterministic retention and revision transitions; and
- shared sensitive-text ingress.

The implementation and Reviewer report are strong, but the Application
Service currently trusts repository return correlation too early.

`_find_session` returns immediately after the first repository finds a
session. It neither checks the second repository nor proves the returned
session has the requested ID and belongs to that repository's retention role.

The complete evidence is in `agent-handoff/architect-review.md`.

## Accepted Architecture Decision

The shared sensitive-text primitive's additive recognition of `Set-Cookie`,
`secret=...`, and `credential(s)=...` is explicitly approved.

Do not roll it back, create separate drifting vocabularies, or change
sensitive-text behavior in this remediation.

The separate `_ConversationContract` base and current canonical wire behavior
are also accepted. Do not refactor contract families.

## Required Session Lookup Invariant

For every service operation that resolves a session:

1. query both injected repository roles;
2. safely canonicalize each successful result;
3. require each returned session ID to equal the requested ID;
4. require a volatile-repository result to use
   `ConversationRetentionPolicy.SESSION_ONLY`;
5. require a durable-repository result to use one of the approved durable
   policies;
6. return only when exactly one repository owns the session;
7. return `SESSION_NOT_FOUND` when neither owns it; and
8. return fixed `REPOSITORY_FAILED` when both own it or either result is
   malformed/miscorrelated.

Do not short-circuit after the volatile repository succeeds.

This invariant must protect:

- `get_session`;
- `get_turn`;
- `list_turns`;
- `start_turn`;
- `complete_turn`;
- `fail_turn`;
- `close_session`; and
- `delete_session`.

Ambiguity must be detected before mutation or deletion.

## Required Turn Correlation

Before trusting a repository turn result:

- require exact `ConversationTurn`;
- reconstruct a fresh canonical snapshot;
- require `turn.turn_id` to equal the requested turn ID;
- require `turn.session_id` to equal the owning session ID;
- require the turn ID to occupy exactly
  `session.turn_ids[turn.sequence_number - 1]`;
- reject out-of-range, duplicate, missing, or mismatched correlation with
  fixed `REPOSITORY_FAILED`.

Do not reveal whether a malformed dependency returned another valid
identifier.

## Required List Correlation

### Session lists

For each repository result:

- require the exact canonical collection shape promised by the Protocol;
- reject a result longer than the requested limit before global aggregation;
- snapshot every exact `ConversationSession`;
- require volatile results to be session-only;
- require durable results to be durable;
- reject duplicate IDs within or across repositories;
- preserve the service's existing deterministic global ordering and limit.

The service may sort a valid bounded result; it must not silently truncate an
oversized dependency response and call it valid.

### Turn lists

Resolve and retain the owning canonical session, then require:

- the exact canonical collection shape promised by the Protocol;
- result length not greater than the requested limit;
- every item is an exact canonical `ConversationTurn`;
- every `session_id` matches the requested/owning session;
- IDs are unique;
- sequence numbers are exactly `1..N` for the returned prefix; and
- returned turn IDs equal
  `session.turn_ids[:len(returned_turns)]`.

Reject sorted-but-gapped, reordered, foreign-session, wrong-ID, duplicate, or
oversized results.

## Required Purge Result Validation

Require the durable repository purge result to be:

- the exact canonical collection shape promised by the Protocol;
- no longer than the requested limit;
- unique; and
- composed only of canonical identifiers.

Do not accept a list subclass, generator, set, mapping, runtime object, or a
tuple containing invalid/mutable items.

No content or repository details may enter the public result or error.

## Safe Failure and Side-Effect Semantics

All newly detected dependency contradictions must:

- expose only fixed `ConversationApplicationErrorCode.REPOSITORY_FAILED`;
- suppress expected cause/context;
- not expose identifiers, retention policy, payload, path, SQL, marker,
  runtime repr, or underlying exception details;
- make no repository mutation or deletion;
- not move a record between repositories;
- not repair ambiguous state automatically.

`MemoryError`, `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit` remain
authoritative and propagate unchanged.

Unexpected programming errors retain the repository/application policy already
established in Attempt 1; do not broaden exception catching unrelated to this
finding.

## Preserve Existing Behavior

Do not change:

- public conversation fields, enums, schema versions, constants, or error
  vocabulary;
- retention policies, expiration, activity, or clock/ID sampling semantics;
- session/turn lifecycle or revision behavior;
- repository protocol or valid repository API output;
- in-memory or SQLite transaction, schema, corruption, purge, or deletion
  semantics;
- canonical serialization;
- sensitive-text matching/redaction;
- Task 3 reasoning behavior;
- Run, Runner, Application, Usage, Workflow, Product Pack, CLI, or packaging
  behavior;
- valid output ordering.

Valid Attempt 1 service flows must remain byte/structurally identical.

## Allowed Changes

Expected:

- `pmqa/conversation/service.py`;
- `tests/test_conversation_service.py`;
- `agent-handoff/coder-report.md`.

If an additional focused conversation test file is genuinely required,
explain why. No production module other than `service.py` should need to
change.

Do not modify:

- conversation contracts or repositories;
- security/sensitive-text or reasoning scrubber code;
- CLI, dependencies, packaging configuration, Web/UI files;
- Task 4/5/5A/5C production code;
- product documentation;
- another role's handoff file.

Use one minimal remediation implementation commit and one report-only Coder
handoff commit. Do not amend Attempt 1.

## Out of Scope

Do not implement:

- Task 5D.1B secure Web/API;
- Task 5D.1C workbench/CLI/packaging;
- FastAPI, Uvicorn, HTTP, React, TypeScript, Vite, or Node;
- ADO/Copilot integration;
- conversation citations, workflow suggestions, capabilities, artifacts,
  approvals, operations, receipts, or usage UI;
- new retention modes;
- database repair or migration;
- contract-family consolidation;
- PR creation or merge;
- Task 5D.2, Task 5B, Task 6, or Task 7.

## Required Focused Tests

Use deterministic Protocol-conforming fakes plus the real in-memory
repositories where appropriate.

Directly test:

- same session ID present in both real repositories;
- same ID with equal payload and with different payload;
- volatile-only repository returning a durable policy;
- durable-only repository returning session-only policy;
- `get_session(requested_id)` returning a different valid session ID;
- `get_turn(requested_id)` returning a different valid turn ID;
- turn returned for a foreign session;
- list result longer than requested;
- wrong collection types and subclasses;
- duplicate, reordered, gapped, foreign-session, or wrong-prefix turn lists;
- duplicate IDs within one session list and across repository lists;
- invalid or noncanonical purge result shapes;
- marker-bearing malformed dependency values never leaked;
- ambiguity detected before start/complete/fail/close/delete mutation;
- both repositories are inspected even when volatile lookup succeeds;
- resource/control-flow propagation.

Retain tests proving:

- exactly one correctly routed session resolves;
- valid list ordering and limit remain unchanged;
- valid turn start/terminal/close/delete flows remain unchanged;
- valid purge output remains unchanged;
- 30-day default and all retention modes remain unchanged;
- sensitive ingress remains unchanged.

## Validation Commands

Run and report:

```bash
.venv/bin/python -m pytest tests/test_conversation_service.py tests/test_conversation_repository.py tests/test_conversation_contracts.py tests/test_conversation_imports.py tests/test_scrubber.py tests/test_boundary_policy.py tests/test_packaging.py -q
.venv/bin/python -m pytest tests/test_run_contracts.py tests/test_application_contracts.py tests/test_application_service.py tests/test_usage_contracts.py tests/test_usage_repository.py tests/test_usage_summary.py -q
.venv/bin/python -m pytest tests/test_workflow_runtime.py tests/test_workflow_reducer.py tests/test_supervisor_policy.py tests/test_langgraph_workflow.py -q
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest products/demo/generated_tests -q
.venv/bin/python -m compileall -q pmqa products
git diff --check
git status --short
```

Use an isolated bytecode cache for compileall. New tests remain offline and
must not use browser, network, Node, provider, ADO, or external Product Pack.

## Acceptance Criteria

- exactly one correctly routed repository owns every resolved session;
- duplicate cross-repository ownership is rejected consistently;
- returned session and turn identities are exactly correlated;
- volatile/durable retention role mismatch is rejected;
- session and turn lists are bounded, canonical, unique, and correlated;
- purge output is canonical and bounded;
- contradictions fail before mutation with fixed safe errors;
- valid Attempt 1 behavior and output remain unchanged;
- shared sensitive-text expansion remains in place;
- focused and full regressions remain green;
- only allowed files change.

## Expected Deliverables

- hardened repository-result correlation in the Application Service;
- focused adversarial regression tests;
- one minimal implementation commit;
- one report-only Coder handoff commit;
- clean synchronized branch;
- no PR or merge.

## Required Coder Handoff

Replace `agent-handoff/coder-report.md` with the complete Task 5D.1A Attempt 2
report. Include:

- Task/Attempt, branch, and exact Git-derived starting HEAD;
- remediation implementation commit;
- changed files;
- exact lookup/list/turn/purge correlation behavior;
- safe-failure and no-side-effect evidence;
- focused and full validation results;
- remaining risks and scope confirmation;
- one recommended review depth (`Light`, `Standard`, or `Deep`);
- one-sentence reason;
- 3–6 suggested Reviewer focus areas;
- Human Summary using the mandatory routing and one-sentence Handoff Note.

Recommended review depth is advisory. The Architect retains final authority.

Do not include the report commit's own SHA. The Independent Reviewer derives
it from Git.
