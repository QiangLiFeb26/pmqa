# Independent Reviewer Report

Owner: Independent Reviewer

Status: Executed for PMQA Task 5C.6, Attempt 2

## Task Correlation

Task: PMQA Task 5C.6 — Repository Root and Platform Boundary Hardening

Task ID: `PMQA-5C.6`

Attempt: `2`

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed Starting HEAD: `a99f06cd95d583320257b4d5c5f8504d3281b0e1`

Reviewed Implementation Commit(s): `fdb075dcad311ee6848dab5e6454871e2d8ce56b`
("harden Task 5C.6 repository boundaries")

Derived Coder Report Commit: `9987f94a20bfc4a68d144f7cd9b4e1696a9eb52e`
("report Task 5C.6 boundary remediation")

Correlation Verification:

- derived with `git log -1 --format=%H -- agent-handoff/coder-report.md` ->
  `9987f94a20bfc4a68d144f7cd9b4e1696a9eb52e`;
- `git merge-base --is-ancestor a99f06cd95d583320257b4d5c5f8504d3281b0e1 HEAD`
  succeeds; `a99f06c...` is an ancestor of `fdb075d...`, and `fdb075d...` is
  an ancestor of `9987f94...` (linear sequence
  `a99f06c -> fdb075d -> 9987f94` on this branch);
- the reviewed Attempt 1 Reviewer HEAD named by `current-task.md`,
  `339191498e7b2a2cfcb473483f1f88509f06bc8a` (this Reviewer's own prior
  Attempt 1 report commit), is an ancestor of the recorded starting HEAD;
- the correlation header of `coder-report.md` at the derived commit names
  Task ID `PMQA-5C.6`, Attempt `2`, branch
  `agent/task-5c-1-canonical-run-contract`, and starting HEAD
  `a99f06cd95d583320257b4d5c5f8504d3281b0e1`, matching `current-task.md`;
- `git diff --stat fdb075d..9987f94` touches only
  `agent-handoff/coder-report.md`, so the derived commit is the report's
  latest authorized change with no later unauthorized replacement.

This Reviewer report does not contain or predict its own commit SHA. The
Architect derives the Reviewer report commit from Git and records it in
`architect-review.md`.

## Independent Review Method

Inspection order completed:

1. `current-task.md` and acceptance criteria (the Architect's F1/F2/F3
   remediation requirements and the three named adversarial gaps);
2. named baseline-to-implementation diff (`a99f06c..fdb075d`) — full read of
   the `pmqa/usage/repository.py` diff and the added/changed sections of
   `tests/test_usage_repository.py`;
3. independently selected validation (see Test Evidence), including
   reproducing all three original findings by hand against the remediated
   code, independent of the Coder's own tests;
4. full `coder-report.md` (read only after steps 1-3).

Active-task `architect-review.md` read before publication: No

Prior closed review or architecture material consulted, with reason: this
Reviewer authored the Attempt 1 review of this same task
(`agent-handoff/reviewer-report.md` at commit `3391914`, superseded by this
report) and is the source of the three findings this attempt remediates;
that prior review context is necessarily part of independently judging
whether F1-F3 are actually closed, so I compared the Attempt 1 code (via
`git diff a99f06c..fdb075d`) directly against my own recollection of the
reported gaps rather than re-deriving them from `architect-review.md`
(unread, per protocol).

## Review Depth

Actual Review Depth: Deep

Review Depth Reason: this is a remediation of three Architect-found
adversarial security/robustness gaps in a filesystem-persistence boundary
(path-traversal root validation, platform-capability fail-closed behavior,
parser-overflow containment); verifying a remediation genuinely closes the
named gaps — rather than superficially papering over them — requires reading
the actual validation logic line-by-line and independently reproducing the
original failure scenarios against the new code, not just running the
Coder's own tests. I did both. This matches the Coder's advisory
recommendation but was independently selected.

## Overall Assessment

All three remediation targets are correctly and robustly closed, with no
regressions to preserved behavior and no scope creep beyond the allowed
files (`pmqa/usage/repository.py`, `tests/test_usage_repository.py`,
`docs/architecture/usage-cost-contracts.md`, `agent-handoff/coder-report.md`
— confirmed via `git diff --stat`; `pmqa/usage/contracts.py`, `pricing.py`,
and `collector.py` are untouched).

