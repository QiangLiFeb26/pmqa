# Architect Review

Owner: Architect

Task: PMQA Task 5C.7 — Retry/Fallback Aggregate Exclusivity

Task ID: `PMQA-5C.7`

Attempt: `3`

Status: Approved

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed Starting HEAD:
`e18ffd74a5cf1a6d97de3709177af86ac073de46`

Reviewed Implementation Commit:
`2540acf98be7a1645c252de595be6930c63ab717`

Derived Coder Report Commit:
`5678d20f239ed40fc8a0cc6749bf98ae1f5e7949`

Derived Reviewer Report Commit:
`9d28c1361111d75e642292ec87a9a8f1f406cdc7`

The Reviewer report commit was derived with:

```bash
git log -1 --format=%H -- agent-handoff/reviewer-report.md
```

This review does not claim the SHA of its own containing commit. The next
Coder derives and records the publication commit containing this disposition
and Task 5D.0.

## Correlation and Ownership Verification

- the active branch and upstream are
  `agent/task-5c-1-canonical-run-contract`;
- starting HEAD
  `e18ffd74a5cf1a6d97de3709177af86ac073de46` is an ancestor of implementation
  commit `2540acf98be7a1645c252de595be6930c63ab717`;
- the implementation commit is an ancestor of Coder report commit
  `5678d20f239ed40fc8a0cc6749bf98ae1f5e7949`;
- the Coder report commit is an ancestor of Reviewer report commit
  `9d28c1361111d75e642292ec87a9a8f1f406cdc7`;
- Coder and Reviewer reports identify the same Task, Attempt, branch,
  starting HEAD, and implementation commit;
- the implementation changed only `pmqa/usage/summary.py` and
  `tests/test_usage_summary.py`;
- the Coder and Reviewer report commits changed only their exclusively owned
  handoff files;
- all role ownership and Git-correlation rules were followed.

## Review Depth Selected

Deep

The Architect independently selected Deep review despite the two-line
production change because this was the third attempt on a public aggregate
contract. Review included the assigned predecessor invariant and a final
pairwise audit of lifecycle, predecessor, token-coverage, cost-bucket, and
cross-level interactions.

## Overall Assessment

Task 5C.7 is approved.

The shared metrics validator now correctly requires:

```text
retry_invocation_count + fallback_invocation_count
    <= invocation_count
```

without unsafe addition, duplication, or equality overconstraint. It applies
to top-level `UsageSummary` and every `UsageProviderModelSummary`.

The completed Task 5C.7 contract now enforces:

- strict immutable canonical summaries;
- empty, observed-zero, partial, and unavailable token distinction;
- exact status and mutually exclusive predecessor coverage;
- bounded duration and token arithmetic;
- provider-reported, estimated, subscription-included, and unavailable cost
  separation;
- currency and complete pricing-provenance separation;
- exact Decimal aggregation independent of caller ambient precision;
- deterministic provider/model grouping and ordering;
- complete top-level/group lifecycle, predecessor, duration, token, and cost
  reconciliation;
- fixed safe public reconstruction failures;
- provider, storage, pricing, workflow, CLI, and UI isolation.

No remaining Task 5C.7 blocker or required follow-up exists.

## Independent Reviewer Result

Reviewer verdict: `Pass`

Reviewer blocking findings: None

The Reviewer independently hand-traced the invariant, reproduced the exact
prior contradiction, ran every required validation command, and deliberately
selected Deep review rather than accepting the Coder's Standard
recommendation.

The Architect accepts the advisory verdict.

## Architect Findings

None.

## Closed Finding

### Retry/fallback aggregate exclusivity

Closed.

The validator first confirms each count does not exceed invocation count,
then safely compares:

```text
retry <= invocation_count - fallback
```

The subtraction cannot become negative because of short-circuit ordering.
Attempt-one invocations may contribute to neither category. Different
invocations may legitimately produce one retry and one fallback.

Independent reproduction confirms:

- `invocation=1, retry=1, fallback=1` is rejected through fixed
  `UsageSummaryValidationError`;
- `invocation=2, retry=1, fallback=1` is accepted and canonical round-trips.

## Final Task 5C.7 Adversarial Disposition

The Architect performed one final interaction audit because earlier attempts
found individually valid nested views that were collectively impossible.

Confirmed:

- status categories sum exactly to invocation count;
- retry and fallback are individually and collectively bounded;
- every token field has exact observed/unavailable coverage;
- `None` and observed numeric zero remain distinct;
- cost buckets cover every invocation exactly once;
- duplicate cost identities are rejected;
- group-derived cost identities/counts/amounts equal top-level buckets;
- provider/model group lifecycle, predecessor, duration, token, and cost
  roll-ups equal the top-level view;
- all public construction and reconstruction paths execute the invariant.

No further contradictory canonical state was found.

## Acceptance Criteria Coverage

| Acceptance criterion | Result |
| --- | --- |
| One invocation cannot be both retry and fallback | Met |
| Valid mixed retry/fallback across different invocations remains accepted | Met |
| Top-level and provider/model summaries share one policy | Met |
| Direct construction, copy, and `from_dict()` enforce it | Met |
| Fixed safe error behavior remains intact | Met |
| Valid aggregation and canonical serialization remain unchanged | Met |
| Existing regressions remain green | Met |
| Only authorized files changed | Met |

## Validation Evidence

Independent Reviewer evidence:

- focused usage suite: `279 passed`;
- Run/Runner/Application/boundary/packaging regressions: `332 passed`;
- Task 4 regressions: `98 passed`;
- full default suite: `1840 passed, 5 skipped`;
- generated Playwright regressions: `2 passed`;
- isolated compileall and `git diff --check`: passed.

Architect evidence:

- complete Reviewer and Coder reports read;
- complete production diff and shared validator inspected;
- ancestry, role ownership, and report correlation verified;
- focused usage suite independently run: `279 passed`;
- invalid predecessor overlap independently rejected;
- valid two-invocation retry/fallback selection independently accepted and
  canonical round-tripped;
- Architect full-suite run produced `1839 passed, 5 skipped` plus one
  sandbox-permission failure in the existing external-example wheel build;
- that exact failed test was rerun with normal build permissions and passed;
- `git diff --check` passed and the worktree remained clean.

The full-suite discrepancy was environmental, not behavioral: the restricted
Architect sandbox prevented updating external-example build metadata. The
Reviewer completed the same full suite successfully, and the isolated failed
test passed immediately when granted its expected build permission.

## Required Changes

None.

## Decision

Approved

PMQA Task 5C.7 is approved at implementation commit
`2540acf98be7a1645c252de595be6930c63ab717`.

## Next Recommended Task

Proceed to PMQA Task 5D.0 — Conversational Workflow Platform Architecture,
defined in `agent-handoff/current-task.md`.
