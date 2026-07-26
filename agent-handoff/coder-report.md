# Coder Report

Owner: Coder

Task: PMQA Task 5D.1B — Web Boundary Canonicalization and Token Containment

Task ID: `PMQA-5D.1B`

Attempt: `2`

Status: Ready for Independent Reviewer

## Branch and Git Correlation

Branch:

`agent/task-5c-1-canonical-run-contract`

Exact Git-derived Coder starting HEAD:

`6398a04df7e1cdfc723013036911bd01839a1b84`

Before implementation, local HEAD and
`origin/agent/task-5c-1-canonical-run-contract` both equaled that commit and
the worktree was clean. The starting commit is the latest pushed branch commit
containing the Architect's Task 5D.1B Attempt 2 remediation publication in
`agent-handoff/current-task.md`. Its parent chain contains reviewed Attempt 1
Reviewer HEAD `949a5e39e85024998204858c900a9fb235a3dca0`.

No Attempt 1 or earlier commit was amended, rebased, or replaced.

## Remediation Implementation Commit

`8775368fb74ee27425946e4c6ea40e745b475c09`

Commit message:

`close Task 5D.1B boundary gaps`

This report is committed separately after the implementation commit. The
Independent Reviewer derives the report commit from Git; this report does not
claim its own future commit SHA.

## Changed Files

Production:

- `pmqa/web/security.py`;
- `pmqa/web/contracts.py`;
- `pmqa/web/app.py`.

Tests:

- `tests/test_web_contracts.py`;
- `tests/test_web_security.py`.

Report-only handoff:

- `agent-handoff/coder-report.md`.

No conversation, Run, Runner, Application, Usage, reasoning, workflow,
Product Pack, product, CLI, dependency, packaging, documentation, frontend,
provider, or later Task 5D implementation changed.

## Required Change 1 — Runtime Token Containment

`PMQAWebSecurityContext.contains_runtime_token` now performs bounded literal
substring containment for both private invocation tokens. It uses no regular
expression, exports no token, and retains exact timing-safe
`hmac.compare_digest` checks for Bearer authentication and CSRF headers.

The existing bounded traversal now rejects either token at any position in:

- decoded/raw-correlated route segments;
- canonically decoded query keys and values;
- nested JSON keys and values;
- valid create-turn user messages;
- pre-existing session/turn read models; and
- workflow catalog text.

Tests cover both session and CSRF tokens in prefix, suffix, and middle
positions for every required boundary, including percent-decoded query
representations. Unrelated partial token prefixes and suffixes remain safe.
Incoming cases fail before service clock/ID sampling or repository mutation.
Outgoing cases return only fixed `internal_failed` and no token bytes.

## Required Change 2 — Canonical Public Contract Invariants

All eleven exported Web contracts now round-trip their own plain-JSON wire
form through explicit `from_dict`. Wire-only reconstruction hooks convert:

- workflow dictionaries to fresh `WorkflowDefinition` snapshots;
- session dictionaries to fresh `ConversationSession` snapshots;
- turn dictionaries to fresh `ConversationTurn` snapshots; and
- canonical JSON arrays to fresh exact tuples.

Direct construction remains strict: response contracts accept only exact
typed domain objects and exact tuples. Wire dictionaries/lists are accepted
only by `from_dict`. Root or nested subclasses, tuples in wire arrays, model
objects, bytes, coercive values, missing/unknown fields, and noncanonical
timestamps are rejected with the fixed contract error. Only
`CreateSessionRequest` retains its approved default insertion, and its direct
typed construction now requires the exact retention enum.

The Web contract base overrides Pydantic's unvalidated `model_copy`.
`model_copy(update=...)` rebuilds the complete field set through strict model
validation, rejects non-dict updates, extras, and coercive values, and
re-snapshots nested domain inputs so caller-owned objects are not retained.
Tests establish canonical JSON round trip, valid update behavior, and invalid
update rejection across every public contract and distinct nested shape.

## Required Change 3 — Finite Canonical JSON

The canonical parser now applies `math.isfinite` to every exact float in its
bounded iterative tree traversal. Literal `NaN`, `Infinity`, and
`-Infinity`, positive and negative exponent overflow, and nested exponent
overflow all produce only `WebAPIContractValidationError`.

The decoder boundary contains only its approved ordinary decoding failures,
including `ValueError`, `OverflowError`, and `RecursionError`. Direct tests
prove `MemoryError`, `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit`
remain authoritative.

## Required Change 4 — Canonical Target and Bounded ASGI Stream

The middleware bounds both raw and decoded targets, requires strict ASCII
encode/decode, and requires exact `scope["path"]`/`raw_path` byte equality.
The prior lossy `errors="ignore"` comparison is removed. Non-ASCII and
mismatched targets now fail at the request boundary before routing or service
work.

The request stream now retains one byte-bounded `bytearray`, not a list of
ASGI message dictionaries. Each input must be an exact dictionary containing
only the canonical request-message keys, an exact `http.request` type, exact
bytes body, and exact boolean `more_body`. Empty nonterminal messages and
non-byte bodies fail fixed-safe. FastAPI receives one immutable canonical
replay message after the complete body, byte limit, declared/received length,
and security checks pass.

Content-Length digit representation is bounded before integer conversion.
Extreme digit strings and values over 64 KiB deterministically return
`request_too_large`; malformed and dishonest values return `invalid_request`.
The required oversized-before-authentication ordering is unchanged.

