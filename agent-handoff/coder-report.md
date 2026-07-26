# Coder Report

Owner: Coder

Task: PMQA Task 5D.0 — Conversational Workflow Platform Architecture

Task ID: `PMQA-5D.0`

Attempt: `1`

Status: Ready for Independent Reviewer

## Branch and Git Correlation

Branch:

`agent/task-5c-1-canonical-run-contract`

Exact Git-derived Coder starting HEAD:

`9d2ba638c9692eb542bb6d1c023388d959573316`

That commit was the latest pushed publication of
`agent-handoff/current-task.md`, identified Task `PMQA-5D.0` Attempt `1`, and
was the clean local and tracking-branch HEAD before documentation changes. Its
Architect-reviewed baseline Reviewer HEAD is
`9d28c1361111d75e642292ec87a9a8f1f406cdc7`. No Task 5C implementation or
handoff commit was amended.

## Documentation Implementation Commit

`df2aeddf8949729cf5121e1c4327a504b6eb59f8`

Commit message:

`define conversational workflow platform architecture`

This report is committed separately after the documentation implementation
commit. The Independent Reviewer derives the report commit from Git; this
report does not claim its own future commit SHA.

## Changed Files

Documentation implementation commit:

- `docs/architecture/conversational-workflow-platform.md` (new);
- `README.md`;
- `docs/Roadmap.md`; and
- `docs/architecture.md`.

Report-only handoff commit:

- `agent-handoff/coder-report.md`.

No production code, tests, fixtures, schemas, configuration, packaging,
dependencies, or other handoff file changed.

## Product Architecture

PMQA is defined as a local-first, provider-neutral conversational QA workflow
platform rather than a fixed wizard or cost-only dashboard. The reasoning
provider interprets arbitrary natural language, reasons over bounded evidence,
and proposes answers, capabilities, workflows, artifacts, actions, or
clarifications. PMQA owns the workbench, context boundary, registrations,
authority, durable structured state, deterministic execution, audit, receipts,
and usage evidence.

The first flagship workflow is the explicitly registered
`ado.story_test_authoring`. It is a reference happy path rather than a global
conversation state machine. The smaller future read-only
`ado.work_item_summary` demonstrates that direct answers and bounded read
workflows do not inherit authoring stages.

The local user journey begins with a loopback workbench and connected-identity
confirmation, supports automatic approved ADO reads without manual content
copy, renders source revision and scope for confirmation, separates artifact
review from external authorization, and ends external actions with verified
per-operation receipts. Source confirmation grants no write authority.

## Logical and Record Architecture

The recommended dependency direction is:

```text
Local Browser Workbench
  -> Local PMQA Web/API Boundary
  -> Conversation Application Service
       -> Workflow Catalog
       -> Capability Registry / Gateway
       -> Structured Artifact Store
       -> Approval / Authorization Service
       -> Deterministic Action Executor
       -> Connection Context
       -> Usage / Audit
  -> provider and product adapters
```

The architecture separately defines conversation sessions and turns, workflow
runs, reasoning invocations, capability invocations, structured artifact
revisions, authorizations, external operations, receipts, and optional
provider-session usage observations. They correlate through bounded IDs but
cannot become one universal object.

Conversation state, artifact revision history, authorization, receipts, and
provider-session observations must not be merged into LangGraph
`WorkflowState`, reasoning traces, or Task 5C usage records. LangGraph remains
an internal runner implementation option for a registered workflow.

## Existing-Contract Reuse

- Existing `WorkflowDefinition` and explicit `WorkflowRegistry` remain the
  canonical workflow catalog source; the future catalog is a UI/read-model
  projection, not a duplicate definition.
- `RunRequest`, `RunRecord`, `RunnerInvocationRecord`,
  `ApplicationRunResult`, `PMQARunner`, and the existing registries/Application
  Service retain workflow-execution correlation and selection semantics.
  Conversation-to-run correlation and future multi-attempt policy are new
  application responsibilities.
- Task 4 state, reducer, Supervisor, runtime, and LangGraph adapter remain
  internal workflow execution boundaries.
- Task 5 composition and verified handoff provide independent-validation and
  exact-terminal-correlation patterns, but `KnowledgeArtifact` is not
  generalized into Story, plan, authorization, or receipt content.
- `RunArtifact` remains a logical output reference. A future immutable
  revision repository is required because `RunArtifact` and replaceable
  `StorageProvider` do not own revision, approval, or source-revision
  semantics.
- Task 5A's manifest, explicit loader, Bridge v1, and bounded process runner
  remain explicit Product Pack execution boundaries; they do not become
  global discovery or conversation capability registration.
- Task 3's `ReasoningProvider`, scrubber, prompt packages, and `TraceRecord`
  remain the reasoning trust boundary. A future conversation response contract
  is required because the current models are product-knowledge shaped and
  traces are audit records rather than conversation or authority.
- Task 5C's collector, repository, and aggregator remain authoritative for
  exact model-invocation evidence. A whole-provider-session AIC observation is
  separate or deferred and is never allocated across invocations.
