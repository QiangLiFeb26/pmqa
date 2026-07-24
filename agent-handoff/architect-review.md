# Architect Review

Owner: Architect

Task: PMQA Task 5C.6 — Repository Root and Platform Boundary Hardening

Task ID: `PMQA-5C.6`

Attempt: `2`

Status: Approved

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed Starting HEAD:
`a99f06cd95d583320257b4d5c5f8504d3281b0e1`

Reviewed Implementation Commit:
`fdb075dcad311ee6848dab5e6454871e2d8ce56b`

Derived Coder Report Commit:
`9987f94a20bfc4a68d144f7cd9b4e1696a9eb52e`

Derived Reviewer Report Commit:
`a258ba59b7fdd1edb6e01ab738ea9203610e954b`

The Reviewer report commit was derived with:

```bash
git log -1 --format=%H -- agent-handoff/reviewer-report.md
```

This review does not claim the SHA of its own containing commit. The next
Coder derives and records the publication commit containing this disposition
and the next task.

## Correlation and Ownership Verification

- the active branch and upstream are
  `agent/task-5c-1-canonical-run-contract`;
- starting HEAD
  `a99f06cd95d583320257b4d5c5f8504d3281b0e1` is an ancestor of implementation
  commit `fdb075dcad311ee6848dab5e6454871e2d8ce56b`;
- the implementation commit is an ancestor of Coder report commit
  `9987f94a20bfc4a68d144f7cd9b4e1696a9eb52e`;
- the Coder report commit is an ancestor of Reviewer report commit
  `a258ba59b7fdd1edb6e01ab738ea9203610e954b`;
- Coder and Reviewer reports identify the same Task, Attempt, branch,
  starting HEAD, and implementation commit;
- the remediation implementation changed only
  `pmqa/usage/repository.py`, `tests/test_usage_repository.py`, and
  `docs/architecture/usage-cost-contracts.md`;
- the Coder report commit changed only `agent-handoff/coder-report.md`;
- the Reviewer report commit changed only
  `agent-handoff/reviewer-report.md`;
- all role ownership and non-circular Git-correlation rules were followed.

## Review Depth Selected

Deep

The Architect independently selected Deep review because this attempt closes
three adversarial findings at a local persistence boundary: path selection,
platform capability enforcement, and hostile persisted-data parsing. The
Coder and Reviewer recommendations agreed with this depth.

## Overall Assessment

Task 5C.6 Attempt 2 closes every blocking finding from Attempt 1 without
weakening the append-only repository design.

The approved repository now provides:

- one explicit absolute, non-anchor, traversal-free root snapshot;
- construction-time rejection of invalid OS paths, existing files, and
  symlink roots through a fixed safe error;
- fail-closed POSIX capability capture before repository creation;
- pre-publication directory-sync verification before temporary or target
  record creation;
- restrictive temporary mode enforcement with post-operation verification;
- atomic hard-link no-replace publication with no weaker fallback;
- identity-verified cleanup and exactly controlled descriptor release;
- preservation of a complete target after post-publication failure;
- bounded parser-overflow containment as corrupt persisted data;
- exact propagation of resource and control-flow exceptions;
- unchanged canonical file layout, query behavior, record contracts, and
  collector separation.

No blocking or follow-up implementation change is required for Task 5C.6.

## Independent Reviewer Result

Reviewer verdict: `Pass`

Reviewer blocking findings: None

The Reviewer performed a legitimate Deep review, independently reproduced all
three original findings against the remediated code, ran every required
validation command, and confirmed the allowed change boundary.

The Architect accepts the advisory verdict.

## Architect Findings

None.

### F1 disposition — repository root validation

Closed.

`_canonical_root` snapshots one plain filesystem string, rejects embedded NUL
and encoding failures, requires an absolute non-anchor path, rejects every
literal `..` component, rejects normalized anchor selection, and uses
`lstat()` without following symlinks. Expected failures expose only
`INVALID_CONFIGURATION`.

### F2 disposition — platform capability boundary

Closed.

Publication captures every mandatory callable before filesystem effects and
fails with `UNSUPPORTED_PUBLICATION` on non-POSIX or incomplete platforms.
The implementation verifies restrictive mode after `fchmod`, preflights
directory synchronization before creating a temporary record, retains atomic
hard-link publication, and never introduces overwrite or rename fallback.

### F3 disposition — parser overflow

Closed.

`OverflowError` is contained only in persisted-record reconstruction and maps
to `CORRUPT_DATA`. Resource and control-flow exceptions remain authoritative.

## Reviewer Non-Blocking Observations

### Empty directory creation before sync preflight

Accepted.

`_prepare_write_directory` may create the private `invocations/` directory
before `_preflight_directory_sync` executes. The task requires unsupported
mandatory synchronization to fail before temporary or target publication,
which it does. An empty identifier-free directory is neither a published
record nor partial domain evidence, and its existence is required for a later
valid save. No remediation is needed.

### Redundant structural equality check

Accepted as harmless. Removing it is unnecessary churn and is not carried
into the next task.

### Windows behavior

Accepted as an explicit limitation. Full Windows publication support was
out of scope; deterministic `UNSUPPORTED_PUBLICATION` is the approved
fail-closed behavior for platforms that cannot enforce the required
guarantees.

## Acceptance Criteria Coverage

| Acceptance criterion | Result |
| --- | --- |
| Traversal/root-equivalent paths cannot select an anchor-level repository | Met |
| Invalid OS paths fail at construction with fixed safe errors | Met |
| Raw path/platform/parser details do not escape expected boundaries | Met |
| Missing mandatory publication capabilities fail before record publication | Met |
| Atomic no-replace publication remains unchanged on supported platforms | Met |
| Post-publication failures preserve the complete target | Met |
| Descriptor and temporary ownership remain exactly controlled | Met |
| Parser overflow becomes fixed corrupt-data evidence | Met |
| Repository, collector, contracts, imports, packaging, and orchestration remain green | Met |
| Only authorized files changed | Met |

## Validation Evidence

Independent Reviewer evidence:

- repository/collector/contracts/pricing/import suite: `215 passed`;
- Run/Runner/Application/boundary/packaging regressions: `332 passed`;
- Task 4 regressions: `98 passed`;
- full default suite: `1776 passed, 5 skipped`;
- generated Playwright regressions: `2 passed`;
- isolated compileall and `git diff --check`: passed;
- direct reproductions of traversal, embedded NUL, and missing `os.fchmod`:
  fixed safe failures with no target or unverified cleanup.

Architect evidence:

- complete Reviewer report and Coder report read;
- full remediation diff and repository implementation inspected;
- ancestry, role ownership, and report correlation verified;
- focused usage suite independently run: `215 passed`;
- full default suite independently run:
  `1776 passed, 5 skipped, 1` existing LangGraph warning;
- `git diff --check` through the Reviewer commit: passed;
- no uncommitted work existed before Architect disposition.

The five skipped tests remain existing environment-gated live tests. The
warning is the pre-existing LangGraph pending-deprecation warning and is
unrelated to Task 5C.6.

## Required Changes

None.

## Decision

Approved

PMQA Task 5C.6 is approved at implementation commit
`fdb075dcad311ee6848dab5e6454871e2d8ce56b`.

## Next Recommended Task

Proceed to PMQA Task 5C.7 — Deterministic Usage Summary Contracts and Pure
Aggregation, defined in `agent-handoff/current-task.md`.
