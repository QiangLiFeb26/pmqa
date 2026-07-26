# Architect Review

Owner: Architect

Task: PMQA Task 5D.1A — Repository Result Correlation

Task ID: `PMQA-5D.1A`

Attempt: `2`

Status: Approved

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed Starting HEAD:
`edb3382e4483fefaaba5c18d0c3baf3980b08109`

Reviewed Implementation Commit:
`c13fc8729e22fe5316719fdf2eafef31b6bcbb80`

Derived Coder Report Commit:
`f1db9a1090513bedfe45036f6a0c6c9f7f817eba`

Derived Reviewer Report Commit:
`55ea5067e87d502951cd102b40ede17a2d23796f`

The Reviewer report commit was derived from Git with:

```bash
git log -1 --format=%H -- agent-handoff/reviewer-report.md
```

This review does not predict the SHA of its own containing commit.

## Correlation and Ownership Verification

- the active branch and upstream are
  `agent/task-5c-1-canonical-run-contract`;
- starting HEAD `edb3382...` is an ancestor of implementation commit
  `c13fc87...`;
- implementation commit `c13fc87...` is an ancestor of Coder report commit
  `f1db9a1...`;
- Coder report commit `f1db9a1...` is an ancestor of Reviewer report commit
  `55ea506...`;
- Coder and Reviewer reports identify Task `PMQA-5D.1A`, Attempt `2`, the same
  branch, starting HEAD, and implementation commit;
- the implementation changed only `pmqa/conversation/service.py` and
  `tests/test_conversation_service.py`;
- the Coder report commit changed only `agent-handoff/coder-report.md`;
- the Reviewer report commit changed only
  `agent-handoff/reviewer-report.md`;
- the branch matched its upstream and the worktree was clean before this
  Architect disposition.

## Review Depth

Deep

The Architect independently selected Deep review because this remediation is
the correlation gate between injected repositories and every future local Web
conversation read or mutation. Attempt 1 passed its own tests while still
containing a boundary defect, so final approval required direct code tracing,
independent focused validation, and review of the Independent Reviewer's
adversarial evidence.

## Independent Reviewer Result

Reviewer verdict: `Pass`

Reviewer findings: none.

The Reviewer:

- traced every changed service path against the complete remediation
  invariants;
- independently constructed repository doubles rather than relying only on
  Coder fixtures;
- reproduced wrong returned identity and wrong retention-role rejection;
- independently ran the complete focused, Task 5C, Task 4, full-suite,
  generated-test, compile, and repository-integrity validations; and
- confirmed the Reviewer changed only `agent-handoff/reviewer-report.md`.

The Architect accepts the advisory verdict and evidence.

## Overall Assessment

The remediation closes the Attempt 1 blocker without changing the approved
conversation contracts, persistence adapters, retention behavior, sensitive
text policy, or unrelated PMQA runtime behavior.

`ConversationApplicationService._find_session` now:

- inspects both volatile and durable repository roles;
- reconstructs every successful result as a fresh exact
  `ConversationSession`;
- requires exact requested identity and correct retention role;
- returns only one unambiguous owner;
- distinguishes no owner from malformed or duplicate ownership; and
- completes correlation before any dependent mutation or deletion.

Turn reads now require exact turn identity, owning session identity, and exact
ordered session slot. Session and turn lists require exact built-in tuples,
respect the requested bound, reject duplicates and role/correlation
contradictions, and preserve valid deterministic ordering. Purge results
require the same exact bounded tuple and canonical unique identifier policy.

All newly detected contradictions use the fixed
`REPOSITORY_FAILED` application error without exposing returned identifiers,
payloads, markers, dependency objects, or underlying exceptions.

The test diff is additive. Existing valid conversation behavior remains
covered by its original assertions, while the new tests directly cover the
previously missing adversarial cases and no-side-effect guarantees.

## Findings

None.

## Acceptance Criteria Coverage

| Acceptance criterion | Result |
| --- | --- |
| Exactly one correctly routed repository owns every resolved session | Met |
| Duplicate cross-repository ownership is rejected consistently | Met |
| Returned session and turn identities are exactly correlated | Met |
| Volatile/durable retention role mismatch is rejected | Met |
| Session and turn lists are bounded, canonical, unique, and correlated | Met |
| Purge output is canonical and bounded | Met |
| Contradictions fail before mutation with fixed safe errors | Met |
| Valid Attempt 1 behavior and output remain unchanged | Met |
| Shared sensitive-text expansion remains in place | Met |
| Focused and full regressions remain green | Met |
| Only allowed files changed | Met |

## Validation Evidence

Independent Reviewer:

- conversation/security/packaging focused group: `195 passed`;
- Task 5C Run/Application/Usage regressions: `467 passed`;
- Task 4 orchestration regressions: `98 passed`;
- full default suite: `2014 passed, 5 skipped`;
- generated Playwright regressions: `2 passed`;
- isolated compileall, `git diff --check`, and clean-worktree checks: passed;
- two independent adversarial repository reproductions: passed.

Architect:

- complete remediation task, implementation diff, Coder report, Reviewer
  report, and affected service paths inspected;
- conversation/security/packaging focused group: `195 passed`;
- Task 5C Run/Application/Usage regressions: `467 passed`;
- Task 4 orchestration regressions: `98 passed`;
- `git diff --check`: passed;
- worktree remained clean before disposition.

The Architect's sandbox emitted a pytest-cache write warning because it could
not update the repository's `.pytest_cache`; all test processes completed
successfully and this did not modify the worktree or affect test outcomes.
The existing LangGraph pending-deprecation warning remains unrelated.

## Residual Boundary

The service validates the canonical consistency and correlation of repository
results. It does not attempt to prove that a malicious repository internally
honored transaction semantics while returning an otherwise self-consistent
snapshot.

That is an intentional adapter trust boundary, not a Task 5D.1A defect.
Concrete in-memory and SQLite transaction/corruption behavior remains covered
by the repository test suite. No risk acceptance or Human decision is needed
for this disposition.

## Required Changes

None.

## Decision

Approved

PMQA Task 5D.1A is approved at implementation commit
`c13fc8729e22fe5316719fdf2eafef31b6bcbb80`.

## Next Recommended Task

Begin PMQA Task 5D.1B — Secure Loopback Web/API Boundary, defined in
`agent-handoff/current-task.md`.
