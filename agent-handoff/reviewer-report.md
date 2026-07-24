# Independent Reviewer Report

Owner: Independent Reviewer

Status: Executed for PMQA Task 5C.6, Attempt 1

## Task Correlation

Task: PMQA Task 5C.6 — Append-Only Local AI Invocation Repository

Task ID: `PMQA-5C.6`

Attempt: `1`

Branch: `agent/task-5c-1-canonical-run-contract`

Reviewed Starting HEAD: `ce1334f4a096dd014170a8791d99969b40c4501b`

Reviewed Implementation Commit(s): `08dee16d43c02f42c32591e242b30bc4035033cb`
("add append-only usage repository")

Derived Coder Report Commit: `ecc11c7e5375ba8c5eba5f5b272841650d2eaf7d`
("report Task 5C.6 implementation")

Correlation Verification:

- derived with `git log -1 --format=%H -- agent-handoff/coder-report.md` ->
  `ecc11c7e5375ba8c5eba5f5b272841650d2eaf7d`;
- `git merge-base --is-ancestor ce1334f4a096dd014170a8791d99969b40c4501b HEAD`
  succeeds; `ce1334f...` is an ancestor of `08dee16...`, and `08dee16...` is
  an ancestor of `ecc11c7...` (linear sequence
  `ce1334f -> 08dee16 -> ecc11c7` on this branch);
- the Task 5C.5 baseline named by `current-task.md`,
  `efe5ee01ec9ddfa574eef74f333fb98ed46528b2`, is an ancestor of the recorded
  starting HEAD;
- the correlation header of `coder-report.md` at the derived commit names
  Task ID `PMQA-5C.6`, Attempt `1`, branch
  `agent/task-5c-1-canonical-run-contract`, and starting HEAD
  `ce1334f4a096dd014170a8791d99969b40c4501b`, matching `current-task.md`;
- `git diff --stat 08dee16..ecc11c7` touches only
  `agent-handoff/coder-report.md`, so the derived commit is the report's
  latest authorized change with no later unauthorized replacement.

This Reviewer report does not contain or predict its own commit SHA. The
Architect derives the Reviewer report commit from Git and records it in
`architect-review.md`.

## Independent Review Method

Inspection order completed:

1. `current-task.md` and acceptance criteria;
2. named baseline-to-implementation diff (`ce1334f..08dee16`) — full read of
   `pmqa/usage/repository.py` (all 634 lines) and `tests/test_usage_repository.py`
   (all 846 lines), plus the additive threaded regression in
   `tests/test_usage_collector.py`;
3. independently selected validation (see Test Evidence);
4. full `coder-report.md` (read only after steps 1-3).

Active-task `architect-review.md` read before publication: No

Prior closed review or architecture material consulted, with reason:
re-verified, via `git diff --stat`, that `pmqa/usage/collector.py`,
`pmqa/usage/contracts.py`, and `pmqa/usage/pricing.py` are byte-identical to
the Task 5C.5 baseline (empty diff), confirming the task's constraint that
collector production code must not change unless the new threaded regression
exposes a defect; no closed handoff report for this task was read.

## Review Depth

Actual Review Depth: Deep

Review Depth Reason: this checkpoint adds a security- and durability-
sensitive local filesystem persistence boundary (atomic no-replace
publication, descriptor ownership, symlink/TOCTOU resistance, corruption
detection) whose correctness cannot be assessed from test pass/fail counts
alone. I read the entire implementation file and the entire test file,
traced every I/O code path (save, get, find_by_session, find_by_run,
list_recent, and every internal helper) against the task's detailed
publication/read/corruption requirements, and independently executed all
listed validation commands. This matches the Coder's advisory recommendation
but was independently selected.

## Overall Assessment

