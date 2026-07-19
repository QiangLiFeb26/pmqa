# Task 3 Reasoning Architecture

Task 3 establishes PMQA's provider-independent reasoning boundary. Its own
scope does not implement product exploration, Patrol, or workflow behavior.
Task 4 subsequently added workflow contracts, deterministic routing, runtime
execution, and a thin LangGraph adapter without changing this reasoning
boundary.

```text
Raw structured context
        ↓
ReasoningScrubber       removes prohibited fields and redacts sensitive strings
        ↓
ReasoningRequest        canonical provider-independent input contract
        ↓
PromptPackageBuilder    deterministic prompt, schema, hashes, and package ID
        ↓
ReasoningProvider       deterministic, manual Copilot, Copilot CLI, or future provider
        ↓
ReasoningResponse       validated structured decisions and correlation
        ↓
TraceStore              immutable request/response history and package correlation
```

## Responsibilities and trust boundary

The scrubber owns deterministic removal and redaction. The request validator is
the final prohibited-key gate, including when a caller directly constructs a
request without using the scrubber. Prompt construction validates its request
and never retains raw pre-scrub input. Providers own reasoning and transport:
terminal and subprocess details do not enter the Prompt Package or execution
service. Canonical validators enforce request and response schemas. The trace
store owns persistence; the execution service only sequences these components.

`PromptPackage` contains the package ID, request and prompt hashes, canonical
request JSON, canonical response schema JSON, rendered prompt text, provider,
request ID, and safe format metadata. Identical request content and provider
identity produce identical packages. Provider identity is part of the prompt
and package identity, while timestamps and transport configuration are not.

`ReasoningExecutionService.execute()` supports automated providers in one call.
Manual reasoning remains non-blocking through `prepare_manual()` and
`complete_manual()`; no terminal input occurs inside the service. A successful
exchange is persisted only after request, package, response, and provider
correlation pass validation. Trace metadata records the package ID, prompt
hash, scrubbed-output hash, execution mode, and secret-free scrub audit details
without storing raw input.

## Validation

Run the complete offline Task 3 and framework suite with:

```bash
pytest -q
```

Run the end-to-end offline demonstration with:

```bash
pmqa task3-demo --database /tmp/pmqa-task3.sqlite3
```

Current reasoning-layer limitations are intentional: there is no retry or
fallback policy, prompt repository, replay engine, provider-selection
heuristic, or failure-trace schema. Task 4 provides multi-agent orchestration
contracts and LangGraph assembly, but it does not yet compose this Task 3
reasoning service into that graph.
