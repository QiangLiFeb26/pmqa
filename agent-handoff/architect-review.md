# Architect Review

Owner: Architect

Task: PMQA Task 5D.1B — Secure Loopback Web/API Boundary

Task ID: `PMQA-5D.1B`

Attempt: `1`

Status: Needs Revision

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed Starting HEAD:
`d9fc04c4c02f3ed13b6f91f05ec6fb3912f49029`

Reviewed Implementation Commits:

- `c2ebcad3cbf6d0456ea55deceaebb06e4a37e69b`;
- `16d34501c1e55afc50cc4006153256e7319d1383`.

Derived Coder Report Commit:
`fbc2810df2475a95b630b6e5f9c6541ec568ae46`

Derived Reviewer Report Commit:
`949a5e39e85024998204858c900a9fb235a3dca0`

The Reviewer report commit was derived from Git with:

```bash
git log -1 --format=%H -- agent-handoff/reviewer-report.md
```

This review does not predict the SHA of its own containing commit.

## Correlation and Ownership Verification

- the active branch and upstream are
  `agent/task-5c-1-canonical-run-contract`;
- starting HEAD `d9fc04c...` is an ancestor of implementation commits
  `c2ebcad...` and `16d3450...`;
- implementation commit `16d3450...` is an ancestor of Coder report commit
  `fbc2810...`;
- Coder report commit `fbc2810...` is an ancestor of Reviewer report commit
  `949a5e3...`;
- Coder and Reviewer reports identify Task `PMQA-5D.1B`, Attempt `1`, the same
  branch, starting HEAD, and implementation commits;
- the implementation changed only authorized Web, test, dependency,
  packaging-test, and documentation surfaces;
- the Coder report commit changed only `agent-handoff/coder-report.md`;
- the Reviewer report commit changed only
  `agent-handoff/reviewer-report.md`;
- the branch matched its upstream and the worktree was clean before this
  Architect disposition.

## Review Depth

Deep

The Architect independently selected Deep review. This is PMQA's first
network-facing trust boundary and will protect future local browser access,
persisted conversation text, and eventually delegated company capabilities.
The Architect read every production Web module, traced middleware ordering and
contract reconstruction, ran focused regressions, and constructed adversarial
requests not present in the implementation tests.

## Independent Reviewer Result

Reviewer verdict: `Pass`

Reviewer findings: none.

The Reviewer performed a legitimate Deep review:

- all production Web modules were read in full;
- Host, authentication, Origin, CSRF, body-size, security-header, and endpoint
  scope paths were traced;
- independent live ASGI/TestClient requests were executed; and
- the complete validation set, including the full suite, was run.

The Architect accepts that evidence for the paths it covers but overrides the
advisory verdict because independent final review found four material
acceptance-criteria gaps.

## Overall Assessment

The checkpoint is strong in structure and most security behavior:

- explicit side-effect-free FastAPI factory;
- exact loopback security context and fixed token wire shape;
- versioned and deliberately narrow endpoint inventory;
- Host, Bearer, Origin, and CSRF enforcement;
- body-byte bounding before authentication and mutation;
- duplicate-key JSON parsing;
- fixed-safe HTTP failures and uniform security headers;
- no CORS, OpenAPI UI, Uvicorn, frontend, provider, workflow execution, or
  later Task 5D scope;
- import and wheel isolation.

However, the runtime-token containment rule is implemented as whole-string
equality, not containment. A token embedded inside a longer accepted string
can cross the Web boundary, enter durable application state, and be returned
to the browser. The public contract base also permits invalid instances
through Pydantic's unvalidated `model_copy`, and response contracts cannot
reconstruct their own canonical wire output. Two parser/transport details
also fail explicit fail-closed requirements.

These issues are local to the new Web modules and can be corrected without
changing the accepted architecture or Task 5D.1A.

## Blocking Findings

### F1 — Embedded runtime tokens cross request, domain, URL, and response boundaries

Severity: Blocking

Locations:

- `pmqa/web/security.py`;
- `PMQAWebSecurityContext.contains_runtime_token`;
- `pmqa/web/app.py`;
- `_contains_runtime_token`;
- path and query validation.

`contains_runtime_token(candidate)` returns true only when the complete
candidate string exactly equals one token. `_contains_runtime_token` merely
applies that equality check to each JSON string.

It does not detect:

```text
prefix-<session-token>-suffix
```

inside a user message, JSON key/value, route segment, query key/value, workflow
description, or response string.

#### Independent reproduction — request, persistence, and response

The Architect created the real app with real in-memory repositories, then:

1. created a valid session;
2. submitted a valid create-turn request whose `user_message` was
   `prefix-<real session token>-suffix`; and
3. inspected both the response and repository through the public service.

Observed:

```text
create session status: 201
create turn status: 201
token present in response: true
token present in stored user_message: true
```

This violates the explicit acceptance criterion that tokens never enter
URLs, payloads, domain state, errors, logs, or responses.

The Architect also sent a GET using a valid identifier-shaped route segment
containing `prefix<real token>suffix`. The middleware accepted the target and
routing produced `404`, rather than rejecting token-bearing URL content at the
security boundary.

Incoming embedded tokens must be rejected before service clock/ID sampling or
repository mutation. Pre-existing embedded tokens in any outgoing read model
must produce only fixed `INTERNAL_FAILED`, with the token absent from the
response.

### F2 — Public Web contracts are not closed under their own construction APIs

Severity: Blocking

Location:

- `pmqa/web/contracts.py`;
- `_WebContract`;
- response nested-field validators.

#### Unvalidated `model_copy`

Pydantic's default `model_copy(update=...)` does not revalidate updates. The
Architect reproduced:

```text
valid CloseSessionRequest
  -> model_copy(expected_revision="not-an-int", unknown="x")
  -> successful invalid public contract
```

The resulting object retained the string revision and an unknown attribute.
This conflicts with the claimed strict, exact-field, non-coercive contract
boundary.

#### Canonical wire round trip fails

Response validators accept only direct typed domain objects/tuples. Explicit
`from_dict(...)` receives canonical JSON dictionaries/lists, so a response
cannot reconstruct its own output.

The Architect reproduced:

```text
wire = SessionResponse(...).to_dict()
SessionResponse.from_dict(wire)
  -> WebAPIContractValidationError
```

Every public Web contract must guarantee:

```python
wire = contract.to_dict()
restored = type(contract).from_dict(
    json.loads(json.dumps(wire))
)
assert restored == contract
```

Direct typed construction must remain strict; only explicit wire
reconstruction may translate canonical JSON dictionaries/lists into fresh
domain snapshots/tuples. Valid and invalid `model_copy(update=...)` must be
fully revalidated.

### F3 — Canonical JSON parser accepts non-finite exponent results

Severity: Blocking

Location:

- `pmqa/web/contracts.py`;
- `_bounded_plain_json`.

`parse_constant` rejects literal `NaN` and `Infinity`, but ordinary JSON
numeric syntax with a large exponent is parsed by Python as a non-finite
float. `_bounded_plain_json` accepts every exact float without an
`isfinite` check.

Independent reproduction:

```text
parse_canonical_json_object(b'{"value":1e9999}')
  -> {"value": inf}
math.isfinite(value) -> false
```

This directly violates the parser's documented and required finite-JSON
guarantee. Positive and negative exponent overflow must fail with the same
fixed contract/request error and no parser detail.

### F4 — Target and streamed-body representations are not fully bounded/canonical

Severity: High

Locations:

- `pmqa/web/app.py`;
- `_validate_target_and_body`;
- request-message buffering.

#### Path ambiguity

The middleware compares:

```python
path.encode("ascii", errors="ignore") == raw_path
```

Ignoring non-ASCII characters can treat a different decoded `scope["path"]`
and raw target as equal.

The Architect independently supplied:

```text
scope.path = /api/v1/healthé
scope.raw_path = /api/v1/health
```