The implementation is a rigorous, carefully-engineered local persistence
boundary that satisfies the task's publication, retrieval, corruption, and
security requirements. `pmqa/usage/repository.py` adds
`UsageRepositoryErrorCode` (10 fixed codes), `UsageRepositoryError`, a
`runtime_checkable` `UsageRepository` protocol, and
`LocalJSONUsageRepository`. No existing `pmqa/usage/collector.py`,
`contracts.py`, or `pricing.py` file was touched (confirmed via an empty
`git diff --stat` against those three paths), and the required durable
threaded collector regression
(`test_real_threads_terminalize_one_handle_exactly_once` in
`tests/test_usage_collector.py`, 8 real threads racing via a `Barrier` to
terminalize one handle) passed without needing any collector fix — this is
independent empirical confirmation that the Task 5C.5 lock-based exactly-once
design (which I flagged in the prior review as tested only sequentially) is
in fact correct under real thread contention.

I independently traced the publication mechanism: `save()` first
reconstructs an independent canonical snapshot
(`AIInvocationRecord.from_dict(record.to_dict())`, rejecting non-instances)
and enforces the byte-size bound entirely before any filesystem effect
(`test_invalid_record_fails_before_filesystem_effects`/
`test_non_record_value_fails_before_filesystem_effects` confirm `root` is
never even created). It then creates a mode-`0600` temporary file inside the
mode-`0700` `invocations/` directory via `tempfile.mkstemp` (same directory
as the target, avoiding cross-device link failures in the common case),
writes the full payload with a partial-write-safe loop, `fsync`s the file
descriptor, and publishes via `os.link(temporary_path, target)` — a
same-filesystem hard link, which is atomic and inherently no-replace at the
OS level (`FileExistsError` on an existing target, never silent overwrite).
This is the correct primitive for the stated constraint ("do not use
`os.replace()`, overwrite mode, unlink-and-retry, ... or a check-then-
overwrite sequence"). After a successful link, the directory entry is
`fsync`'d for durability, and the temporary name is unlinked only after
verifying (via captured `st_dev`/`st_ino` identity) that the path still
refers to the exact file this call created — preventing an unrelated file
from being deleted if the temporary name were somehow reused.
`errno.EXDEV`/`ENOSYS`/`ENOTSUP`/`EOPNOTSUPP` on `os.link` are mapped to a
distinct `UNSUPPORTED_PUBLICATION` code rather than silently degrading to a
weaker publish path. All of this is exercised by
`test_concurrent_instances_publish_exactly_once` (8 real threads via
`Barrier`, one success + seven `DUPLICATE_RECORD`),
`test_reader_observes_absent_then_complete_atomic_publication` (a
monkeypatched, `Event`-gated `os.link` proves a concurrent reader sees either
nothing or one complete record, never a partial one),
`test_publication_failure_preserves_existing_target_and_hides_detail`,
`test_unsupported_publication_is_distinct_and_leaves_no_record`,
`test_post_publication_failure_keeps_complete_record`,
`test_cleanup_never_unlinks_changed_temporary_identity`, and
`test_release_control_flow_failure_propagates_after_publication` (verifies a
resource exception raised during post-publication descriptor cleanup still
propagates by identity while the already-published record remains intact) —
I read and ran all of these.

Read-time corruption handling is equally thorough: `_read_record` re-`lstat`s
the path, rejects non-regular/symlink entries, opens with `O_NOFOLLOW` where
available, and re-verifies the opened descriptor's `(st_dev, st_ino)` against
the pre-open `lstat` — a real double-layered symlink-swap/TOCTOU defense that
I traced by hand: even without `O_NOFOLLOW` (e.g. a platform lacking it), a
symlink swapped in between the two stats would still be caught because
`fstat` on a followed descriptor reports the *target's* inode, which cannot
match the *symlink's own* inode captured by the earlier `lstat`.
`_parse_record` rejects duplicate JSON keys (`object_pairs_hook`), non-finite
constants (`parse_constant` override, catching the non-standard
`NaN`/`Infinity` tokens `json.loads` otherwise accepts silently), excessive
nesting (via `RecursionError`, safely caught, plus the inherited
`MAX_RUN_PAYLOAD_DEPTH`-bounded `AIInvocationRecord.from_dict()` check),
trailing non-whitespace data (`json.JSONDecodeError: Extra data`), and
byte-exact noncanonical formatting (`_canonical_bytes(record) != raw`, which
independently re-serializes with `sort_keys`/compact separators and compares
byte-for-byte against the file, catching reordered keys or extra whitespace
that `AIInvocationRecord.from_dict()`'s own structural-equality check would
not by itself distinguish). Filename/content digest mismatch is checked
separately. `_query` never swallows a `UsageRepositoryError` raised by
`_read_record` for a name-matching entry, so one corrupt file fails the
entire query rather than silently dropping it — I confirmed this by reading
the loop structure (no `try`/`except` around the per-entry `_read_record`
call) and by running `test_corrupt_matching_record_fails_entire_query`.

All 11 raises in `UsageRepositoryError.__init__`/call sites use `from None`
or otherwise suppress cause/context; expected-error tests thread a
`"runtime-secret-marker"` canary through paths, payloads, and monkeypatched
exception messages and confirm it never appears in any raised error's string
form. `MemoryError`/`KeyboardInterrupt`/`SystemExit`/`GeneratorExit` are
re-raised by identity (not just type) at every injection point tested
(`from_dict`, `os.read`, post-publication descriptor release).

All validation commands listed in `current-task.md`, run independently
rather than accepted from the Coder report, pass with no failures, errors,
or unexplained skips.

## Findings

None blocking. One trivial, non-blocking code-quality observation is
recorded under Suggested Architect Focus (a defensive-but-unreachable
equality check in `_parse_record`); it has no behavioral or security effect
and does not affect the verdict.

## Acceptance Criteria Coverage

| Acceptance criterion | Evidence | Result |
| --- | --- | --- |
| Publication is atomic, no-replace, and duplicate-safe under concurrency | `os.link()` hard-link publish (`repository.py:174-184`); `test_concurrent_instances_publish_exactly_once`, `test_save_snapshots_caller_and_duplicate_never_overwrites` independently run and pass | Met |
| No `os.replace()`, overwrite, unlink-and-retry, or check-then-overwrite path exists | Read `save()` in full: only `os.link` (never `os.replace`/`os.rename` for publication) and no pre-check of target existence before the atomic link attempt | Met |
| Temporary files are private, unidentifiable, and safely cleaned up | mode-`0600` `tempfile.mkstemp` in the private directory, no identifiers in the name (`_TEMPORARY_PREFIX`/`_TEMPORARY_SUFFIX` only), identity-verified unlink; `test_cleanup_never_unlinks_changed_temporary_identity`, `test_owned_descriptors_are_closed_once_and_success_cleans_temp` independently run and pass | Met |
| Reads reject symlink/non-regular entries, corruption, and digest mismatch without leaking detail | `_read_record`/`_parse_record` traced in full; `test_symlink_and_non_regular_record_entries_are_corrupt`, `test_corrupt_record_forms_fail_safely` (7 parametrized forms), `test_filename_content_digest_mismatch_is_corrupt`, `test_noncanonical_and_oversized_records_are_corrupt` independently run and pass | Met |
| Queries are deterministic (newest-first, ascending-ID tie-break), bounded, and fail closed on corruption | Double stable-sort in `_query` (`repository.py:447-448`) traced by hand; `test_queries_are_newest_first_with_ascending_id_tie_break`, `test_corrupt_matching_record_fails_entire_query`, `test_query_limits_are_exact_bounded_positive_integers` independently run and pass | Met |
| No raw dictionaries accepted/returned; results are independently reconstructed immutable tuples | `save()`/`get()`/queries all type-check for `AIInvocationRecord` and round-trip via `from_dict(to_dict())`; `test_empty_queries_missing_get_and_independent_query_results` mutates a returned record's `__dict__` and confirms no effect on a fresh read | Met |
| Fixed, marker-safe error vocabulary; resource/control-flow exceptions authoritative | 10-code `UsageRepositoryErrorCode`; all raises use `from None`; `test_release_control_flow_failure_propagates_after_publication`, `test_resource_and_control_flow_failures_propagate_before_io`, `test_resource_and_control_flow_read_failures_propagate` independently run and pass with identity-checked exceptions | Met |
| Import isolation; no database; no runtime dependency added | `tests/test_usage_imports.py` extended and independently rerun; `repository.py` imports only stdlib (`enum`, `errno`, `hashlib`, `json`, `os`, `pathlib`, `re`, `stat`, `sys`, `tempfile`, `typing`) plus `pmqa.run`/`pmqa.usage.contracts` | Met |
| No collector wiring, aggregation, CLI, parser, or cost calculation added; collector production code unchanged unless a defect was proven | `git diff --stat` confirms `collector.py`/`contracts.py`/`pricing.py` untouched; the required threaded regression passed without exposing a defect, so no fix was needed or made | Met |
| Real-wheel inclusion and output/temp-file exclusion | `tests/test_packaging.py` extended with `repository.py` inclusion and `artifacts/usage`/`.pmqa-usage-` exclusion assertions, independently rerun as part of the 332-test regression set | Met |
| All new and existing required tests pass | 199 focused + 332 regression + 98 Task 4 + 1760/5-skip full suite + 2 Playwright, all independently run, all pass | Met |
| Coder and Reviewer follow their exclusive write boundaries | `git diff --stat` from starting HEAD to the derived report commit touches only allowed implementation/test/doc/`.gitignore` paths plus `agent-handoff/coder-report.md`; no Architect/Reviewer file changed | Met |

## Test Evidence

### Coder Evidence Reviewed

The Coder report claims: 199 passed for focused repository + collector +
Task 5C.4 usage/pricing + import tests; 332 passed for the Run/Runner/
Application/boundary/packaging regression set; 98 passed for the Task 4
orchestration set (one pre-existing LangGraph deprecation warning); 1760
passed, 5 skipped for the full default suite; 2 passed for
`products/demo/generated_tests` (noting a transient macOS Chromium sandbox
permission denial on first launch, resolved on rerun); `compileall`,
Markdown-link validation, and `git diff --check` clean; clean worktree. This
claimed evidence was read only after independent execution below and matches
it exactly, except the Reviewer's environment did not encounter the noted
transient Chromium permission issue and did not independently run a
Markdown-link validator (not part of the task's listed Validation Commands).

### Independently Run

All commands below were executed by the Reviewer directly, before reading
the Coder's claimed results, from the repository root on the reviewed
branch:

- `.venv/bin/python -m pytest tests/test_usage_repository.py tests/test_usage_collector.py tests/test_usage_contracts.py tests/test_usage_pricing.py tests/test_usage_imports.py -q`
  -> `199 passed`
- `.venv/bin/python -m pytest tests/test_run_contracts.py tests/test_runner_contracts.py tests/test_application_contracts.py tests/test_application_service.py tests/test_boundary_policy.py tests/test_packaging.py -q`
  -> `332 passed`
- `.venv/bin/python -m pytest tests/test_workflow_runtime.py tests/test_workflow_reducer.py tests/test_supervisor_policy.py tests/test_langgraph_workflow.py -q`
  -> `98 passed, 1 warning` (pre-existing `LangChainPendingDeprecationWarning`,
  unrelated to this change)
- `.venv/bin/python -m pytest -q` (full default suite) -> `1760 passed, 5 skipped, 1 warning`
- `.venv/bin/python -m pytest products/demo/generated_tests -q` -> `2 passed`
- `PYTHONPYCACHEPREFIX=<isolated scratch directory> .venv/bin/python -m compileall -q pmqa products`
  -> exit code `0`, no output
- `git diff --check` -> exit code `0`, no output
- `git status --short` -> empty (clean worktree)

No listed validation command was left unrun. No test was skipped by
Reviewer choice. Environment: local `.venv` (Python 3.9), macOS/Darwin, no
network access used or required. The filesystem primitives exercised
(`os.link`, `O_NOFOLLOW`, `fsync`) all behaved as expected on this platform;
Windows-specific hard-link behavior was not exercised (noted under Suggested
Architect Focus).

## Security, Scope, and Compatibility

Security observations: the repository accepts and returns only exact
`AIInvocationRecord` instances (never raw dicts), so it structurally cannot
carry prompts, credentials, provider clients, or the Task 5C.5
`AIInvocationHandle`. All ten expected-error paths use bounded static
messages, suppress cause/context, and were independently confirmed (via a
canary marker threaded through paths/payloads/monkeypatched exceptions) to
never leak file paths, identifiers, JSON content, or underlying exception
text. The publication and read paths defend against TOCTOU/symlink-swap
races via captured device/inode identity comparisons rather than relying on
`O_NOFOLLOW` alone, which is a stronger guarantee than the task's minimum
"reject symlink/non-regular record entries" wording requires. No new
prohibited-key list was introduced; the repository reuses
`validate_run_identifier` from `pmqa.run` and `AIInvocationRecord.from_dict`
for reconstruction, as required.

Scope observations: the diff touches only `pmqa/usage/repository.py` (new),
`pmqa/usage/__init__.py` exports, one new focused test file, an additive
threaded-regression block in `tests/test_usage_collector.py`, small additive
blocks in `tests/test_packaging.py` and `tests/test_usage_imports.py`, one
new `.gitignore` line, and the four allowed documentation files, plus the
Coder-owned report in a separate commit. No file under `pmqa/run`,
`pmqa/runners`, `pmqa/application`, `pmqa/security`, or `products/` was
modified, and `pmqa/usage/collector.py`/`contracts.py`/`pricing.py` are
byte-identical to the Task 5C.5 baseline.

Compatibility observations: `pmqa.usage` still imports only from
`pmqa.run`/`pmqa.run.models` plus the standard library; no new runtime
dependency was added. All pre-existing suites listed in `current-task.md`,
plus the full default suite, pass unchanged.

## Verdict

Verdict: Pass

This verdict is advisory. The Architect makes the final technical
disposition.

## Suggested Architect Focus

- `_parse_record` (`pmqa/usage/repository.py:527-528`) contains
  `if record.to_dict() != value: raise ValueError` immediately after a
  successful `AIInvocationRecord.from_dict(value)` call. By construction,
  `from_dict()` only returns when the input is already `_plain_json_equal`
  to its own canonical re-serialization, which is strictly stronger than
  Python's native `!=`, so this specific line is defensively redundant and
  currently unreachable. This is harmless (no behavioral or security effect,
  and the *next* line's byte-exact `_canonical_bytes` comparison is the real,
  necessary canonical-formatting check) — purely a minor code-clarity note,
  not a defect.
- The publication mechanism depends on the target filesystem supporting
  same-directory hard links (`os.link`); this is well-handled (a distinct
  `UNSUPPORTED_PUBLICATION` code on `ENOSYS`/`ENOTSUP`/`EOPNOTSUPP`/`EXDEV`),
  but the Reviewer's environment is macOS/Darwin only — Windows NTFS hard-
  link behavior (permission requirements, `os.link` availability) was not
  exercised by either the Coder or this review. Worth confirming this is an
  acceptable scope limitation if the project ever targets Windows operators.
- The task explicitly scopes this repository to a "trusted local repository
  root" and disclaims protection against a malicious OS administrator; this
  is correctly reflected in the implementation (e.g., relying on directory/
  file mode bits rather than any stronger isolation) and documentation, and
  is not a gap against this checkpoint's stated acceptance criteria — noting
  it here only so the trust boundary is explicit for whoever designs the
  next checkpoint (collector-to-repository wiring) on top of it.

## Reviewer Write-Boundary Confirmation

Repository files changed by Reviewer:

- `agent-handoff/reviewer-report.md`

Confirmation: I changed no production code, tests, configuration, schemas,
packaging, scripts, product documentation, or another role's handoff file.