- The shared prohibited-key policy remains the neutral base for serializable
  boundaries; credentials and runtime clients stay outside all records.

## Capability and Authority Architecture

The provider-neutral policy levels are:

- `read_only`: a provider may request one registered, scope-approved read;
  PMQA may execute it under explicit connection/session policy, and the
  adapter alone can access delegated credentials;
- `proposal_only`: PMQA may automatically perform a local deterministic
  transformation, but the proposal has no external authority;
- `approval_required`: sensitive reads, provider sharing, or costly
  non-mutating execution requires explicit approval bound to exact content and
  scope; and
- `external_write`: a provider may only propose the action; final
  revision/digest-bound Human authorization and deterministic PMQA execution
  are mandatory.

Story, comment, Test Case, attachment, and provider content is untrusted and
cannot register a capability, change policy, expand scope, approve a plan, or
select an executor. Prompt wording is not a security boundary. Copilot never
receives an unrestricted ADO writer. If company Copilot CLI read-tool
restriction is not technically enforceable, the architecture selects a
PMQA-controlled read wrapper or direct ADO read adapter.

Every authorization binds exact plan ID, revision, canonical digest, ADO
organization/project scope, relevant source revisions, approving user, and
timestamp. A relevant edit invalidates authorization. Authoring Plan and
Authorization remain distinct concepts.

## ADO Read, Write, and Recovery Decisions

The provider-neutral `StorySource` seam allows Copilot-mediated or direct ADO
read adapters without changing conversation/artifact contracts. The canonical
snapshot includes source scope, item identity/type/revision, bounded sanitized
fields, relations, paginated discussion completeness, timestamps, and
explicit missing/inaccessible/truncated evidence. Attachment content is
deferred; names and links remain untrusted metadata.

Read and write interfaces are separate. Before a deterministic write, PMQA
revalidates identity/scope, permissions, exact authorization digest, and
current external revisions. Optimistic-concurrency mismatch fails closed and
requires a new plan revision and authorization.

An operation plan has stable IDs, idempotency correlation, typed bounded
arguments, expected revisions, and deterministic order. Each operation has a
verified receipt. Partial completion is reported as partial rather than
success. Resume re-reads state and skips only operations proven satisfied;
unknown outcomes stop for Human review. Automatic multi-operation rollback is
not promised, and compensating actions require a new authorized plan.

## UI, Security, and Deployment Recommendation

The explicit future recommendation is a React + strict TypeScript frontend
built with Vite and served as packaged assets by a loopback-only FastAPI /
Uvicorn Python application. Versioned REST/JSON commands and queries plus
server-sent progress events keep the browser independent of Python, LangGraph,
provider, and repository internals. WebSockets are deferred.

The workspace is a Conversation pane beside a Structured Workspace for
connection state, Story snapshots, citations, scenarios, coverage, Test Case
diffs, plans, authorization, receipts, and usage/audit views. It consumes
versioned API read models and never imports LangGraph or reads repository JSON.

The future local boundary requires loopback binding, an unpredictable local
session token, strict Host/Origin validation, CSRF protection, restrictive
CORS/CSP, HTML sanitization, output encoding, bounded contracts, safe
browser-to-command allowlists, and fixed-safe redacted logs. Official delegated
credential stores remain authoritative; raw passwords, PATs, tokens, cookies,
and browser state never enter conversation, artifact, Run, WorkflowState,
trace, usage, receipt, or log records.

A separate local SQLite repository is recommended for conversation indexes,
artifact revisions, authorizations, and receipts. It does not reuse reasoning
trace SQLite or usage JSON because their retention and corruption semantics
differ. The hosted path preserves API/application/adapter contracts while
adding authenticated users, tenant isolation, managed credentials, roles, and
managed repositories.

## Human and Company-Environment Decisions

The document records defaults and exact stop points for:

- initial ADO organization/project/process-template scope: 5D.2 stops before
  live acquisition until validated;
- sandbox Test Plan/Suite and write identity: 5D.5 stops before any write;
- discussion sharing with Copilot: 5D.3 omits it until approved;
- attachments: metadata-only until a separate content security decision;
- local retention: 5D.1 stops before persistence release without a default;
- supported Work Item types/custom fields: 5D.2 fails safely outside an
  explicit validated allowlist;
- Copilot structured output: 5D.3 stops before selecting the live adapter;
- Copilot read-tool enforcement: 5D.2 uses a controlled wrapper/direct adapter
  when enforcement is absent;
- delegated ADO authentication, expiry, reconnect, and scope: 5D.2 stops until
  proven;
- destructive/bulk operations: disabled in 5D.5; and
- provider-session AIC semantics: 5D.6 keeps them separate/unavailable and
  never invents allocation.

No company authentication behavior is asserted as fact.

## Phased Delivery Plan

1. **5D.1 — Local Web Foundation and Session State:** loopback workbench,
   versioned API, workflow catalog view, offline conversation shell, and
   repository seams. Recommended review: Deep.
