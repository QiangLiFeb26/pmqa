# Independent Reviewer Report

Owner: Independent Reviewer

Status: Executed for PMQA Task 5D.0, Attempt 1

## Task Correlation

Task: PMQA Task 5D.0 — Conversational Workflow Platform Architecture

Task ID: `PMQA-5D.0`

Attempt: `1`

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed Starting HEAD: `9d2ba638c9692eb542bb6d1c023388d959573316`

Reviewed Implementation Commit(s): `df2aeddf8949729cf5121e1c4327a504b6eb59f8`
("define conversational workflow platform architecture")

Derived Coder Report Commit: `4e8ecc8c525eb65031abf03aaba7ba7febaca408`
("report Task 5D.0 architecture handoff")

Correlation Verification:

- derived with `git log -1 --format=%H -- agent-handoff/coder-report.md` ->
  `4e8ecc8c525eb65031abf03aaba7ba7febaca408`;
- `git merge-base --is-ancestor 9d2ba638c9692eb542bb6d1c023388d959573316 HEAD`
  succeeds; `9d2ba63...` is an ancestor of `df2aedd...`, and `df2aedd...` is
  an ancestor of `4e8ecc8...` (linear sequence
  `9d2ba63 -> df2aedd -> 4e8ecc8` on this branch);
- the Task 5C.7 (Attempt 3) Reviewer baseline named by `current-task.md`,
  `9d28c1361111d75e642292ec87a9a8f1f406cdc7` (this Reviewer's own prior
  report commit), is an ancestor of the recorded starting HEAD;
- the correlation header of `coder-report.md` at the derived commit names
  Task ID `PMQA-5D.0`, Attempt `1`, branch
  `agent/task-5c-1-canonical-run-contract`, and starting HEAD
  `9d2ba638c9692eb542bb6d1c023388d959573316`, matching `current-task.md`;
- `git diff --stat df2aedd..4e8ecc8` touches only
  `agent-handoff/coder-report.md`, so the derived commit is the report's
  latest authorized change with no later unauthorized replacement.

This Reviewer report does not contain or predict its own commit SHA. The
Architect derives the Reviewer report commit from Git and records it in
`architect-review.md`.

## Independent Review Method

This is a documentation/architecture checkpoint, not a code change, so the
independent inspection order was adapted while preserving its intent:

1. `current-task.md` and its acceptance criteria (the full required-content
   list — product position, logical architecture, existing-contract reuse
   map, record correlation, capability/authority matrix, artifact/approval
   lifecycle, flagship workflow, ADO read/write boundaries, identity/
   security, untrusted-content policy, usage/AIC integration, UI/deployment
   recommendation, decisions/stop-points, phased delivery plan);
2. the named baseline-to-implementation diff (`9d2ba63..df2aedd`) — a full
   read of the new `docs/architecture/conversational-workflow-platform.md`
   (all 745 lines) and the `README.md`/`docs/Roadmap.md`/`docs/architecture.md`
   diffs, plus independent spot-verification of specific factual claims
   against the actual codebase (not just the document's own internal
   consistency);
3. independently selected validation (see Test Evidence), including a
   from-scratch relative-link check, a stale-status search across the docs
   tree, and a private-information scan, all run independently of the
   Coder's own claimed results;
4. full `coder-report.md` (read only after steps 1-3).

Active-task `architect-review.md` read before publication: No

Prior closed review or architecture material consulted, with reason: this
Reviewer authored all three prior reviews on the branch (Task 5C.7 Attempts
1-3), giving direct knowledge of the actual current shape of
`AIInvocationCollector`, `UsageRepository`, `UsageAggregator`, and
`WorkflowDefinition`/`RunRequest`/`PMQAApplicationService` referenced
throughout this architecture document; this was used only to sanity-check
the document's factual claims against code already independently verified
in this session, not to substitute for reading the document itself.

## Review Depth

Actual Review Depth: Deep

