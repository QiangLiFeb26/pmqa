# Coder Report

Owner: Coder

Task: PMQA Task 5D.1A — Repository Result Correlation

Task ID: `PMQA-5D.1A`

Attempt: `2`

Status: Ready for Independent Reviewer

## Branch and Git Correlation

Branch:

`agent/task-5c-1-canonical-run-contract`

Exact Git-derived Coder starting HEAD:

`edb3382e4483fefaaba5c18d0c3baf3980b08109`

That commit was the latest pushed branch commit containing the Attempt 2
Architect handoff in `agent-handoff/current-task.md`. Before implementation,
local HEAD and `origin/agent/task-5c-1-canonical-run-contract` both equaled
that commit and the worktree was clean. The handoff identified reviewed
Attempt 1 Reviewer HEAD
`67492ea5ef551fd10a47338f270408e92baa99c4`. No Attempt 1 or earlier commit
was amended, rebased, or replaced.

## Remediation Implementation Commit

`c13fc8729e22fe5316719fdf2eafef31b6bcbb80`

Commit message:

`harden conversation repository correlation`

This report is committed separately after the implementation commit. The
Independent Reviewer derives the report commit from Git; this report does not
claim its own future commit SHA.

## Changed Files

Implementation:

- `pmqa/conversation/service.py`;
- `tests/test_conversation_service.py`.

Report-only handoff:

- `agent-handoff/coder-report.md`.

No contract, repository implementation, security primitive, reasoning code,
CLI, dependency, packaging, Task 4/5/5A/5C production code, product
documentation, or another role's handoff file changed.

## Session Lookup Correlation

Every `_find_session` resolution now queries the injected volatile and durable
repository roles before selecting an owner. Each successful result must be an
exact `ConversationSession` that survives fresh canonical wire
reconstruction, has the requested session ID, and matches its repository
role:

- volatile results must use `session_only`;
- durable results must use one of `7_days`, `30_days`, or `90_days`.

Exactly one valid owner is required. No owner produces the existing fixed
`session_not_found`; duplicate ownership, a non-`not_found` dependency
failure, a malformed snapshot, wrong ID, or role mismatch produces only fixed
`repository_failed`.

The same lookup protects `get_session`, `get_turn`, `list_turns`,
`start_turn`, `complete_turn`, `fail_turn`, `close_session`, and
`delete_session`. Tests use two real in-memory repositories to prove equal-ID
ownership with equal and different payloads is rejected. They also prove the
durable role is inspected after a volatile hit and that ambiguity is rejected
before append, replacement, close, or deletion.

Creation-time identifier availability was hardened consistently: a returned
session is canonically reconstructed and ID/retention-role checked before an
identifier conflict is trusted. A returned turn is reconstructed and must
carry the generated ID before it can establish a conflict.

## Turn and List Correlation

A repository turn result must now:

- be an exact `ConversationTurn`;
- survive fresh canonical wire reconstruction;
- have the requested turn ID;
- belong to the owning canonical session; and
- occupy exactly `session.turn_ids[sequence_number - 1]`.

Out-of-range, wrong-ID, foreign-session, or wrong-slot turns fail with fixed
`repository_failed`, including before complete/fail replacement.

Session-list results from each role must be exact built-in tuples no longer
than the requested per-repository limit. Every item is freshly reconstructed,
IDs must be unique within the role, and every retention policy must match the
role. Duplicate IDs across roles are then rejected before the existing stable
global `updated_at`/ID ordering and global limit are applied.

Turn-list results must be exact built-in tuples no longer than the requested
limit. Reconstructed turns must all belong to the owner, have unique IDs,
carry sequence numbers exactly `1..N`, and match the exact ordered
`session.turn_ids[:N]` prefix. Lists, tuple subclasses, oversized responses,
duplicates, reordered responses, gaps, foreign-session turns, and wrong
prefixes are rejected. A correct bounded prefix and existing deterministic
output remain unchanged.

## Purge Result Validation

The durable purge result must be an exact built-in tuple no longer than the
requested limit. Every member must be an exact canonical PMQA identifier and
the tuple must be unique. The service no longer materializes arbitrary
iterables.

Focused tests reject lists, tuple subclasses, generators/iterators, sets,
mappings, mutable tuple members, runtime objects, duplicates, invalid
identifiers, and oversized exact tuples. Valid deterministic purge output is
unchanged.

