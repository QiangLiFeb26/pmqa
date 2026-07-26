# Independent Reviewer Report

Owner: Independent Reviewer

Status: Executed for PMQA Task 5D.1A, Attempt 2

## Task Correlation

Task: PMQA Task 5D.1A — Repository Result Correlation

Task ID: `PMQA-5D.1A`

Attempt: `2`

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed Starting HEAD: `edb3382e4483fefaaba5c18d0c3baf3980b08109`

Reviewed Implementation Commit(s): `c13fc8729e22fe5316719fdf2eafef31b6bcbb80`
("harden conversation repository correlation")

Derived Coder Report Commit: `f1db9a1090513bedfe45036f6a0c6c9f7f817eba`
("report Task 5D.1A repository correlation remediation")

Correlation Verification:

- derived with `git log -1 --format=%H -- agent-handoff/coder-report.md` ->
  `f1db9a1090513bedfe45036f6a0c6c9f7f817eba`;
- `git merge-base --is-ancestor edb3382e4483fefaaba5c18d0c3baf3980b08109 HEAD`
  succeeds; `edb3382...` is an ancestor of `c13fc87...`, and `c13fc87...` is
  an ancestor of `f1db9a1...` (linear sequence
  `edb3382 -> c13fc87 -> f1db9a1` on this branch);
- the reviewed Attempt 1 Reviewer HEAD named by `current-task.md`,
  `67492ea5ef551fd10a47338f270408e92baa99c4` (this Reviewer's own prior
  Attempt 1 report commit), is an ancestor of the recorded starting HEAD;
- the correlation header of `coder-report.md` at the derived commit names
  Task ID `PMQA-5D.1A`, Attempt `2`, branch
  `agent/task-5c-1-canonical-run-contract`, and starting HEAD
  `edb3382e4483fefaaba5c18d0c3baf3980b08109`, matching `current-task.md`;
- `git diff --stat c13fc87..f1db9a1` touches only
  `agent-handoff/coder-report.md`, so the derived commit is the report's
  latest authorized change with no later unauthorized replacement.

This Reviewer report does not contain or predict its own commit SHA. The
Architect derives the Reviewer report commit from Git and records it in
`architect-review.md`.

## Independent Review Method

Inspection order completed:

1. `current-task.md` and acceptance criteria (the Architect's reported gap
   in `_find_session`'s short-circuit behavior and the full required
   session/turn/list/purge correlation invariant list);
2. named baseline-to-implementation diff (`edb3382..c13fc87`) — full read of
   the `pmqa/conversation/service.py` diff and a structural pass over the
   entire additive `tests/test_conversation_service.py` diff;