Review Depth Reason: this checkpoint sets the authority, record-separation,
and security boundaries that every later 5D.1-5D.6 implementation phase will
inherit — an error here (e.g., a capability level that implicitly lets
retrieved content grant authority, or a record design that collapses
authorization into conversation state) would propagate through six future
checkpoints before being caught. I read the entire architecture document,
cross-checked its factual claims about existing contracts against the actual
source files rather than trusting the document's own assertions, and
independently ran every listed validation plus additional link/stale-status/
privacy scans. This matches the Coder's advisory recommendation but was
independently selected.

## Overall Assessment

The document is a comprehensive, internally consistent, and factually
well-grounded architecture that satisfies the task's required content list
and acceptance criteria. It is documentation-only: the diff touches exactly
`docs/architecture/conversational-workflow-platform.md` (new, 745 lines),
`README.md`, `docs/Roadmap.md`, and `docs/architecture.md` — no production
code, test, schema, packaging, or dependency file changed, confirmed by
`git diff --stat` and by the full test suite reporting the identical
`1840 passed, 5 skipped` count as the pre-existing baseline (i.e., zero
tests were added or altered by this checkpoint, as expected for an
architecture-only task).

I independently spot-verified several of the document's specific claims
about existing contracts against the actual source, rather than accepting
them at face value:

- the claim that "the current Application Service supports only its
  no-approval execution path" and that `WorkflowDefinition.approval_mode`
  "is not a substitute for the future revision- and digest-bound
  `Authorization` record" is factually accurate — I read
  `pmqa/application/service.py:124-127`, which raises
  `PMQAApplicationError(ApplicationFailureCode.APPROVAL_REQUIRED)`
  unconditionally whenever `definition.approval_mode is not
  ApprovalMode.NONE`, meaning the existing service genuinely cannot execute
  any approval-gated workflow today;
- the claim that `KnowledgeArtifact` "is product knowledge, not a general
  story, plan, approval, or receipt envelope" matches its actual definition
  in `pmqa/models/knowledge.py` (fields: `artifact_id`, `product_id`,
  `reasoning_provenance`, ...), which has no revision, approval, or
  external-scope field;
- `ReasoningProvider` (`pmqa/reasoning/provider.py`) and `StorageProvider`
  (`pmqa/providers/interfaces.py`) both exist as described, supporting the
  document's characterization that reasoning models are "product-knowledge
  shaped" and that `StorageProvider` is "replaceable" rather than an
  immutable-revision repository.

This gives me confidence the "Existing-Contract Reuse and gaps" table is not
aspirational or invented, but reflects the actual current codebase — which
directly matters for the acceptance criterion "existing Task 4/5/5A/5C
contracts are reused rather than duplicated," since a reviewer cannot verify
that claim without checking the contracts it claims to reuse.

