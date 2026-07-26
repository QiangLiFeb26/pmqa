# Conversational Workflow Platform Architecture

## Status and scope

PMQA Task 5D.0 passed architecture review. Task 5D.1A implements the bounded
conversation session and retention foundation described here and is ready for
independent architecture review. It does not implement a Web application,
capability gateway, Azure DevOps (ADO) connector, authorization service,
external writer, or new workflow.

PMQA is:

> a conversational QA workflow platform, not a fixed wizard and not a
> cost-only dashboard.

The first flagship workflow is `ado.story_test_authoring`, but it is one
explicitly registered workflow on a reusable platform. General QA questions
and smaller read-only workflows remain first-class. Task 5D.1B, Task 5D.1C,
the company-side pilot, Task 6, and Task 7 have not started.

## Product definition

The reasoning provider is the brain: it interprets natural language, reasons
over bounded evidence, proposes artifacts and actions, and asks for
clarification. PMQA is the workbench, capability gateway, authority boundary,
durable memory, and deterministic executor.

PMQA, rather than the reasoning provider, owns:

- conversation and context boundaries;
- explicit workflow and capability registration;
- structured artifact identities and revision history;
- approval and authorization policy;
- connection identity and allowed scope;
- deterministic external-action execution;
- audit records, execution receipts, and usage evidence; and
- the distinction between suggestions and authorized external effects.

This ownership split permits Copilot or another provider to answer arbitrary
QA questions without allowing model output or retrieved product content to
grant authority.

## Local-first user journey

The initial user is one QA on a company-managed computer:

```text
start PMQA locally
→ open the loopback-only browser workbench
→ confirm the connected ADO and reasoning-provider identities and scope
→ ask an arbitrary QA question in natural language
→ allow approved read-only acquisition when context is needed
→ inspect citations and versioned structured artifacts beside the conversation
→ revise a proposal
→ explicitly authorize an exact external operation plan when a write is wanted
→ receive verified per-operation receipts and separate AI usage evidence
```

A message may reference a work item without requiring the QA to copy its
title, description, acceptance criteria, or discussion into PMQA. An approved
read source retrieves the item through the user's delegated identity and
returns a bounded `StorySnapshot`. The workbench displays that snapshot,
including source scope and revision, for confirmation.

Confirming the correct story is not authorization to modify ADO. Reviewing a
scenario proposal is not authorization to create test cases. Authorization is
a separate, version-bound act.

## Logical architecture and dependency direction

```text
Local Browser Workbench
        |
        v
Local PMQA Web/API Boundary
        |
        v
Conversation Application Service
        |-- Workflow Catalog
        |-- Capability Registry / Gateway
        |-- Structured Artifact Store
        |-- Approval / Authorization Service
        |-- Deterministic Action Executor
        |-- Connection Context
        `-- Usage / Audit
                |
                v
Provider and Product Adapters
        |-- Copilot Reasoning Adapter
        |-- ADO Read Adapter
        |-- ADO Write Adapter
        `-- Product Pack / Test Execution
```

The browser depends only on a versioned local API and UI read models. It does
not import LangGraph, open repository JSON files, use provider credentials, or
invoke local commands. The Web/API boundary validates identity, origin,
session, contract version, and request size before calling the Conversation
Application Service.

The application service coordinates records and policies but depends on
provider-neutral contracts. Adapters depend inward on those contracts.
Provider SDK objects, subprocesses, credentials, browsers, and ADO clients
stay behind adapter boundaries. Generic `pmqa` imports remain product- and
provider-lazy.

The future centrally hosted form preserves the API, application-service, and
adapter boundaries. It replaces the loopback identity and local repositories
with authenticated multi-user hosting, tenant-aware policy, and managed
storage; it does not move browser state or provider clients into domain
records.

## Existing-contract reuse and gaps

The platform extends existing boundaries instead of renaming them.