## Safe Failure and Side-Effect Evidence

New dependency contradictions expose only
`ConversationApplicationErrorCode.REPOSITORY_FAILED` and its fixed safe
message. Expected errors have no retained cause or context, and tests verify
marker-bearing malformed values do not appear in the public exception.
Identifiers, policy values, dependency representations, paths, payloads, and
repository details are not copied into an error or public state.

Ambiguous ownership tests cover start, complete, fail, close, and delete and
assert that neither repository receives `append_turn`, `replace_turn`,
`close_session`, or `delete_session`. The implementation performs no
cross-store move, repair, or cleanup.

`MemoryError`, `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit` remain
authoritative. Focused lookup tests prove exact propagation, and validation
paths retain explicit resource/control-flow propagation. Unexpected
programming errors continue to follow the pre-existing application/repository
policy; no broad dependency exception catch was added.

## Validation Results

All commands were run from the repository at implementation commit
`c13fc8729e22fe5316719fdf2eafef31b6bcbb80`, with the report file still
unchanged:

- Conversation/security/packaging focused group: `195 passed`.
- Task 5C Run/Application/Usage regressions: `467 passed`.
- Task 4 runtime/reducer/Supervisor/LangGraph regressions: `98 passed`.
- Full default suite: `2014 passed, 5 skipped`.
- Generated SauceDemo Playwright regressions: `2 passed`.
- Isolated `compileall` for `pmqa` and `products`: passed with
  `PYTHONPYCACHEPREFIX` outside the repository.
- `git diff --check`: passed.
- Pre-report implementation worktree: clean and implementation commit pushed.

The only observed warnings were the pre-existing local LibreSSL warning and
LangGraph pending-deprecation warning. The five default-suite skips are
existing environment-gated tests. New tests are deterministic and offline;
they use no browser, network, Node, provider, ADO, or external Product Pack.

## Remaining Risks and Scope Confirmation

The service defensively validates returned snapshots but cannot prove a
malicious repository honored its internal transaction semantics; repository
implementations and their existing transaction/corruption tests remain the
trusted persistence adapters. This is not a known Attempt 2 defect.

Task 5D.1B, Task 5D.1C, Task 5D.2, Task 5B, Task 6, and Task 7 were not
started. No Web/API/frontend/HTTP/FastAPI/Uvicorn/React/TypeScript/Vite/Node,
new CLI, ADO/Copilot, workflow capability, approval, operation, receipt,
artifact, or usage UI was added. No PR was created and nothing was merged.

## Recommended Review Depth

**Deep**

Reason: this remediation defines the untrusted repository correlation gate
that protects every future conversation read and mutation before the local
Web boundary is added.

## Suggested Reviewer Focus

- Reproduce same-ID ownership in two real repositories and verify every
  resolving read/mutation rejects it before side effects.
- Challenge wrong session IDs, retention-role mismatches, wrong turn IDs,
  foreign turns, sequence slots, and exact ordered turn prefixes.
- Exercise non-tuple/subclass/oversized/duplicate session, turn, and purge
  results and confirm fixed safe failures without marker or cause leakage.
- Confirm valid volatile/durable routing, list ordering/limits, turn
  lifecycle, retention, deletion, and purge remain structurally unchanged.
- Verify resource/control-flow propagation and confirm no contract,
  repository, sensitive-text, Task 5C, packaging, or later Task 5D surface
  changed.

## Human Summary

PMQA-5D.1A Attempt 2 已完成，Git 派生起点为 `edb3382e4483fefaaba5c18d0c3baf3980b08109`。
实现提交为 `c13fc8729e22fe5316719fdf2eafef31b6bcbb80`。
Application Service 现在要求 session 恰有一个正确 repository owner，并验证 retention role、session/turn ID、turn slot 与有序 prefix。
所有 session/turn/purge collection 都要求 exact tuple、bounded、canonical、unique；矛盾统一安全失败且 mutation 前终止。
验证结果：focused 195、Task 5C 467、Task 4 98、全量 2014 passed / 5 skipped、Playwright 2 passed，compileall 与 diff check 通过。
Action Needed From Human: 请将下方 Handoff Note 传递给 Independent Reviewer。
Handoff Note: 请读取 agent-handoff/README.md 与 agent-handoff/current-task.md，从 Git 派生最新 coder-report commit，并按独立审查顺序完成 review。
