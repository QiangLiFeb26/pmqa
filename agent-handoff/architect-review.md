# Architect Review

Owner: Architect

Task: PMQA Task 5C.7 — Cross-Level Summary Consistency

Task ID: `PMQA-5C.7`

Attempt: `2`

Status: Needs Revision

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed Starting HEAD:
`370434c4c42c31b3bde573f10bf63e2b503b0c00`

Reviewed Implementation Commit:
`3419a9e5d4460186c2608dbd7f1e26762241c070`

Derived Coder Report Commit:
`71aa76384a628915e170950758f256add9d5eaee`

Derived Reviewer Report Commit:
`d6b1acd1572bf55de8cb85ed303059b832daa55d`

The Reviewer report commit was derived with:

```bash
git log -1 --format=%H -- agent-handoff/reviewer-report.md
```

This review does not claim the SHA of its own containing commit. The Coder
records the publication commit containing this disposition and remediation
task as the next starting HEAD.

## Correlation and Ownership Verification

- the active branch and upstream are
  `agent/task-5c-1-canonical-run-contract`;
- starting HEAD
  `370434c4c42c31b3bde573f10bf63e2b503b0c00` is an ancestor of implementation
  commit `3419a9e5d4460186c2608dbd7f1e26762241c070`;
- the implementation commit is an ancestor of Coder report commit
  `71aa76384a628915e170950758f256add9d5eaee`;
- the Coder report commit is an ancestor of Reviewer report commit
  `d6b1acd1572bf55de8cb85ed303059b832daa55d`;
- Coder and Reviewer reports identify the same Task, Attempt, branch,
  starting HEAD, and implementation commit;
- the remediation changed only `pmqa/usage/summary.py` and
  `tests/test_usage_summary.py`;
- the Coder and Reviewer report commits changed only their exclusively owned
  handoff files;
- all role ownership and Git-correlation rules were followed.

## Review Depth Selected

Deep

The Architect independently selected Deep review because this attempt makes a
public multi-level aggregate mathematically self-consistent. Review included
cross-level and cross-field adversarial construction, not only the generated
aggregator path.

## Overall Assessment

Attempt 2 correctly closes both findings assigned by the prior Architect:

- top-level lifecycle, predecessor, duration, token, and cost metrics are now
  reconciled from provider/model groups;
- reconciliation uses bounded integer and exact Decimal arithmetic;
- direct construction, `from_dict()`, and revalidated copy paths run the
  invariant;
- persisted contradictions become fixed safe summary-validation errors;
- the monetary aggregation loop no longer relies on a removable `assert`;
- generated aggregator output and all existing public fields remain
  unchanged.

However, independent cross-field review found one remaining impossible public
summary state. Retry and fallback counts are each bounded independently, but
their combined count is not bounded by invocation count.

Because every source `AIInvocationRecord` permits at most one predecessor kind,
a canonical summary cannot legitimately count one invocation as both retry
and fallback. This affects future retry-waste and fallback reporting, so Task
5C.7 remains unapproved.

## Independent Reviewer Result

Reviewer verdict: `Pass`

Reviewer blocking findings: None

The Reviewer performed a legitimate Deep review, independently reproduced the
assigned cross-level contradiction and optimized-Python monetary case, and ran
all required tests.

The Architect accepts that both assigned remediation targets are closed, but
overrides the advisory verdict because the broader predecessor-count contract
still admits an impossible aggregate.

## Closed Findings

### Cross-level roll-up consistency

Closed.

`_validate_group_rollup` now derives and compares lifecycle counts, predecessor
counts, duration, token coverage/totals, and normalized cost buckets. The
Attempt 1 contradictory status/duration/token/cost wire payload is rejected.

### Monetary domain assertion

Closed.

The aggregation service now uses an explicit fixed `INVALID_RECORD` branch and
retains the same behavior under `python -O`.

## New Blocking Finding

### F1 — Retry and fallback counts can overlap beyond invocation count

Severity: Blocking

Location:

- `pmqa/usage/summary.py`
- `_validate_metrics`

Current validation checks:

```text
retry_invocation_count <= invocation_count
fallback_invocation_count <= invocation_count
```

but does not require:

```text
retry_invocation_count + fallback_invocation_count <= invocation_count
```

Every valid `AIInvocationRecord` has either:

- no predecessor on attempt one; or
- exactly one retry predecessor; or
- exactly one fallback predecessor.

It can never have both predecessor fields.

Independent reproduction:

```text
invocation_count=1
retry_invocation_count=1
fallback_invocation_count=1
```

The same values were placed in the sole provider/model group, so all new
cross-level reconciliation passed. `UsageSummary.from_dict()` accepted the
payload.

Impact:

- one invocation may be counted twice across mutually exclusive predecessor
  categories;
- retry-waste and fallback analysis can overstate activity;
- top-level and group views may agree with each other while both contradict
  every possible source-record selection;
- a future CLI or Web UI can display impossible operational evidence.

Required correction:

- enforce the combined predecessor bound in the shared `_validate_metrics`
  path so it applies to top-level and provider/model summaries;
- prove all public contract entry points reject overlap;
- retain legitimate mixtures where different invocations account for retry
  and fallback separately.

## Acceptance Criteria Coverage

| Acceptance criterion | Result |
| --- | --- |
| Assigned top-level/group lifecycle reconciliation | Met |
| Assigned duration/token/cost reconciliation | Met |
| Every contract entry point runs cross-level validation | Met |
| Exact bounded integer and Decimal behavior | Met |
| Monetary aggregation contains no domain `assert` | Met |
| Predecessor aggregate represents possible source records | Not met |
| Fixed safe reconstruction errors | Met |
| Existing behavior and allowed scope preserved | Met |

## Validation Evidence

Independent Reviewer evidence:

- focused usage suite: `267 passed`;
- Run/Runner/Application/boundary/packaging regressions: `332 passed`;
- Task 4 regressions: `98 passed`;
- full default suite: `1828 passed, 5 skipped`;
- generated Playwright regressions: `2 passed`;
- isolated compileall and `git diff --check`: passed.

Architect evidence:

- complete Reviewer and Coder reports read;
- full remediation diff and new roll-up helpers inspected;
- ancestry, role ownership, and report correlation verified;
- focused usage suite independently run: `267 passed`;
- direct `UsageSummary.from_dict()` reproduction accepted
  `invocation_count=1`, `retry=1`, `fallback=1` at both top-level and the sole
  provider/model group;
- `git diff --check` through the Reviewer commit: passed;
- the worktree was clean before Architect disposition.

The passing suite validates cross-level equality but lacks a mutually
exclusive predecessor-category test.

## Required Changes

Complete one minimal PMQA-5C.7 Attempt 3 remediation for predecessor-count
exclusivity. Do not change public fields or revisit the completed roll-up
implementation.

## Decision

Needs Revision

PMQA Task 5C.7 is not approved at implementation commit
`3419a9e5d4460186c2608dbd7f1e26762241c070`.

## Next Recommended Task

Complete PMQA Task 5C.7 Attempt 3 — Retry/Fallback Aggregate Exclusivity,
defined in `agent-handoff/current-task.md`.

PMQA Task 5D.0 begins immediately after this narrow remediation passes final
review.
