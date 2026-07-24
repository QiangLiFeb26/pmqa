# Current Task

Owner: Architect

Task: AI Team Workflow Foundation — Provider-Neutral Independent Review

Task ID: `AI-TEAM-1`

Attempt: `1`

Status: Ready for Coder

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed baseline: `307ff706acc445c63880a253df0621dac82afd4d`

Coder starting HEAD: use the latest pushed branch commit containing this
handoff and record its exact SHA before making changes.

This file is the authoritative task handoff. Chat summaries are informational
only.

## Task Objective

Evolve the existing file-driven Architect → Coder → Architect workflow by
adding a provider-neutral Independent Reviewer role, while preserving the
current workflow, Human-in-the-Loop control, and strict authority boundaries.

This task establishes only the lightweight Markdown protocol used by people
and AI clients inside VS Code. It does not automate agent triggering or change
PMQA runtime behavior.

## Background

The current `agent-handoff/` workflow has successfully reduced copy/paste
between Architect and Coder. The next evolutionary step is:

```text
Human
  → Architect
  → Coder
  → Independent Reviewer
  → Architect
  → Human
```

The Reviewer independently evaluates the task, acceptance criteria, diff,
Coder report, and test evidence. The Architect remains the final technical
decision-maker within clear scope. Questions involving product direction,
business priority, material risk acceptance, or unresolved ambiguity must be
returned to the Human.

Only the Coder may modify implementation surfaces. Architect and Reviewer are
read-only with respect to code, tests, configuration, schemas, packaging,
scripts, and product documentation.

## Scope

Create the minimum durable protocol needed to run the new workflow every day:

1. a stable `agent-handoff/README.md` describing roles, authority, lifecycle,
   file ownership, communication rules, Human escalation, and VS Code usage;
2. a provider-neutral `agent-handoff/reviewer-report.md` template owned by the
   Independent Reviewer;
3. the Coder's updated completion report for this task.

The foundation itself is implemented and reviewed through the existing
Architect → Coder → Architect workflow. Do not invoke the new Reviewer for
this bootstrap task. The first live Reviewer pilot will be PMQA Task 5C.4
after this foundation is approved.

## Authority and File Ownership Requirements

The protocol must state these rules unambiguously.

### Human

- owns product direction, business priority, final approval, conflict
  resolution, and material risk acceptance;
- is not the routine messenger between agents;
- receives a 5–10 line Human Summary after each stage;
- may inspect the Markdown record when more detail is desired.

### Architect

- owns task definition, acceptance criteria, architecture decisions within
  approved product direction, review synthesis, and final technical
  disposition;
- may write only:
  - `agent-handoff/README.md`;
  - `agent-handoff/current-task.md`;
  - `agent-handoff/architect-review.md`;
- must not modify implementation, tests, configuration, schemas, packaging,
  scripts, or product documentation;
- must escalate to the Human when product direction, business trade-offs,
  material risk acceptance, or genuinely unresolved ambiguity is involved;
- may decide `Approved`, `Needs Revision`, `Split Task`,
  `Follow-up Task`, or `Human Decision Required`.

### Coder

- is the only role allowed to modify implementation surfaces, including code,
  tests, configuration, schemas, packaging, scripts, and product
  documentation;
- owns `agent-handoff/coder-report.md`;
- implements only the active `current-task.md`;
- reports exact branch/baseline/commit evidence, validation, scope, risks,
  recommended review depth, reason, and review focus;
- does not approve its own work.

### Independent Reviewer

- is read-only for the entire repository except its single owned file:
  `agent-handoff/reviewer-report.md`;
- never modifies production code, tests, configuration, schemas, packaging,
  scripts, product documentation, or another role's handoff file;
- does not participate in implementation;
- performs an independent evidence-based review;
- returns `Pass`, `Changes Requested`, or `Inconclusive`;
- recommends but does not issue the Architect's final approval;
- does not send remediation instructions directly to the Coder; findings flow
  to the Architect, who decides the disposition and writes any next task.

