# Independent Reviewer Report

Owner: Independent Reviewer

Status: Template — not executed for the AI-TEAM-1 bootstrap

Replace this file in full for each active reviewed task and attempt. Git
history preserves prior reports.

## Task Correlation

Task:

Task ID:

Attempt:

Branch:

Reviewed Starting HEAD:

Reviewed Implementation Commit(s):

Derived Coder Report Commit:

Correlation Verification:

- derived with
  `git log -1 --format=%H -- agent-handoff/coder-report.md`;
- derived commit is reachable from the active branch HEAD;
- report at that commit identifies the active Task ID and Attempt;
- named implementation commits descend from the recorded starting HEAD and
  are ancestors of the derived report commit; and
- no later unauthorized change replaced the active Coder report.

This Reviewer report does not contain or predict its own commit SHA. The
Architect derives the Reviewer report commit from Git and records it in
`architect-review.md`.

## Independent Review Method

Inspection order completed:

1. `current-task.md` and acceptance criteria;
2. named baseline-to-implementation diff and relevant tests;
3. independently selected validation;
4. full `coder-report.md`.

Active-task `architect-review.md` read before publication: No

Prior closed review or architecture material consulted, with reason:

## Review Depth

Actual Review Depth: Light / Standard / Deep

Review Depth Reason:

The Coder recommendation is advisory and did not determine the actual depth.

## Overall Assessment

Provide a concise evidence-based assessment without issuing Architect
approval.

## Findings

List each finding with:

- ID and severity;
- evidence;
- affected files and lines where practical;
- acceptance criterion or established contract affected; and
- impact.

Write `None` when no finding remains. Do not implement remediation or direct
remediation instructions to the Coder; findings flow to the Architect.

## Acceptance Criteria Coverage

| Acceptance criterion | Evidence | Result |
| --- | --- | --- |
| Replace with each active criterion | Diff/test/report evidence | Met / Not met / Inconclusive |

## Test Evidence

### Coder Evidence Reviewed

Record claimed commands and results only after completing independent
inspection and validation.

### Independently Run

Record exact commands, results, environment limitations, and any test not run.
Do not present claimed evidence as independently reproduced evidence.

## Security, Scope, and Compatibility

Security observations:

Scope observations:

Compatibility observations:

## Verdict

Verdict: Pass / Changes Requested / Inconclusive

This verdict is advisory. The Architect makes the final technical disposition.

## Suggested Architect Focus

List the highest-value areas for Architect synthesis or write `None`.

## Reviewer Write-Boundary Confirmation

Repository files changed by Reviewer:

- `agent-handoff/reviewer-report.md`

Confirmation: I changed no production code, tests, configuration, schemas,
packaging, scripts, product documentation, or another role's handoff file.