The document consistently maintains the required non-collapsing record
separation (conversation session/turn, workflow run, reasoning invocation,
capability invocation, artifact revision, approval/authorization, external
operation, receipt, provider-session usage observation) both in its
"Records and correlation" table and in explicit negative statements at each
relevant section (e.g., "Chat text is never the source of truth for an
approved change," "An identifier link does not transfer authority"). The
capability/authority matrix explicitly forbids the exact failure mode named
in the task ("Story/Test Plan content cannot grant itself new capability")
via "Story text, Test Case text, comments, attachments, provider responses,
and prompt instructions cannot register capabilities, change policy levels,
expand connection scope, approve plans, or choose an executor."

The phased delivery plan matches the six required phases exactly, states a
vertical outcome, dependencies, deferred work, and a recommended review
depth for each, and every phase explicitly does not start in this
checkpoint ("No delivery phase begins as part of Task 5D.0" — confirmed true
by the diff containing zero non-documentation files).

## Findings

None. One item worth recording as a non-blocking observation rather than a
finding: `docs/architecture/usage-cost-contracts.md` (a file outside this
task's Allowed Changes list) still reads "Task 5C.7 is Ready for
architecture review" even though Task 5C.7 has since passed. I found this
independently during my own stale-status search before reading the Coder's
report, and confirmed the Coder found and disclosed the identical
discrepancy, proactively adding an explicit sentence to `docs/Roadmap.md`
("Status wording retained inside the individual Task 5C checkpoint
architecture documents records the review stage at which each checkpoint
document was published; this roadmap is authoritative for the current
cumulative status.") to resolve the ambiguity without touching a file this
task was not authorized to change. This is correct handling of an
out-of-scope constraint, not an oversight, so it is not a finding.

## Acceptance Criteria Coverage

| Acceptance criterion | Evidence | Result |
| --- | --- | --- |
| PMQA is defined as a multi-workflow conversational QA platform | "Product definition" section states the required product position verbatim and elaborates the ownership split | Met |
| Arbitrary conversation and structured workflows coexist without a fixed global wizard | "Open conversation and workflow semantics" section; `ado.work_item_summary` explicitly proves the catalog/UI are not hard-coded to authoring | Met |
| The first Story authoring flow is a registered flagship workflow, not UI architecture | "Flagship workflow" section: "LangGraph remains an implementation detail of that registered runner, not the conversation or UI architecture" | Met |
| Reasoning, capability, approval, and deterministic external execution boundaries are explicit | "Capability and authority model" table (4 levels x 6 dimensions) plus explicit executor/authorization separation throughout | Met |
| Copilot-mediated automatic ADO read preserves no-copy UX without granting unrestricted write authority | "ADO Story acquisition boundary" and "Capability and authority model" sections; explicit PMQA-controlled read-wrapper fallback if CLI enforcement is unavailable | Met |
| ADO content remains untrusted and cannot elevate capability | Dedicated "Untrusted content and prompt injection" section with an explicit adversarial test-strategy list | Met |
| Artifact revision, digest-bound authorization, partial execution, and receipts are defined | "Structured artifacts and authorization" and "ADO write, concurrency, and recovery boundary" sections, including the required succeeded/partially_succeeded/failed/cancelled receipt states | Met |
| Local-first identity and Web security are addressed without inventing company authentication facts | "Identity, authentication, and local Web security" section explicitly separates recommended defaults from a "Company-environment validation must establish, rather than assume" list | Met |
| Exact invocation usage and provider-session AIC usage are not conflated | "Usage, AIC, and audit integration" section explicitly defers/separates `ProviderSessionUsageObservation` and states "PMQA does not allocate it across model calls" | Met |
| Existing Task 4/5/5A/5C contracts are reused rather than duplicated | "Existing-contract reuse and gaps" table; independently spot-verified 4 specific claims against actual source files (see Overall Assessment) | Met |
| The UI technology recommendation and hosted migration path are explicit | "UI and deployment recommendation" section: React/TypeScript/Vite + FastAPI/Uvicorn, with an explicit "Local persistence and migration" subsection | Met |
| Implementation phases are independently reviewable | "Phased delivery plan" section: 6 phases, each with vertical outcome, dependencies, deferred work, and recommended review depth | Met |
| Only allowed documentation and Coder report files change | `git diff --stat` from starting HEAD to the derived report commit touches exactly the 4 allowed doc paths plus `agent-handoff/coder-report.md`; no Architect/Reviewer file, production code, test, or packaging file changed | Met |

## Test Evidence

### Coder Evidence Reviewed

The Coder report claims: Markdown relative-link validation passed across 19
files; a stale-status search found only the one out-of-scope
`usage-cost-contracts.md` match (described above) and no stale Task 5D.0
wording; a private-information scan of the new document found no URL, org/
project name, Work Item ID, credential, or internal metadata; full default
suite `1840 passed, 5 skipped` (one pre-existing warning); generated
Playwright regressions `2 passed`; `git diff --check` clean; clean
worktree. This claimed evidence was read only after independent execution
below and matches it exactly.

### Independently Run

All checks below were executed by the Reviewer directly, before reading the
Coder's claimed results, from the repository root on the reviewed branch:

- `git diff --check` -> exit code `0`, no output
- `git status --short` -> empty (clean worktree)
- `.venv/bin/python -m pytest -q` (full default suite) -> `1840 passed, 5 skipped, 1 warning`
  (identical count to the pre-Task-5D.0 baseline, confirming zero test
  impact from a documentation-only change)
- `.venv/bin/python -m pytest products/demo/generated_tests -q` -> `2 passed`
- an independent Python script parsing every `](...)` relative link in the
  four changed documentation files and resolving each against the
  filesystem -> "All relative markdown links in changed files resolve
  correctly" (not the Coder's own link-check tooling, a separate ad hoc
  implementation)
- `grep -rn "5C\.7"` / `grep -rn "5D\.0"` across `README.md`, `docs/*.md`,
  and `docs/architecture/*.md` -> confirmed the one out-of-scope stale match
  in `usage-cost-contracts.md` described under Findings, and no stale/
  inconsistent Task 5D.0 wording anywhere in the changed files
- independent regex scans of the new architecture document for `https?://`
  URLs, 4+ digit numeric sequences (plausible Work Item IDs), and
  credential-related keywords (`password`, `secret`, `api[_-]?key`,
  `token=`, `bearer `) -> no URL, no plausible Work Item ID, and the only
  password/secret/token matches are in policy-statement prose ("PMQA does
  not accept or persist raw passwords... tokens", "managed secrets" as a
  generic future hosted-deployment concern), not leaked values

No listed validation command was left unrun. No test was skipped by
Reviewer choice. Environment: local `.venv` (Python 3.9), macOS/Darwin, no
network access used or required.

## Security, Scope, and Compatibility

Security observations: the document's capability/authority model correctly
treats "read only" prompt instructions as non-enforcing guidance rather than
a security boundary, requires the deterministic executor (never the
reasoning provider) to hold write authority, and requires every
authorization to bind an exact content digest so that a later edit
invalidates it — these are the load-bearing security properties for
everything the later 5D.1-5D.6 phases will build, and I did not find a gap
or contradiction in how they are stated. The untrusted-content section
correctly extends "untrusted" classification to automatically-retrieved ADO
content (not just user-typed text), closing the specific loophole the task
called out ("Automatic retrieval does not make ADO content trusted").

Scope observations: the diff touches only the four allowed documentation
paths plus the Coder-owned report in a separate commit. No production code,
test, configuration, schema, packaging, or dependency file changed, and no
other architecture document besides the newly created one and the three
explicitly allowed index/status files was modified.

Compatibility observations: the full test suite passes with an identical
count to the pre-existing baseline, confirming this checkpoint has zero
runtime effect, as required for an architecture-only task.

## Verdict

Verdict: Pass

This verdict is advisory. The Architect makes the final technical
disposition.

## Suggested Architect Focus

- No blocking findings from this Reviewer's independent inspection. The one
  non-blocking stale-status observation (`usage-cost-contracts.md`) is
  already disclosed and correctly handled by the Coder within this task's
  scope constraints; no action is required unless the Architect wants that
  file's own status line refreshed as part of a future in-scope edit.
- Given this document sets direction for six future phases, it may be worth
  the Architect explicitly confirming the recommended default policy list
  (disabled destructive/bulk operations, no discussion sharing with Copilot
  until approved, metadata-only attachments, etc.) reflects actual product
  intent before 5D.1 begins, since the document itself frames these as
  defaults pending Human/company validation rather than final decisions.
- This is the first Task 5D checkpoint; the Attempt-1/2/3 pattern seen on
  Task 5C.7 (where genuine gaps surfaced only through the Architect's own
  adversarial reproduction) suggests that for the first *implementation*
  phase (5D.1), it may again be worth budgeting for a Deep review pass that
  actively constructs cross-boundary contradictions (e.g., an
  internally-valid-looking session/authorization pair that is jointly
  impossible) rather than only exercising each new contract's own declared
  invariants in isolation.

## Reviewer Write-Boundary Confirmation

Repository files changed by Reviewer:

- `agent-handoff/reviewer-report.md`

Confirmation: I changed no production code, tests, configuration, schemas,
packaging, scripts, product documentation, or another role's handoff file.