3. independently selected validation (see Test Evidence), including two ad
   hoc adversarial "misbehaving repository" scripts written from scratch
   (not the Coder's `CountingRepository` test harness) to independently
   reproduce the fix;
4. full `coder-report.md` (read only after steps 1-3).

Active-task `architect-review.md` read before publication: No

Prior closed review or architecture material consulted, with reason: this
Reviewer authored the Attempt 1 review of this same task
(`agent-handoff/reviewer-report.md` at commit `67492ea`, superseded by this
report), which did not catch the `_find_session` short-circuit gap the
Architect subsequently found; that prior review context is directly relevant
to independently judging whether this attempt closes the gap, so I compared
the Attempt 1 code (via `git diff edb3382..c13fc87`) against my own
recollection of what Attempt 1 validated, rather than re-deriving the gap
from `architect-review.md` (unread, per protocol).

## Review Depth

Actual Review Depth: Deep

Review Depth Reason: this remediation is the trust boundary between the
Application Service and its injected repository dependencies — every future
conversation read and mutation (and, per the Task 5D.0 architecture, every
future Web/API request) depends on this correlation gate rejecting
ambiguous or miscorrelated repository results before they are exposed or
acted on. A superficial pass re-running the Coder's own tests would not by
itself prove the fix is genuine, since Attempt 1 also passed all of its own
tests while still admitting the reported gap. I traced every changed method
in `service.py` line-by-line against the eight-point session-lookup
invariant and the turn/list/purge correlation requirements, and
independently constructed two "misbehaving repository" adversarial scripts
from scratch. This matches the Coder's advisory recommendation but was
independently selected.

## Overall Assessment

The remediation correctly and thoroughly closes the reported gap, with no
regression to Attempt 1 behavior and no scope creep. The diff touches
exactly the two allowed files (`pmqa/conversation/service.py`,
`tests/test_conversation_service.py`); the test file diff is **purely
additive** (417 insertions, 0 deletions — confirmed via
`git diff --stat`), meaning every Attempt 1 test assertion for valid flows
remains verbatim and (per Test Evidence below) still passes against the
hardened code, directly supporting "Valid Attempt 1 service flows must
remain byte/structurally identical."

**Session lookup (`_find_session`).** I traced the full control flow: the
loop now always iterates both `(self._volatile_repository, True)` and
`(self._durable_repository, False)` with no early `return` inside the loop
body — ambiguity or malformed-result detection sets a `malformed` flag or
appends to a `matches` list and always `continue`s to the next repository,
closing the exact short-circuit gap the Architect reported. Each successful
`get_session` result is passed through `_session_snapshot` (exact-type
check plus full canonical `from_dict(to_dict())` reconstruction) inside a
nested `try`/`except ConversationApplicationError: malformed = True;
continue`, so a malformed snapshot from either repository is caught without
ever aborting the loop early. The role check
(`volatile and retention_policy is not SESSION_ONLY`, or `not volatile and
not retention_policy.durable`) and the identity check
(`canonical_session.session_id != session_id`) run inside that same
protected block. After the loop, `if malformed or len(matches) > 1: raise
REPOSITORY_FAILED`, `elif matches: return matches[0]`, `else: raise
SESSION_NOT_FOUND` — this is an exact, correct implementation of all eight
required invariant points, including "return fixed REPOSITORY_FAILED when
both own it or either result is malformed/miscorrelated" (the `or`
correctly combines both failure classes into one fixed outcome).

**Turn correlation (`_get_turn`).** Now takes the already-validated
`session` object (threaded through from `_find_session` at every call site:
`get_turn`, and `_terminalize_turn` for `complete_turn`/`fail_turn`) and,
after reconstructing the turn, requires `turn.turn_id == requested`,
`turn.session_id == session.session_id`, and — the strongest check —
`session.turn_ids[turn.sequence_number - 1] == turn_id` with an explicit
bounds check on the index first. This closes the case where a repository
returns a structurally valid turn for the *wrong* slot or a *foreign*
session, which Attempt 1 did not check.

