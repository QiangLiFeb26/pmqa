# Architect Review

Owner: Architect

Task: PMQA Task 5D.1A — Conversation Session and Retention Foundation

Task ID: `PMQA-5D.1A`

Attempt: `1`

Status: Needs Revision

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed Starting HEAD:
`16655cd3a8129599a585b78bcc5336706d595a3b`

Reviewed Implementation Commit:
`4ae3893d4f12a4dff1a8f6bf18cbfcc07578be20`

Derived Coder Report Commit:
`4f0b6ae28a1a7aea0acdacadb9180ee4cf6693b3`

Derived Reviewer Report Commit:
`67492ea5ef551fd10a47338f270408e92baa99c4`

The Reviewer report commit was derived from Git with:

```bash
git log -1 --format=%H -- agent-handoff/reviewer-report.md
```

This review does not predict the SHA of its own containing commit.

## Correlation and Ownership Verification

- the active branch and upstream are
  `agent/task-5c-1-canonical-run-contract`;
- starting HEAD `16655cd...` is an ancestor of implementation commit
  `4ae3893...`;
- implementation commit `4ae3893...` is an ancestor of Coder report commit
  `4f0b6ae...`;
- Coder report commit `4f0b6ae...` is an ancestor of Reviewer report commit
  `67492ea...`;
- Coder and Reviewer reports identify the same Task, Attempt, branch,
  starting HEAD, and implementation commit;
- the implementation changed only authorized production, test, and
  documentation files;
- the Coder report commit changed only `agent-handoff/coder-report.md`;
- the Reviewer report commit changed only
  `agent-handoff/reviewer-report.md`;
- the branch matched its upstream and the worktree was clean before this
  Architect disposition.

## Review Depth

Deep

The Architect independently selected Deep review. This checkpoint establishes
persisted user text, retention, SQLite transaction, repository routing, and
safe-ingress boundaries used by the future local Web trust root.

## Independent Reviewer Result

Reviewer verdict: `Pass`

Reviewer finding:

- one Low scope deviation: the shared sensitive-text primitive expands the
  existing Task 3 scrubber's matching surface.

The Reviewer performed a legitimate Deep review, read all production modules,
traced SQL and transaction behavior, ran the full validation set, and
independently reproduced high-risk invariants.

The Architect accepts the Reviewer's evidence but overrides the advisory
verdict because independent application-boundary review found a blocking
repository-correlation defect.

## Overall Assessment

The core implementation is strong:

- strict immutable conversation contracts and retention invariants;
- approved session-only/7/30/90-day policy with 30-day default;
- deterministic turn lifecycle and optimistic session revision;
- separate volatile and durable repository composition;
- real SQLite schema, parameterized SQL, transactions, foreign keys,
  corruption checks, deletion, and expiry purge;
- fixed-safe sensitive-text ingress;
- import and wheel isolation;
- no premature Web/API/frontend/ADO/Copilot scope.

However, `ConversationApplicationService` does not consistently treat its
injected repositories as untrusted correlated dependencies. Lookup returns
the first session found and does not inspect the second repository, validate
the returned session ID, or validate retention-policy ownership.

The result is a valid public service state that is ambiguous or incorrectly
correlated across repositories.

## Accepted Reviewer Finding

### Shared sensitive-text matching expansion

Accepted as an intentional security hardening.

The neutral primitive adds recognition of:

- `Set-Cookie`;
- `secret=...`; and
- `credential=...` / `credentials=...`.

This expands Task 3 scrubber behavior for previously unrecognized
high-confidence credential shapes. It does not reduce redaction, change
previously matched output, expose data, or break existing tests.

The original task contained competing requirements: use one non-drifting
primitive, cover these conversation-ingress shapes, and preserve Task 3
behavior. Expanding the shared security boundary is safer than maintaining
two independent vocabularies. The Architect explicitly authorizes this
additive behavior.

No rollback or split pattern vocabulary is required.

## Blocking Finding

### F1 — Repository lookup silently accepts ambiguous or miscorrelated state

Severity: Blocking

Primary location:

- `pmqa/conversation/service.py`;
- `ConversationApplicationService._find_session`;
- adjacent service read/correlation helpers.

Current `_find_session` iterates:

```text
volatile repository
durable repository
```

and returns immediately after the first successful lookup.

It does not:

- query the second repository before deciding uniqueness;
- reject the same `session_id` existing in both repositories;
- require the returned `ConversationSession.session_id` to equal the
  requested ID; or
- require session-only records to come from the volatile role and durable
  retention records to come from the durable role.

#### Independent reproduction 1 — duplicate ownership

