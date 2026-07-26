# Current Task

Owner: Architect

Task: PMQA Task 5D.0 — Conversational Workflow Platform Architecture

Task ID: `PMQA-5D.0`

Attempt: `1`

Status: Ready for Coder

Branch: `agent/task-5c-1-canonical-run-contract`

Architect-reviewed baseline Reviewer HEAD:
`9d28c1361111d75e642292ec87a9a8f1f406cdc7`

Coder starting HEAD: derive and record the latest pushed branch commit that
contains this task publication before changing files.

Repository Markdown and Git history are authoritative. Chat summaries are
informational only.

## Task Objective

Define the product and technical architecture for PMQA as a local-first,
provider-neutral, conversational QA Workflow Platform with a browser-based
workbench.

PMQA must support arbitrary natural-language QA questions and multiple future
workflows. It must not hard-code the entire product around one linear Story
workflow.

The first flagship workflow is ADO Story analysis and test-case authoring, but
it is one registered workflow on a reusable platform:

```text
ado.story_test_authoring
```

This checkpoint is architecture and product-flow definition only. Do not
implement Web UI, connectors, conversation runtime, workflow code, ADO access,
or Copilot integration.

## Product Context

The first user is one QA on a company-managed computer. The desired initial
experience is:

```text
start PMQA locally
→ open a Web interface
→ use the QA's own ADO and GitHub Copilot identities
→ ask arbitrary QA questions in natural language
→ review structured artifacts beside the conversation
→ explicitly authorize external changes
→ receive verified ADO receipts and AI usage evidence
```

The QA should not manually copy Story title, description, acceptance criteria,
or discussion into PMQA. A natural-language message containing a Work Item ID
may cause Copilot to use the user's existing ADO/Azure CLI access to retrieve
the content automatically. PMQA then displays a structured Story snapshot so
the user can confirm the correct item and revision.

The platform must preserve a future path to a centrally hosted team service,
but the MVP is a single-user local Web application using the user's delegated
identities.

## Required Product Position

The architecture must explicitly define PMQA as:

> a conversational QA workflow platform, not a fixed wizard and not a
> cost-only dashboard.

Copilot or another reasoning provider may:

- answer general QA questions;
- interpret arbitrary natural language;
- request approved read capabilities;
- reason over retrieved context;
- propose structured artifacts and actions;
- revise proposals from human feedback.

PMQA owns:

- conversation and context boundaries;
- workflow and capability registration;
- structured artifacts and revisions;
- approval and authorization policy;
- deterministic external-action execution;
- connection identity and scope;
- audit, receipts, and usage evidence.

The reasoning provider is the brain; PMQA is the workbench, capability
gateway, authority boundary, durable memory, and deterministic executor.

## Required Architecture Analysis

Before recommending new modules, inspect and map the existing:

- Task 4 LangGraph workflow and Supervisor boundaries;
- Task 5 SauceDemo composition and artifact handoff;
- Task 5A Product Pack and Bridge architecture;
- Task 5C RunRequest, WorkflowDefinition, WorkflowRegistry, RunnerRegistry,
  PMQAApplicationService, AIInvocationCollector, UsageRepository, and
  UsageAggregator;
- reasoning-provider contracts and Copilot CLI provider;
- artifact and storage abstractions;
- CLI composition and package/import isolation.

For every proposed platform component, state:

- what existing contract it reuses;
- what gap remains;
- whether the gap requires a new contract, adapter, service, or UI-only view;
- why it must not be merged into LangGraph `WorkflowState`, reasoning traces,
  or Usage records.

Do not duplicate existing WorkflowDefinition, registry, run, artifact, or
usage concepts under new names without a documented incompatibility.

## Required Logical Architecture

Define clear responsibilities and dependency direction for at least:

```text
Local Browser Workbench
        ↓
Local PMQA Web/API Boundary
        ↓
Conversation Application Service
        ├── Workflow Catalog
        ├── Capability Registry / Gateway
        ├── Structured Artifact Store
        ├── Approval / Authorization Service
        ├── Deterministic Action Executor
        ├── Connection Context
        └── Usage / Audit
                ↓
        Provider and Product Adapters
        ├── Copilot Reasoning Adapter
        ├── ADO Read Adapter
        ├── ADO Write Adapter
        └── Product Pack / Test Execution
```

