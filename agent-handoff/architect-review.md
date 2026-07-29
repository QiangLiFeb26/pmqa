# Architect Review

Owner: Architect

Task: PMQA Task 5D.1B — Web Boundary Canonicalization and Token Containment

Task ID: `PMQA-5D.1B`

Attempt: `2`

Status: Approved

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed Starting HEAD:
`6398a04df7e1cdfc723013036911bd01839a1b84`

Reviewed Implementation Commit:
`8775368fb74ee27425946e4c6ea40e745b475c09`

Derived Coder Report Commit:
`651181eb8302f2a7d2416ed14d5bb2ba27e6fd9c`

Derived Reviewer Report Commit:
`d173b54df47f9ea54d82b731680e40e6977ca455`

The report commits were derived from the path-specific Git history. This
review does not predict the SHA of its own containing commit.

## Correlation and Ownership Verification

- the active local branch and its upstream are
  `agent/task-5c-1-canonical-run-contract`;
- the worktree was clean and local HEAD equaled the pushed upstream Reviewer
  report commit before this disposition;
- Attempt 2 starting HEAD `6398a04...` is the direct parent of implementation
  commit `8775368...`;
- implementation commit `8775368...` is the direct parent of Coder report
  commit `651181e...`;
- Coder report commit `651181e...` is the direct parent of Reviewer report
  commit `d173b54...`;
- the Coder and Reviewer reports identify Task `PMQA-5D.1B`, Attempt `2`,
  the same branch, starting HEAD, and implementation commit;
- the implementation commit changes only the three allowed Web modules and
  two allowed focused test files;
- the Coder report commit changes only `agent-handoff/coder-report.md`;
- the Reviewer report commit changes only
  `agent-handoff/reviewer-report.md`.

## Review Depth

Deep

The Coder recommended Deep review and the Reviewer independently performed a
Deep review. The Architect also selected Deep review because this remediation
changes PMQA's first network trust boundary and closes four previously
reproduced security and canonicalization defects.

## Independent Reviewer Result

Reviewer verdict: `Pass`

Reviewer findings: none.

The Reviewer read every changed production line, independently reproduced all
four remediated defect classes, directly exercised raw ASGI scopes for target
and stream behavior, and reran the complete required validation set. The
Architect accepts the Reviewer evidence and independently verified the
critical implementation paths and repository scope.

## Overall Assessment

Task 5D.1B Attempt 2 closes every blocking Attempt 1 finding without weakening
the accepted Web architecture:

- runtime session and CSRF tokens are rejected by bounded literal substring
  containment in relevant request, domain, catalog, and response strings;
- authentication and CSRF header verification remain exact and use
  `hmac.compare_digest`;
- every exported Web contract has explicit canonical wire reconstruction and
  revalidated `model_copy(update=...)` behavior while direct typed
  construction remains strict;
- canonical JSON rejects named non-finite values and ordinary exponent
  overflow at every bounded nesting level;
- decoded and raw request paths must be exact strict-ASCII equivalents;
- request streaming retains only one byte-bounded buffer, rejects
  non-progressing messages, and replays one canonical ASGI request message;
- Content-Length representation is bounded before integer conversion;
- failures retain the existing fixed-safe error vocabulary, security headers,
  no-mutation behavior, and resource/control-flow propagation;
- no endpoint, dependency, CLI, frontend, workflow execution, provider, ADO,
  Product Pack, or later Task 5D behavior was introduced.

The Architect found no residual blocker or scope violation.

## Findings

None.

## Acceptance Criteria Disposition

| Acceptance criterion | Architect evidence | Result |
| --- | --- | --- |
| Embedded runtime tokens cannot cross URL/request/state/response string boundaries | Traced bounded substring containment and all request/response traversal call sites; independently reran the complete Web security suite | Met |
| Exact authentication and CSRF verification remain timing-safe | `authenticates` and `validates_csrf` remain exact `hmac.compare_digest` checks | Met |
| Public Web contracts remain canonical and fully revalidated | Inspected every `_wire_values` reconstruction shape and the revalidating `model_copy`; contract tests pass | Met |
| Canonical JSON rejects every non-finite result | Inspected the exact-float `math.isfinite` traversal and decoder containment; overflow tests pass | Met |
| Decoded/raw targets are exact strict-ASCII matches | Inspected strict encode/decode and byte equality before routing | Met |
| Body processing is bounded and canonical | Inspected single `bytearray` accumulation, exact ASGI message validation, non-progress rejection, and canonical replay | Met |
| Rejections remain fixed-safe and mutation-free | Web/conversation focused group passes and no new error vocabulary or alternate operation exists | Met |
| Attempt 1 API behavior remains unchanged | Existing Web/conversation regressions pass | Met |
| Task 5D.1A and unrelated PMQA behavior remain unchanged | Diff scope is exact; full default suite passes | Met |
| Only allowed files changed | Git name-status matches the five allowed implementation/test files | Met |

## Architect Validation

Independently executed:

- Web/conversation focused group: `368 passed`;
- full default suite: `2214 passed, 5 skipped, 1` existing LangGraph warning;
- generated SauceDemo Playwright regressions: initial managed-sandbox browser
  launch failed with the known Chromium permission error; the identical
  command was rerun with approved local browser permission and passed
  `2 passed`;
- isolated `compileall`: passed;
- `git diff --check`: passed.

The five full-suite skips are existing environment-gated tests. No new test
was skipped by Architect choice.

## Required Changes

None.

## Final Disposition

**Approved**

Task 5D.1B is complete at implementation commit
`8775368fb74ee27425946e4c6ea40e745b475c09`.

This approval does not authorize a PR, merge, Task 5D.2, company integration,
ADO access, Copilot integration, or external writes.

## Next Recommended Task

Proceed to Task 5D.1C — Local Browser Workbench, `pmqa web`, and Distribution
Packaging.

The next checkpoint should expose only the already-approved Task 5D.1B
conversation and workflow-catalog APIs through a minimal local browser
workbench. It must not add reasoning, workflow execution, ADO, Copilot,
capability execution, authorization, receipts, or usage UI.
