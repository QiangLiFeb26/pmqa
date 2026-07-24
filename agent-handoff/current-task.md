# Current Task

Owner: Architect

Task: PMQA Task 5C.7 — Deterministic Usage Summary Contracts and Pure Aggregation

Task ID: `PMQA-5C.7`

Attempt: `1`

Status: Ready for Coder

Branch: `agent/task-5c-1-canonical-run-contract`

Architect-reviewed baseline Reviewer HEAD:
`a258ba59b7fdd1edb6e01ab738ea9203610e954b`

Coder starting HEAD: derive and record the latest pushed branch commit that
contains this task publication before changing implementation files.

Repository Markdown and Git history are authoritative. Chat summaries are
informational only.

## Task Objective

Add a provider-neutral, deterministic, immutable summary contract and pure
aggregation service for canonical `AIInvocationRecord` values.

This checkpoint must make zero distinct from unavailable, keep reported and
estimated cost separate, preserve currency and pricing provenance, expose
retry/fallback/status counts, and provide stable provider/model grouping
without reading storage, launching providers, calculating prices, or changing
existing records.

The result is the domain/service layer needed before a later repository-backed
CLI summary. It is not itself a CLI or workflow integration.

## Background

Task 5C.4 defined provider-neutral usage, cost, and pricing evidence. Task
5C.5 added exactly-once invocation collection. Task 5C.6 added append-only
local persistence and deterministic retrieval.

The current architecture can record and retrieve exact invocation evidence,
but it does not yet derive a bounded, canonical view suitable for:

- one PMQA session;
- one PMQA run;
- provider/model comparison;
- status, retry, fallback, duration, token, and cost reporting;
- future cost-per-success and cache-benefit analysis.

Aggregation must not manufacture missing evidence. A numeric zero is an
observed value. An absent token field remains absent even when other records
provide that field. Provider-reported cost must never be combined with
estimated cost, subscription inclusion must never become a zero-dollar amount,
and different currencies must never be summed together.

## Scope

- Add immutable summary contracts under `pmqa.usage`.
- Add one provider-neutral pure aggregation boundary and deterministic default
  implementation.
- Aggregate only caller-supplied canonical `AIInvocationRecord` snapshots.
- Support session and run scope.
- Add deterministic provider/model groups.
- Add stable status, retry/fallback, duration, token-field, and cost buckets.
- Add strict correlation, duplicate, overflow, canonical-round-trip, and
  safe-error behavior.
- Update focused documentation and Task 5C status text.
- Replace `agent-handoff/coder-report.md` with the Task 5C.7 report.

Do not connect the aggregator to the repository or any workflow in this task.

## Required Public Design

Place the implementation in a focused module such as:

```text
pmqa/usage/summary.py
```

Export the approved public API from `pmqa.usage`, but do not export it from
top-level `pmqa`.

Use names equivalent in meaning to:

```python
class UsageSummaryScope(str, Enum):
    SESSION = "session"
    RUN = "run"


class UsageAggregator(Protocol):
    def summarize(
        self,
        records: tuple[AIInvocationRecord, ...],
        *,
        scope: UsageSummaryScope,
        scope_id: str,
    ) -> UsageSummary:
        ...


class DefaultUsageAggregator:
    ...
```

Exact class names may vary only if the Coder documents a materially clearer
fit with the existing repository style. Do not add asynchronous APIs,
callbacks, dependency injection containers, or provider-specific concepts.

## Required Summary Semantics

The canonical top-level summary must contain:

- schema version;
- scope type and canonical scope ID;
- total invocation count;
- succeeded, failed, and cancelled counts;
- retry invocation count;
- fallback invocation count;
- exact total duration in milliseconds;
- one deterministic token-field summary for every `TokenField`;
- deterministic cost buckets;
- deterministic provider/model groups.

Do not add a generated timestamp. The summary must be a pure deterministic
function of its records and explicit scope.

### Status and predecessor counts

- Status counts must add exactly to invocation count.
- `retry_invocation_count` counts records with
  `retry_of_invocation_id is not None`.
