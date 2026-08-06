# Architect Review

Owner: Architect

Task: PMQA Task 5D.1C — Browser Boundary and Contract Drift Remediation

Task ID: `PMQA-5D.1C`

Attempt: `2`

Status: Approved

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed Starting HEAD:
`5f0c1413bc0d726592f0e590fc4646fadac5519c`

Reviewed Implementation Commit:
`da474009bd603e46ce4ffcbdb03de85986094208`

Derived Coder Report Commit:
`11be60dee8c1fee5032ef635e43f9de0d49081dc`

Derived Reviewer Report Commit:
`fc3d46f0f7801599661dfdce0ddd447ec4f0e782`

This disposition does not predict the SHA of its own containing commit.

## Correlation and Ownership Verification

- the active branch is `agent/task-5c-1-canonical-run-contract`;
- before this disposition, the worktree was clean and local HEAD and the
  configured upstream both equaled the Git-derived Reviewer report commit
  `fc3d46f0...`;
- `5f0c1413...` is the parent of implementation commit `da474009...`;
- `da474009...` is the parent of Coder report commit `11be60de...`;
- `11be60de...` is the parent of Reviewer report commit `fc3d46f0...`;
- the current task, Coder report, and Reviewer report identify Task
  `PMQA-5D.1C`, Attempt `2`, the same branch, starting HEAD, and
  implementation commit;
- the implementation commit changes only the seven implementation/test
  files allowed by `current-task.md`;
- the Coder and Reviewer report commits each change only their owner-controlled
  handoff file; and
- the Architect changes only this `architect-review.md` disposition.

## Review Depth

Deep

The Coder recommended Deep review, the Independent Reviewer independently
selected Deep, and the Architect selected Deep because the remediation
changes fixed-safe classification at browser-launch and native-thread-start
trust boundaries and expands the maintained Python/TypeScript API drift
surface.

## Independent Reviewer Result

Reviewer verdict: `Pass`

Reviewer blocking findings: none.

The Reviewer reported one process deviation: it read the complete Coder
report before independently inspecting the implementation, rather than
limiting the initial read to correlation fields. The deviation was disclosed
precisely. The Reviewer then independently read the primary-source diff,
cross-checked fields, enums and routes, and reran every required Python and
frontend command. Those results matched the Coder evidence. The Architect
therefore treats the deviation as non-blocking and adequately mitigated.

The Reviewer also recorded one non-blocking advisory: the selected frontend
operation inventory is deliberately maintained and its operation-name set is
pinned rather than derived from TypeScript source. This matches the accepted
no-code-generation design and covers every current `APIClient` method. Any
future API-client method must update the fixture and both Python and
TypeScript assertions in the same checkpoint.

## Overall Assessment

Attempt 2 closes all three Attempt 1 findings without broadening production
behavior.

The runtime now contains only the expected standard-library browser error and
native thread-start `RuntimeError` at their exact call sites. It converts them
to the existing fixed `PMQAWebRuntimeError` without cause, context, token,
URL, path, executable or underlying detail. Resource/control-flow exceptions,
thread-construction programming failures, browser programming failures and
server-body failures retain their approved propagation. The existing
readiness, stop signaling, bounded join and owned-socket cleanup structure is
unchanged.

The selected frontend contract fixture now covers every outer Web contract,
all `ConversationSession` and `ConversationTurn` fields, the exact
`WorkflowDefinition` subset consumed by the client, all relevant enum values,
the API schema version, and all nine current `APIClient` method/path pairs.
Python tests compare the selected domain surface with authoritative Pydantic
models, enums and live FastAPI routes. TypeScript tests pin the same selected
surface.

Focused client and component tests cover every currently exposed operation,
session selection, bounded turn rendering, pending-turn behavior without
fabricated assistant output, close, confirmed/cancelled delete, one conflict
refresh without mutation retry, and safe not-found/unavailable/server-error
rendering. Production React and API-client source, endpoint inventory,
packaged assets and prior Task 5D.1 security behavior were not expanded.

## Findings

No blocking or required follow-up finding remains.

Advisory only: retain the maintained operation-inventory update rule whenever
a future checkpoint changes `APIClient`. This does not require a separate
remediation task.

## Acceptance Criteria Disposition

| Acceptance criterion | Result |
| --- | --- |
| Browser and thread-start operational failures are fixed-safe | Met |
| Programming/resource/control-flow exception behavior is preserved | Met |
| Cleanup and browser-before-readiness invariants are unchanged | Met |
| Selected nested/enum/operation drift surface is complete | Met |
| Existing API-client and UI actions have bounded regression tests | Met |
| No production capability, endpoint or workflow behavior is added | Met |
| Task 5D.1A/1B/runtime/static/bootstrap/package compatibility remains | Met |
| Focused, frontend and full evidence is green | Met |
| Generated assets remain consistent | Met |
| Diff and role ownership stay within scope | Met |
| Worktree and upstream correlation are clean | Met |

## Architect Validation

Independently completed by the Architect:

- Git-derived Coder and Reviewer report correlation: passed;
- implementation and report ownership/diff scope: passed;
- line-by-line review of runtime helpers and their call sites: passed;
- review of frontend selected-contract fixture and Python drift checks:
  passed;
- review of current TypeScript `APIClient` against all nine fixture
  operations: passed;
- required focused Web group: `225 passed`;
- frontend strict TypeScript typecheck: passed;
- frontend Vitest: `29 passed` across four files;
- `git diff --check`: passed; and
- worktree remained clean before this Architect-owned report update.

The initial Vitest attempt could not write Vite's temporary cache under the
managed review sandbox. The identical command under normal repository
permissions passed `29/29`; this is environment-only and not a product or
test defect.

The Architect accepts the Coder and independently reproduced Reviewer
evidence for the full default suite (`2239 passed, 6 skipped`), packaging,
generated Playwright regressions, isolated compileall and byte-identical
frontend build. Repeating the full suite a third time was not necessary for
this bounded remediation disposition.

## Final Disposition

**Approved**

PMQA Task 5D.1C Attempt 2 passes final architecture review. Task 5D.1C is
complete. No further remediation is required.

## Next Recommended Task

Do not start Task 5D.2 on this long-running unmerged branch yet.

First complete a cumulative integration and release-boundary closure for
Task 5C and Task 5D.0–5D.1C, then prepare bounded PRs into `main`. The
recommended history-preserving split is:

1. Task 5C through its approved boundary;
2. Task 5D.0–5D.1C after Task 5C is present in `main`.

After both are merged and their post-merge documentation is closed, define
Task 5D.2A for provider-neutral Story acquisition and Skills Runner contract
alignment. PR creation, merge and Task 5D.2 remain outside this disposition.
