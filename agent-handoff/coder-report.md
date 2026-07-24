# Coder Report

Owner: Coder

Task: PMQA Task 5C.6 — Repository Root and Platform Boundary Hardening

Task ID: `PMQA-5C.6`

Attempt: `2`

Status: Ready for Independent Reviewer

## Branch and Git Correlation

Branch:

`agent/task-5c-1-canonical-run-contract`

Exact Git-derived Coder starting HEAD:

`a99f06cd95d583320257b4d5c5f8504d3281b0e1`

That commit is the latest path-specific publication of
`agent-handoff/current-task.md`, identifies Task `PMQA-5C.6` Attempt `2`, and
was the clean local and tracking-branch HEAD before remediation. The reviewed
Attempt 1 Reviewer HEAD
`339191498e7b2a2cfcb473483f1f88509f06bc8a` is its ancestor. The Attempt 1
implementation and report were not amended.

## Remediation Implementation Commit

`fdb075dcad311ee6848dab5e6454871e2d8ce56b`

Commit message:

`harden Task 5C.6 repository boundaries`

This report is committed separately after the remediation commit. The
Independent Reviewer derives the report commit from Git; this report does not
claim its own future commit SHA.

## Changed Files

Remediation implementation commit:

- `pmqa/usage/repository.py`
- `tests/test_usage_repository.py`
- `docs/architecture/usage-cost-contracts.md`

Report-only handoff commit:

- `agent-handoff/coder-report.md`

No other implementation, documentation, packaging, test, or handoff file
changed.

## F1 — Repository Root Correction

Construction now creates one private `Path` snapshot from one bounded
filesystem-string conversion and validates it before retaining any state. It
requires a platform-absolute non-anchor path, rejects every lexical `..`
component, rejects paths that normalize to their filesystem anchor, rejects
embedded NUL, and exercises platform encoding before any filesystem effect.
All ordinary conversion, path, and `lstat` failures become the fixed
`INVALID_CONFIGURATION` error without cause, context, path, or marker.

The check is lexical and uses `lstat`; it never calls `resolve()` or follows a
symlink to make it acceptable. Existing files and symlink roots now fail in
the constructor. Existing real directories remain valid, and an ordinary
absolute path containing spaces successfully saves and reads a record.

Platform-derived tests cover the anchor itself, `<anchor>/tmp/..`, nested
traversal back to the anchor, traversal selecting a different directory,
embedded NUL with a marker, existing file and symlink roots, and a valid path
with spaces. Rejected constructors never call directory or temporary creation.

## F2 — Platform Capability Correction

Save captures one immutable private capability snapshot before directory
creation. The inventory covers:

- directory and temporary creation;
- descriptor mode enforcement and verification;
- descriptor stat, write, and file synchronization;
- hard-link no-replace publication;
- directory open and synchronization; and
- path identity checks, unlink, and descriptor close.

The implementation deliberately fails closed outside a POSIX mode-capable
platform. Missing `makedirs`, `mkstemp`, `fchmod`, `fstat`, `write`, `fsync`,
`link`, `open`, `lstat`, `unlink`, or `close` produces fixed
`UNSUPPORTED_PUBLICATION` before repository directory creation. No weaker
rename, replacement, check-then-write, unlink-and-retry, or overwrite fallback
exists.

Directory synchronization is exercised after directory preparation but before
temporary creation and target publication. A missing/not-implemented or
unsupported mandatory directory-sync capability therefore leaves no target.
Unexpected pre-publication operational failure is fixed
`PERSISTENCE_FAILURE`. The directory is synchronized again after hard-link
publication; any later failure returns fixed `PERSISTENCE_FAILURE` while
preserving the complete published target.

`mkstemp` remains the restrictive private creation primitive. The descriptor
identity is captured before `fchmod`; mode `0600` and identity are verified
afterward. `fchmod` `NotImplementedError` produces
`UNSUPPORTED_PUBLICATION`, one temporary-descriptor close attempt, no target,
and identity-verified cleanup. Missing `fchmod` fails before any directory or
temporary exists.

Hard-link `NotImplementedError` and the established unsupported errnos produce
`UNSUPPORTED_PUBLICATION` before a target exists. All ordinary platform
`OSError`, `ValueError`, `TypeError`, and `AttributeError` at the publication
boundary are contained behind fixed safe codes. Resource/control-flow
exceptions remain authoritative.

Temporary cleanup still unlinks only a path whose current device/inode equals
the captured descriptor identity. Every ownership record receives one release
call and every descriptor receives one close attempt. If capability failure
occurs before identity can be captured, cleanup deliberately preserves only
the empty restrictive random-name `mkstemp` orphan; it is not a record and its
name contains no domain identifier. After identity capture, unsupported
failures are cleaned when ownership is still verifiable.

Simulated tests cover absent `fchmod`, `link`, `fsync`, and directory creation;
`fchmod` and `link` `NotImplementedError`; unsupported hard-link errno;
unavailable pre-publication directory sync; post-publication sync failure;
non-POSIX mode semantics; descriptor close count; identity-changed cleanup;
safe messages; orphan cleanup; and target absence/preservation at the correct
stage.