The one bootstrap exception is this task: the Coder may create
`agent-handoff/README.md` and the initial
`agent-handoff/reviewer-report.md` template because the protocol does not yet
exist. After this task is approved, their normal owners become exclusive.

## Communication Protocol Requirements

`agent-handoff/README.md` must define:

- repository Markdown as the formal single source of truth;
- Chat as a Human-facing status surface, not a formal handoff;
- the active files and their owners;
- required Task ID or name, attempt number, branch, starting HEAD, and relevant
  implementation/report commit SHAs;
- the sequential lifecycle:

```text
Architect publishes current-task
Coder implements and publishes coder-report
Reviewer independently publishes reviewer-report
Architect publishes architect-review and next disposition
Human receives concise stage summaries and resolves escalations
```

- no direct agent-to-agent copy/paste through the Human;
- no automatic triggering in this phase;
- no concurrent writes to the handoff files;
- a later stage must verify that it is reviewing the exact commits named by
  the previous stage;
- stale reports must be clearly replaced for the active task/attempt.

## Independent Review Requirements

The Reviewer protocol and template must require:

- Task and Attempt;
- Branch;
- Reviewed Starting HEAD, implementation commit(s), and Coder report commit;
- Actual Review Depth: `Light`, `Standard`, or `Deep`;
- Review Depth Reason;
- Overall Assessment;
- Findings with severity, evidence, and affected files/lines where practical;
- Acceptance Criteria coverage;
- Test Evidence reviewed and independently run;
- Security/scope/compatibility observations;
- Verdict: `Pass`, `Changes Requested`, or `Inconclusive`;
- Suggested Architect Focus;
- confirmation that the Reviewer changed no file except
  `reviewer-report.md`.

To reduce opinion anchoring, the Reviewer must inspect, in this order:

1. `current-task.md` and its acceptance criteria;
2. the named baseline-to-implementation diff and relevant tests;
3. independently selected validation evidence;
4. `coder-report.md`;

The Reviewer must not read the active task's `architect-review.md` before
publishing its own report. Prior architecture documentation and earlier
closed reviews may be used only when needed to understand established
contracts.

The Coder's recommended review depth is advisory. The Reviewer selects its own
actual depth, and the Architect independently selects the depth of final
review.

## Architect Decision and Human Escalation Requirements

The protocol must distinguish:

- technical findings resolvable within accepted task/product direction, which
  the Architect may decide;
- product direction, user experience, business priority, significant scope
  expansion, material security/cost risk acceptance, or irreconcilable
  reviewer disagreement, which must go to the Human.

Define a compact Human Decision Required section containing:

- decision needed;
- why it cannot be decided safely by the Architect;
- options and trade-offs;
- Architect recommendation, if one is supportable;
- default state: work pauses only on the affected decision while other
  independent safe work may continue.

If the Architect disagrees with a Reviewer finding, the Architect must record
specific evidence and reasoning. High-severity disagreement or risk acceptance
must be escalated to the Human.

## Human Summary Requirements

Define this 5–10 line Chat template:

```text
### Human Summary
Status:
What Changed:
Risk: Low / Medium / High
Review Result:
Next Step:
Action Needed From Human: None / concise decision request
```

The summary must not replace the formal Markdown record or copy its detailed
contents.

## VS Code Daily-Use Plan

Document a provider-neutral, manual VS Code setup:

- one shared checkout and branch;
- separate persistent chat/terminal panels for Architect, Coder, and Reviewer;
- each role starts by reading its owned protocol inputs from
  `agent-handoff/`;
- each role writes only its authorized file(s);
- Human wakes/starts a role when the preceding report is ready, but does not
  copy task details or reports between roles;
- each role verifies branch and exact SHA before acting;
- Git commits remain intentional and role-attributed;
- the approach must work with any AI client capable of reading the repository,
  inspecting diffs/tests, and editing its authorized Markdown file.

Do not require provider-specific configuration. Provider-specific examples may
be clearly labeled optional and non-normative.

