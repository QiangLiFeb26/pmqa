# Architect Review

Owner: Architect

Task: PMQA Task 5C.7 — Deterministic Usage Summary Contracts and Pure Aggregation

Task ID: `PMQA-5C.7`

Attempt: `1`

Status: Needs Revision

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed Starting HEAD:
`4128ef969e1a3dc90297a74c513a6cd2eabf0376`

Reviewed Implementation Commit:
`eeba9a9dd1d2fac6a007580d4511fbb51722bd15`

Derived Coder Report Commit:
`7b5b577ee369cc9b717d97c723a4ae8a479cec37`

Derived Reviewer Report Commit:
`569c519c043b3ce97a17dca5d1370ed60a6bc5d9`

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
  `4128ef969e1a3dc90297a74c513a6cd2eabf0376` is an ancestor of implementation
  commit `eeba9a9dd1d2fac6a007580d4511fbb51722bd15`;
- the implementation commit is an ancestor of Coder report commit
  `7b5b577ee369cc9b717d97c723a4ae8a479cec37`;
- the Coder report commit is an ancestor of Reviewer report commit
  `569c519c043b3ce97a17dca5d1370ed60a6bc5d9`;
- Coder and Reviewer reports identify the same Task, Attempt, branch,
  starting HEAD, and implementation commit;
- the implementation changed only the nine allowed production, test,
  packaging, and documentation files;
- the Coder report commit changed only `agent-handoff/coder-report.md`;
- the Reviewer report commit changed only
  `agent-handoff/reviewer-report.md`;
- all role ownership and non-circular correlation rules were followed.

## Review Depth Selected

Deep

The Architect independently selected Deep review because Task 5C.7 creates a
public canonical aggregate tree whose top-level and grouped views must remain
mathematically consistent across status, predecessor, duration, token, and
cost evidence.

The Coder and Reviewer both recommended Deep review.

## Overall Assessment

The pure aggregation implementation is well isolated and its generated output
is correct for the tested inputs. It successfully preserves:

- empty versus unavailable evidence;
- observed zero versus missing values;
- exact bounded duration and token arithmetic;
- provider-reported versus estimated cost;
- currency and pricing provenance;
- subscription-included and unavailable non-monetary evidence;
- deterministic provider/model grouping;
- input-order-independent canonical output;
- safe aggregation failures and import isolation.

However, the public `UsageSummary` contract does not enforce consistency
between its top-level aggregate and its `provider_model_groups`. A canonical
wire payload can therefore claim mutually contradictory status, duration,
token, and cost facts at the same time and still pass `from_dict()`.

Because `UsageSummary` is a public persisted/transmitted contract, correctness
cannot depend solely on callers using `DefaultUsageAggregator`. Direct
construction, `from_dict()`, and revalidated copies must enforce the same
aggregate invariant.

Task 5C.7 is therefore not approved in Attempt 1.

## Independent Reviewer Result

Reviewer verdict: `Pass`

Reviewer blocking findings: None

The Reviewer performed a legitimate Deep review, read the full implementation
and tests, and independently executed all required validation. The passing
test evidence is valid.

The Architect's finding extends the adversarial matrix to cross-level
contract reconstruction. It does not indicate a process or ownership failure
by the Reviewer.

The Architect overrides the advisory verdict with `Needs Revision`.

## Review Finding

### F1 — Provider/model groups can contradict the top-level summary

Severity: Blocking

Location:

- `pmqa/usage/summary.py`
- `UsageSummary.validate_group_coverage`

The current validator checks only:

```text
sum(group.invocation_count) == summary.invocation_count
```

It does not reconcile:

- succeeded, failed, and cancelled counts;
- retry and fallback counts;
- total duration;
- token totals and observed/unavailable coverage;
- cost-bucket invocation counts and monetary amounts.

Each `UsageProviderModelSummary` is internally valid, but it can describe
different evidence from the valid top-level aggregate.