## F3 — Parser Overflow Correction

`OverflowError` is now contained only inside `_parse_record` alongside the
existing persisted JSON and contract reconstruction failures. It becomes
fixed `CORRUPT_DATA` with no raw value, marker, parser message, cause, or
context.

One simulated `json.loads` overflow test exercises the public `get` boundary.
A real compact payload containing an extreme JSON exponent exercises bounded
parser/contract rejection. Separate parser tests prove exact identity
propagation for `MemoryError`, `KeyboardInterrupt`, `SystemExit`, and
`GeneratorExit`. Valid canonical record bytes and round trips remain
unchanged.

## Preserved Behavior

The remediation does not change `UsageRepository` methods, record layout,
digest naming, canonical sorted compact UTF-8 plus newline bytes,
`AIInvocationRecord`, query ordering or limits, duplicate/not-found behavior,
hard-link no-replace semantics on supported platforms, corruption handling,
collector behavior, import isolation, or wheel contents.

The focused architecture document now states the fail-closed platform policy,
directory-sync preflight, post-publication preservation, and bounded private
orphan policy. No general status document changed.

## Validation Results

- Repository-only focused tests: `76 passed`.
- Repository, collector, usage contracts, pricing, and usage-import tests:
  `215 passed`.
- Run, Runner contract, Application contract/service, boundary-policy, and
  real-wheel packaging regressions: `332 passed`.
- Task 4 runtime, reducer, Supervisor, and LangGraph regressions:
  `98 passed` with one existing LangGraph pending-deprecation warning.
- Full default suite: `1776 passed, 5 skipped` with the same existing warning.
  The skips are existing opt-in live/external environment gates.
- Generated SauceDemo Playwright regressions: `2 passed`.
- Isolated `compileall` for `pmqa` and `products`: passed with bytecode routed
  to `/private/tmp`.
- `git diff --check`: passed.
- Pre-report implementation worktree: clean.

The default and focused remediation tests remained offline. New tests invoked
no model, provider CLI, network, browser, Node.js, or external Product Pack.

## Remaining Risks and Open Items

- Full Windows repository support remains intentionally deferred; platforms
  that cannot enforce the required POSIX permission and durability semantics
  fail with `UNSUPPORTED_PUBLICATION`.
- A failure before temporary inode identity is available may preserve the
  empty restrictive random-name orphan rather than delete an unverified path.
- The explicit root remains a trusted local operator boundary and does not
  defend against a malicious operating-system administrator.

These are documented task boundaries, not known acceptance blockers.

## Scope Confirmation

No persistence format, schema, public method, collector wiring, aggregation,
summary, CLI/UI, pricing, provider parser, retention, deletion, background
work, remote storage, fallback publication primitive, or runtime dependency
was added. `pmqa/usage/contracts.py`, pricing, collector, Run, Runner,
Application Service, WorkflowState, LangGraph, Supervisor, Task 5, and Product
Pack behavior were not modified. Task 5B, Task 6, and Task 7 were not started.
No PR was created and nothing was merged.

## Recommended Review Depth

**Deep**

Reason: this remediation changes path selection, platform capability
preflighting, descriptor ownership, publication phase classification, and
hostile parser containment at a security-sensitive persistence boundary.

## Suggested Reviewer Focus

- Reproduce anchor-equivalent, traversal, NUL, file, and symlink roots and
  confirm construction is side-effect free and marker-safe.
- Challenge missing and `NotImplemented` capability handling before and after
  target publication, including exact error-code phase classification.
- Verify every temporary descriptor receives one close attempt and cleanup
  never unlinks an identity-mismatched path.
- Confirm restrictive-mode verification and hard-link no-replace semantics
  remain fail-closed with no weaker fallback.
- Verify parser overflow is contained while resource/control-flow exceptions
  propagate with exact identity.

## Human Summary

PMQA-5C.6 Attempt 2 已完成，精确起点为 `a99f06cd95d583320257b4d5c5f8504d3281b0e1`。
remediation 提交为 `fdb075dcad311ee6848dab5e6454871e2d8ce56b`。
F1 已阻止 anchor/traversal/NUL/file/symlink root，并保持 constructor 无写入副作用。
F2 已加入 fail-closed capability snapshot、directory-sync preflight、mode 验证与发布后 target 保留。
F3 已将 parser `OverflowError` 安全归类为 `CORRUPT_DATA`，resource/control-flow 仍原样传播。
验证结果：focused 215、边界/packaging 332、Task 4 回归 98、全量 1776 passed / 5 skipped、Playwright 2 passed。
Action Needed From Human: 请将下方 Handoff Note 传递给 Independent Reviewer。
Handoff Note: 请读取 agent-handoff/README.md 与 agent-handoff/current-task.md，从 Git 派生最新 coder-report commit，并按独立审查顺序完成 review。
