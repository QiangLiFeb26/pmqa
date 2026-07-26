# Independent Reviewer Report

Owner: Independent Reviewer

Status: Executed for PMQA Task 5D.1A, Attempt 1

## Task Correlation

Task: PMQA Task 5D.1A — Conversation Session and Retention Foundation

Task ID: `PMQA-5D.1A`

Attempt: `1`

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed Starting HEAD: `16655cd3a8129599a585b78bcc5336706d595a3b`

Reviewed Implementation Commit(s): `4ae3893d4f12a4dff1a8f6bf18cbfcc07578be20`
("add conversation session retention foundation")

Derived Coder Report Commit: `4f0b6ae28a1a7aea0acdacadb9180ee4cf6693b3`
("report Task 5D.1A conversation foundation")

Correlation Verification:

- derived with `git log -1 --format=%H -- agent-handoff/coder-report.md` ->
  `4f0b6ae28a1a7aea0acdacadb9180ee4cf6693b3`;
- `git merge-base --is-ancestor 16655cd3a8129599a585b78bcc5336706d595a3b HEAD`
  succeeds; `16655cd...` is an ancestor of `4ae3893...`, and `4ae3893...` is
  an ancestor of `4f0b6ae...` (linear sequence
  `16655cd -> 4ae3893 -> 4f0b6ae` on this branch);
- the Task 5D.0 Reviewer baseline named by `current-task.md`,
  `115910e2662ce6bd2de6f807dfb3dfddc201a4b3` (this Reviewer's own prior
  report commit), is an ancestor of the recorded starting HEAD;
- the correlation header of `coder-report.md` at the derived commit names
  Task ID `PMQA-5D.1A`, Attempt `1`, branch
  `agent/task-5c-1-canonical-run-contract`, and starting HEAD
  `16655cd3a8129599a585b78bcc5336706d595a3b`, matching `current-task.md`;
- `git diff --stat 4ae3893..4f0b6ae` touches only
  `agent-handoff/coder-report.md`, so the derived commit is the report's
  latest authorized change with no later unauthorized replacement.

This Reviewer report does not contain or predict its own commit SHA. The
Architect derives the Reviewer report commit from Git and records it in
`architect-review.md`.

## Independent Review Method

Inspection order completed:

1. `current-task.md` and acceptance criteria;
2. named baseline-to-implementation diff (`16655cd..4ae3893`) — full read of
   all four new/changed production modules
   (`pmqa/conversation/contracts.py`, `pmqa/security/sensitive_text.py` plus
   the `pmqa/reasoning/scrubber.py` diff, `pmqa/conversation/repository.py`,
   `pmqa/conversation/service.py`), plus `pmqa/conversation/__init__.py`,
   the `tests/test_packaging.py` diff, and a structural pass over all five
   new test files;
3. independently selected validation (see Test Evidence), including four
   ad hoc adversarial scripts run directly against the implementation,
   independent of the Coder's own tests;
4. full `coder-report.md` (read only after steps 1-3).

Active-task `architect-review.md` read before publication: No

Prior closed review or architecture material consulted, with reason: this
Reviewer authored the Task 5D.0 review that approved the architecture this
checkpoint implements; that context was used only to confirm this
implementation matches the approved logical design (session/turn/retention
separation, reuse-not-duplication of Task 4/5/5A/5C boundaries), not to
substitute for independently reading this attempt's actual code.

## Review Depth

Actual Review Depth: Deep

Review Depth Reason: this is the first real code implementation under Task
5D, establishing the persistence, retention, and sensitive-text ingress
trust boundary that the future local Web/API layer (5D.1B) will build on
directly. It also touches a security-sensitive shared primitive
(`pmqa.security.sensitive_text`) whose behavior change propagates into the
existing Task 3 reasoning scrubber — an area where an incorrect or
under-scrutinized change could silently alter already-shipped redaction
behavior. I read all four production modules in full, traced the SQLite
transaction/compare-and-swap logic and the sensitive-text extraction by
hand, and independently reproduced four key invariants outside the Coder's
own test suite. This matches the Coder's advisory recommendation but was
independently selected.

## Overall Assessment