2. **5D.2 — Conversational ADO Read / Story Acquisition:** one controlled read
   capability and bounded cited `StorySnapshot`. Recommended review: Deep.
3. **5D.3 — Reasoning, Structured Artifacts, and Scenario Review:** validated
   conversational reasoning and immutable scenario revisions. Recommended
   review: Deep.
4. **5D.4 — Test Inventory and Authoring Plan:** read-only inventory, coverage
   matrix, and non-executable plan. Recommended review: Standard.
5. **5D.5 — Version-Bound Authorization and Deterministic ADO Write:** sandbox
   preflight, optimistic concurrency, deterministic operations, verification,
   partial results, and receipts. Recommended review: Deep.
6. **5D.6 — Usage, Audit, Security, Packaging, and End-to-End Hardening:**
   bounded cross-record views, retention/redaction closure, real packaging,
   and gated end-to-end validation. Recommended review: Deep.

Task 5D.0 starts none of these phases.

## Documentation Status Changes

README and the authoritative Roadmap now record Task 5C.7 as architecture
review passed. The Roadmap adds Task 5D as in progress and Task 5D.0 as ready
for architecture review while making clear that no runtime phase started.
The architecture index links and summarizes the new decision document.

The stale-status search found Task 5C.7 “Ready for architecture review” only in
`docs/architecture/usage-cost-contracts.md`, an unmodified checkpoint-local
document outside the allowed file list. The Roadmap explicitly records that
individual Task 5C checkpoint documents preserve their publication-stage
status and that the Roadmap is authoritative for cumulative status. No stale
Task 5D.0 “not started” or “awaiting review” statement remains in the changed
documentation.

## Validation Results

- Repository Markdown relative-link validation: all `19` Markdown files
  passed.
- Stale Task 5C.7/Task 5D.0 status search: passed with the one explicitly
  historical checkpoint-local Task 5C.7 match described above.
- Private-information search in the new architecture document: no URL,
  organization/project name, concrete Work Item ID, selector, credential,
  private code, repository path, or internal metadata found.
- Full default suite: `1840 passed, 5 skipped` with one existing LangGraph
  pending-deprecation warning. The skips are existing opt-in live/external
  environment gates.
- Generated SauceDemo Playwright regressions: `2 passed`.
- `git diff --check`: passed.
- Pre-report documentation implementation worktree: clean.

## Scope Confirmation

This task changed documentation only. It added no Python, TypeScript, test,
schema, packaging, fixture, dependency, CLI, server, frontend, conversation
runtime, connector, capability implementation, artifact contract,
authorization contract, ADO read/write behavior, Copilot integration,
LangGraph node, usage contract, or external side effect. No company-private
information was added. Task 5D.1 and later, Task 5B, Task 6, and Task 7 were
not started. No PR was created and nothing was merged.

## Recommended Review Depth

**Deep**

Reason: this checkpoint establishes the product-wide authority, identity,
record-separation, external-write, local-Web, and phased-delivery boundaries
that every later conversational implementation will inherit.

## Suggested Reviewer Focus

- Verify every proposed component reuses or documents an incompatibility with
  existing Task 4/5/5A/5C contracts and does not duplicate Run, workflow,
  artifact, trace, or usage semantics.
- Challenge the separation between arbitrary conversation, workflow
  selection, provider capability proposals, Human authorization, deterministic
  external execution, and receipts.
- Review Copilot-mediated ADO read fallback, untrusted-content handling,
  credential isolation, and the claim that retrieved content cannot elevate
  policy.
- Exercise authorization invalidation, optimistic concurrency, partial
  execution, idempotent resume, unknown outcomes, and no automatic rollback.
- Confirm the UI/deployment recommendation addresses loopback authentication,
  Origin/CSRF/XSS, local command boundaries, persistence separation, packaging,
  and future hosted migration.
- Verify each Human/company decision has a fail-closed implementation stop
  point and that no Task 5D implementation phase was started.

## Human Summary

PMQA-5D.0 Attempt 1 已完成，Git 派生起点为 `9d2ba638c9692eb542bb6d1c023388d959573316`。
文档实现提交为 `df2aeddf8949729cf5121e1c4327a504b6eb59f8`。
架构将 PMQA 定义为本地优先、provider-neutral 的 conversational QA workflow platform，并明确 reasoning、capability、artifact、authorization、executor、receipt 与 usage 的独立边界。
旗舰流程 `ado.story_test_authoring` 是注册 workflow，而不是全局 UI 状态机；5D.1–5D.6 均未启动。
验证结果：全仓库 Markdown links 通过，全量 1840 passed / 5 skipped，Playwright 2 passed，diff check 通过。
Action Needed From Human: 请将下方 Handoff Note 传递给 Independent Reviewer。
Handoff Note: 请读取 agent-handoff/README.md 与 agent-handoff/current-task.md，从 Git 派生最新 coder-report commit，并按独立审查顺序完成 review。