| Existing contract or service | Reuse | Remaining gap and future owner | Why it remains separate |
| --- | --- | --- | --- |
| `WorkflowDefinition` and explicit `WorkflowRegistry` | Canonical workflow identity, version, schemas, preview metadata, runner capabilities, and exact local registration | A read-only Workflow Catalog projection and intent-to-workflow suggestion policy; UI-only view plus application policy | A catalog is presentation and selection, not another workflow definition or a LangGraph state field |
| `RunRequest`, `RunRecord`, `RunnerInvocationRecord`, and `ApplicationRunResult` | Correlate one selected workflow execution and its runner outcome | Conversation-to-run links and future multi-attempt orchestration; new correlation records/application service | A conversation can have zero or many runs, while a run remains a canonical execution record |
| `RunnerRegistry`, `PMQARunner`, and `PMQAApplicationService` | Explicit provider-neutral selection, bounded request/result validation, and one deterministic attempt | Conversation orchestration, authorization execution, retry policy, and progress delivery; new services/adapters | The current Application Service is deliberately single-attempt and does not own chat or authorization |
| Task 4 `WorkflowState`, reducer, Supervisor, and LangGraph adapter | Internal state, deterministic patch reduction, validated routing, and recovery for a registered graph | A runner adapter may invoke a graph for a selected workflow | Checkpoint state is not durable conversation, approval, artifact, receipt, or usage state |
| Task 5 SauceDemo composition and verified-artifact handoff | Example of real agents, independent validation, exact terminal correlation, persistence, and deterministic generation | General revisioned workspace artifacts and authorization-bound operation plans; new artifact and authorization contracts | `KnowledgeArtifact` is product knowledge, not a general story, plan, approval, or receipt envelope |
| `RunArtifact` and `StorageProvider` | Logical artifact references and existing replaceable artifact persistence where semantics fit | Immutable revision history, canonical digest lookup, optimistic writes, and artifact-type repositories | `RunArtifact` references output but does not contain revision, approval, source-revision, or authorization semantics |
| Task 5A manifest, explicit loader, Bridge Protocol v1, and bounded runner | Explicit Product Pack metadata and one bounded external product execution seam | Product-specific adapters chosen by explicit composition | A Product Pack does not become global capability discovery, a conversation store, or an ADO writer |
| `ReasoningProvider`, scrubber, prompt packages, and `TraceRecord` | Provider-neutral structured reasoning boundary, data minimization, and reasoning audit | A conversation-oriented provider request/response envelope and capability-call proposal vocabulary; new contracts/adapters | Existing reasoning models are product-knowledge shaped; a trace is an exchange audit, not conversation or authority |
| `AIInvocationCollector`, `UsageRepository`, and `UsageAggregator` | Exact invocation evidence, append-only storage, and bounded deterministic summaries | Correlation views and a separate provider-session observation if only session-wide AIC is available | Usage must not absorb conversation text, capability arguments, approvals, or provider-session totals |
| Shared security boundary policy | Prohibited-key normalization and fixed-safe serializable boundaries | Conversation/artifact-specific allowlists, size bounds, HTML policy, and log redaction | Runtime credentials and provider objects remain outside every serializable record |

No proposed component duplicates `WorkflowDefinition`, `RunRecord`,
`KnowledgeArtifact`, `RunArtifact`, `TraceRecord`, or `UsageSummary`. A new
contract is justified only where the existing semantics are incompatible.

## Records and correlation

The following records correlate through bounded identifiers but never collapse
into one universal object:

| Record | Meaning | Owns | Must not own |
| --- | --- | --- | --- |
| Conversation session | One user's local conversational context and retention boundary | Session identity, timestamps, connection-context reference, ordered turn IDs | Workflow checkpoint state, credentials, raw provider sessions |
| Conversation turn | One user message and one canonical provider/application response | Bounded text, citations, proposal references, clarification state | External authorization or execution success |
| Workflow run | One selected `WorkflowDefinition` execution | Existing `RunRequest`, `RunRecord`, and runner correlation | Chat history or model token details |
| Reasoning invocation | One model/provider exchange | Existing reasoning request/response, trace, and optional `AIInvocationRecord` | Capability authority or external receipt |
| Capability invocation | One validated call to one registered capability | Capability ID/version, policy level, bounded arguments, evidence/result reference, requester and timing | Raw credentials, unrestricted clients, approval inheritance |
| Structured artifact revision | One immutable semantic revision | Artifact ID/type, revision, schema, canonical content digest, source evidence/revisions, creator and timestamp | Mutable chat text or runtime handles |
| Approval/authorization | Human permission for one exact plan revision | Artifact/plan ID, version, digest, external scope, source revisions, approver identity and timestamp | A general permission token or mutable plan |
| External execution operation | One deterministic step from an authorized plan | Stable operation ID, order, exact arguments, expected revisions, idempotency correlation | Model-generated free-form commands |
| Execution receipt | Verified outcome of one operation or plan | Operation ID, status, observed external IDs/revisions, verification evidence, safe errors and timestamps | Claim of atomic rollback or hidden partial success |
| Provider-session usage observation | Optional whole-session provider evidence | Provider session correlation, source, interval, exact reported aggregate or unavailable reason | Invented per-invocation allocation |