## First Pilot and Migration Plan

Document the small rollout:

1. Foundation: this task, using the old Architect → Coder → Architect flow.
2. Pilot: PMQA Task 5C.4 uses the complete
   Coder → Independent Reviewer → Architect flow once.
3. Stabilization: one lightweight retrospective updates only proven pain
   points, templates, and ownership wording.

The current Coder workflow must otherwise remain unchanged. The Reviewer adds
one independent evidence stage; it does not become a manager or second Coder.

## Allowed Changes

- create `agent-handoff/README.md`;
- create `agent-handoff/reviewer-report.md`;
- replace `agent-handoff/coder-report.md` with this task's completion report.

No other file may change.

Use one focused protocol implementation commit and one report-only Coder
handoff commit. Do not amend prior Task 5C commits.

## Out of Scope

Do not:

- modify PMQA production code, tests, configuration, schemas, packaging,
  scripts, README, Roadmap, or architecture/product documentation;
- modify `agent-handoff/current-task.md` or
  `agent-handoff/architect-review.md`;
- build MCP, an event bus, a scheduler, a state machine, LangGraph workflow,
  autonomous agent network, daemon, watcher, webhook, or automatic trigger;
- add provider SDKs or depend on ChatGPT, Codex, Claude, Gemini, Copilot, or
  another named provider;
- add CLI commands, runtime models, persistence, telemetry, Usage/Cost, UI, or
  APIs;
- execute the Independent Reviewer stage for this bootstrap task;
- start PMQA Task 5C.4, Task 5B, Task 6, or Task 7;
- create a PR or merge.

## Acceptance Criteria

The task is complete only if:

- role authority and exclusive file ownership are explicit and internally
  consistent;
- only Coder can change implementation surfaces;
- Architect and Reviewer are explicitly prohibited from changing code/tests
  and other implementation surfaces;
- Architect must escalate unresolved or product-direction decisions to Human;
- Reviewer independence, inputs, inspection order, verdict vocabulary, and
  read-only boundary are operationally clear;
- Architect remains the final technical decision-maker, while Human retains
  product and risk authority;
- formal handoff lifecycle no longer requires Human copy/paste;
- Human Summary is concise and mandatory after each stage;
- VS Code guidance is provider-neutral and usable without new automation;
- bootstrap and first-pilot migration are unambiguous;
- templates include exact commit correlation and review-depth evidence;
- no implementation or product behavior changes;
- no provider-specific dependency or automatic orchestration is introduced.

## Validation Commands

Run and report:

```bash
git diff --check
git status --short
git diff --name-only <starting-head>..HEAD
```

Also perform a manual consistency audit:

- every role has exactly one clear authority boundary;
- no statement permits Architect or Reviewer to modify implementation;
- no statement permits Reviewer to direct or implement remediation;
- every product-direction or material-risk decision routes to Human;
- file lifecycle and exact-SHA correlation are complete;
- all relative Markdown links in `agent-handoff/` resolve;
- provider names, if present, are only non-normative examples.

No production test run is required because this task may change only handoff
Markdown. If any non-handoff file changes, stop: that is a scope violation.

## Expected Deliverables

- `agent-handoff/README.md`;
- `agent-handoff/reviewer-report.md`;
- updated `agent-handoff/coder-report.md`;
- one focused protocol commit;
- one report-only Coder handoff commit;
- clean worktree with local and remote branch HEADs synchronized;
- no PR and no merge.

## Required Coder Handoff

Replace `agent-handoff/coder-report.md` with a complete report containing:

- task and attempt;
- branch and exact Coder starting HEAD;
- implementation and report commit SHAs;
- changed files;
- protocol and template summary;
- manual authority/consistency audit;
- validation results;
- remaining risks/open items;
- scope confirmation;
- exactly one recommended review depth: `Light`, `Standard`, or `Deep`;
- one-sentence review-depth reason;
- 3–6 suggested review focus areas.

The Coder recommendation is advisory. The Architect makes the final review
decision.