Independent reproduction:

```text
UsageSummary.from_dict(...) accepted:

top-level:
  succeeded=1, failed=0
  duration_ms=100
  input_tokens=10
  provider_reported USD amount=0.1

only provider/model group:
  succeeded=0, failed=1
  duration_ms=999
  input_tokens=999
  provider_reported USD amount=999
```

The group retained `invocation_count=1`, so the existing coverage check
passed.

Impact:

- one canonical summary can present contradictory answers to a CLI or future
  Web UI;
- provider/model comparisons may not reconcile to the session/run total;
- cost and token reporting can be internally false even though every nested
  contract is individually valid;
- `from_dict()` can accept an impossible persisted summary.

Required correction:

- reconcile every provider/model group back to the top-level aggregate;
- reject any mismatch during direct construction, `from_dict()`, or
  `model_copy(update=...)`;
- retain deterministic exact Decimal and bounded integer behavior;
- keep `DefaultUsageAggregator` output and public field sets unchanged.

## Reviewer Observation Disposition

### Bare monetary `assert`

The Reviewer correctly observed:

```python
assert cost.amount is not None
```

The assertion is currently unreachable-as-false because `_snapshot_record`
reconstructs `CostEvidence` before aggregation. It is not the Attempt 1
blocker.

Nevertheless, the focused remediation should replace it with an explicit
fixed safe branch. Python optimization can remove assertions, and a public
aggregation boundary should not rely on one for domain correctness.

No new error code is required. An impossible monetary record after the
authoritative snapshot may use the existing fixed `INVALID_RECORD` boundary.

## Acceptance Criteria Coverage

| Acceptance criterion | Result |
| --- | --- |
| Strict immutable provider-neutral summary contracts | Partially met |
| Empty, zero, partial, and unavailable distinction | Met |
| Cost type, currency, and pricing provenance separation | Met within each level |
| Exact bounded aggregation | Met for aggregator output |
| Deterministic non-recursive provider/model grouping | Met |
| Top-level and provider/model grouped views are mutually consistent | Not met |
| Input-order-independent canonical output | Met |
| Duplicate/correlation rejection | Met |
| No storage/provider/workflow/CLI side effects | Met |
| Import and packaging isolation | Met |
| Only authorized files changed | Met |

## Validation Evidence

Independent Reviewer evidence:

- focused usage suite: `245 passed`;
- Run/Runner/Application/boundary/packaging regressions: `332 passed`;
- Task 4 regressions: `98 passed`;
- full default suite: `1806 passed, 5 skipped`;
- generated Playwright regressions: `2 passed`;
- isolated compileall and `git diff --check`: passed.

Architect evidence:

- complete Reviewer and Coder reports read;
- full `pmqa/usage/summary.py` implementation inspected;
- ancestry, role ownership, and path correlation verified;
- focused usage suite independently run: `245 passed`;
- direct adversarial `UsageSummary.from_dict()` reconstruction accepted
  contradictory top-level/group status, duration, token, and cost evidence;
- `git diff --check` through the Reviewer commit: passed;
- the worktree was clean before Architect disposition.

The passing suite demonstrates correct aggregator output but does not test
cross-level contradiction at the public summary reconstruction boundary.

## Required Changes

Complete one focused PMQA-5C.7 Attempt 2 remediation for F1 and replace the
bare monetary assertion. Do not redesign summary fields, change aggregation
meaning, add repository integration, or begin UI work.

## Decision

Needs Revision

PMQA Task 5C.7 is not approved at implementation commit
`eeba9a9dd1d2fac6a007580d4511fbb51722bd15`.

## Next Recommended Task

Complete PMQA Task 5C.7 Attempt 2 — Cross-Level Summary Consistency,
defined in `agent-handoff/current-task.md`.

PMQA Task 5D.0 — Conversational Workflow Platform Architecture begins only
after this focused remediation passes final review.