## Independent Architect-Reproduction Closure

The four published reproductions now fail safely:

1. A valid create-turn payload containing
   `prefix<session-token>suffix` returns fixed 400, samples no new clock/ID,
   persists no turn, and exposes no token. An identifier-shaped route segment
   containing the token returns fixed 400 rather than reaching routing.
2. `CloseSessionRequest.model_copy` rejects a string revision plus unknown
   field, while `SessionResponse.from_dict(json_roundtrip(wire))` reconstructs
   an equal fresh response.
3. `parse_canonical_json_object(b'{"value":1e9999}')` and negative/nested
   counterparts raise the fixed contract error rather than returning
   infinity.
4. `/api/v1/healthé` paired with raw `/api/v1/health` returns fixed 400.
   Empty nonterminal streams, non-byte bodies, dishonest lengths, and extreme
   Content-Length values return fixed failures with zero mutation; many small
   valid chunks still create exactly one valid session.

Focused tests also seed embedded tokens into an existing turn and a registry
workflow description. Both responses are fixed 500 `internal_failed`, carry
all six security headers, and contain neither token nor source text.

## Fixed-Safe and No-Mutation Evidence

Every new HTTP rejection uses only existing `invalid_request`,
`request_too_large`, or `internal_failed` codes and existing fixed messages.
Assertions cover the six required security headers and absence of permissive
CORS. Responses contain no runtime token, candidate string, path, parser
detail, exception detail, or underlying cause.

Route, query, nested JSON, user-message, target mismatch, malformed stream,
overflow, and declared/received mismatch tests assert unchanged clock counts
and/or empty repository state. No retry, fallback, repository repair,
alternate operation, logging, or token serialization was introduced.
Resource/control-flow exceptions remain authoritative.

## Validation Results

Final cumulative implementation validation:

- Web/conversation focused group: `368 passed`.
- Task 5C Application/Run/Usage regressions: `467 passed`.
- Security/import/real-wheel group: `29 passed`.
- Task 4 runtime/reducer/Supervisor/LangGraph regressions: `98 passed`.
- Full default suite: `2214 passed, 5 skipped`.
- Generated SauceDemo Playwright regressions: `2 passed`.
- Isolated `compileall` for `pmqa` and `products`: passed with bytecode
  outside the repository.
- `git diff --check`: passed.
- Implementation commit was pushed to the existing remote branch.

The generated Playwright command initially could not launch Chromium inside
the managed sandbox (`MachPortRendezvousServer` permission denied); the exact
command was rerun with approved local browser permission and passed both
tests. The only test warnings were the existing LibreSSL warning and LangGraph
pending-deprecation warning. The five default-suite skips remain existing
environment-gated tests. All new Web tests are offline and in-process.

## Remaining Risks and Scope Confirmation

The token helper deliberately scans only already bounded strings; target,
query, JSON, conversation, and workflow contract bounds prevent unbounded
search at the Web boundary. This remediation does not generate tokens, bind a
socket, start Uvicorn, open a browser, or implement frontend/runtime
composition; those remain outside Task 5D.1B.

Task 5D.1C, Task 5D.2+, Task 5B, Task 6, and Task 7 were not started. No
Uvicorn, CLI, React/TypeScript/Vite/Node, SSE/WebSocket, provider, ADO,
reasoning, runner/workflow execution, external write, or Product Pack behavior
was added. No PR was created and nothing was merged.

## Recommended Review Depth

**Deep**

Reason: this remediation closes four trust-boundary defects spanning secret
containment, immutable public contracts, numeric parsing, and raw ASGI
canonicalization at PMQA's first HTTP boundary.

## Suggested Reviewer Focus

- Re-run both-token containment attempts in route/query/body/state/catalog
  strings, including prefix/suffix/middle and percent-decoded variants.
- Challenge every exported contract with JSON round trips, typed versus wire
  nested inputs, mutable/subclass inputs, and adversarial `model_copy`
  updates.
- Probe exponent overflow and decoder resource/control-flow propagation.
- Send raw non-ASCII/mismatched targets, malformed ASGI message shapes,
  nonprogress streams, many small chunks, and extreme Content-Length values.
- Confirm every rejection is fixed-safe, includes all security headers, and
  reaches no conversation mutation.
- Confirm the diff remains restricted to the five authorized implementation
  and test files plus this report-only handoff.

## Human Summary

PMQA-5D.1B Attempt 2 已完成，Git 派生起点为 `6398a04df7e1cdfc723013036911bd01839a1b84`。
实现提交为 `8775368fb74ee27425946e4c6ea40e745b475c09`，已推送到 `agent/task-5c-1-canonical-run-contract`。
四个 blocker 均已聚焦关闭：embedded runtime-token containment、全 Web contract canonical round-trip/validated copy、finite JSON，以及 strict target/bounded ASGI stream。
验证结果：focused 368、Task 5C 467、security/import/wheel 29、Task 4 98、全量 2214 passed / 5 skipped、Playwright 2 passed。
Action Needed From Human: 请将下方 Handoff Note 传递给 Independent Reviewer。
Handoff Note: 请读取 agent-handoff/README.md 与 agent-handoff/current-task.md，从 Git 派生最新 coder-report commit，并按独立审查顺序完成 PMQA-5D.1B Attempt 2 review。
