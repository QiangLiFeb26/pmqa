# Current Task

Owner: Architect

Task: AI Team Workflow Foundation — Commit Correlation Remediation

Task ID: `AI-TEAM-1`

Attempt: `2`

Status: Changes Required

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed attempt 1 HEAD: `cfe78bf1a3ee95c69255e3e0547e4e169efbb989`

Coder starting HEAD: use the latest pushed branch commit containing this
handoff and record its exact SHA before making changes.

This file is the authoritative task handoff. Chat summaries are informational
only.

## Task Objective

Remove the self-referential commit-SHA contradiction from the AI Team handoff
protocol so repository Markdown remains the complete formal evidence chain and
Chat remains informational only.

Do not change the accepted role, authority, Reviewer, escalation, or manual
workflow design.

## Background

AI-TEAM-1 attempt 1 correctly established the Independent Reviewer role and
exclusive file ownership. Standard architecture review found one blocking
protocol defect:

- a file cannot contain the SHA of the Git commit containing that exact file;
- the attempt 1 Coder report therefore moved its own report SHA into the Human
  Summary;
- this makes Chat part of the formal correlation chain despite the
  Markdown-only source-of-truth rule.

The formal review is in `agent-handoff/architect-review.md`.

## Scope

- Correct the commit-correlation rules in `agent-handoff/README.md`.
- Update `agent-handoff/reviewer-report.md` so it records the preceding Coder
  report commit but does not require its own self-referential commit SHA.
- Replace `agent-handoff/coder-report.md` with the attempt 2 completion report
  using the corrected rule.
- Preserve every other accepted AI-TEAM-1 behavior.

The AI-TEAM-1 bootstrap exception remains active for attempt 2, allowing the
Coder to modify the initial protocol README and Reviewer template. It ends only
after Architect approval of this remediation.

## Required Commit-Correlation Model

Document one unambiguous chain:

1. No handoff file is required or permitted to claim the SHA of the commit
   that contains that same file.
2. The publishing role records:
   - branch;
   - task and attempt;
   - starting HEAD;
   - all implementation commit SHAs already created before its report commit.
3. The receiving role derives the exact preceding report commit from Git,
   verifies branch/ancestry/path identity, and records that SHA in the
   receiving role's Markdown report.
4. The minimum derivation is:

   ```bash
   git log -1 --format=%H -- agent-handoff/<preceding-report>.md
   ```

5. The receiving role must also confirm that:
   - the derived commit is reachable from the active branch HEAD;
   - the report file at that commit identifies the active task and attempt;
   - the named implementation commits are reachable from the starting HEAD
     and are ancestors of the report commit;
   - no later unauthorized change replaced the report.
6. The repository evidence chain is:

   ```text
   current-task publication commit
     -> recorded by Coder as starting HEAD
   Coder report commit
     -> derived and recorded by Reviewer
   Reviewer report commit
     -> derived and recorded by Architect
   Architect disposition/current-task publication commit
     -> recorded by the next Coder as starting HEAD
   ```

7. Human Summary may display the same SHA for observability, but it is never
   authoritative and is not needed by the next role.

Do not solve self-reference with an extra attestation commit that modifies the
same report again; that merely creates another unrecorded self SHA.

## README Requirements

Update the protocol so:

- "exact SHA verification" refers to the preceding stage's commit;
- active records collectively form the evidence chain;
- each receiving report records the preceding handoff commit;
- self-commit hashes are explicitly excluded;
- Human Summary SHAs are informational;
- Git history, not Chat text, is authoritative;
- mismatch behavior still pauses the affected stage;
- sequential publication and exclusive ownership remain unchanged.

Keep the existing:

- Human, Architect, Coder, and Reviewer authority;
- exclusive write surfaces;
- Reviewer inspection order;
- advisory Reviewer verdict;
- Architect technical disposition;
- Human product/risk authority;
- escalation rules;
- provider-neutral VS Code workflow;
- bootstrap, Task 5C.4 pilot, and retrospective plan.