- `fallback_invocation_count` counts records with
  `fallback_from_invocation_id is not None`.
- Do not infer retries from `attempt_number` alone.
- Do not require predecessor records to be present in the selected input;
  cross-record lineage validation remains outside this checkpoint.

### Duration

- Sum the exact canonical `duration_ms` values.
- Do not derive duration from wall timestamps.
- Enforce an explicit bounded aggregate maximum.
- Overflow must fail through a fixed safe aggregation error; it must not wrap,
  clamp, convert to float, or silently truncate.

### Token-field summaries

For each `TokenField`, preserve at least:

- the field identity;
- total value, which is optional;
- number of invocations with an observed value;
- number of invocations where the field is unavailable.

Required invariant:

```text
observed_invocation_count + unavailable_invocation_count
    == total invocation count
```

Required meaning:

- total is `None` exactly when no invocation observed that field;
- total is numeric zero when one or more invocations observed only zero;
- a partial total may exist while `unavailable_invocation_count > 0`;
- the summary must not claim that a partial total covers unavailable records;
- unavailable reasons remain in invocation evidence and are not guessed or
  collapsed into a fake numeric value.

Token totals must use bounded integer arithmetic and fail safely on overflow.

### Cost buckets

Never combine incompatible cost evidence.

Group monetary evidence by the complete compatible identity needed to avoid
mixing meanings:

- `cost_type`;
- currency;
- pricing source ID;
- pricing version;
- pricing effective timestamp.

Provider-reported and estimated amounts therefore remain separate. Estimated
amounts with different pricing provenance remain separate. Different
currencies remain separate.

Group non-monetary evidence separately:

- subscription-included evidence;
- unavailable evidence, including its exact bounded unavailable reason.

Each cost bucket must contain:

- exact evidence identity/provenance fields;
- invocation count;
- amount only for monetary buckets.

Required behavior:

- monetary zero remains an observed amount of zero;
- subscription-included does not carry amount or currency and is not treated
  as monetary zero;
- unavailable does not carry amount or currency;
- Decimal arithmetic remains exact;
- canonical decimal bounds remain enforced;
- no conversion to float;
- bucket ordering is deterministic and independent of input order.

### Provider/model groups

Create one deterministic group for each exact provider/model identity:

- canonical provider;
- model when known;
- exact model-unavailable reason when model is unavailable.

Each group must expose the same status, retry/fallback, duration, token-field,
and cost-bucket semantics as the top-level aggregate, without recursively
nesting further provider/model groups.

Ordering must be deterministic and independent of input order. A known model
and unavailable-model evidence must never be merged.

### Empty input

An empty tuple is valid when the explicit scope is valid.

The empty summary must contain:

- invocation count and all status/retry/fallback/duration counts equal to
  numeric zero;
- every token field exactly once with `total=None`, observed count `0`, and
  unavailable count `0`;
- no cost buckets;
- no provider/model groups.

This is an empty selected set, not fabricated unavailable invocation evidence.

## Correlation and Input Boundary

The aggregator must:

- require a built-in tuple of exact `AIInvocationRecord` instances;
- independently reconstruct every record before aggregation;
- never retain caller-owned records or containers;
- reject duplicate invocation IDs;
- validate the explicit scope and `scope_id` through canonical existing
  identifier policy;
- for session scope, require every record's `session_id == scope_id`;
- for run scope, require every record's `run_id == scope_id`;
- reject mixed or mismatched correlation rather than silently filtering;
- accept records in any input order and produce byte-equivalent canonical
  output;
- propagate `MemoryError`, `KeyboardInterrupt`, `SystemExit`, and
  `GeneratorExit` with exact identity.

Do not verify repository completeness, predecessor existence, run existence,
session existence, or runner-invocation existence. The input tuple is an
explicit bounded selection supplied by the caller.

Define and enforce a conservative maximum number of records per aggregation.
Reject excess input before performing aggregation. Do not silently truncate.

## Error Boundary

