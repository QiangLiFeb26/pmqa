# AI Team Handoff Protocol

## Purpose and Authority

This directory is the formal, provider-neutral record for the sequential
Human → Architect → Coder → Independent Reviewer → Architect → Human workflow.
Repository Markdown is the single source of truth for task scope, evidence,
findings, and disposition. Chat is a concise Human-facing status surface; it
does not replace or override these files.

The workflow is manual in this phase. It adds no automatic trigger, watcher,
scheduler, event bus, state machine, agent network, or provider dependency.
The Human starts or wakes the next role after the preceding committed report
is ready, without copying task details or reports between roles.

## Roles and Exclusive Authority

### Human

The Human owns product direction, business priority, final approval, conflict
resolution, and material risk acceptance. The Human is not the routine
messenger between roles. After every stage, the Human receives the concise
5–10 line Human Summary defined below and may inspect the Markdown record for
detail.

Only the Human may decide product direction, user-experience trade-offs,
business priority, significant scope expansion, or acceptance of material
security, cost, or operational risk.

### Architect

The Architect owns task definition, acceptance criteria, architecture
decisions within approved product direction, review synthesis, and final
technical disposition.

The Architect may write only:

- `agent-handoff/README.md`;
- `agent-handoff/current-task.md`; and
- `agent-handoff/architect-review.md`.

The Architect must not modify production code, tests, configuration, schemas,
packaging, scripts, product documentation, or another role's handoff file.
The Architect may decide only `Approved`, `Needs Revision`, `Split Task`,
`Follow-up Task`, or `Human Decision Required`. The Architect escalates the
Human-owned decisions above and any genuinely unresolved ambiguity.

### Coder

The Coder is the only AI-team role allowed to modify implementation surfaces:
production code, tests, configuration, schemas, packaging, scripts, and
product documentation. The Coder owns only
`agent-handoff/coder-report.md` within this directory and implements only the
active `current-task.md`.

The Coder reports the exact branch, baseline, implementation and report commit
evidence, validation, scope, risks, one advisory review-depth recommendation,
its reason, and suggested review focus. The Coder never approves its own work
and never writes the Reviewer or Architect disposition.

### Independent Reviewer

The Independent Reviewer is read-only for the entire repository except
`agent-handoff/reviewer-report.md`, which it exclusively owns. The Reviewer
never modifies production code, tests, configuration, schemas, packaging,
scripts, product documentation, or another role's handoff file. It does not
implement or repair findings.

The Reviewer performs an independent, evidence-based review and returns only
`Pass`, `Changes Requested`, or `Inconclusive`. This verdict is advisory: the
Architect remains the final technical decision-maker. Findings flow to the
Architect. The Reviewer must not send remediation instructions directly to
the Coder or act as a manager or second Coder.

### Bootstrap exception

For AI-TEAM-1 attempt 1 only, the Coder may create this README and the initial
`reviewer-report.md` template because their normal ownership protocol does not
yet exist. After AI-TEAM-1 is approved, the Architect exclusively owns this
README and the Independent Reviewer exclusively owns `reviewer-report.md`.

## Active Files and Owners

| File | Exclusive owner after bootstrap | Purpose |
| --- | --- | --- |
| [`README.md`](README.md) | Architect | Stable protocol, authority, and lifecycle |
| [`current-task.md`](current-task.md) | Architect | Active task, attempt, scope, acceptance criteria, and starting evidence |
| [`coder-report.md`](coder-report.md) | Coder | Implementation evidence and Coder handoff |
| [`reviewer-report.md`](reviewer-report.md) | Independent Reviewer | Independent findings, evidence, and advisory verdict |
| [`architect-review.md`](architect-review.md) | Architect | Review synthesis and final technical disposition |

Only one role writes at a time. A role must commit and publish its authorized
file or implementation before the next stage begins. No concurrent handoff
file edits are permitted.

Each active task record must identify:

- Task ID or exact task name;
- attempt number;
- branch;
- starting HEAD;
- relevant implementation commit SHA(s);
- Coder report commit SHA;
- Reviewer report commit SHA when the Reviewer stage applies; and
- Architect review commit SHA when the disposition is published.

A later stage must verify its branch and the exact commits named by the
preceding stage before acting. A mismatch pauses that stage until the
authoritative owner corrects or explains it.

Each role replaces its stale active report in full; reports are not appended
across tasks or attempts. The title, Task, Attempt, branch, and commit fields
must identify the active task. Git history preserves closed reports.

## Sequential Lifecycle

```text
Architect publishes current-task
Coder implements and publishes coder-report
Reviewer independently publishes reviewer-report
Architect publishes architect-review and next disposition
Human receives concise stage summaries and resolves escalations
```

1. **Architect task publication**
   - Verify the shared branch and exact starting HEAD.
   - Replace `current-task.md` with one bounded active task and acceptance
     criteria.
   - Commit and publish the task, then send the Human Summary.
