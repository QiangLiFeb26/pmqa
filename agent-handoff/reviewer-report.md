# Independent Reviewer Report

Owner: Independent Reviewer

Status: Executed for PMQA Task 5D.1B, Attempt 2

## Task Correlation

Task: PMQA Task 5D.1B — Web Boundary Canonicalization and Token Containment

Task ID: `PMQA-5D.1B`

Attempt: `2`

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed Starting HEAD: `6398a04df7e1cdfc723013036911bd01839a1b84`

Reviewed Implementation Commit(s): `8775368fb74ee27425946e4c6ea40e745b475c09`
("close Task 5D.1B boundary gaps")

Derived Coder Report Commit: `651181eb8302f2a7d2416ed14d5bb2ba27e6fd9c`
("report Task 5D.1B boundary remediation")

Correlation Verification:

- derived with `git log -1 --format=%H -- agent-handoff/coder-report.md` ->
  `651181eb8302f2a7d2416ed14d5bb2ba27e6fd9c`;
- `git merge-base --is-ancestor 6398a04df7e1cdfc723013036911bd01839a1b84 HEAD`
  succeeds; `6398a04...` is an ancestor of `8775368...`, and `8775368...` is
  an ancestor of `651181e...` (linear sequence
  `6398a04 -> 8775368 -> 651181e` on this branch);
- the reviewed Attempt 1 Reviewer HEAD named by `current-task.md`,
  `949a5e39e85024998204858c900a9fb235a3dca0` (this Reviewer's own prior
  Attempt 1 report commit), is an ancestor of the recorded starting HEAD;
- the correlation header of `coder-report.md` at the derived commit names
  Task ID `PMQA-5D.1B`, Attempt `2`, branch
  `agent/task-5c-1-canonical-run-contract`, and starting HEAD
  `6398a04df7e1cdfc723013036911bd01839a1b84`, matching `current-task.md`;
- `git diff --stat 8775368..651181e` touches only
  `agent-handoff/coder-report.md`, so the derived commit is the report's
  latest authorized change with no later unauthorized replacement.

This Reviewer report does not contain or predict its own commit SHA. The
Architect derives the Reviewer report commit from Git and records it in
`architect-review.md`.

## Independent Review Method

Inspection order completed:

1. `current-task.md` and acceptance criteria (the four Required Changes:
   runtime token containment, canonical public contract invariants,
   finite canonical JSON, canonical target/bounded ASGI stream);
2. named baseline-to-implementation diff (`6398a04..8775368`) — full
   line-by-line read of the changes to `pmqa/web/security.py`,
   `pmqa/web/contracts.py`, and `pmqa/web/app.py`, plus a structural pass
   over the entire additive diffs to `tests/test_web_contracts.py` and
   `tests/test_web_security.py`;
3. independently selected validation (see Test Evidence), including
   deliberately fresh ad hoc adversarial scripts — not reused from the
   Coder's test files — targeting exactly the four gap categories, plus
   two raw ASGI-scope probes constructed by hand for the most subtle
   fixes (non-ASCII path bypass, unbounded empty-chunk loop);
4. full `coder-report.md` (read only after steps 1-3).

Active-task `architect-review.md` read before publication: No

Prior closed review or architecture material consulted, with reason: this
Reviewer authored the Attempt 1 review of this same task
(`agent-handoff/reviewer-report.md` at commit `949a5e3`, superseded by
this report), in which a "Deep" review with eight live adversarial HTTP
requests still missed all four gaps the Architect subsequently found;
that history directly informed how this attempt needed to be checked, so
each of my adversarial checks below was deliberately designed to target
the *exact* class of defect my Attempt 1 review missed (substring
containment vs. exact match; nested-object contract round trip vs.
end-to-end request flow; regular-literal float overflow vs. the special
JSON constant tokens; raw ASGI scope manipulation vs. only
TestClient-mediated requests), rather than re-deriving the gaps from
`architect-review.md` (unread, per protocol).

## Review Depth

Actual Review Depth: Deep