Add one fixed provider-neutral aggregation exception and a small bounded enum,
for example:

```text
invalid_request
invalid_record
correlation_mismatch
duplicate_invocation
aggregate_overflow
```

Exact vocabulary may be consolidated if the distinctions remain deterministic
and tests demonstrate them.

Expected failures must:

- expose only fixed bounded messages;
- suppress cause and context;
- never expose identifiers, provider/model names, amounts, paths, caller
  payloads, runtime object representations, or injected markers.

Do not reuse repository errors for a pure aggregation failure.

## Canonical Contract Requirements

All public summary records must follow existing usage/run contract style:

- Pydantic v2;
- strict and frozen;
- `extra="forbid"`;
- explicit schema version;
- deeply immutable tuples and independently reconstructed nested records;
- canonical plain-JSON `to_dict()` / `from_dict()` round trips;
- `model_copy(update=...)` full revalidation;
- unknown fields and coercion rejected;
- caller-owned containers not retained;
- complete tree depth/item/string bounds;
- stable field order and deterministic collection ordering;
- fixed safe reconstruction errors.

Do not add a new prohibited/sensitive-key list. Reuse the existing canonical
contract/security boundary.

## Import and Dependency Isolation

Importing `pmqa.usage` or the new summary module must not:

- read usage repository files;
- create directories or artifacts;
- inspect environment variables;
- load products, external Product Packs, Playwright, LangGraph, Supervisor,
  orchestration, provider SDKs, or reasoning providers;
- inspect installed distributions;
- launch subprocesses;
- perform pricing lookup;
- register global state.

Add no runtime dependency.

## Required Tests

At minimum cover:

- exact public field sets and enum values;
- empty summary semantics;
- one complete zero-valued invocation;
- one fully unavailable invocation;
- mixed observed/unavailable token fields with partial totals;
- success, failure, and cancellation counts;
- retry and fallback counts;
- exact duration aggregation;
- duration and token overflow rejection;
- provider-reported and estimated costs remain separate;
- different currencies remain separate;
- estimated pricing versions/effective timestamps remain separate;
- monetary zero versus subscription-included versus unavailable;
- exact Decimal summation without float conversion;
- provider/model group separation and deterministic ordering;
- unavailable model grouping by reason;
- input-order-independent canonical output;
- duplicate invocation IDs;
- session and run correlation mismatch;
- non-tuple, subclass, malformed, mutated, or excessive record input;
- independent snapshots and caller mutation after summary construction;
- canonical JSON round trips;
- revalidated copies;
- unknown/runtime/prohibited data rejection;
- marker-safe fixed errors with no cause/context;
- exact propagation of resource/control-flow exceptions;
- import isolation;
- real PMQA wheel packaging if the new module is not already covered by the
  package allowlist;
- existing collector/repository/contracts/pricing regressions.

New tests remain offline and invoke no provider, model, CLI, network, browser,
Node.js, or external Product Pack.

## Documentation

Update only the focused status and architecture surfaces needed to record:

- Task 5C.6 passed architecture review;
- Task 5C.7 adds summary contracts and pure aggregation;
- summaries operate on an explicit caller-supplied bounded selection;
- zero, partial, unavailable, reported, estimated, subscription-included, and
  currency/provenance meanings remain distinct;
- repository access, completeness, CLI display, outcome metrics, price
  calculation, and provider integration remain deferred;
- Task 5C remains in progress and unmerged.

Expected documentation surfaces:

- `README.md`;
- `docs/Roadmap.md`;
- `docs/architecture.md`;
- `docs/architecture/usage-cost-contracts.md`.

Do not change Task 5A/5B/6/7 status except where an existing sentence needs
to preserve their unchanged state.

## Allowed Changes

- `pmqa/usage/summary.py`;
- `pmqa/usage/__init__.py`;
- focused summary tests, preferably `tests/test_usage_summary.py`;
- minimal additive `tests/test_usage_imports.py`;
- minimal additive `tests/test_packaging.py` only if required by the real
  wheel allowlist;
