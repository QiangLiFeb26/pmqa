# Architect Review

Owner: Architect

Task: PMQA Task 5D.0 — Conversational Workflow Platform Architecture

Task ID: `PMQA-5D.0`

Attempt: `1`

Status: Approved

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed Starting HEAD:
`9d2ba638c9692eb542bb6d1c023388d959573316`

Reviewed Documentation Implementation Commit:
`df2aeddf8949729cf5121e1c4327a504b6eb59f8`

Derived Coder Report Commit:
`4e8ecc8c525eb65031abf03aaba7ba7febaca408`

Derived Reviewer Report Commit:
`115910e2662ce6bd2de6f807dfb3dfddc201a4b3`

The Reviewer report commit was derived from Git with:

```bash
git log -1 --format=%H -- agent-handoff/reviewer-report.md
```

This review does not predict the SHA of its own containing commit.

## Correlation and Ownership Verification

- the current branch and upstream are
  `agent/task-5c-1-canonical-run-contract`;
- starting HEAD `9d2ba63...` is an ancestor of documentation commit
  `df2aedd...`;
- documentation commit `df2aedd...` is an ancestor of Coder report commit
  `4e8ecc8...`;
- Coder report commit `4e8ecc8...` is an ancestor of Reviewer report commit
  `115910e...`;
- Coder and Reviewer reports identify the same Task, Attempt, branch,
  starting HEAD, and documentation implementation commit;
- the implementation changed only the four authorized product/architecture
  documentation paths;
- the Coder report commit changed only `agent-handoff/coder-report.md`;
- the Reviewer report commit changed only
  `agent-handoff/reviewer-report.md`;
- the branch matched its upstream and the worktree was clean before this
  Architect disposition.

## Review Depth

Deep

The Architect independently selected Deep review. Task 5D.0 is
documentation-only, but its record separation, capability policy, Human
authorization, external-write, local-Web, and provider boundaries become the
trust foundation for six later implementation checkpoints.

## Independent Reviewer Result

Reviewer verdict: `Pass`

Reviewer findings: None

The Reviewer read the complete architecture document, checked its factual
reuse claims against implementation contracts, verified scope, and
independently ran the full validation set. The Architect accepts the advisory
verdict.

## Overall Assessment

Task 5D.0 is approved.

The architecture establishes PMQA as a local-first, provider-neutral
conversational QA workflow platform rather than a fixed Story wizard or a
cost dashboard. It preserves arbitrary conversation while requiring explicit
registered workflows and deterministic lifecycle for structured artifacts and
external effects.

The flagship `ado.story_test_authoring` flow is a catalog workflow, not the UI
or global conversation state machine. The smaller future
`ado.work_item_summary` flow proves the proposed workbench and application
boundary are not hard-coded to authoring.

The design correctly separates:

- conversation sessions and turns;
- workflow runs and runner invocations;
- reasoning/model invocations;
- capability invocations;
- immutable artifact revisions;
- Human authorization;
- deterministic external operations;
- execution receipts; and
- provider-session usage observations.

Correlation does not transfer authority. Chat text, provider output, retrieved
ADO content, a workflow run, or a prior approval cannot become an executable
write without an exact current plan revision, canonical digest, external
scope, source revisions, approving identity, and deterministic executor.

## Architect Findings

None.

## Architecture Disposition

### Existing contract reuse

Approved.

The document reuses the existing Workflow and Runner registries, Run
contracts, Application Service, Task 4 orchestration, Task 5 verified handoff,
Task 5A external execution seam, Task 3 reasoning boundary, and Task 5C usage
services where their semantics fit.

New future contracts are limited to genuine gaps: conversation response,
capability invocation, artifact revision, authorization, operation/receipt,
connection context, and optional provider-session usage observation.

`WorkflowState`, `KnowledgeArtifact`, `RunArtifact`, reasoning traces, and
usage records are not broadened into universal state containers.

### Capability and authority

Approved.

The provider may interpret intent and propose registered calls, artifacts,
workflows, and actions. It cannot register capabilities, change policy,
expand connection scope, approve a plan, supply an executor, or receive an
unrestricted ADO writer.

`read_only`, `proposal_only`, `approval_required`, and `external_write`
express materially different authority. Prompt wording is explicitly not
treated as a security boundary.

### ADO read and write

Approved.

Copilot-mediated acquisition preserves the desired no-copy user experience,
but only when its read-tool restriction is technically enforceable. Otherwise
the design selects a PMQA-controlled wrapper or direct read adapter.

Writes are isolated behind final version/digest-bound Human authorization,
permission preflight, optimistic concurrency, deterministic operation order,
idempotency correlation, verification, and per-operation receipts. Partial
completion cannot be reported as complete, unknown outcomes stop for Human
review, and automatic rollback is not promised.

### Local Web and identity

Approved as an architecture direction.

