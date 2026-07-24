# Architect Review

Owner: Architect

Task: PMQA Task 5C.6 — Append-Only Local AI Invocation Repository

Task ID: `PMQA-5C.6`

Attempt: `1`

Status: Needs Revision

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed Coder Starting HEAD:
`ce1334f4a096dd014170a8791d99969b40c4501b`

Reviewed Implementation Commit:
`08dee16d43c02f42c32591e242b30bc4035033cb`

Derived Coder Report Commit:
`ecc11c7e5375ba8c5eba5f5b272841650d2eaf7d`

Derived Reviewer Report Commit:
`339191498e7b2a2cfcb473483f1f88509f06bc8a`

The Reviewer report commit was derived with:

```bash
git log -1 --format=%H -- agent-handoff/reviewer-report.md
```

This review does not claim the SHA of its own containing commit. The Coder
records the publication commit containing this review and remediation task as
the next starting HEAD.

## Correlation and Ownership Verification

- active branch and upstream:
  `agent/task-5c-1-canonical-run-contract`;
- starting HEAD
  `ce1334f4a096dd014170a8791d99969b40c4501b` is an ancestor of implementation
  commit `08dee16d43c02f42c32591e242b30bc4035033cb`;
- implementation commit is an ancestor of Coder report commit
  `ecc11c7e5375ba8c5eba5f5b272841650d2eaf7d`;
- Coder report commit is an ancestor of Reviewer report commit
  `339191498e7b2a2cfcb473483f1f88509f06bc8a`;
- Coder and Reviewer reports identify the same Task, Attempt, branch,
  starting HEAD, and implementation commit;
- Reviewer publication changed only
  `agent-handoff/reviewer-report.md`;
- Coder and Reviewer ownership boundaries were followed.

## Review Depth Selected

Deep

The Architect accepted the recommended depth because this checkpoint owns
filesystem path selection, atomic publication, concurrent writers, descriptor
release, and corruption classification.

## Overall Assessment

The repository design is strong but Task 5C.6 is not yet approved.

The implementation correctly provides:

- canonical per-invocation files;
- digest-only record names;
- atomic hard-link no-replace publication;
- duplicate-safe concurrent writers;
- independent record snapshots;
- deterministic bounded queries;
- strict canonical-byte and digest verification;
- symlink/non-regular/corrupt record rejection;
- fixed safe repository errors;
- import and package isolation;
- a durable real-thread collector contention regression.

Architect review found three blocking configuration, platform, and parser
boundary defects outside the Reviewer test matrix. They allow the repository
to leave its fixed safe failure boundary or misclassify corrupt persisted
data.

## Independent Reviewer Result

Reviewer verdict: `Pass`

Reviewer blocking findings: None

The Reviewer performed a legitimate Deep review and followed every ownership
and correlation rule. The Architect's findings do not indicate Reviewer
misconduct; they extend the adversarial matrix to semantic root paths and
missing platform functions.

The Architect therefore overrides the advisory verdict with `Needs Revision`
and records concrete reproductions below.

## Review Findings

### F1 — Semantic filesystem root and invalid OS paths are accepted

Severity: Blocking

Location:

- `pmqa/usage/repository.py`
- `LocalJSONUsageRepository.__init__`

The constructor rejects only a path lexically equal to its anchor. It does not
reject parent traversal or semantically root-equivalent absolute paths.

Independent no-write reproduction:

```text
input root: /tmp/..
accepted _root: /tmp/..
derived record directory: /tmp/../invocations
```

The operating system resolves that directory to `/invocations`, defeating the
explicit absolute non-root configuration boundary.

The constructor also accepts an absolute path containing NUL. Calling `save`
then leaks:

```text
ValueError: embedded null byte
```

instead of a fixed marker-safe repository error.

Impact:

- operator input can bypass the non-root guard;
- a broad root-level directory becomes the write target;
- invalid OS path syntax escapes the stable failure vocabulary;
- path validation is deferred until after repository construction.

Required correction:

- reject every root containing a parent-traversal component;
- reject NUL and other path forms that cannot safely reach the OS boundary;
- guarantee semantic root-equivalent inputs cannot produce an anchor-level
  `invocations` directory;
- keep constructor validation side-effect free;
- preserve explicit absolute caller configuration and existing symlink-root
  checks;