## Reviewer Template Requirements

The template must continue to require:

- task, task ID, attempt, and branch;
- reviewed starting HEAD;
- implementation commit(s);
- derived Coder report commit and correlation verification;
- independent review order and depth;
- findings, acceptance coverage, independent tests, scope, security,
  compatibility, verdict, and Architect focus;
- Reviewer write-boundary confirmation.

Add a concise statement that:

- the Reviewer report does not contain its own commit SHA;
- the Architect derives and records that commit in
  `architect-review.md`.

Do not add an unfillable `Reviewer Report Commit SHA` placeholder.

## Coder Report Requirements

The attempt 2 report must:

- identify Task ID `AI-TEAM-1`, attempt `2`, branch, and exact Coder starting
  HEAD;
- identify the focused remediation implementation commit;
- explain the receiving-stage derivation rule;
- explicitly state that its own report commit is not embedded in the report;
- state that the future Reviewer derives the Coder report commit, while the
  bootstrap Architect derives it directly for attempt 2;
- not claim that Chat or Human Summary is the formal source for its SHA;
- include validation, risks, scope confirmation, and review-depth advice.

The report should be committed separately after the implementation commit.

## Allowed Changes

- `agent-handoff/README.md`
- `agent-handoff/reviewer-report.md`
- `agent-handoff/coder-report.md`

No other file may change.

Do not amend attempt 1 commits. Add:

- one focused remediation implementation commit;
- one report-only Coder handoff commit.

## Out of Scope

Do not:

- modify `agent-handoff/current-task.md` or
  `agent-handoff/architect-review.md`;
- modify production code, tests, configuration, schemas, packaging, scripts,
  README, Roadmap, architecture, or product documentation;
- change role ownership or decision authority;
- execute the Independent Reviewer stage for this bootstrap;
- add automation, MCP, watchers, schedulers, hooks, state machines, bots,
  provider integrations, CLI, persistence, telemetry, or UI;
- start Task 5C.4, Task 5B, Task 6, or Task 7;
- create a PR or merge.

## Acceptance Criteria

- No active protocol statement requires a handoff file to embed its own commit
  SHA.
- The next stage can derive the preceding handoff commit using only repository
  and Git history.
- Every derived SHA is recorded by the receiving role in its Markdown report.
- The chain covers current task, Coder report, Reviewer report, and Architect
  disposition without circularity.
- Chat and Human Summary are explicitly non-authoritative.
- Branch, ancestry, task/attempt, and report-path verification are required.
- No extra self-attestation loop is introduced.
- The Reviewer template is immediately usable for Task 5C.4.
- All role, authority, independence, escalation, and ownership rules remain
  unchanged.
- Only the three allowed handoff Markdown files change.

## Validation Commands

Run and report:

```bash
git diff --check
git status --short
git diff --name-only <coder-starting-head>..HEAD
git log -1 --format=%H -- agent-handoff/coder-report.md
git log -1 --format=%H -- agent-handoff/reviewer-report.md
git merge-base --is-ancestor <starting-head> <implementation-commit>
git merge-base --is-ancestor <implementation-commit> <report-commit>
```

Also verify:

- all relative Markdown links in `agent-handoff/` resolve;
- no self-SHA requirement remains;
- no statement makes Chat authoritative;
- all exclusive ownership and escalation rules remain consistent;
- only the allowed files changed.

No production tests are required because this remediation is Markdown-only.

## Expected Deliverables

- Corrected non-circular commit-correlation protocol.
- Updated Reviewer template.
- Updated attempt 2 Coder report.
- One implementation commit and one report-only commit.
- Clean worktree and synchronized branch.
- No PR, merge, Reviewer execution, or Task 5C.4 implementation.

## Required Coder Handoff

Replace `agent-handoff/coder-report.md` with the complete attempt 2 report.

Include exactly one recommended review depth:

- `Light`
- `Standard`
- `Deep`

Also include one-sentence reasoning and 3–6 suggested review focus areas. The
recommendation is advisory; the Architect makes the final review decision.