Recommended correlation is directional and explicit:

```text
conversation session
  |-- conversation turns
  |     |-- zero or more reasoning invocations
  |     |-- zero or more capability invocations
  |     `-- zero or more artifact revisions
  |-- zero or more workflow runs
  |     |-- runner invocations
  |     `-- zero or more AI invocations
  `-- authorizations
        `-- external operation plan
              `-- operation receipts
```

An identifier link does not transfer authority. A turn that references an
authorization cannot change its digest or scope. A receipt can correlate to a
run and authorization but remains a distinct immutable fact.

## Open conversation and workflow semantics

The UI accepts arbitrary messages. It does not require a command prefix,
workflow ID, or wizard step. A provider-neutral conversation response may
contain any compatible combination of:

- a conversational answer;
- citations to retrieved evidence;
- requested read-only capability calls;
- a suggested registered workflow and bounded rationale;
- one or more proposed structured artifact revisions;
- proposed external actions that are not yet executable; or
- a request for clarification.

This requires a future versioned conversation-response contract. It is not an
extension of `WorkflowState` or the current product-knowledge-shaped
`ReasoningResponse`. The Conversation Application Service validates provider
output, resolves cited evidence and capability IDs, and decides what is
displayable, executable, or requires clarification.

Workflow selection can be:

- explicit, when the user chooses a catalog entry or names an unambiguous
  workflow;
- suggested, when the provider identifies a registered workflow matching the
  request; or
- absent, when a direct answer or isolated read capability is sufficient.

An ambiguous message never silently becomes an external-write workflow. The
service asks for clarification or presents a workflow suggestion. Only
structured artifacts and side-effecting actions have deterministic lifecycle;
ordinary conversation does not inherit the flagship workflow's state machine.

The small future workflow `ado.work_item_summary` proves the catalog and UI are
not hard-coded to authoring. It would acquire a bounded snapshot, produce a
cited read-only summary, and create no operation plan. Task 5D.0 defines but
does not implement it.

## Capability and authority model

Every future capability is explicitly registered with an identifier, version,
input/output schemas, connection requirements, scope constraints, policy
level, and implementation adapter. Provider output names a capability and
supplies bounded arguments; it never supplies an implementation, command,
credential, executable path, or policy.

| Policy level | Provider may request | Automatic PMQA execution | Human review | Audit evidence | Credential access | External side effect |
| --- | --- | --- | --- | --- | --- | --- |
| `read_only` | Yes | Only when explicitly registered, enabled for the current connection/scope, and allowed by session policy | Connection/scope confirmation is required; per-call review may be waived by policy | Requester, capability/version, bounded argument digest, scope, result/evidence reference, timing, outcome | Only the adapter may use delegated credentials | No |
| `proposal_only` | Yes | Yes, for local deterministic transformation of already authorized evidence | Review is required before any proposal can become an authorized external plan | Inputs, source revisions, artifact ID/version/digest, provider/algorithm provenance | No | No |
| `approval_required` | Yes, as a proposal | Only after explicit approval; suitable for sensitive reads, provider sharing, or costly execution that does not mutate the external product | Explicit review bound to exact request content and scope | Exact request identity/version/digest, scope, source revisions, approver and timestamp | Only the approved adapter may use delegated credentials after approval | No external product mutation |
| `external_write` | The provider may propose it but cannot invoke it | Never automatically in the MVP | Explicit final authorization is mandatory | Authorization, operation sequence, preflight, per-operation receipts, verification, partial outcome | Only the deterministic write adapter/executor may use delegated credentials | Yes |

Story text, Test Case text, comments, attachments, provider responses, and
prompt instructions cannot register capabilities, change policy levels,
expand connection scope, approve plans, or choose an executor. “Read only” in
a prompt is guidance, not enforcement.

Copilot never receives a direct unrestricted ADO writer. If a company Copilot
CLI cannot technically expose only the approved read tool set, the MVP uses a
PMQA-controlled read wrapper or `DirectAdoApiStorySource`. This preserves the
no-copy experience without granting Copilot write authority.

Destructive deletion, broad bulk edit, process-template administration, and
unbounded queries are prohibited in the MVP. A future policy would need a
separate architecture review rather than reuse ordinary `external_write`.

## Structured artifacts and authorization

### Minimum future concepts

The Structured Artifact Store needs immutable, versioned envelopes for:

- `StorySnapshot`;
- test-scenario proposal;
- coverage matrix;
- test-inventory snapshot;
- Test Case Authoring Plan;
- external operation plan;
- authorization record; and
- execution receipt.

Each artifact revision has a stable artifact ID, monotonically advancing
revision, schema identity/version, canonical content digest, source evidence
and external revision references, creator type, creation time, and supersedes
link. Canonical content is validated against its artifact schema before
persistence.

The existing `RunArtifact` can point from a run to a stored revision. It does
not replace the revision envelope. The existing `StorageProvider` may support
simple content persistence, but an append-only revision repository with
compare-and-append semantics is required for authoritative approval state.

### Lifecycle

```text
retrieved evidence
→ immutable source snapshot
→ proposed artifact revision
→ human edits create a new revision
→ Authoring Plan revision
→ final review
→ Authorization bound to exact plan revision and digest
→ deterministic operation execution
→ per-operation verification and receipts
```

Chat text is never the source of truth for an approved change. “Looks good” is
not executable unless the UI resolves it to a displayed plan and records an
authorization containing:

- exact artifact or plan ID;
- exact revision/version;
- canonical content digest;
- ADO organization and project scope identifiers;
- source Work Item and Test Case revisions;
- approving user identity; and
- approval timestamp.

Any relevant content, target scope, source revision, operation order, or
expected external revision change produces a new plan revision and invalidates
the earlier authorization. The user must authorize the new digest.

“Authoring Plan” always means what PMQA proposes to create or update.
“Authorization” always means the human permission to execute one exact plan.
The existing `WorkflowDefinition.approval_mode` remains workflow metadata and
the current Application Service supports only its no-approval execution path.
It is not a substitute for the future revision- and digest-bound
`Authorization` record or service.

## Flagship workflow: `ado.story_test_authoring`

The reference happy path is:

```text
natural-language request containing a work-item reference
→ approved automatic ADO Story acquisition
→ structured StorySnapshot displayed with scope and revision
→ user confirms the intended source item
→ story analysis and scenario proposal
→ human revision and scenario approval
→ read-only Test Plan/Suite inventory
→ coverage matrix and Test Case Authoring Plan
→ human revision
→ final digest- and revision-bound Authorization
→ deterministic ADO execution
→ linkage verification and per-operation receipts
```

The workflow definition declares schemas, preview steps, required runner
capabilities, and approval behavior through existing Task 5C contracts. A
future adapter validates workflow-specific requests/results. A runner may
compose deterministic services and, where appropriate, an internal Task 4
graph. LangGraph remains an implementation detail of that registered runner,
not the conversation or UI architecture.

The stages above are not mandatory for unrelated questions. A user can request
only a cited summary, risk analysis, comparison, scenario proposal, or current
test inventory. Those interactions end without an authorization or write.

## ADO Story acquisition boundary

The provider-neutral source seam is:

```text
StorySource.load(connection_context, work_item_reference) -> StorySnapshot
```

`connection_context` is a runtime-only, PMQA-owned reference to an explicitly
connected identity and allowed organization/project scope. It does not contain
raw tokens in the request or snapshot.

A future `CopilotAdoStorySource` may allow Copilot to use an approved,
technically constrained ADO/Azure CLI read capability. A
`DirectAdoApiStorySource` can implement the same contract. The conversation,
artifact, and workflow contracts do not change when the adapter changes.

`StorySnapshot` must capture:

- organization and project scope identifiers;
- work item identity, type, and exact revision;
- title, sanitized description, acceptance criteria, state, area, iteration,
  tags, and relations;
- bounded, ordered discussion/comment pages with page evidence and an explicit
  complete, truncated, unavailable, or inaccessible state;
- capture timestamp and source adapter identity/version;
- explicit missing/inaccessible field evidence; and
- content bounds and truncation markers.

ADO HTML is sanitized before display and before reasoning. The canonical
reasoning input preserves text/data boundaries and source-field labels.
Relation links are metadata only and are not automatically followed. The MVP
defers attachment content; attachment names and links remain untrusted metadata
and are not fetched or sent to a provider. Any later attachment support
requires content-type, size, malware, data-loss, and provider-sharing policy.

User confirmation establishes that the displayed item, scope, and revision are
the intended reasoning source. It grants no write permission.

## ADO write, concurrency, and recovery boundary

Read and write interfaces are separate. A read adapter cannot be cast or
configured into a writer. The write adapter is reachable only from the
Deterministic Action Executor after authorization validation.

Before execution, PMQA:

1. verifies the current connected identity and allowed organization/project;
2. performs permission and capability preflight;
3. reloads every relevant external revision;
4. rejects stale source or target revisions and invalidates authorization;
5. validates the exact authorized plan digest and operation sequence; and
6. establishes stable plan, execution, and operation correlation IDs.

The plan supports deterministic operations such as create Test Case, update
specified fields, add Suite membership, and link a Test Case to its Story.
Each operation contains exact target scope, bounded typed arguments, expected
revision where applicable, deterministic order, and a stable idempotency key.
It never contains free-form shell or CLI commands.

Optimistic concurrency is fail-closed: a revision mismatch produces a stale
plan outcome, no automatic overwrite, and a new proposal/review cycle.

Every operation receives its own receipt. A multi-operation plan is:

- `succeeded` only when all required operations execute and verify;
- `partially_succeeded` when at least one operation succeeded but the full plan
  did not;
- `failed` when no required operation succeeded; or
- `cancelled` when cancellation is authoritative and receipts preserve all
  prior effects.

PMQA never reports the whole plan as successful after partial completion.
Receipts distinguish created, updated, already-satisfied, failed, skipped, and
verification-failed operations.

Resume re-reads external state, verifies earlier receipts, skips only
operations proven satisfied, and continues remaining operations under a new
execution attempt linked to the same authorized plan. Retry reuses stable
operation correlation and must not duplicate a previously verified create.
Unknown outcomes stop for human review. Automatic multi-operation rollback is
not promised because external systems may not provide reversible or atomic
semantics; compensating actions require a new explicit plan and authorization.

## Identity, authentication, and local Web security

The MVP backend runs as the local QA user and binds only to a loopback address.
It never listens on all interfaces by default. The workbench continuously
shows:

- connected ADO user identity;
- selected organization and project scope;
- connected reasoning-provider identity;
- current read-only or write-enabled mode; and
- expired, disconnected, or wrong-account state.

PMQA does not accept or persist raw passwords, personal access tokens, GitHub
tokens, Azure tokens, cookies, or browser storage state in conversation,
artifact, Run, WorkflowState, trace, usage, receipt, or log records. Official
credential stores and delegated login flows remain authoritative. Runtime
adapters receive only a connection handle or obtain credentials through their
approved platform mechanism.

Logout clears PMQA's connection handle and local session authorization but
does not claim to revoke an upstream identity unless the official flow confirms
it. Reconnect revalidates identity and scope. Wrong-account detection blocks
capabilities until the user confirms or reconnects.

The local Web boundary requires:

- loopback-only binding and a fail-closed startup check;
- an unpredictable invocation-local session token delivered without URL query
  persistence;
- strict Origin and Host validation;
- CSRF protection on every state-changing request;
- no wildcard CORS and no cross-origin credential use;
- restrictive Content Security Policy and output encoding;
- server-side sanitization of ADO HTML plus safe frontend rendering;
- same-site, HTTP-only cookie policy if cookies are selected;
- bounded request bodies and schema-version validation;
- explicit browser-to-local-command allowlists rather than arbitrary command
  execution; and
- fixed-safe errors, structured redaction, and no raw adapter stderr in logs.

The loopback network boundary is not authentication by itself. The local
session token, origin enforcement, and CSRF policy defend against another page
driving the local service.

Company-environment validation must establish, rather than assume:

- the exact delegated ADO authentication mechanism;
- whether Azure CLI identity can safely obtain the required ADO scope;
- Copilot CLI structured-output behavior;
- Copilot CLI tool allowlisting and approval enforcement;
- provider-session usage/AIC output and stability; and
- logout, reconnect, and wrong-account signals for both providers.

## Untrusted content and prompt injection

ADO titles, descriptions, acceptance criteria, comments, HTML, attachment
names, links, Test Case text, and provider output are untrusted data.
Automatic retrieval does not change that classification.

PMQA enforces:

- explicit separation of system instructions, capability descriptions, user
  intent, and retrieved data blocks;
- canonical field labels, source revisions, bounded lengths, page counts, and
  deterministic truncation before reasoning;
- HTML sanitization before display and text extraction before provider input;
- schema validation and capability registry resolution for every proposed
  call;
- policy evaluation independent of provider rationale or retrieved content;
- version/digest verification independent of chat text;
- fixed-safe adapter errors and marker-safe logs; and
- no capability, credential, authorization, or executable object in model
  payloads.

Malicious content tests must include instruction-like ADO text, fake approval
language, capability-name injection, oversized comments, hostile HTML,
duplicate/ambiguous JSON fields, marker-bearing adapter errors, misleading
links, and stale-revision substitution. Tests assert that the content can be
quoted or summarized as data but cannot expand capability, alter scope,
authorize a plan, or reach a writer.

## Usage, AIC, and audit integration

Task 5C remains authoritative for exact model invocations:

- `AIInvocationRecord` stores observed invocation identity, lifecycle, token
  evidence, and cost evidence;
- `AIInvocationCollector` owns exactly-once lifecycle capture;
- `UsageRepository` stores immutable invocation evidence; and
- `UsageAggregator` summarizes one explicit bounded session or run selection.

The conversation UI may request bounded read models by conversation, workflow
run, external operation, provider/model, and outcome. Those views correlate
existing records; they do not mutate them or claim completeness beyond their
explicit selected invocation set.

The UI distinguishes:

- exact model invocation usage;
- parsed provider/CLI invocation evidence;
- provider-reported cost;
- estimated cost with pricing provenance;
- subscription-included evidence; and
- unavailable evidence.

If Copilot exposes only a whole provider-session AIC total, PMQA does not
allocate it across model calls. Task 5D should add a separate immutable
`ProviderSessionUsageObservation` only after the company environment proves
the semantics, or defer display. It records the provider session, observation
interval, exact source, aggregate evidence, and unavailable reason. It is not
an `AIInvocationRecord`, `UsageSummary`, conversation turn, or reasoning trace.

Capability audit records retain digests and safe classifications, not raw
credentials, provider stderr, or unrestricted payload dumps. External
operation receipts remain separate from usage so a successful write cannot be
inferred from token consumption.

## UI and deployment recommendation

### Recommended technology

Use a React + strict TypeScript frontend built with Vite, and a local Python
FastAPI application served by Uvicorn. This is a future implementation
recommendation; Task 5D.0 adds no dependency.

Reasons:

- React supports the conversation/workspace split and typed artifact-specific
  views without coupling the UI to workflow internals;
- strict TypeScript supports versioned API models and exhaustive lifecycle
  rendering;
- Vite produces static assets that can be built in CI and packaged into the
  PMQA wheel;
- FastAPI fits Python application services and explicit Pydantic boundary
  models; and
- Uvicorn supports a small loopback-only local process with a future path to a
  hosted ASGI deployment.

Use versioned REST/JSON commands and queries under a future `/api/v1`
boundary. Use server-sent events for one-way progress and read-model
invalidation; state-changing actions remain authenticated POST requests.
WebSockets are deferred until a demonstrated bidirectional requirement.

The future `pmqa web` command starts the loopback server, selects a free port,
creates a local session token, and opens the default browser only after
readiness and security checks. It does not accept provider credentials on the
command line. Packaged frontend assets are served from package resources, not
from a source checkout or arbitrary filesystem path.

### Workbench shape

```text
+---------------- Conversation ----------------+-- Structured Workspace --+
| messages, citations, clarification, intent   | connection identity       |
| workflow suggestions and progress            | StorySnapshot/revisions   |
| capability request status                    | scenarios and coverage    |
| safe errors                                  | Test Case diffs/plans     |
|                                               | authorization and receipts|
|                                               | usage/audit views         |
+-----------------------------------------------+---------------------------+
```

The workspace renders artifact schemas through registered UI components with a
safe generic JSON fallback. It receives API read models and never imports
LangGraph state, provider SDKs, repository implementations, or local JSON
files.

### Local persistence and migration

Recommend a separate local SQLite repository for conversation indexes,
artifact revisions, authorizations, and receipt correlation, with content
digests and explicit migrations. Reuse neither the reasoning trace database
nor the append-only usage-file repository: their content, retention,
concurrency, and corruption semantics differ. Large artifact bodies may use a
content-addressed local store referenced by logical keys.

Retention is an explicit user setting. The approved choices are session-only,
7, 30, or 90 days after the session's last authoritative activity; 30 days is
the default. Manual deletion is available immediately, and indefinite
retention is never selected silently. Task 5D.1A applies this decision to
conversation sessions and turns. Future structured artifact repositories must
reuse it, while reasoning traces, usage, and execution receipts retain
separate explicit policies.

A hosted migration replaces the local session principal with authenticated
users, adds tenant/scope isolation, managed secrets, server-side repositories,
authorization roles, and deployment controls. Provider and ADO adapters remain
behind the same capability boundary. Local credential inheritance is not
carried into a hosted service.

### Test strategy

Future implementation requires:

- Python contract and application-service unit tests;
- strict TypeScript type checking and component tests;
- API schema drift tests generated from one authoritative contract;
- offline fake reasoning, ADO read/write, clock, and repository adapters;
- Playwright browser tests for conversation, artifact revision, authorization,
  stale-plan rejection, CSRF/origin policy, partial receipts, and reconnect;
- prompt-injection and marker-leak adversarial tests;
- packaging tests that run from outside the source checkout; and
- opt-in company-environment read and sandbox-write tests with explicit gates.

Default tests remain offline and never use company identities or live systems.

## Decisions, validation questions, and stop points

Architecture analysis can proceed with safe defaults, but implementation must
stop at the listed checkpoint when evidence or a Human decision is missing.

| Decision or evidence | Recommended default | Required stop point |
| --- | --- | --- |
| Initial ADO organization, project, and process template | No compiled-in default; explicit connection selection | 5D.2 cannot enable live acquisition until scope and supported fields are validated |
| Sandbox Test Plan/Suite for write validation | Separate non-production sandbox selected by the Human | 5D.5 cannot enable any write adapter without an approved sandbox and identity |
| Discussion sharing with Copilot | Disabled until field-level policy is approved | 5D.3 must omit discussion if policy is unresolved |
| Attachment handling | Metadata only; no fetch or provider sharing | Any attachment-content checkpoint requires separate security review |
| Local session/artifact retention | Session-only, 7, 30, or 90 days; 30 days by default; immediate manual deletion | Decision approved for conversations in 5D.1A; later artifact storage must reuse it |
| Supported Work Item types and custom fields | Story-like type and an explicit allowlist after schema inspection | 5D.2 must fail safely on unvalidated types/fields |
| Copilot CLI structured output | Treat as unverified | 5D.3 cannot select the live adapter until bounded structured output is proven |
| Copilot CLI tool allowlisting/approval | Require technical enforcement, not prompt text | 5D.2 uses a PMQA read wrapper/direct adapter if enforcement is absent |
| ADO delegated authentication | Use an official delegated mechanism after validation | 5D.2 cannot access live ADO until identity, expiry, reconnect, and scope are proven |
| Destructive or broad bulk operations | Disabled | 5D.5 must reject them; enabling requires a future architecture checkpoint |
| Provider-session AIC semantics | Keep separate and unavailable until proven | 5D.6 cannot allocate or display inferred per-call totals |

No company name, endpoint, selector, credential, repository path, or private
field belongs in this public architecture.

## Phased delivery plan

### 5D.1 — Local Web Foundation and Session State

**Vertical outcome:** a loopback-only workbench with versioned API health,
local session identity, explicit workflow catalog read model, offline
conversation shell, and durable session/artifact repository seams.

**Dependencies:** existing `WorkflowDefinition`/`WorkflowRegistry`, Run
identifiers, shared security policy, approved UI/API technology and retention
decision.

**Deferred:** live reasoning, ADO, structured QA artifacts, authorization,
external writes, and usage UI.

**Recommended review depth:** Deep, because loopback authentication, CSRF,
origin enforcement, persistence, packaging, and browser/local-command
boundaries establish the platform trust root.

This phase is decomposed as follows:

- **5D.1A — Conversation Session and Retention Foundation:** strict sessions
  and turns, shared sensitive-text ingress, in-memory/session-only storage,
  durable revision-checked SQLite storage, retention purge, manual deletion,
  and a synchronous application service. Status: ready for architecture
  review.
- **5D.1B — Secure Loopback Web/API Boundary:** not started.
- **5D.1C — Browser Workbench, `pmqa web`, and Distribution Packaging:** not
  started.

5D.1A rejects malformed or recognizable sensitive text before sampling.
After static input validation, it samples one clock value for each attempted
authoritative create/start/terminalize/close/purge operation, and one new
identifier only for create or turn start. Reads do not extend retention.
Successful turn start,
turn completion/failure, and session close each advance the session revision,
`updated_at`, and durable expiration together. Session-only state uses only the
in-memory repository and makes no durable expiration claim.

### 5D.2 — Conversational ADO Read / Story Acquisition

**Vertical outcome:** arbitrary conversation can request one explicitly
registered read capability and display a bounded, sanitized, revisioned
`StorySnapshot` with citations and connection identity.

**Dependencies:** 5D.1, company validation of delegated ADO identity and
scope, read-only tool enforcement or direct read adapter, and supported-field
policy.

**Deferred:** scenario generation, authoring plans, write permissions,
attachments, and bulk traversal.

**Recommended review depth:** Deep, because delegated identity, untrusted ADO
content, pagination/completeness, HTML sanitization, and read-only enforcement
cross the first live company boundary.

### 5D.3 — Reasoning, Structured Artifacts, and Scenario Review

**Vertical outcome:** a provider-neutral conversation adapter produces cited
answers and immutable test-scenario revisions that users can review and edit
in the workspace.

**Dependencies:** 5D.2 evidence, existing reasoning boundary and trace store,
approved Copilot data-sharing policy, structured-output validation, and the
new artifact-revision repository.

**Deferred:** Test Plan inventory, authoring plans, external writes, and
provider-session usage allocation.

**Recommended review depth:** Deep, because provider output, prompt injection,
artifact provenance, revision semantics, and data-sharing policy converge.

### 5D.4 — Test Inventory and Authoring Plan

**Vertical outcome:** read-only Test Plan/Suite acquisition produces a
revisioned inventory, coverage matrix, and deterministic Test Case Authoring
Plan without executing it.

**Dependencies:** 5D.3 artifacts, explicit inventory capability, source and
target revision schemas, bounded pagination, and workflow registration for
`ado.story_test_authoring`.

**Deferred:** authorization, writes, rollback/compensation, and destructive
operations.

**Recommended review depth:** Standard, because it extends read-only evidence
and structured planning while preserving the no-write boundary.

### 5D.5 — Version-Bound Authorization and Deterministic ADO Write

**Vertical outcome:** a Human authorizes one exact plan digest; the
deterministic executor performs preflight, optimistic-concurrency checks,
ordered sandbox operations, verification, partial-result handling, and
receipts.

**Dependencies:** 5D.4, approved sandbox target, validated write identity and
permissions, immutable authorization contracts, idempotency design, and
explicitly disabled destructive/bulk operations.

**Deferred:** automatic rollback, production rollout, administrative actions,
and unattended bulk execution.

**Recommended review depth:** Deep, because this is the first external
side-effect boundary and must prove authority, identity, concurrency,
idempotency, partial success, and recovery.

### 5D.6 — Usage, Audit, Security, Packaging, and End-to-End Hardening

**Vertical outcome:** the local workbench correlates bounded Task 5C usage,
capability audit, runs, artifacts, authorizations, and receipts; packaged
installation passes offline and gated live end-to-end security tests.

**Dependencies:** 5D.1–5D.5, Task 5C usage contracts, proven provider-session
AIC semantics or explicit unavailability, retention decisions, and packaging
assets.

**Deferred:** centrally hosted multi-user deployment, Product Pack API v1
stabilization, budgets/optimization, Task 6, and Task 7.

**Recommended review depth:** Deep, because cross-record correlation,
redaction, retention, real packaging, and security regression closure determine
release readiness.

Only the bounded 5D.1A foundation has begun. No Web/API/frontend checkpoint or
later Task 5D phase has started.