**List correlation.** `list_turns` now rejects a non-`tuple`
(explicit `type(turns) is not tuple`, which also rejects tuple subclasses)
or over-limit result *before* any per-item work, then requires unique turn
IDs, sequence numbers forming the exact prefix `1..N` (stronger than
Attempt 1's "already sorted" check), correct `session_id` on every item,
and — new in this attempt — that the returned turn-ID sequence exactly
equals `session.turn_ids[:len(canonical_turns)]`, cross-checking against
the independently-validated session's own ordering rather than only the
turn list's internal self-consistency. `_list_sessions` performs the
equivalent per-repository-role check (exact tuple, bounded, unique within
the role, correct retention role for that slot) before the existing
combined cross-repository duplicate check and global ordering/limit logic
in `list_sessions` runs unchanged.

**Purge validation.** `purge_expired` now requires the durable repository's
result to be an exact `tuple` (rejecting lists, generators, sets, mappings,
and tuple subclasses) and bounded *before* attempting to validate
individual identifiers, then validates each item as a canonical identifier
and rejects duplicates — correctly ordered so a non-tuple/oversized
response never reaches the per-item validation loop at all.

I independently constructed two adversarial "misbehaving repository" test
doubles from scratch — not the Coder's `CountingRepository` harness — and
confirmed the fix against both (see Test Evidence): a repository that
returns a session with the wrong `session_id`, and a repository plugged
into the *volatile* slot that dishonestly returns a real *durable*-policy
session. Both were correctly rejected with `REPOSITORY_FAILED` and no
identifier leaked into the exception.

All validation commands listed in `current-task.md`, run independently
rather than accepted from the Coder report, pass with no failures, errors,
or unexplained skips.

## Findings

None. The reported `_find_session` short-circuit gap is independently
confirmed closed by direct code tracing and by two adversarial
reproductions built independently of the Coder's own test suite. No new
gap surfaced during this Deep inspection.

## Acceptance Criteria Coverage

| Acceptance criterion | Evidence | Result |
| --- | --- | --- |
| Exactly one correctly routed repository owns every resolved session | `_find_session` traced in full; independently reproduced same-ID-in-both-repositories rejection is covered by the Coder's own `test_lookup_rejects_same_session_id_in_both_repositories` (using two real in-memory repositories), independently rerun | Met |
| Duplicate cross-repository ownership is rejected consistently | `if malformed or len(matches) > 1: raise REPOSITORY_FAILED` traced; applies uniformly to all 8 protected operations since they all route through `_find_session` | Met |
| Returned session and turn identities are exactly correlated | Session identity/role checks in `_find_session`; turn identity/slot check in `_get_turn`; independently reproduced a wrong-`session_id` repository result being rejected with no leak | Met |
| Volatile/durable retention role mismatch is rejected | Role checks in `_find_session` and `_list_sessions`; independently reproduced a volatile-slot repository dishonestly returning a durable-policy session being rejected | Met |
| Session and turn lists are bounded, canonical, unique, and correlated | `_list_sessions`/`list_turns` traced; both reject non-tuple/oversized results before per-item work and cross-check against the validated session's `turn_ids` | Met |
| Purge output is canonical and bounded | `purge_expired` traced: exact-tuple and bound check precede per-item identifier validation and duplicate rejection | Met |
| Contradictions fail before mutation with fixed safe errors | `_find_session` (and therefore every mutating operation) runs before any `append_turn`/`replace_turn`/`close_session`/`delete_session` call; the Coder's `test_ambiguous_ownership_fails_before_every_mutation` (parametrized over all 5 mutating actions, asserting the mutation methods are never called) independently rerun | Met |
| Valid Attempt 1 behavior and output remain unchanged | `tests/test_conversation_service.py` diff is 417 insertions / 0 deletions (confirmed via `git diff --stat`); all pre-existing Attempt 1 assertions independently rerun unchanged and pass | Met |
| Shared sensitive-text expansion remains in place | `git diff --stat edb3382..c13fc87` shows zero changes to `pmqa/security/sensitive_text.py`, `pmqa/reasoning/scrubber.py`, or `pmqa/conversation/contracts.py` | Met |
| Focused and full regressions remain green | 195 focused + 467 Task 5C + 98 Task 4 + 2014/5-skip full suite + 2 Playwright, all independently run, all pass | Met |
| Only allowed files change | `git diff --stat` from starting HEAD to the derived report commit touches exactly `pmqa/conversation/service.py`, `tests/test_conversation_service.py`, and `agent-handoff/coder-report.md` | Met |

## Test Evidence

### Coder Evidence Reviewed

The Coder report claims: 195 passed for the focused conversation/security/
packaging group; 467 passed for the Task 5C Run/Application/Usage
regression set; 98 passed for the Task 4 orchestration set; 2014 passed, 5
skipped for the full default suite; 2 passed for
`products/demo/generated_tests`; `compileall` and `git diff --check` clean;
clean worktree with the implementation commit pushed. This claimed evidence
was read only after independent execution below and matches it exactly.

### Independently Run

All commands below were executed by the Reviewer directly, before reading
the Coder's claimed results, from the repository root on the reviewed
branch:

- `.venv/bin/python -m pytest tests/test_conversation_service.py tests/test_conversation_repository.py tests/test_conversation_contracts.py tests/test_conversation_imports.py tests/test_scrubber.py tests/test_boundary_policy.py tests/test_packaging.py -q`
  -> `195 passed`
- `.venv/bin/python -m pytest tests/test_run_contracts.py tests/test_application_contracts.py tests/test_application_service.py tests/test_usage_contracts.py tests/test_usage_repository.py tests/test_usage_summary.py -q`
  -> `467 passed`
- `.venv/bin/python -m pytest tests/test_workflow_runtime.py tests/test_workflow_reducer.py tests/test_supervisor_policy.py tests/test_langgraph_workflow.py -q`
  -> `98 passed, 1 warning` (pre-existing `LangChainPendingDeprecationWarning`,
  unrelated to this change)
- `.venv/bin/python -m pytest -q` (full default suite) -> `2014 passed, 5 skipped, 1 warning`
- `.venv/bin/python -m pytest products/demo/generated_tests -q` -> `2 passed`
- `PYTHONPYCACHEPREFIX=<isolated scratch directory> .venv/bin/python -m compileall -q pmqa products`
  -> exit code `0`, no output
- `git diff --check` -> exit code `0`, no output
- `git status --short` -> empty (clean worktree)

In addition, and independent of the Coder's own `CountingRepository` test
harness, I wrote two standalone adversarial fake `ConversationRepository`
implementations and wired each into a real `ConversationApplicationService`:

- an `EvilRepository` whose `get_session` always returns a real session
  object with its `session_id` field rewritten to a different value than
  requested — calling `service.get_session(real_session.session_id)`
  correctly raised `ConversationApplicationErrorCode.REPOSITORY_FAILED`,
  with the injected wrong ID absent from the exception's string form;
- a `WrongRoleRepository`, plugged in as the *volatile* repository slot,
  whose `get_session` returns a genuine `THIRTY_DAYS`-policy session (i.e.
  a repository lying about which retention role it serves) — calling
  `service.get_session(...)` correctly raised `REPOSITORY_FAILED`.

Both scripts were written from scratch against the public
`ConversationRepository` Protocol and `ConversationApplicationService` API,
independent of any fixture or helper in `tests/test_conversation_service.py`.

No listed validation command was left unrun. No test was skipped by
Reviewer choice. Environment: local `.venv` (Python 3.9), macOS/Darwin, no
network access used or required.

## Security, Scope, and Compatibility

Security observations: the hardened `_find_session`/`_get_turn`/
`_list_sessions`/`list_turns`/`purge_expired` no longer trust a single
repository's result in isolation — every path that resolves or lists
session/turn state now independently reconstructs and cross-validates the
result before it is exposed or used as the basis for a mutation. All newly
detected contradictions map to the single fixed
`ConversationApplicationErrorCode.REPOSITORY_FAILED` with no identifier,
retention policy, or dependency detail leaked into the exception — confirmed
both by reading the code (every new raise path funnels through
`_raise_application_error`, which suppresses cause/context via `from None`)
and by my own independent adversarial reproductions above.

Scope observations: the diff touches only `pmqa/conversation/service.py`
and `tests/test_conversation_service.py`, plus the Coder-owned report in a
separate commit. No contract, repository implementation, security/
sensitive-text, reasoning scrubber, CLI, dependency, packaging, or Task
4/5/5A/5C production file was modified — confirmed via `git diff --stat`.

Compatibility observations: the additive-only test diff plus the identical
pass counts for every pre-existing regression suite (467 Task 5C, 98 Task
4, and the full 2014-test default suite — up from 1970 in Attempt 1,
consistent with the 44 net new tests, no reduction) confirm valid Attempt 1
behavior is preserved unchanged.

## Verdict

Verdict: Pass

This verdict is advisory. The Architect makes the final technical
disposition.

## Suggested Architect Focus

- The reported `_find_session` short-circuit gap is independently confirmed
  closed, including under two adversarial repository doubles constructed
  from scratch by this Reviewer (not the Coder's own test harness). Nothing
  further is blocking from this Reviewer's independent inspection.
- The Coder's own "Remaining Risks" section notes the service "cannot prove
  a malicious repository honored its internal transaction semantics"
  (e.g., a repository could still return a *self-consistent* but stale
  snapshot that passes every correlation check yet reflects data from
  before a concurrent write completed). This is accurately scoped as
  outside this remediation — the task was about *result correlation*
  (detecting incoherent/miscorrelated returns), not about re-verifying a
  repository's own transactional correctness, which Attempt 1's SQLite
  transaction tests already cover separately. No action needed, just
  flagging that this boundary is intentional and documented, not an
  oversight.

## Reviewer Write-Boundary Confirmation

Repository files changed by Reviewer:

- `agent-handoff/reviewer-report.md`

Confirmation: I changed no production code, tests, configuration, schemas,
packaging, scripts, product documentation, or another role's handoff file.
