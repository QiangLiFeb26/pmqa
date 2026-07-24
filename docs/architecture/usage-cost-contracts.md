# Provider-Neutral AI Usage and Cost Contracts

## Status

Task 5C.1–5C.5 have passed architecture review. Task 5C.6 is **Ready for
architecture review**. Task 5C remains in progress and unmerged. Task 5B,
Task 6, and Task 7 have not started.

Task 5C.5 adds lifecycle collection to the Task 5C.4 contracts. Task 5C.6 adds
explicit local persistence and deterministic retrieval. Neither checkpoint is
the complete Usage Tracking MVP.

## Relationship to Runs and Runner Attempts

`pmqa.usage` models one AI/model invocation independently from a logical PMQA
runner attempt:

```text
PMQA session
  └── RunRecord
      ├── RunnerInvocationRecord
      └── zero or more AIInvocationRecord values
```

An `AIInvocationRecord` has its own identity, session and run correlation, an
optional `runner_invocation_id`, provider, model identity or fixed unavailable
reason, operation, terminal lifecycle, timing, retry/fallback evidence, usage,
cost, and a bounded safe error classification.

This is local correlation only. A future repository or application service
will verify that referenced sessions, runs, runner invocations, and predecessor
AI invocations exist. The contract does not duplicate or modify `RunRecord`,
`RunnerInvocationRecord`, `OutcomeMetrics`, reasoning `TraceRecord`, or
LangGraph `WorkflowState`.

## Token-Usage Evidence

`TokenUsageEvidence` keeps source and completeness explicit:

- `provider_reported`;
- `parsed_from_cli`;
- `estimated`; or
- `unavailable`.

Input, output, cached-input, and total token counts are independent optional
non-negative integers. Zero is a present observed value. Every absent field is
named in `unavailable_fields` with its own bounded
`EvidenceUnavailableReason`. An entirely unavailable record contains no
counts. A non-unavailable source contains at least one count.

The contract never calculates or repairs totals and makes no assumption about
whether cached input is included in another provider count. Partial provider
or parser evidence therefore remains partial.

## Cost Evidence

`CostEvidence` distinguishes:

- provider-reported monetary cost;
- estimated monetary cost;
- subscription-included execution; and
- unavailable cost.

Monetary amounts are bounded, non-negative canonical decimal strings in JSON
with explicit uppercase three-letter currency codes. Floats are not accepted.
A real amount of zero remains monetary evidence.

Estimated cost requires pricing source, version, and effective timestamp
evidence. Subscription-included and unavailable evidence carry no amount,
currency, or pricing evidence. Subscription inclusion does not assert
zero-dollar marginal cost. Unavailable cost requires a bounded fixed reason.
No amount, currency, or price is inferred.

## Pricing Lookup Boundary

`ModelPricing` is immutable versioned evidence for one provider/model and
effective interval. Input, output, and cached-input prices are independent
`PricingComponent` values with canonical decimal amounts and explicit
`per_token`, `per_1k_tokens`, or `per_1m_tokens` units. Missing components are
named explicitly with a bounded reason, and a pricing record must contain at
least one real component.

`PricingCatalog` is a provider-neutral read-only protocol:

```text
get_price(provider, model, effective_at) -> ModelPricing | None
```

`None` means no applicable price; it never means a zero price. The catalog
does not calculate or mutate invocation cost. Task 5C.4 includes no concrete
catalog, production price table, network lookup, configuration lookup, or
provider SDK.

## Canonical and Security Boundary

All public records are strict frozen Pydantic v2 contracts with forbidden
extra fields, hidden invalid inputs, canonical JSON round trips, UTC
timestamps, revalidated copying, bounded trees and identifiers, and
independently reconstructed nested records. Persisted reconstruction failures
use one fixed safe usage-contract error.

The contracts contain no prompts, responses, credentials, authentication
state, raw CLI output, commands, executable or repository paths, environment
mappings, DOM/browser evidence, provider clients, runtime controls, arbitrary
metadata, exception messages, or stack traces. They reuse the neutral Run
Contract validation boundary and shared security policy rather than defining a
new prohibited-key list.

Importing `pmqa.usage` performs no discovery, I/O, environment access, process
launch, provider loading, product loading, pricing lookup, or global
registration. The package is not exported from top-level `pmqa`.

## Invocation Lifecycle Collector

