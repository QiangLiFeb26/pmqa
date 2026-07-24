# Provider-Neutral AI Usage and Cost Contracts

## Status

Task 5C.1–5C.3 have passed architecture review. Task 5C.4 is **Ready for
architecture review**. Task 5C remains in progress and unmerged. Task 5B,
Task 6, and Task 7 have not started.

Task 5C.4 is a contracts and pricing-boundary checkpoint, not the Usage
Tracking MVP.

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

## Deferred Usage Tracking Work

Later checkpoints may add explicit collectors, provider/CLI parsers, pricing
calculation, persistence, run/session aggregation, CLI summaries, budgets, and
optimization. None exists in Task 5C.4, and no real provider integration or
provider-specific evidence is added.