- the four focused documentation surfaces listed above;
- `agent-handoff/coder-report.md`.

Do not modify:

- `agent-handoff/README.md`;
- `agent-handoff/current-task.md`;
- `agent-handoff/reviewer-report.md`;
- `agent-handoff/architect-review.md`;
- `pmqa/usage/contracts.py`;
- `pmqa/usage/pricing.py`;
- `pmqa/usage/collector.py`;
- `pmqa/usage/repository.py`;
- RunRecord, Runner, Application Service, WorkflowState, LangGraph,
  Supervisor, Task 5, or Product Pack behavior.

Use one focused implementation commit and one report-only Coder handoff
commit. Do not amend Task 5C.6.

## Out of Scope

Do not add:

- repository reads or writes in the aggregator;
- pagination or repository completeness claims;
- CLI commands or terminal rendering;
- outcome-metric joining;
- pricing lookup or cost calculation;
- a built-in pricing table;
- provider/CLI parsing or adapters;
- Copilot, Codex, OpenAI, Azure OpenAI, or other SDK integration;
- automatic collector persistence;
- workflow/Application Service/Runner integration;
- prompts, responses, raw terminal output, or provider metadata;
- retry/fallback execution policy;
- retention, deletion, compaction, migration, database, background work, or
  remote storage;
- budgets, optimization, model routing, or quality scoring;
- new runtime dependencies;
- Task 5B, Task 6, or Task 7;
- PR creation or merge.

## Validation Commands

Run and report:

```bash
.venv/bin/python -m pytest tests/test_usage_summary.py tests/test_usage_repository.py tests/test_usage_collector.py tests/test_usage_contracts.py tests/test_usage_pricing.py tests/test_usage_imports.py -q
.venv/bin/python -m pytest tests/test_run_contracts.py tests/test_runner_contracts.py tests/test_application_contracts.py tests/test_application_service.py tests/test_boundary_policy.py tests/test_packaging.py -q
.venv/bin/python -m pytest tests/test_workflow_runtime.py tests/test_workflow_reducer.py tests/test_supervisor_policy.py tests/test_langgraph_workflow.py -q
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest products/demo/generated_tests -q
.venv/bin/python -m compileall -q pmqa products
git diff --check
git status --short
```

Use an isolated bytecode cache for compileall. New tests must remain offline.

## Acceptance Criteria

- summary contracts are strict, immutable, canonical, and provider-neutral;
- empty, zero, partial, and unavailable evidence remain semantically distinct;
- reported, estimated, subscription-included, unavailable, currency, and
  pricing provenance are never conflated;
- status, retry/fallback, duration, token, and cost aggregation is exact and
  bounded;
- provider/model groups are deterministic and non-recursive;
- input order cannot change canonical output;
- duplicate or mismatched records fail safely rather than being filtered;
- no storage, pricing, provider, workflow, or CLI side effect is added;
- import and packaging isolation remain intact;
- existing usage, application, Task 4, Task 5, and Product Pack behavior
  remains unchanged;
- only allowed files change.

## Expected Deliverables

- immutable usage summary contracts;
- pure provider-neutral aggregation protocol and default implementation;
- focused adversarial and deterministic tests;
- focused documentation updates;
- one implementation commit;
- one report-only Coder handoff commit;
- clean synchronized branch;
- no PR or merge.

## Required Coder Handoff

Replace `agent-handoff/coder-report.md` with the complete Task 5C.7 Attempt 1
report. Include:

- Task/Attempt, branch, and exact Git-derived starting HEAD;
- implementation commit;
- changed files;
- exact public contracts and aggregation API;
- empty/zero/unavailable, token, cost, grouping, and correlation semantics;
- validation results;
- remaining risks and scope confirmation;
- one recommended review depth (`Light`, `Standard`, or `Deep`);
- one-sentence reason for that recommendation;
- 3–6 suggested Reviewer focus areas;
- Human Summary using the mandatory routing and one-sentence Handoff Note.

Do not include the report commit's own SHA. The Independent Reviewer derives
it from Git.