`AIInvocationCollector` is the provider-neutral synchronous runtime boundary.
`DefaultAIInvocationCollector` validates only canonical invocation correlation
and returns an opaque `AIInvocationHandle`. The handle is bound to its owning
collector, cannot be constructed or serialized as domain data, and exposes no
correlation or capability value. Its private active state contains only the
metadata and timing needed to construct a terminal record.

One handle produces at most one terminal `AIInvocationRecord` through success,
failure, or cancellation. Mandatory `TokenUsageEvidence` and `CostEvidence`
are independently reconstructed before any terminal clock is sampled. A
caller-validation failure therefore leaves the handle active for corrected
evidence. Ownership is consumed immediately before terminal clock sampling;
an expected clock, duration, or final-record failure after that point cannot
produce a later duplicate record. Resource and control-flow exceptions remain
authoritative.

The collector samples its injected wall and monotonic clocks once at start and
once at the applicable terminal stage. Wall samples must be timezone-aware and
become UTC timestamps. Monotonic samples must be exact finite integers or
floats. Duration uses only their non-negative difference and deterministic
decimal half-up rounding to milliseconds; wall-clock drift never replaces it.
Unavailable usage, cost, or model evidence remains explicitly unavailable and
is never guessed, clamped, converted to zero, or fabricated.

## Append-Only Local Repository

`UsageRepository` is a provider-neutral synchronous boundary for saving and
retrieving exact `AIInvocationRecord` values. `LocalJSONUsageRepository`
requires an explicit absolute operator-selected root; `artifacts/usage/` is an
example, not a hidden default or environment convention.

The local layout is:

```text
<root>/
  invocations/
    <sha256-of-canonical-invocation-id>.json
```

Each file is one sorted, compact UTF-8 canonical JSON object plus a trailing
newline. The lowercase SHA-256 filename prevents provider, model, session,
run, and invocation identifiers from entering repository-controlled paths.
No repository metadata is added to the domain record.

Saving reconstructs an independent canonical snapshot and enforces a bounded
serialized size before filesystem effects. A restrictive same-directory
temporary file is fully written and synchronized, then published with an
atomic hard-link no-replace operation. An existing target is always a
duplicate, whether its bytes are identical or different. Concurrent
repository instances therefore produce one publisher and duplicate losers;
no overwrite, `os.replace()`, unlink-and-retry, or check-then-overwrite path
exists. Safe publication reports unsupported filesystems explicitly. Private
temporary orphans are ignored and cleanup only unlinks a still-owned inode.
The current implementation fails closed with fixed
`unsupported_publication` when the platform cannot enforce POSIX restrictive
descriptor modes, hard-link no-replace publication, or mandatory file and
directory synchronization. Capabilities are captured before directory
creation; directory synchronization is also exercised before target
publication. Missing capabilities create no temporary, while a capability
that fails after `mkstemp` may leave only an empty, restrictive,
identifier-free private orphan if its inode cannot be identity-verified.
Post-publication directory-sync failure preserves the complete target and
returns the fixed persistence failure.

Reads consider only exact lowercase 64-hex `.json` entries. Matching symlinks,
non-regular entries, oversized files, invalid UTF-8, duplicate keys,
non-finite constants, malformed or noncanonical JSON, unknown fields,
contract failures, and filename/content digest mismatch are corruption.
Corrupt matching records fail `get` and the whole query rather than being
skipped. Empty queries remain distinct from operational read failures.

Session, run, and recent queries return immutable independently reconstructed
tuples. Ordering is newest `completed_at` first; equal timestamps use
ascending `invocation_id`. The boundary provides no update, overwrite,
delete, upsert, arbitrary filter, or raw dictionary method.

The design favors inspectable immutable per-invocation files and simple
no-replace concurrency for the trusted local-root checkpoint. JSONL would
require shared append framing and corruption recovery; a database would add
schema, locking, and migration policy not yet needed. The repository does not
claim protection from a malicious operating-system administrator.

Generic `StorageProvider` is not reused because it stores replaceable mutable
artifacts rather than immutable invocation history. Reasoning trace SQLite
storage is not reused because its prompt/response audit semantics, retention,
and trust boundary differ from data-minimized usage correlation.

The collector and repository remain explicitly decoupled. The collector
returns a canonical terminal record and never writes it automatically; the
caller explicitly chooses a repository and save point.

## Deferred Usage Tracking Work

Later checkpoints may add provider/CLI parsers, pricing calculation,
run/session aggregate models, summaries, CLI output, workflow integration,
retention, compaction, archival, migration, budgets, and optimization. Task
5C.6 adds none of those capabilities, and no real provider integration or
provider-specific evidence is added.