2. **Coder implementation**
   - Verify `current-task.md`, branch, and starting evidence.
   - Change only the allowed implementation surfaces.
   - Commit implementation, replace `coder-report.md`, commit the report, and
     publish both commits.
   - Send the Human Summary without self-approval.
3. **Independent review**
   - Begin only after the Coder report commit is published.
   - Follow the independent inspection order below.
   - Change only `reviewer-report.md`, commit and publish it, then send the
     Human Summary.
4. **Architect disposition**
   - Verify all reviewed SHAs and read the independent report.
   - Independently inspect evidence at the depth the Architect selects.
   - Replace `architect-review.md` with synthesis and one allowed disposition.
   - If revision is required, replace `current-task.md` with the next bounded
     attempt; the Reviewer does not address the Coder directly.
   - Commit and publish the disposition, then send the Human Summary.
5. **Human control**
   - Resolve only escalated decisions and give final approval where required.
   - The Human need not copy task or report content between roles.

There is no automatic triggering. The Human manually wakes the next role when
the repository report is ready.

## Independent Review Procedure

To reduce opinion anchoring, the Reviewer inspects in this order:

1. `current-task.md` and its acceptance criteria;
2. the named baseline-to-implementation diff and relevant tests;
3. independently selected validation evidence; and
4. `coder-report.md`.

Before substantive review, the Reviewer may read only the correlation header
of `coder-report.md` needed to locate the exact implementation and report
commits. The Coder's assessment, recommendations, and claimed test results
remain unread until step 4. This narrow correlation read is not substantive
inspection.

The Reviewer must not read the active task's `architect-review.md` before
publishing `reviewer-report.md`. Earlier closed reviews and established
architecture documentation may be consulted only when necessary to understand
existing contracts.

The Coder's recommended depth is advisory. The Reviewer independently selects
and records actual depth as exactly `Light`, `Standard`, or `Deep`, with a
reason. The Architect separately selects the final-review depth.

The Reviewer report must include:

- Task and Attempt;
- Branch;
- Reviewed Starting HEAD, implementation commit(s), and Coder report commit;
- Actual Review Depth and Review Depth Reason;
- Overall Assessment;
- findings with severity, evidence, and affected files/lines where practical;
- acceptance-criteria coverage;
- Coder test evidence reviewed and tests independently run;
- security, scope, and compatibility observations;
- Verdict: `Pass`, `Changes Requested`, or `Inconclusive`;
- Suggested Architect Focus; and
- confirmation that no file except `reviewer-report.md` changed.

## Architect Decisions and Human Escalation

Technical findings that can be resolved within accepted task scope and product
direction remain the Architect's responsibility. The Architect records
specific evidence and reasoning when disagreeing with a Reviewer finding.

The Architect must escalate:

- product direction or user-experience choices;
- business priority or trade-offs;
- significant scope expansion;
- material security, cost, or operational risk acceptance;
- genuinely unresolved ambiguity; and
- irreconcilable Reviewer disagreement.

A disagreement involving high-severity findings or any material risk
acceptance always goes to the Human.

Use this compact section in `architect-review.md` when escalation is required:

```text
## Human Decision Required

Decision Needed:
Why Architect Cannot Safely Decide:
Options and Trade-offs:
Architect Recommendation: recommendation or "None"
Default State: Pause only the affected decision; independent safe work may continue.
```

## Mandatory Human Summary

Every Architect, Coder, and Reviewer stage ends with this 5–10 line Chat
summary:

```text
### Human Summary
Status:
What Changed:
Risk: Low / Medium / High
Review Result:
Next Step:
Action Needed From Human: None / concise decision request
```

The Human Summary does not replace the formal Markdown record and must not copy
its detailed contents.

## Provider-Neutral VS Code Daily Use

Use one shared checkout and one shared active branch. Keep separate persistent
chat or terminal panels for Architect, Coder, and Independent Reviewer. Each
role begins by reading its protocol inputs from `agent-handoff/`, verifies the
branch and exact SHA, and writes only its authorized files or implementation
surfaces.

The Human starts or wakes a role after the preceding committed report is
ready, but does not transfer task text, findings, or reports through Chat.
Git commits remain intentional, role-attributed, and sequential. This workflow
works with any AI client capable of reading the repository, inspecting diffs
and tests, and editing its authorized Markdown file. No provider-specific
configuration is required; any named-client example is optional and
non-normative.

## Rollout

1. **Foundation:** AI-TEAM-1 uses the existing Architect → Coder → Architect
   flow. The Independent Reviewer is not invoked for this bootstrap task.
2. **Pilot:** after the foundation is approved, PMQA Task 5C.4 uses the full
   Coder → Independent Reviewer → Architect review flow once.
3. **Stabilization:** one lightweight retrospective changes only demonstrated
   pain points, templates, or ownership wording.

The Reviewer adds one independent evidence stage. It does not replace the
current Coder workflow, become a manager, or become a second implementer.