The document must distinguish:

- conversation session;
- workflow run;
- reasoning/model invocation;
- capability invocation;
- structured artifact revision;
- approval/authorization;
- external execution operation;
- execution receipt;
- provider-session usage observation.

These records may correlate, but must not be collapsed into one universal
state object.

## Open Conversation and Workflow Model

The UI must accept arbitrary user messages, not a fixed command pattern.

Examples:

```text
Story 12345 主要风险是什么？
总结一下这个 Story 的 discussion。
比较 12345 和 12346。
先分析这个 AC，不要生成 Test Case。
为刚才的 Story 生成 Test Scenarios。
检查现有 Test Plan 是否已经覆盖。
把已经批准的方案写入 ADO。
```

Define how a reasoning provider may return:

- a conversational answer;
- citations to retrieved evidence;
- requested read-only capability calls;
- a proposed workflow;
- one or more structured artifacts;
- proposed external actions;
- a request for clarification.

Workflow selection may be explicit or suggested from user intent. PMQA must
not silently convert an ambiguous conversation into an external write
workflow.

The Story-to-Test-Case flow is a reference happy path, not a global state
machine. Only structured artifacts and side-effecting actions require
deterministic lifecycle.

## Capability and Authority Model

Define a provider-neutral capability vocabulary with policy equivalent to:

```text
read_only
proposal_only
approval_required
external_write
```

For each level, specify:

- whether the reasoning provider may request it;
- whether PMQA may execute it automatically;
- whether human review is required;
- what audit evidence is recorded;
- whether the capability may access credentials;
- whether it may cause an external side effect.

The architecture must enforce:

- Copilot may reason and use approved read capabilities;
- Copilot never receives a direct unrestricted ADO writer;
- Story/Test Plan content cannot grant itself new capability;
- ADO writes are performed only by a deterministic PMQA executor from an
  exact approved action plan;
- destructive or broad bulk operations are either prohibited in the MVP or
  assigned a stricter future policy.

A prompt instruction such as “read only” is not a security boundary.

If company Copilot CLI cannot technically enforce a read-only ADO tool set,
the recommended design must use a PMQA-controlled read wrapper or direct
read adapter while preserving the same no-copy user experience.

## Structured Artifact and Approval Model

Define the minimum versioned concepts needed for:

- `StorySnapshot`;
- test-scenario proposal;
- coverage matrix;
- test inventory snapshot;
- test-case authoring plan;
- external operation plan;
- approval/authorization record;
- execution receipt.

Chat text is not the source of truth for an approved change. Every approval
must bind to:

- exact artifact/plan ID;
- version;
- canonical content digest;
- ADO organization/project scope;
- source Work Item and Test Case revisions;
- approving user identity;
- approval timestamp.

Any relevant edit creates a new revision and invalidates the prior approval.

Use “Authoring Plan” for what PMQA proposes to create/update and
“Authorization” for the human permission to execute it.

## Flagship Workflow Reference

Document the first reusable workflow:

```text
ado.story_test_authoring
```

Its happy path is:

```text
natural-language request containing Work Item ID
→ automatic ADO Story acquisition
→ structured Story snapshot displayed for confirmation
→ Story analysis and scenario proposal
→ human revision/approval
→ read-only Test Plan/Suite inventory
→ coverage matrix and Test Case Authoring Plan
→ human revision
→ final version-bound authorization
→ deterministic ADO execution
→ linkage verification and receipts
```

Do not make every stage mandatory for unrelated questions. A user may ask
only for a summary, risk analysis, comparison, test inventory, or another
read-only answer.

Define at least one small future/read-only workflow to prove the platform is
not UI-hard-coded to the flagship workflow, for example:

```text
ado.work_item_summary
```

No second workflow is implemented in Task 5D.0.

## ADO Story Acquisition

Define a provider-neutral source boundary such as:

```text
StorySource.load(connection_context, work_item_id) -> StorySnapshot
```

The MVP may use a `CopilotAdoStorySource` that lets Copilot invoke the user's
existing ADO/Azure CLI read capability. Preserve a future
`DirectAdoApiStorySource` without changing the conversation or artifact
contracts.

The snapshot design must address:

- organization and project context;
- Work Item ID, type, and revision;
- title, description, acceptance criteria, state, area/iteration, tags, and
  relations;