The implementation is a careful, thorough, and largely correct local
persistence and retention foundation. `pmqa/conversation/contracts.py` adds
strict frozen `ConversationSession`/`ConversationTurn` records following the
established Run/Usage contract discipline (own parallel `_ConversationContract`
base rather than importing `pmqa.run.models._RunContract` — see Suggested
Architect Focus); `pmqa/conversation/repository.py` adds a `ConversationRepository`
protocol with `InMemoryConversationRepository` and a real
`SQLiteConversationRepository`; `pmqa/conversation/service.py` adds the
synchronous `ConversationApplicationService`; and
`pmqa/security/sensitive_text.py` extracts the Task 3 scrubber's credential
patterns into a shared primitive reused by both the scrubber and the new
conversation ingress boundary.

**SQLite correctness (the highest-risk surface).** I traced every query and
confirmed all statements use parameterized `?` placeholders — no string
interpolation of any caller-supplied value into SQL text anywhere in the
file. Every multi-statement transition (`create_session`, `_write_transition`
for append/replace, `close_session`, `delete_session`, `purge_expired`,
`_initialize`) uses `BEGIN IMMEDIATE` (acquiring the write lock up front
rather than SQLite's default deferred locking, which avoids a class of
races where two transactions can both proceed through reads before either
blocks on a write) followed by `commit()` on success and `rollback()` in
every expected-failure branch, with the `threading.RLock()` providing
intra-process serialization on top of SQLite's own inter-connection
locking. Optimistic concurrency is implemented as a genuine SQL-level
compare-and-swap: `_update_session`'s `UPDATE ... WHERE session_id = ? AND
revision = ?` is atomic at the database level, and `cursor.rowcount != 1`
(session missing or revision mismatch) correctly raises
`REVISION_CONFLICT` without partial mutation. Foreign-key cascade delete
(`ON DELETE CASCADE`) correctly removes all of a session's turns as part of
the same atomic `DELETE FROM conversation_sessions` statement, rather than
relying on the application to explicitly delete turns first — I confirmed
`delete_session`/`purge_expired` contain no explicit turn-deletion
statement, relying entirely on this DB-enforced cascade. `_validate_schema`
performs a strict structural check (`PRAGMA table_info`/
`PRAGMA foreign_key_list`) rather than trusting only the stored
`schema_version` integer, which would catch schema drift a version bump
alone would miss.

**Corruption handling.** `_decode_record` requires exact UTF-8, a byte-size
bound, rejects duplicate JSON keys and non-finite constants via
`object_pairs_hook`/`parse_constant`, and then re-encodes the parsed value
and compares it byte-for-byte against the original stored string — the same
canonical-round-trip defense I verified in the Task 5C.6 usage repository
review, correctly reused here for a different domain. `_session_from_row`/
`_turn_from_row` additionally cross-check the dedicated `revision`/
`updated_at`/`expires_at` columns against the values encoded inside the JSON
payload itself, and `_session_from_row` independently re-asserts
`retention_policy.durable` on every read — meaning a session-only record
could not survive even if it were somehow force-written into the table
outside the normal `create_session` path, which itself already rejects
session-only input before touching SQL.

**Sensitive-text ingress.** The service-layer `_inspect_text` (in
`service.py`) runs before any clock/ID sampling for `start_turn`/
`complete_turn`, giving a specific `SENSITIVE_TEXT_REJECTED` application
code, while the contract-level `_conversation_text` validator
(`contracts.py`) independently re-runs the same check on every
construction/reconstruction path (direct construction, `from_dict`,
`model_copy`) as defense-in-depth — meaning even a hypothetical future
caller that bypasses the service layer entirely still cannot construct or
read back a `ConversationTurn` containing recognizable sensitive text. I
independently confirmed (see Test Evidence) that a `Bearer <marker>` message
is rejected with the specific code and the raw marker never appears in the
resulting exception, and that ordinary QA discussion of "password"/"token"
concepts is accepted unchanged.

## Findings

**F1 (Low, disclosed scope deviation — not a security regression).** The
task instructed: "make the reasoning scrubber and conversation boundary
reuse it without changing existing Task 3 behavior." I compared the
extracted `pmqa/security/sensitive_text.py` patterns against the private
patterns they replaced inside `pmqa/reasoning/scrubber.py` (via
`git diff 16655cd..4ae3893 -- pmqa/reasoning/scrubber.py`) and found the
shared primitive's detection surface is strictly larger than the original
scrubber's:

- the cookie pattern changed from `\b(cookie)\s*:` (Cookie only) to
  `\b(cookie|set-cookie)\s*:` (now also matches `Set-Cookie:`);
- the assignment-pattern vocabulary changed from `api[_-]?key|password|
  passwd|access[_-]?token|refresh[_-]?token|token` to the same list plus
  `|secret|credentials?` (now also matches bare `secret=`/`credential:`
  assignments the original scrubber did not).

Since `DeterministicReasoningScrubber._redact_string` now calls this shared
primitive instead of its own private patterns, the Task 3 scrubber's own
redaction behavior has expanded, not merely been "reused unchanged." This
is evidenced directly in the diff: `tests/test_scrubber.py` gained a new
parametrized test
(`test_shared_sensitive_text_rules_cover_conversation_ingress_shapes`)
asserting that `DeterministicReasoningScrubber` itself now redacts
`Set-Cookie:`, `secret=`, and `credential:` values that it previously would
not have matched. I checked for any pre-existing scrubber test asserting
the *opposite* (that these shapes are left untouched) and found none — the
change is strictly additive (more redaction, never less), and the full
`test_scrubber.py` suite, both old and new cases, passes. This is not a
security regression and I found no functional defect from it. However, the
task's own background section asserted the scrubber "already covered" Cookie/
Set-Cookie and credential/secret shapes, which was not accurate for the
pre-existing code — the Coder faced a genuine contradiction between "reuse
one primitive, don't create a second drifting regex" and "don't change Task
3 behavior," and resolved it by expanding the shared primitive (the safer
of the two available violations, given the alternative was exactly the
duplicated/drifting regex the task explicitly prohibited). The Coder's
report describes the change as the primitive letting the scrubber "preserve
its existing redacted output, rule names, counts, and report behavior,"
which is true for previously-matched inputs but does not disclose that the
matched-input set itself grew. I recommend the Architect explicitly bless
this trade-off (or provide alternate guidance) since it is a genuine,
if benign, deviation from the literal task instruction.

No other findings. All other reviewed behavior matches the task's stated
requirements, and four adversarial invariants were independently reproduced
successfully outside the Coder's own tests (see Test Evidence).

## Acceptance Criteria Coverage

| Acceptance criterion | Evidence | Result |
| --- | --- | --- |
| Canonical provider-neutral conversation session and turn records exist | `pmqa/conversation/contracts.py` read in full: strict frozen Pydantic v2, `extra=forbid`, canonical `to_dict()`/`from_dict()`, revalidated `model_copy` | Met |
| 30-day retention is the default and only session-only/7/30/90 are valid | `DEFAULT_CONVERSATION_RETENTION = THIRTY_DAYS` in `service.py`; `ConversationRetentionPolicy` enum has exactly 4 members; `conversation_expiration` maps each to `None`/7d/30d/90d with no indefinite option | Met |
| Session-only content never reaches SQLite | `SQLiteConversationRepository.create_session` rejects non-durable input before any SQL; `_session_from_row` independently re-asserts durability on read; independently reproduced (fresh DB, 3 session-only creates, `SELECT COUNT(*)` = 0) and independently attempted a direct bypass (constructing a session-only `ConversationSession` and calling `SQLiteConversationRepository.create_session` directly) -> rejected with `INVALID_REQUEST` | Met |
| Durable activity and expiration are deterministic | `_advance_session` re-derives `expires_at` from `conversation_expiration(policy, now)` on every authoritative transition; independently reproduced expiry extending exactly from the latest activity timestamp (not original creation) and confirmed reads/lists do not extend it | Met |
| Immediate manual deletion and expiry purge are implemented | `delete_session`/`purge_expired` on both repositories; independently reproduced deleting a session-only session does not affect an unrelated durable session | Met |
| Repository writes are atomic and stale revisions cannot overwrite | Traced `BEGIN IMMEDIATE`/commit/rollback and the `WHERE revision = ?` compare-and-swap by hand; independently reproduced a stale-revision `start_turn` attempt failing with `REVISION_CONFLICT` and confirmed zero partial mutation (`turn_ids == ()` after) | Met |
| Sensitive ingress uses shared non-drifting rules and rejects before persistence without marker leaks | Traced `_inspect_text` (service) and `_conversation_text` (contract) both calling `contains_recognizable_sensitive_text`; independently reproduced a `Bearer <marker>` rejection with the marker absent from the exception string; see Finding F1 for the one disclosed scope nuance | Met, with F1 noted |
| Arbitrary QA text remains usable; no perfect-detection claim | Independently reproduced "please test the password field and confirm token usage is unavailable" being accepted and reaching `PENDING` turn status; `docs/architecture/conversational-workflow-platform.md` documents this as defense-in-depth | Met |
| No credentials/runtime objects/raw output enter records; only validated assistant response enters a completed turn | `ConversationTurn` has no credential/connection/runtime-object field; `_terminalize_turn` only ever writes the caller-supplied, already-`_inspect_text`-validated `assistant_response` | Met |
| SQLite corruption and operational failures are contained safely | `_decode_record`'s canonical round-trip check, `_validate_schema`'s structural check, and every `sqlite3.Error`/`sqlite3.IntegrityError` handler mapped to fixed `ConversationRepositoryErrorCode` values with no SQL/path/payload in the message, traced by hand | Met |
| Public imports are side-effect free and existing generic imports stay lazy | `tests/test_conversation_imports.py` independently rerun as part of the focused suite; `tests/test_packaging.py` confirms `pmqa`/`pmqa.cli` remain conversation-lazy | Met |
| Existing workflows, application/run/usage layers, CLI, packaging, and tests remain compatible | 467 Task 5C regression tests + 98 Task 4 tests + full 1970/5-skip suite, all independently rerun, all pass | Met |
| No Web/API/frontend/ADO/Copilot implementation started | Diff contains no such file; grep of the diff for FastAPI/Uvicorn/React/ADO/Copilot terms found none outside documentation prose | Met |
| Only allowed files change | `git diff --stat` from starting HEAD to the derived report commit touches exactly the allowed production/test/doc paths plus `agent-handoff/coder-report.md` | Met |

## Test Evidence

### Coder Evidence Reviewed

The Coder report claims: 151 passed for the focused conversation/scrubber/
boundary/packaging group; 467 passed for the Task 5C Run/Application/Usage
regression set; 98 passed for the Task 4 orchestration set (one pre-existing
LangGraph deprecation warning); 1970 passed, 5 skipped for the full default
suite; 2 passed for `products/demo/generated_tests`; Markdown-link and
stale-status search passed; `compileall` and `git diff --check` clean; clean
worktree. This claimed evidence was read only after independent execution
below and matches it exactly.

### Independently Run

All commands below were executed by the Reviewer directly, before reading
the Coder's claimed results, from the repository root on the reviewed
branch:

- `.venv/bin/python -m pytest tests/test_conversation_contracts.py tests/test_conversation_repository.py tests/test_conversation_service.py tests/test_conversation_imports.py tests/test_scrubber.py tests/test_boundary_policy.py tests/test_packaging.py -q`
  -> `151 passed`
- `.venv/bin/python -m pytest tests/test_run_contracts.py tests/test_application_contracts.py tests/test_application_service.py tests/test_usage_contracts.py tests/test_usage_repository.py tests/test_usage_summary.py -q`
  -> `467 passed`
- `.venv/bin/python -m pytest tests/test_workflow_runtime.py tests/test_workflow_reducer.py tests/test_supervisor_policy.py tests/test_langgraph_workflow.py -q`
  -> `98 passed, 1 warning` (pre-existing `LangChainPendingDeprecationWarning`,
  unrelated to this change)
- `.venv/bin/python -m pytest -q` (full default suite) -> `1970 passed, 5 skipped, 1 warning`
- `.venv/bin/python -m pytest products/demo/generated_tests -q` -> `2 passed`
- `PYTHONPYCACHEPREFIX=<isolated scratch directory> .venv/bin/python -m compileall -q pmqa products`
  -> exit code `0`, no output
- `git diff --check` -> exit code `0`, no output
- `git status --short` -> empty (clean worktree)

In addition, and independent of the Coder's own tests, I wired a real
`ConversationApplicationService` (with a `SQLiteConversationRepository`
against a temporary file and an `InMemoryConversationRepository`) in ad hoc
scripts and independently reproduced:

- a `Bearer <marker>` user message rejected with
  `ConversationApplicationErrorCode.SENSITIVE_TEXT_REJECTED`, with the
  marker value absent from the raised exception's string form;
- an ordinary QA sentence discussing "password field" and "token usage" being
  accepted and reaching a `PENDING` turn;
- 3 session-only session creations against a *fresh* SQLite file resulting
  in `SELECT COUNT(*) FROM conversation_sessions` = `0`, and a direct
  attempt to call `SQLiteConversationRepository.create_session` with a
  hand-constructed session-only `ConversationSession` (bypassing the
  service layer entirely) failing with `INVALID_REQUEST` before any SQL
  executed;
- a `start_turn` call using a deliberately stale `expected_revision` (+5)
  failing with `REVISION_CONFLICT`, followed by a re-read confirming
  `turn_ids == ()` (zero partial mutation);
- expiry correctly extending to exactly `latest_activity + 7 days` after a
  turn was started 3 days after session creation (not `creation + 7 days`),
  and a subsequent `list_sessions`/`get_session` read 2 days later leaving
  that expiration unchanged;
- deleting a session-only session leaving an unrelated durable session in a
  separate repository untouched.

No listed validation command was left unrun. No test was skipped by
Reviewer choice. Environment: local `.venv` (Python 3.9), macOS/Darwin, no
network access used or required.

## Security, Scope, and Compatibility

Security observations: SQL injection surface is clean (all parameterized
queries, confirmed by reading every `connection.execute` call). Sensitive-
text rejection is enforced at two independent layers (service pre-check and
contract-level defense-in-depth on every reconstruction path) with no raw
value ever appearing in a raised exception, confirmed both by reading the
code and by independent reproduction. See Finding F1 for the one disclosed,
non-blocking scope nuance around the shared scrubber primitive's expanded
detection surface — safe (additive-only) but worth an explicit Architect
acknowledgment given the literal task wording.

Scope observations: the diff touches exactly the allowed production files
(`pmqa/conversation/*`, `pmqa/security/sensitive_text.py`,
`pmqa/security/__init__.py`, `pmqa/reasoning/scrubber.py`), the expected new
and updated test files, and the four allowed documentation surfaces, plus
the Coder-owned report in a separate commit. No file under `pmqa/run`,
`pmqa/runners`, `pmqa/application`, `pmqa/usage`, `pmqa/reasoning/provider.py`
or `models.py`, `pmqa/cli.py`, or `pyproject.toml` was modified.

Compatibility observations: all 467 Task 5C regression tests and the full
1970-test default suite pass unchanged; the only behavioral change outside
the new `pmqa.conversation` package is the disclosed, additive-only Task 3
scrubber detection-surface expansion in Finding F1, which is covered by both
old and new passing tests.

## Verdict

Verdict: Pass

This verdict is advisory. The Architect makes the final technical
disposition.

## Suggested Architect Focus

- **F1 above**: explicitly confirm whether expanding the Task 3 scrubber's
  detection surface (Set-Cookie, secret=, credential:) to satisfy the
  conversation-ingress requirement is an acceptable resolution of the
  task's internal contradiction, or whether a different design (e.g., two
  independently-configured pattern sets sharing only the regex-application
  machinery, not the exact vocabulary) was intended.
- `pmqa/conversation/contracts.py` reimplements its own
  `_ConversationContract`/`_is_plain_json`/timestamp-canonicalization
  helpers rather than importing `_RunContract` and friends from
  `pmqa.run.models` the way `pmqa.usage.contracts` does. This appears to be
  a deliberate, defensible choice (conversation-specific bounds like the
  32 KiB message length and 16-level tree depth differ from Run's payload
  bounds, and the shared helpers' constants are not parameterizable), but
  it is a divergence from the `pmqa.usage` precedent worth a one-line
  architecture note if this pattern will recur for future Task 5D
  contracts.
- `_ConversationContract.from_dict` uses plain Python `==` to compare the
  submitted wire dict against the reconstructed canonical form, rather than
  the stricter type-sensitive `_plain_json_equal` helper used in
  `pmqa.run.models`/`pmqa.usage.contracts` (which also rejects e.g. `1.0`
  where `1` is expected, even where native `==` would treat them as equal).
  I traced this and found no exploitable gap given the current field types
  (no numeric fields exist in `ConversationSession`/`ConversationTurn`
  where an int/float substitution could slip through Pydantic's own strict-
  mode field validation), but it is a latent inconsistency worth noting if
  numeric fields are added to this contract family later.
- No blocking findings otherwise. This is a substantial (~4,600 line)
  checkpoint; the Reviewer's independent adversarial reproduction focused
  on the highest-risk properties (SQL injection, session-only durability
  leakage, optimistic-concurrency correctness, sensitive-text leakage,
  retention-extension-on-activity) rather than re-deriving every one of the
  Coder's ~150 individual test assertions from scratch.

## Reviewer Write-Boundary Confirmation

Repository files changed by Reviewer:

- `agent-handoff/reviewer-report.md`

Confirmation: I changed no production code, tests, configuration, schemas,
packaging, scripts, product documentation, or another role's handoff file.