The middleware accepted the target and routing returned `404`; the explicit
non-ASCII target ambiguity requirement says it must fail at the request
boundary. Encoding must be strict and decoded/raw target equality exact.

#### ASGI chunk metadata

The middleware bounds total body bytes but retains one dictionary for every
ASGI `http.request` message. A stream can therefore create unbounded
per-message/list overhead with empty nonterminal chunks even while total body
bytes remain below 64 KiB.

Buffer only the bounded bytes needed downstream, replay a canonical bounded
body message, and reject malformed/non-byte or non-progressing stream
messages. Request handling must be bounded by the byte limit rather than by an
unbounded number of retained transport objects.

Malformed or oversized `Content-Length` conversion must also remain
cross-version fixed-safe; do not permit integer conversion limits or overflow
to become an unexpected 500 classification.

## Acceptance Criteria Coverage

| Acceptance criterion | Result |
| --- | --- |
| Task 5D.1A remains approved and unchanged | Met |
| Explicit side-effect-free FastAPI app factory | Met |
| Versioned and bounded endpoint inventory | Met |
| Authentication, Host, Origin, and CSRF fail closed | Met for exact header values |
| Tokens never enter URLs, payloads, state, or responses | Not met |
| Request body bytes bounded before mutation | Partially met; transport-message retention is not bounded |
| API contracts are strict and canonical | Not met |
| Non-finite JSON rejected | Not met |
| Non-ASCII target ambiguity rejected | Not met |
| Fixed-safe application/dependency errors | Met for covered paths |
| Security headers and no permissive CORS | Met |
| Imports and real-wheel packaging remain isolated | Met |
| Focused/full regressions pass | Met, but missing adversarial cases allow blockers above |
| Only allowed files changed | Met |

## Validation Evidence

Independent Reviewer:

- Web/conversation focused group: `258 passed`;
- Task 5C regressions: `467 passed`;
- security/import/wheel group: `29 passed`;
- Task 4 regressions: `98 passed`;
- full default suite: `2104 passed, 5 skipped`;
- generated Playwright regressions: `2 passed`;
- compileall, `git diff --check`, and clean-worktree checks: passed;
- independent live ASGI requests: passed for the cases selected by Reviewer.

Architect:

- complete current task, implementation diff, Coder report, Reviewer report,
  and all Web production modules inspected;
- Web/conversation focused group: `258 passed`;
- Task 5C regressions: `467 passed`;
- `git diff --check`: passed;
- embedded-token request/persistence/response reproduction: failed the
  intended security invariant;
- embedded-token route reproduction: failed the intended security invariant;
- response-contract canonical round-trip reproduction: failed;
- `model_copy(update=...)` validation reproduction: failed;
- non-finite exponent parser reproduction: failed;
- decoded/raw path ambiguity reproduction: failed.

The Architect's sandbox emitted only a pytest-cache write warning; the test
processes completed successfully and the worktree remained clean.

## Required Changes

Complete one narrow Task 5D.1B Attempt 2 remediation:

- detect actual runtime tokens anywhere inside bounded string leaves;
- preserve exact timing-safe authentication and CSRF comparisons;
- prevent embedded tokens from reaching URLs, request/domain state, or
  responses;
- make every public Web contract revalidate `model_copy` and round-trip its
  canonical JSON wire representation;
- reject all non-finite JSON results, including exponent overflow;
- require exact strict decoded/raw target equality;
- make streamed-body buffering bounded by bytes and canonical transport
  representation;
- add focused adversarial tests for every independent reproduction above.

Do not begin Uvicorn, CLI, frontend, token generation/delivery, or Task
5D.1C.

## Decision

Needs Revision

PMQA Task 5D.1B is not approved at implementation commit
`16d34501c1e55afc50cc4006153256e7319d1383`.

## Next Recommended Task

Complete PMQA Task 5D.1B Attempt 2 — Web Boundary Canonicalization and Token
Containment, defined in `agent-handoff/current-task.md`.
