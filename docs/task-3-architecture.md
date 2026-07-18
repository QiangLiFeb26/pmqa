# Task 3 Reasoning Architecture

Task 3 establishes PMQA's provider-independent reasoning boundary. It does not
implement product exploration, Patrol, LangGraph orchestration, or Task 4
workflow behavior.

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

The scrubber alone owns sanitization. Prompt construction accepts only the
resulting validated request and never retains raw pre-scrub input. Providers
own reasoning and transport: terminal and subprocess details do not enter the
Prompt Package or execution service. Canonical validators enforce request and
response schemas. The trace store owns persistence; the execution service only
sequences these components.

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
hash, scrubbed-output hash, and execution mode without storing raw input.

## Validation

Run the complete offline Task 3 and framework suite with:

```bash
pytest -q
```

Run the end-to-end offline demonstration with:

```bash
pmqa task3-demo --database /tmp/pmqa-task3.sqlite3
```

Current limitations are intentional: there is no retry or fallback policy,
prompt repository, replay engine, provider-selection heuristic, failure-trace
schema, multi-agent orchestration, or Task 4 integration.