- return only fixed safe `INVALID_CONFIGURATION` or the documented fixed
  operational error;
- never echo the path, marker, or underlying exception.

Do not use filesystem-resolving canonicalization that silently follows a
symlink and weakens the existing symlink-root policy.

### F2 — Missing platform functions leak raw exceptions

Severity: Blocking

Location:

- `pmqa/usage/repository.py`
- temporary permission and publication capability path

`save()` calls `os.fchmod()` unconditionally. `os.fchmod` is Unix-only in the
supported Python surface and may be absent on another platform.

Independent simulation with `os.fchmod` absent:

```text
AttributeError: module 'os' has no attribute 'fchmod'
```

The call leaves a private temporary orphan and bypasses
`UsageRepositoryErrorCode`.

The task explicitly requires platforms/filesystems lacking the safe
publication capability to fail through a fixed unsupported/IO boundary rather
than leak raw platform exceptions or silently weaken safety.

Required correction:

- feature-detect every optional OS primitive used by save/publication;
- define deterministic behavior when restrictive mode operations, hard links,
  or directory synchronization are unavailable;
- map expected missing/not-implemented platform capability to a fixed safe
  error;
- do not publish a target before an unsupported mandatory capability is
  detected;
- do not weaken atomic no-replace publication;
- preserve already published targets on post-publication failure;
- close owned descriptors exactly once and clean only identity-verified owned
  temporary paths;
- never leak `AttributeError`, `NotImplementedError`, platform paths, or
  underlying messages.

Supporting Windows fully is not required by this remediation. Failing closed
and safely as unsupported is acceptable. Any platform-specific relaxation of
durability or permissions would be a product decision and is out of scope.

### F3 — JSON parser overflow is not contained

Severity: Blocking boundary completeness

Location:

- `pmqa/usage/repository.py`
- `_parse_record`

The JSON corruption boundary contains `ValueError`, `JSONDecodeError`,
`RecursionError`, and contract validation failures but not `OverflowError`.
Parser overflow is structural/corrupt-input failure inside the explicit read
boundary, not an application programming error.

Required correction:

- contain `OverflowError` raised specifically during JSON decoding or
  canonical numeric reconstruction as fixed `CORRUPT_DATA`;
- keep containment scoped to persisted-data parsing;
- continue propagating `MemoryError`, `KeyboardInterrupt`, `SystemExit`, and
  `GeneratorExit`;
- add an adversarial parser-overflow regression with marker/cause/context
  checks.

## Non-Blocking Reviewer Focus Disposition

- The redundant `record.to_dict() != value` check is harmless. Removing it is
  optional and must not distract from the remediation.
- Hard-link publication on Windows was not tested. Full Windows support is
  deferred, but fixed safe unsupported-platform behavior is required now.
- The trusted local-root boundary remains accepted; the remediation does not
  need to defend against a malicious OS administrator.

## Validation Evidence

Independent Reviewer evidence:

- focused usage repository/collector/contracts/import tests: `199 passed`;
- Run/Runner/Application/boundary/packaging regressions: `332 passed`;
- Task 4 regressions: `98 passed`;
- full default suite: `1760 passed, 5 skipped`;
- generated Playwright regressions: `2 passed`;
- isolated compileall and `git diff --check`: passed.

Architect evidence:

- full repository implementation inspected;
- correlation, ancestry, report-path, and ownership checks: passed;
- `git diff --check` through the Reviewer commit: passed;
- semantic-root constructor reproduction: accepted `/tmp/..`;
- invalid NUL-path reproduction: raw `ValueError` escaped;
- missing-`os.fchmod` reproduction: raw `AttributeError` escaped and a private
  temporary orphan remained.

The passing suite proves the implemented paths but does not cover F1–F3.

## Required Changes

Complete one focused Task 5C.6 attempt 2 remediation for F1–F3. Do not redesign
the repository, change canonical records, or add new persistence features.

## Decision

Needs Revision

Task 5C.6 is not approved at
`08dee16d43c02f42c32591e242b30bc4035033cb`.

## Next Recommended Task

Complete PMQA Task 5C.6 Attempt 2 — Repository Root and Platform Boundary
Hardening, defined in `agent-handoff/current-task.md`.