Review Depth Reason: this is the second consecutive Deep review of the
same file where the first one, despite genuine live adversarial testing,
missed four real defects that only surfaced through the Architect's own
adversarial construction. A third pass that only re-verifies the Coder's
own test assertions would carry the same blind spots as before. I
therefore read every changed line by hand and, more importantly,
independently constructed *new* adversarial scenarios from scratch for
each of the four Required Changes — deliberately choosing input shapes
different from what I (or, as far as I can tell, the Coder's own tests)
had tried before, including two raw ASGI-scope probes that bypass
`TestClient` entirely to directly exercise the middleware's `receive()`
loop. This matches the Coder's advisory recommendation but was
independently selected, and driven specifically by the history of this
checkpoint.

## Overall Assessment

All four Required Changes are correctly and precisely implemented, with
no regression to valid Attempt 1 behavior and no scope creep. The diff
touches exactly `pmqa/web/security.py`, `pmqa/web/contracts.py`,
`pmqa/web/app.py`, `tests/test_web_contracts.py`, and
`tests/test_web_security.py` — no conversation, Run, Runner, Application,
Usage, reasoning, workflow, dependency, or documentation file changed.

**Required Change 1 (token containment).** The exact-equality
`hmac.compare_digest(candidate, token)` calls in
`contains_runtime_token` were replaced with
`self.__session_token in candidate or self.__csrf_token in candidate`
(bounded to 64 KiB candidates), correctly catching a token embedded
anywhere within a larger string rather than only an exact match. This
method is used purely for leak/containment *detection* on
attacker-supplied haystacks, not for authentication itself; the actual
`authenticates`/`validates_csrf` comparison methods are unchanged and
still use `hmac.compare_digest` for exact, timing-safe verification, which
is what the task's "authentication and CSRF header validation remain
exact and timing-safe" clause specifically scopes. I independently
constructed a token embedded in the *middle* of a string (a position
category not obviously covered by "prefix, suffix" wording) and a
one-character "near miss" string, and confirmed the former is detected
and the latter is not (see Test Evidence).

**Required Change 2 (canonical contract invariants).** This was the gap
I most directly missed in Attempt 1 — I tested the full HTTP request/
response cycle (which constructs response contracts via direct
construction with real typed objects) but never tested
`SomeResponse.from_dict(json.loads(json.dumps(some_response.to_dict())))`
in isolation for the nested-object response contracts. I traced why this
was broken: `_session_snapshot`/`_turn_snapshot`/`_workflow_snapshot`
(the field validators) require an *already-typed* domain instance and
reject raw dicts outright, so a wire-JSON round trip through
`from_dict`'s old plain `dict(value)` pass-through would have failed for
`SessionResponse`, `TurnResponse`, `TurnMutationResponse`,
`SessionListResponse`, `TurnListResponse`, and `WorkflowCatalogResponse`.
The fix adds a `_wire_values` hook, overridden per contract, that
explicitly reconstructs nested fields via their own `from_dict` (e.g.
`ConversationSession.from_dict(selected.get("session"))`) *before*
`model_validate` runs, so the field validators then receive an
already-typed instance as required. I independently verified this by
round-tripping a freshly-constructed `SessionResponse` (not reusing any
Coder fixture) through `to_dict()` -> JSON -> `from_dict()` and confirmed
equality. The new `model_copy` override mirrors the established
`pmqa.run`/`pmqa.usage`/`pmqa.conversation` pattern (rebuild the full
field set, apply the update, fully revalidate via `model_validate`),
correctly retaining the requirement that direct construction/`model_copy`
still only accept already-typed nested objects (distinct from
`from_dict`'s wire-dict acceptance), which I confirmed is consistent with
every other contract family in this codebase.

**Required Change 3 (finite JSON).** `_bounded_plain_json` previously
matched `float` inside the same branch as `bool`/`int` with no finiteness
check at all — meaning any float value, however produced, passed through
unchecked. The fix splits `float` into its own branch and calls
`math.isfinite(current)`, rejecting the value if it fails. Because this
runs inside the recursive/iterative tree walker, it catches non-finite
values at any nesting depth, and — critically — it catches them
regardless of *how* Python arrived at the float, not just the special
`NaN`/`Infinity`/`-Infinity` JSON constant tokens. I independently
confirmed this distinction matters by testing `1e400` (an ordinary
numeric literal that Python's `float()` silently resolves to `inf`,
never touching the `parse_constant` hook that only intercepts the
named-constant spelling) and confirmed it is now rejected.

**Required Change 4 (canonical target and bounded stream).** Two
independent fixes: (a) the path/`raw_path` comparison now uses
`path.encode("ascii", errors="strict")` (raising immediately on any
non-ASCII character) instead of the old `errors="ignore"` (which silently
*dropped* non-ASCII characters before comparing, meaning a non-ASCII
`path` could still equal an all-ASCII `raw_path` and pass). I
independently constructed a raw ASGI scope with a `path` containing a
non-ASCII character and a `raw_path` that omits it — exactly the
condition the old lossy comparison would have accepted — and confirmed
it is now rejected with `400` before ever reaching routing. (b) The body-
streaming loop now explicitly rejects a message with an empty body and
`more_body=True` (`if not body and more_body: raise`), and replaces the
growing list of buffered ASGI message dicts with a single `bytearray`
that accumulates only the (bounded) byte content, then replays one
canonical reconstructed message. I independently drove the middleware
directly (bypassing `TestClient`) with a `receive()` callable that always
returns a non-progressing empty chunk claiming more data is coming, with
a safety assertion capping the probe at 5 calls so my own script could
not hang if the fix were absent — and confirmed the middleware rejects
the request after exactly one `receive()` call rather than looping.

All validation commands listed in `current-task.md`, run independently
rather than accepted from the Coder report, pass with no failures,
errors, or unexplained skips.

## Findings

None. All four reported gaps are independently confirmed closed by fresh
adversarial reproduction constructed from scratch — including two raw
ASGI-scope probes for the two most subtle fixes — rather than by only
re-running the Coder's own tests. No new gap surfaced during this Deep
inspection.

## Acceptance Criteria Coverage

| Acceptance criterion | Evidence | Result |
| --- | --- | --- |
| Embedded session/CSRF tokens cannot cross any URL/request/state/response string boundary | `contains_runtime_token` traced and independently reproduced with a token embedded mid-string; response-side non-disclosure independently confirmed via a fresh `SessionResponse` round-trip (Required Change 2 test) and the Coder's `internal_failed` seeding tests, independently rerun | Met |
| Exact auth and CSRF comparison remains timing-safe | `authenticates`/`validates_csrf` unchanged, still `hmac.compare_digest`-based; confirmed via `git diff` showing no change to those two methods | Met |
| Every public Web contract is strict under direct construction, `from_dict`, canonical JSON round trip, and `model_copy(update=...)` | Traced `_wire_values` overrides for all 6 nested-object contracts and the new `model_copy` override; independently round-tripped `HealthResponse` and `SessionResponse` from scratch; `test_every_public_contract_has_canonical_json_round_trip` and `test_every_public_contract_model_copy_revalidates` independently rerun | Met |
| Canonical JSON parsing rejects every non-finite result | `_bounded_plain_json`'s new `math.isfinite` branch traced; independently reproduced rejection of `1e400` (a regular literal, not the special constant spelling) | Met |
| Decoded/raw targets are exact strict ASCII matches | `errors="strict"` fix traced; independently constructed a raw ASGI scope with non-ASCII `path`/ASCII `raw_path` (the exact old-bug condition) and confirmed rejection | Met |
| Streamed body processing is bounded by bytes and canonicalized without unbounded message retention | `bytearray`-based accumulation and non-progressing-empty-message rejection traced; independently drove the middleware's `receive()` loop directly with a non-progressing empty-chunk generator and confirmed rejection after one call | Met |
| All rejection paths are fixed-safe and mutation-free | Every new raise path uses the existing `WebAPIFailureCode` vocabulary via `_RequestBoundaryFailure`/`WebAPIContractValidationError`; `test_embedded_runtime_tokens_in_json_fail_before_mutation` and related tests independently rerun | Met |
| Every valid Attempt 1 endpoint and security behavior remains unchanged | Full Attempt 1 test suites (`test_web_app.py`, prior `test_web_security.py`/`test_web_contracts.py` assertions) independently rerun unchanged and pass | Met |
| Task 5D.1A and unrelated PMQA behavior remain unchanged | `git diff --stat` confirms zero changes to `pmqa/conversation/*`; 467 Task 5C + 98 Task 4 regression tests independently rerun and pass | Met |
| Focused and full regressions pass | 368 focused Web/conversation + 467 Task 5C + 29 security/import/wheel + 98 Task 4 + 2214/5-skip full suite + 2 Playwright, all independently run, all pass | Met |
| Only allowed files change | `git diff --stat 6398a04..8775368` shows exactly the five allowed implementation/test files | Met |

## Test Evidence

### Coder Evidence Reviewed

The Coder report claims: 368 passed for the Web/conversation focused
group; 467 passed for Task 5C regressions; 29 passed for security/import/
wheel; 98 passed for Task 4; 2214 passed, 5 skipped for the full default
suite; 2 passed for `products/demo/generated_tests` (noting a transient
sandbox Chromium permission issue resolved on rerun); `compileall` and
`git diff --check` clean; implementation commit pushed. The report also
describes four specific "Independent Architect-Reproduction Closure"
scenarios matching the four Required Changes. This claimed evidence was
read only after independent execution below and matches it exactly,
except the Reviewer's environment did not encounter the noted transient
Chromium permission issue.

### Independently Run

All commands below were executed by the Reviewer directly, before reading
the Coder's claimed results, from the repository root on the reviewed
branch:

- `.venv/bin/python -m pytest tests/test_web_contracts.py tests/test_web_security.py tests/test_web_app.py tests/test_conversation_service.py tests/test_conversation_repository.py tests/test_conversation_contracts.py -q`
  -> `368 passed`
- `.venv/bin/python -m pytest tests/test_application_contracts.py tests/test_application_service.py tests/test_run_contracts.py tests/test_usage_contracts.py tests/test_usage_repository.py tests/test_usage_summary.py -q`
  -> `467 passed`
- `.venv/bin/python -m pytest tests/test_boundary_policy.py tests/test_scrubber.py tests/test_packaging.py tests/test_conversation_imports.py tests/test_run_imports.py -q`
  -> `29 passed`
- `.venv/bin/python -m pytest tests/test_workflow_runtime.py tests/test_workflow_reducer.py tests/test_supervisor_policy.py tests/test_langgraph_workflow.py -q`
  -> `98 passed, 1 warning` (pre-existing `LangChainPendingDeprecationWarning`,
  unrelated to this change)
- `.venv/bin/python -m pytest -q` (full default suite) -> `2214 passed, 5 skipped, 1 warning`
- `.venv/bin/python -m pytest products/demo/generated_tests -q` -> `2 passed`
- `PYTHONPYCACHEPREFIX=<isolated scratch directory> .venv/bin/python -m compileall -q pmqa products`
  -> exit code `0`, no output
- `git diff --check` -> exit code `0`, no output
- `git status --short` -> empty (clean worktree)

In addition, and deliberately using fresh scenarios distinct from the
Coder's own tests (and from my own Attempt 1 checks), I independently
verified all four Required Changes in ad hoc scripts:

- a token embedded in the *middle* of a string (`"zzz" + token + "yyy"`)
  is detected by `contains_runtime_token`, and a one-character "near
  miss" string (the token with its last character altered) is correctly
  *not* flagged;
- a freshly-constructed `HealthResponse` and a freshly-constructed
  `SessionResponse` (built from a real `ConversationApplicationService`-
  created session, not a Coder fixture) both round-trip exactly through
  `to_dict()` -> `json.dumps`/`json.loads` -> `from_dict()`;
- `parse_canonical_json_object(b'{"schema_version":"1","x":1e400}')`
  raises `WebAPIContractValidationError` rather than silently accepting
  an `inf` value;
- a raw ASGI scope with `path="/api/v1/healthé"` (non-ASCII) and
  `raw_path=b"/api/v1/health"` (all-ASCII, the exact byte sequence the
  old lossy `errors="ignore"` comparison would have accepted) is rejected
  with `400`, driven directly through the middleware's `__call__` without
  `TestClient`;
- a raw ASGI scope driven with a `receive()` callable that always returns
  `{"type": "http.request", "body": b"", "more_body": True}` (a non-
  progressing empty chunk) causes the middleware to reject with `400`
  after exactly one `receive()` call, rather than looping — verified with
  a hard cap of 5 calls in my own probe script so it could not hang even
  if the fix were absent.

No listed validation command was left unrun. No test was skipped by
Reviewer choice. Environment: local `.venv` (Python 3.9), macOS/Darwin,
FastAPI 0.128.8 / httpx 0.28.1 (within the declared `pyproject.toml`
bounds, unchanged by this remediation), no network access used or
required.

## Security, Scope, and Compatibility

Security observations: all four remediated gaps are genuine trust-
boundary issues (secret-leak detection bypassable via substring
embedding, a broken canonical-reconstruction invariant for response
contracts, a numeric-overflow bypass of finite-JSON enforcement, and two
distinct request-target/stream canonicalization bypasses including an
unbounded-memory-growth vector) and all four are now independently
confirmed closed through adversarial reproduction independent of the
Coder's own test suite. I did not identify a residual gap in the
`contains_runtime_token` substring search not being constant-time; the
task's timing-safety requirement is explicitly scoped to "authentication
and CSRF header validation" (unchanged, still `hmac.compare_digest`-
based), and the containment check operates on attacker-supplied haystacks
being searched for a fixed needle, which is a materially different threat
shape than a secret-vs-secret equality comparison — worth noting for the
Architect's awareness, not a finding.

Scope observations: the diff touches exactly `pmqa/web/security.py`,
`pmqa/web/contracts.py`, `pmqa/web/app.py`, `tests/test_web_contracts.py`,
and `tests/test_web_security.py`, plus the Coder-owned report in a
separate commit. No conversation, Run, Runner, Application, Usage,
reasoning, workflow, CLI, dependency, packaging, or documentation file was
modified — confirmed via `git diff --stat`.

Compatibility observations: all Attempt 1 regression suites (467 Task 5C,
98 Task 4, and the previously-passing Web/conversation tests) continue to
pass unchanged, and the full default suite grew from 2104 (Attempt 1) to
2214 tests (110 net new, consistent with the substantial new adversarial
coverage), with no reduction in passing count.

## Verdict

Verdict: Pass

This verdict is advisory. The Architect makes the final technical
disposition.

## Suggested Architect Focus

- All four reported gaps are independently confirmed closed through fresh
  adversarial reproduction, including two raw ASGI-level probes
  constructed specifically to bypass this Reviewer's own prior blind
  spots. Nothing further is blocking from this Reviewer's independent
  inspection.
- This is now the third checkpoint in a row (Task 5C.7, Task 5D.1A, and
  now Task 5D.1B) where a genuine defect surfaced only through the
  Architect's own adversarial construction after this Reviewer's Deep
  pass — including live testing — missed it. For Task 5D.1B specifically,
  the missed defects shared a common shape: each was a place where a
  *general-purpose* check (exact-match containment, generic `from_dict`,
  a `bool`/`int`/`float`-lumped type check, a lossy encode-and-compare
  idiom) was silently insufficient for the *specific* adversarial input
  shape needed. If this pattern continues into Task 5D.1C, it may be
  worth the Architect and Reviewer explicitly agreeing on a shared
  "adversarial input taxonomy" checklist (substring/embedding, wire-vs-
  typed round trips, numeric-overflow-without-named-constants, lossy-
  decode-then-compare, unbounded-resource-via-non-progress) to apply
  systematically to new security-boundary code, rather than relying on
  each Reviewer pass to independently rediscover it.

## Reviewer Write-Boundary Confirmation

Repository files changed by Reviewer:

- `agent-handoff/reviewer-report.md`

Confirmation: I changed no production code, tests, configuration, schemas,
packaging, scripts, product documentation, or another role's handoff file.