**F1 (root validation).** The constructor now routes through a new
`_canonical_root` static method that: extracts one immutable string via
`os.fspath(root)` (severing any reference to a caller-controlled mutable
`Path` subclass before further validation — satisfying "retain one private
canonical path snapshot not controlled by a mutable caller object"); rejects
an embedded NUL explicitly in Python before any OS call could raise a raw
`ValueError` (the exact mechanism of the original finding); calls
`os.fsencode` to surface unrepresentable-path encoding failures early;
rejects any path containing a literal `..` path segment outright (a
conservative superset of "reject paths that could lexically or semantically
select the anchor after normalization" — it does not try to distinguish
"safe" `..` usage from unsafe, matching "do not silently rewrite a
traversal-containing operator path"); separately rejects paths whose
`os.path.normpath` result equals the anchor (catching non-`..` traversal
syntax such as bare `.` components); and, for a path that already exists,
uses `os.lstat` (never `os.stat`/`resolve()`, so symlinks are never
followed) to reject non-directory or symlink roots at construction time
rather than only at `save()` time as in Attempt 1. I independently
reproduced the original two path-based findings directly against the
remediated code (not via the Coder's tests) — see Test Evidence — and both
now raise `UsageRepositoryError` with code `INVALID_CONFIGURATION` and no
raw exception.

**F2 (platform capability boundary).** `save()` now calls
`_publication_capabilities()` first, which captures all eleven OS primitives
used by publication (`mkstemp`, `makedirs`, `fchmod`, `fstat`, `write`,
`fsync`, `link`, `open`, `lstat`, `unlink`, `close`) via
`getattr(module, name, None)` and fails closed with
`UNSUPPORTED_PUBLICATION` — before any directory or file is touched — if any
is missing/non-callable or if `os.name != "posix"` (a clean, deterministic
way to satisfy "full Windows support is not required... a fixed safe
unsupported result is acceptable" without needing Windows-specific
edge-case logic). After acquiring the temporary file, the code captures the
descriptor's identity, calls `fchmod`, then **re-stats and verifies** the
resulting mode actually has no group/other bits set — so a stub or
partially-functioning `fchmod` that doesn't raise but also doesn't actually
restrict permissions is still caught, not just an `fchmod` that raises. A
`NotImplementedError` from `fchmod` or `link` is caught by a dedicated
handler that classifies the failure as `UNSUPPORTED_PUBLICATION` before
publication or `PERSISTENCE_FAILURE` after (via a `published` flag set only
after a successful `link()`), correctly distinguishing "nothing was ever
published" from "the target now exists but a later step failed" — I traced
this flag through every branch and it is set in exactly one place,
immediately after the `else:` of a successful `link()` call. Directory
synchronization is exercised as a preflight (via `_preflight_directory_sync`,
called after directory creation but before any temporary file exists) so an
unavailable/unsupported sync capability is caught with zero temporary or
target files created — the Coder's own test asserts `mkstemp` was never even
called in this case, which I independently verified by reading the
assertion and re-running it. I independently reproduced the original
`os.fchmod`-absent finding directly against the remediated code (deleting
`os.fchmod` at runtime, bypassing the Coder's tests entirely) and confirmed
it now raises `UsageRepositoryError(UNSUPPORTED_PUBLICATION)` with zero
orphaned temporary files, rather than the original raw `AttributeError`.

**F3 (parser overflow).** `OverflowError` is added to the existing bounded
exception tuple in `_parse_record` (alongside `UnicodeError`,
`json.JSONDecodeError`, `UsageContractValidationError`, `ValueError`,
`RecursionError`), all mapped to `CORRUPT_DATA` with no cause/context/marker.
I confirmed this is correctly scoped to `_parse_record` only (not a
blanket catch elsewhere) and that `MemoryError`/`KeyboardInterrupt`/
`SystemExit`/`GeneratorExit` are still checked and re-raised before this
tuple in every affected `except` clause, so resource/control-flow exceptions
remain authoritative. The "real oversized/extreme numeric payload" test
(`1e1000000` as `duration_ms`) does not trigger a literal `OverflowError` in
this CPython version — I independently confirmed `json.loads("1e1000000")`
returns `inf`, not an exception — but the resulting `float('inf')` is then
correctly rejected by `AIInvocationRecord.from_dict()`'s existing strict-int
validation on `duration_ms`, landing in `CORRUPT_DATA` via the pre-existing
`UsageContractValidationError` branch. This is consistent with the task
wording, which explicitly allows "a bounded parser/**contract** rejection"
for the real-world case, reserving the literal `OverflowError` path for the
separate simulated (monkeypatched `json.loads`) test — both are present and
both pass.

All validation commands listed in `current-task.md`, run independently
rather than accepted from the Coder report, pass with no failures, errors,
or unexplained skips.

## Findings

None. All three remediation targets (F1, F2, F3) are verified closed by
independent code reading and independent reproduction outside the Coder's
own test suite.

## Acceptance Criteria Coverage

| Acceptance criterion | Evidence | Result |
| --- | --- | --- |
| Traversal/root-equivalent paths cannot target an anchor-level repository | `_canonical_root` (`repository.py:249-291`) rejects any `..` segment and any `normpath`-equivalent-to-anchor path; independently reproduced `Path("/tmp") / ".."`-style traversal -> `INVALID_CONFIGURATION`, no raw exception | Met |
| Invalid OS paths fail at construction with fixed safe errors | Embedded-NUL and unrepresentable-encoding checks in `_canonical_root`; independently reproduced embedded-NUL case -> `INVALID_CONFIGURATION`, not the original raw `ValueError` | Met |
| No raw `ValueError`/`AttributeError`/`NotImplementedError`/path/marker/platform message escapes | All three original raw-exception scenarios independently reproduced and now yield only `UsageRepositoryError` with a fixed code; `_assert_safe_error` pattern (marker/`__cause__`/`__context__` checks) independently spot-checked | Met |
| Missing/unsupported mandatory capabilities fail safely before publication | `_publication_capabilities()` gate before any I/O; `_preflight_directory_sync` before any temp/target file; independently reproduced missing `os.fchmod` -> `UNSUPPORTED_PUBLICATION`, zero orphans | Met |
| Supported-platform atomic no-replace semantics remain unchanged | `os.link()`-based publication mechanism itself untouched by this diff (only wrapped via the `capabilities.link` indirection); `test_concurrent_instances_publish_exactly_once` from Attempt 1 still passes unmodified | Met |
| Post-publication failure preserves the target | `published` flag correctly gates `NotImplementedError` classification; `test_post_publication_failure_keeps_complete_record` updated to target the second (post-publication) sync call specifically and independently rerun | Met |
| Descriptor and temporary ownership remain exactly controlled | `_release_temporary_ownership` extended to also suppress `NotImplementedError` during best-effort cleanup; identity-based unlink guard unchanged; independently rerun `test_owned_descriptors_are_closed_once_and_success_cleans_temp` (now 4 closes, consistent with the added preflight directory open/close) | Met |
| Parser overflow is fixed corrupt-data evidence | `OverflowError` added to the bounded exception tuple in `_parse_record`; both simulated and real-payload tests independently rerun and pass | Met |
| Existing repository, collector, contract, import, package, and orchestration regressions remain green | 215 focused + 332 regression + 98 Task 4 + 1776/5-skip full suite + 2 Playwright, all independently run, all pass | Met |
| Only allowed files changed | `git diff --stat a99f06c..fdb075d` shows exactly `pmqa/usage/repository.py`, `tests/test_usage_repository.py`, `docs/architecture/usage-cost-contracts.md`; `contracts.py`/`pricing.py`/`collector.py` untouched | Met |

## Test Evidence

### Coder Evidence Reviewed

The Coder report claims: 215 passed for repository + collector + Task 5C.4
usage/pricing + import tests (76 repository-only); 332 passed for the Run/
Runner/Application/boundary/packaging regression set; 98 passed for the
Task 4 orchestration set (one pre-existing LangGraph deprecation warning);
1776 passed, 5 skipped for the full default suite; 2 passed for
`products/demo/generated_tests`; `compileall` and `git diff --check` clean;
clean worktree. This claimed evidence was read only after independent
execution below and matches it exactly.

### Independently Run

All commands below were executed by the Reviewer directly, before reading
the Coder's claimed results, from the repository root on the reviewed
branch:

- `.venv/bin/python -m pytest tests/test_usage_repository.py tests/test_usage_collector.py tests/test_usage_contracts.py tests/test_usage_pricing.py tests/test_usage_imports.py -q`
  -> `215 passed`
- `.venv/bin/python -m pytest tests/test_run_contracts.py tests/test_runner_contracts.py tests/test_application_contracts.py tests/test_application_service.py tests/test_boundary_policy.py tests/test_packaging.py -q`
  -> `332 passed`
- `.venv/bin/python -m pytest tests/test_workflow_runtime.py tests/test_workflow_reducer.py tests/test_supervisor_policy.py tests/test_langgraph_workflow.py -q`
  -> `98 passed, 1 warning` (pre-existing `LangChainPendingDeprecationWarning`,
  unrelated to this change)
- `.venv/bin/python -m pytest -q` (full default suite) -> `1776 passed, 5 skipped, 1 warning`
- `.venv/bin/python -m pytest products/demo/generated_tests -q` -> `2 passed`
- `PYTHONPYCACHEPREFIX=<isolated scratch directory> .venv/bin/python -m compileall -q pmqa products`
  -> exit code `0`, no output
- `git diff --check` -> exit code `0`, no output
- `git status --short` -> empty (clean worktree)

In addition, and independent of the Coder's own tests, I directly
reproduced all three original Attempt-1 findings against the remediated
`LocalJSONUsageRepository` in an ad hoc script:

- `LocalJSONUsageRepository(Path(tmp) / "sub" / "..")` ->
  `UsageRepositoryError(INVALID_CONFIGURATION)` (previously accepted);
- `LocalJSONUsageRepository(Path(tmp) / ("runtime" + "\x00" + "marker"))` ->
  `UsageRepositoryError(INVALID_CONFIGURATION)` (previously a raw
  `ValueError: embedded null byte`);
- `save()` with `os.fchmod` deleted from the `os` module at runtime ->
  `UsageRepositoryError(UNSUPPORTED_PUBLICATION)` with zero `.pmqa-usage-*`
  orphan files left behind (previously a raw `AttributeError` and an
  orphaned temporary file).

No listed validation command was left unrun. No test was skipped by
Reviewer choice. Environment: local `.venv` (Python 3.9), macOS/Darwin
(`os.name == "posix"`), no network access used or required. As in the
Attempt 1 review, Windows-specific behavior (`os.name == "nt"`) was not
exercised on this platform; the implementation's `os.name != "posix"` gate
makes this an explicit, deterministic `UNSUPPORTED_PUBLICATION` rather than
untested behavior, which the task explicitly permits ("full Windows support
is not required").

## Security, Scope, and Compatibility

Security observations: all three findings are closed by validation that
runs strictly before the corresponding filesystem effect (root validation
before any I/O; capability/preflight checks before directory/temp/target
creation), not by catching and relabeling exceptions after damage is
already done — I confirmed this ordering by reading the control flow, not
just by trusting the test names. Every new/changed exception handler
continues to check `_RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS` first and
re-raise by identity, and every new fixed error uses `from None` with a
static message, consistent with the rest of the file. No new prohibited-key
list, arbitrary metadata surface, or weakened publication primitive was
introduced.

Scope observations: the diff touches only the three allowed implementation/
test/doc files plus the Coder-owned report in a separate commit. No file
under `pmqa/run`, `pmqa/runners`, `pmqa/application`, `pmqa/security`,
`pmqa/usage/contracts.py`, `pmqa/usage/pricing.py`, `pmqa/usage/collector.py`,
or `products/` was modified, and no general README/Roadmap/architecture
status text changed (only the one permitted focused-doc addition).

Compatibility observations: `UsageRepository`'s five public methods,
on-disk layout, digest naming, canonical byte format, query ordering/
limits, and duplicate/not-found semantics are all unchanged — confirmed by
reading the diff (all changes are internal to `save()`'s helper methods and
the new `_canonical_root`/`_publication_capabilities` additions) and by the
fact that every Attempt 1 test not directly touching root-validation or
platform-capability behavior continues to pass unmodified.

## Verdict

Verdict: Pass

This verdict is advisory. The Architect makes the final technical
disposition.

## Suggested Architect Focus

- All three F1-F3 findings from the Attempt 1 Architect review are
  independently confirmed closed (see Test Evidence for the ad hoc
  reproduction, not just the Coder's own tests). Nothing further is blocking
  from this Reviewer's independent inspection.
- `_prepare_write_directory` still creates the `invocations/` directory
  itself (via `capabilities.makedirs`) before `_preflight_directory_sync`
  runs; this means directory creation is not gated by the sync-capability
  preflight, only temporary/target file creation is. This appears
  intentional and harmless (an empty, identifier-free directory is not a
  "target" in the sense the task cares about, and it must exist for any
  future save attempt regardless), but is worth a one-line confirmation if
  the Architect intended "before target publication" to also cover the
  directory itself.
- The Attempt 1 non-blocking observations already recorded in this
  Reviewer's superseded report (a harmless dead-code equality check in
  `_parse_record`, and untested Windows hard-link behavior) still apply
  unchanged; neither was in scope for this remediation and neither blocks
  Pass here either.

## Reviewer Write-Boundary Confirmation

Repository files changed by Reviewer:

- `agent-handoff/reviewer-report.md`

Confirmation: I changed no production code, tests, configuration, schemas,
packaging, scripts, product documentation, or another role's handoff file.