React with strict TypeScript and Vite, served as packaged assets by a
loopback-only FastAPI/Uvicorn process, is a reasonable local-first boundary
with a hosted migration path. The browser consumes versioned read models and
cannot import LangGraph, read repository JSON, use provider credentials, or
invoke arbitrary commands.

The loopback interface is correctly not treated as authentication by itself.
Session-token delivery, Host/Origin enforcement, CSRF, CORS/CSP, XSS/HTML
sanitization, output encoding, and browser-to-command allowlisting are
identified as 5D.1 trust-root work.

### Untrusted content and secret handling

Approved with a mandatory 5D.1 implementation focus.

ADO and provider content remain untrusted and cannot elevate authority.
Existing prohibited-key and reasoning scrubber policies are reusable, but
future implementation must distinguish:

- excluding credential fields and runtime objects, which is enforceable;
- high-confidence redaction/rejection of recognizable secrets in arbitrary
  text, which is best-effort; and
- the impossible claim that all user-authored free text can be proven
  secret-free.

5D.1 must define ingress behavior before persistence or provider forwarding,
must not log rejected raw text, and must use fixed-safe errors. It must not
claim that a detector can recognize every arbitrary password. This is a
next-phase acceptance focus, not a Task 5D.0 blocker.

### Usage and AIC

Approved.

Task 5C remains authoritative for model-invocation evidence. A whole Copilot
session total is separate evidence and cannot be allocated across
invocations. Provider-reported, parsed, estimated, subscription-included, and
unavailable evidence remain distinct; no tokens or dollar cost are invented.

## Acceptance Criteria Coverage

| Acceptance criterion | Result |
| --- | --- |
| Multi-workflow conversational product position | Met |
| Arbitrary conversation and structured workflows coexist | Met |
| Story authoring is a registered flagship workflow | Met |
| Reasoning, capability, authorization, and execution are separate | Met |
| Automatic ADO read does not grant unrestricted write | Met |
| Retrieved content remains untrusted | Met |
| Revision/digest authorization and receipts are defined | Met |
| Partial execution and recovery are explicit | Met |
| Local-Web identity/security boundary is addressed | Met |
| Exact invocation usage is separate from provider-session AIC | Met |
| Existing Task 4/5/5A/5C contracts are reused | Met |
| UI technology and hosted migration recommendations are explicit | Met |
| 5D.1–5D.6 are independently reviewable | Met |
| Only authorized documentation/report files changed | Met |

## Validation Evidence

Independent Reviewer:

- full default suite: `1840 passed, 5 skipped`;
- generated Playwright regressions: `2 passed`;
- Markdown relative-link, stale-status, private-information, scope, and
  `git diff --check` checks: passed.

Architect:

- complete `current-task.md`, Coder report, Reviewer report, and all `744`
  architecture-document lines reviewed;
- complete documentation implementation diff inspected;
- implementation, Coder-report, and Reviewer-report ancestry and exclusive
  ownership verified;
- existing Run, Application, Runner, Workflow, reasoning, storage, knowledge,
  security, and usage contract claims spot-checked against source;
- full default suite: `1839 passed, 5 skipped`, with one expected restricted
  sandbox failure while updating external-example wheel metadata;
- the exact sandbox-blocked wheel test rerun with normal build permission:
  `1 passed`;
- generated Playwright regressions: `2 passed`;
- `git diff --check` passed and the worktree remained clean.

The full-suite discrepancy is environmental, not behavioral. The Reviewer ran
the complete suite successfully, and the one sandbox-blocked test passed when
given its normal build permission.

## Non-Blocking Follow-ups

- `docs/architecture/usage-cost-contracts.md` preserves its historical
  publication-stage wording for Task 5C.7. The authoritative Roadmap explains
  this convention. Refreshing that checkpoint document is optional future
  closure work, not a Task 5D.0 finding.
- 5D.1 must calibrate the secret-ingress guarantee as described above.
- Company-side ADO/Copilot authentication, CLI structure, read-tool
  allowlisting, and provider-session AIC semantics remain evidence gates, not
  assumed facts.

## Human Decision Gate Before 5D.1

Task 5D.1 requires a product decision about the default local retention of
conversation messages and structured artifact revisions.

Architect recommendation:

- retain local conversation and artifact content for `30 days` after the
  session's last activity;
- permit immediate manual deletion;
- permit explicit user configuration for session-only, `7`, `30`, or `90`
  days;
- do not silently select indefinite retention;
- keep Task 5C usage, reasoning traces, and future execution receipts under
  their own explicit retention policies rather than deleting them implicitly
  with conversation content.

The Human accepted this recommendation on `2026-07-25`. The decision gate is
closed, and the executable Task 5D.1A handoff is published in
`agent-handoff/current-task.md`.

## Required Changes

None for Task 5D.0.

## Decision

Approved

PMQA Task 5D.0 is approved at documentation implementation commit
`df2aeddf8949729cf5121e1c4327a504b6eb59f8`.

## Next Recommended Task

Proceed to PMQA Task 5D.1A — Conversation Session and Retention Foundation,
defined in `agent-handoff/current-task.md`.