- discussion/comments, pagination, and completeness;
- captured timestamp;
- HTML sanitization;
- missing or inaccessible fields;
- bounded content;
- attachments and links as explicit supported/deferred policy.

The user confirmation verifies the correct item/context. It is not permission
to modify ADO.

## ADO Write and Recovery Boundary

Define, without implementing:

- separate read and write interfaces;
- permission preflight;
- revision re-read before execution;
- optimistic concurrency behavior;
- stable operation IDs and idempotency/correlation;
- creation, update, suite membership, and Story linkage operations;
- deterministic ordering;
- partial success;
- resume versus retry policy;
- verification receipts;
- why automatic multi-operation rollback is not promised.

The architecture must never report a multi-operation plan as successful when
only part of it completed.

## Identity, Authentication, and Local Web Security

Document the desired MVP behavior without choosing an unverified company
authentication mechanism:

- the local backend runs as the QA user;
- the Web server binds only to loopback;
- the UI displays connected ADO user, organization, project, Copilot identity,
  and current read/write mode;
- PMQA does not accept or persist raw passwords, PATs, GitHub tokens, Azure
  tokens, cookies, or browser storage state in conversation/artifact/usage
  records;
- official credential stores or delegated login flows remain authoritative;
- expired login, logout, reconnect, and wrong-account detection are explicit;
- CSRF, Origin/CORS, XSS/ADO HTML, local session token, log redaction, and
  browser-to-local-command boundaries are addressed.

The document must list as company-environment validation items, not assumed
facts:

- exact ADO delegated authentication mechanism;
- whether Azure CLI identity can obtain the required ADO access safely;
- Copilot CLI structured output;
- Copilot CLI tool allowlisting/approval behavior;
- provider-session usage output and stability.

## Untrusted Content and Prompt Injection

Treat ADO title, description, acceptance criteria, comments, HTML, attachment
names, links, and Test Case text as untrusted data.

Define:

- data/instruction separation;
- bounded canonical input to reasoning;
- HTML sanitization;
- tool-call validation;
- why retrieved content cannot expand capability or approval;
- marker-safe errors and logs;
- prompt-injection and malicious-content test strategy.

Automatic retrieval does not make ADO content trusted.

## Usage and AIC Observability

Map Task 5C usage contracts into the future platform without changing them.

Distinguish:

- exact model invocation usage;
- Copilot/CLI provider-session AIC usage;
- estimated cost;
- provider-reported cost;
- subscription-included usage;
- unavailable evidence.

If Copilot exposes only a whole-session usage total, do not allocate it
across model invocations. Define a separate provider-session observation or
explicitly defer that contract. Do not invent tokens or dollar cost.

Show how future UI may present usage by conversation, workflow run, operation,
provider/model, and outcome while preserving the Task 5C bounded-selection
limitation.

## UI Product Architecture

Recommend a local Web implementation shape, but do not add dependencies or
code.

Evaluate and make one explicit recommendation for:

- browser frontend technology;
- local Python Web/API technology;
- versioned UI/read-model boundary;
- serving packaged frontend assets;
- startup experience such as future `pmqa web`;
- local session persistence;
- test strategy, including strict TypeScript and Playwright where applicable;
- future migration from local single-user to centrally hosted team service.

The expected interaction is:

```text
Conversation pane + Structured Workspace
```

The structured workspace should render Story snapshots, citations, scenarios,
coverage, Test Case diffs, approvals, connection state, receipts, and usage.
It must not directly import LangGraph internals or read repository JSON files.

## Required Decisions and Open Questions

The architecture must recommend defaults while clearly recording questions
that require company-side validation or Human decision, including:

- initial ADO organization/project/process template;
- first sandbox Test Plan/Suite for write validation;
- whether discussion and attachments may be sent to Copilot;
- local session/artifact retention;
- supported Work Item types and custom fields;
- exact Copilot CLI and ADO authentication/tool behavior;
- whether destructive/bulk operations remain disabled in the MVP.

Do not block safe architecture analysis on these answers. Mark the exact
implementation checkpoint that must stop for each unresolved decision.

## Required Phased Delivery Plan

Define a recommended sequence equivalent to:

1. **5D.1 — Local Web Foundation and Session State**
2. **5D.2 — Conversational ADO Read / Story Acquisition**
3. **5D.3 — Reasoning, Structured Artifacts, and Scenario Review**
4. **5D.4 — Test Inventory and Authoring Plan**
5. **5D.5 — Version-Bound Authorization and Deterministic ADO Write**
6. **5D.6 — Usage, Audit, Security, Packaging, and End-to-End Hardening**

For each phase, state its vertical outcome, dependencies, deferred work, and
recommended review depth.

Do not begin any phase in Task 5D.0.

## Required Deliverables

Create:

- `docs/architecture/conversational-workflow-platform.md`

Update only as needed:

- `README.md`;
- `docs/Roadmap.md`;
- `docs/architecture.md`;
- `agent-handoff/coder-report.md`.

The architecture document must contain:

- product definition and user journey;
- logical component and dependency diagram;
- existing-contract reuse map;
- record/correlation map;
- capability/authority matrix;
- conversation versus workflow semantics;
- artifact/approval/execution lifecycle;
- flagship workflow happy path;
- ADO read/write and recovery boundaries;
- identity/security/prompt-injection boundary;
- usage/AIC integration;
- UI/deployment recommendation;
- open decisions and implementation stop points;
- phased delivery plan.

## Allowed Changes

- `docs/architecture/conversational-workflow-platform.md`;
- `README.md`;
- `docs/Roadmap.md`;
- `docs/architecture.md`;
- `agent-handoff/coder-report.md`.

Do not modify:

- production code;
- tests, fixtures, configuration, schemas, packaging, or dependencies;
- any other architecture document;
- `agent-handoff/README.md`;
- `agent-handoff/current-task.md`;
- `agent-handoff/reviewer-report.md`;
- `agent-handoff/architect-review.md`.

Use one documentation implementation commit and one report-only Coder
handoff commit.

## Out of Scope

Do not implement:

- Web frontend or backend;
- `pmqa web`;
- conversation or workflow runtime;
- capability registry/gateway;
- artifact, approval, session, or receipt contracts;
- ADO or Copilot adapter;
- authentication;
- ADO reads or writes;
- new LangGraph nodes;
- Usage contract changes;
- new dependencies;
- Task 5D.1 or later;
- Task 5B, Task 6, or Task 7;
- PR creation or merge.

## Validation Commands

Run and report:

```bash
git diff --check
git status --short
```

Also run:

- repository Markdown relative-link validation;
- stale-status search for Task 5C.7 and Task 5D.0;
- `.venv/bin/python -m pytest -q`;
- `.venv/bin/python -m pytest products/demo/generated_tests -q`.

The new document must contain no company URL, organization/project name,
Work Item ID, selector, credential, private code, or internal metadata.

## Acceptance Criteria

- PMQA is defined as a multi-workflow conversational QA platform;
- arbitrary conversation and structured workflows coexist without a fixed
  global wizard;
- the first Story authoring flow is a registered flagship workflow, not UI
  architecture;
- reasoning, capability, approval, and deterministic external execution
  boundaries are explicit;
- Copilot-mediated automatic ADO read preserves no-copy UX without granting
  unrestricted write authority;
- ADO content remains untrusted and cannot elevate capability;
- artifact revision, digest-bound authorization, partial execution, and
  receipts are defined;
- local-first identity and Web security are addressed without inventing
  company authentication facts;
- exact invocation usage and provider-session AIC usage are not conflated;
- existing Task 4/5/5A/5C contracts are reused rather than duplicated;
- the UI technology recommendation and hosted migration path are explicit;
- implementation phases are independently reviewable;
- only allowed documentation and Coder report files change.

## Required Coder Handoff

Replace `agent-handoff/coder-report.md` with the complete Task 5D.0 Attempt 1
report. Include:

- Task/Attempt, branch, and exact Git-derived starting HEAD;
- documentation implementation commit;
- changed files;
- recommended product, logical, authority, UI, and deployment architecture;
- existing-contract reuse decisions;
- unresolved Human/company-environment decisions and stop points;
- phased delivery plan;
- validation results;
- scope confirmation;
- one recommended review depth (`Light`, `Standard`, or `Deep`);
- one-sentence reason;
- 3–6 suggested Reviewer focus areas;
- Human Summary using the mandatory routing and one-sentence Handoff Note.

Do not include the report commit's own SHA. The Independent Reviewer derives
it from Git.