The Architect created one valid `ConversationSession` with the same ID in two
independent real `InMemoryConversationRepository` instances, then injected
them as volatile and durable repositories.

Observed:

```text
service.get_session(id)  -> accepted and returned the volatile record
service.list_sessions()  -> repository_failed
```

The same invalid cross-repository state is therefore accepted or rejected
depending on the read path.

#### Independent reproduction 2 — wrong returned identity

The Architect injected a Protocol-conforming repository whose
`get_session(requested_id)` returned a valid canonical session with a
different ID.

Observed:

```text
requested: conversation.session.requested
returned:  conversation.session.wrong
```

`get_session()` returned the miscorrelated record without error.

#### Affected behavior

Because `_find_session` is shared, the ambiguity affects:

- `get_session`;
- `get_turn`;
- `list_turns`;
- `start_turn`;
- `complete_turn`;
- `fail_turn`;
- `close_session`; and
- `delete_session`.

A duplicated or miscorrelated identity can select the wrong retention store,
return the wrong conversation, mutate the wrong copy, close it, or delete it.
This is incompatible with the service report's claim that duplicate identities
are rejected across repositories and with the task's dependency-snapshot and
correlation requirements.

#### Adjacent boundary gaps to close in the same remediation

The same service trust boundary should directly validate:

- `get_turn(requested_id)` returns that exact turn ID;
- bounded session lists do not exceed the requested limit and each record
  belongs to the repository's retention role;
- bounded turn lists match the owning session's exact ordered turn-ID prefix,
  sequence numbers, and session ID;
- repository collection results use the canonical exact collection shape
  promised by the Protocol; and
- purge results are bounded, unique, canonical IDs in their canonical
  collection shape.

These are not requests to redesign repository implementations. They are
defensive checks on values returned by injected dependencies before the
Application Service trusts or exposes them.

## Non-Blocking Architecture Notes

### Conversation contract base

The independent `_ConversationContract` is acceptable.

Importing a private Run base would create inappropriate coupling, and
conversation message/tree bounds differ from Run and Usage. Do not consolidate
contract families in the remediation.

### Plain-JSON equality

The current plain `==` canonical comparison is not a demonstrated bypass:
strict Pydantic fields reject int/float and bool/int coercion for the existing
numeric fields. Do not change wire semantics in this remediation.

If a future conversation contract adds dynamic numeric payloads, it must use
or add a type-sensitive recursive equality check.

## Acceptance Criteria Coverage

| Acceptance criterion | Result |
| --- | --- |
| Canonical session and turn contracts | Met |
| Approved retention modes and 30-day default | Met |
| Session-only state excluded from SQLite | Met at repository create boundary |
| Deterministic activity and expiration | Met |
| Manual deletion and purge | Met in valid repository state |
| SQLite atomic writes and revision CAS | Met |
| Shared safe sensitive ingress | Met; additive Task 3 expansion accepted |
| SQLite corruption and operational containment | Met |
| Import and packaging isolation | Met |
| Service rejects duplicate identities across repositories | Not met |
| Service validates dependency result correlation | Not met |
| Existing regressions remain green | Met |
| No later 5D scope started | Met |

## Validation Evidence

Independent Reviewer:

- focused conversation/security/packaging group: `151 passed`;
- Task 5C regressions: `467 passed`;
- Task 4 regressions: `98 passed`;
- full default suite: `1970 passed, 5 skipped`;
- generated Playwright regressions: `2 passed`;
- compileall, Markdown links, `git diff --check`, scope, and worktree checks:
  passed.

Architect:

- complete task, Coder report, Reviewer report, production modules, and
  implementation diff inspected;
- focused conversation/security/packaging group: `151 passed`;
- duplicate same-ID state independently reproduced with two real in-memory
  repositories;
- wrong-session-ID return independently reproduced with a
  Protocol-conforming injected repository;
- `git diff --check` passed and the worktree remained clean.

The passing suite does not contain the cross-repository duplicate and
miscorrelated dependency-return cases above.

## Required Changes

Complete one narrow Task 5D.1A Attempt 2 remediation:

- harden Application Service repository-result correlation;
- reject ambiguous cross-repository ownership;
- validate repository role, IDs, bounds, and ordered correlations;
- retain all approved contract, repository, SQLite, retention, and
  sensitive-text behavior;
- add focused adversarial tests.

Do not begin Web/API/frontend work.

## Decision

Needs Revision

PMQA Task 5D.1A is not approved at implementation commit
`4ae3893d4f12a4dff1a8f6bf18cbfcc07578be20`.

## Next Recommended Task

Complete PMQA Task 5D.1A Attempt 2 — Repository Result Correlation,
defined in `agent-handoff/current-task.md`.
