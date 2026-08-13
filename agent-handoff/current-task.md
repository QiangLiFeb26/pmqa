# Current Task

Owner: Architect

Task: PMQA Task 5C Final PR Preparation

Task ID: `PMQA-5C-PR`

Attempt: `1`

Status: Approved — Awaiting Human Merge Authorization

Branch: `agent/task-5c-cumulative-closure`

Main base:
`d0186f2f8d37e3b52029a8c3195226e4432a6b43`

Approved Task 5C implementation boundary:
`9d2ba638c9692eb542bb6d1c023388d959573316`

Approved cumulative closure documentation commit:
`e4cceed2c25953a168453670c0a408ba233fe388`

Prior cumulative-closure Independent Reviewer report commit:
`2432cd1a256fac6bea9e5cd47195bab21133289f`

Coder starting HEAD: derive and record the latest pushed branch commit that
contains this task publication before changing any authorized file.

Repository Markdown and Git history are authoritative. Chat summaries are
informational only.

Architect final disposition: PMQA-5C-PR Attempt 1 and PR #24 passed Deep
Independent Reviewer and Architect review. No Coder implementation work
remains in this attempt. The Human must explicitly authorize or defer merge.
If authorized, the merge operator must verify the live PR head is a linear
descendant of Reviewer report `05b73e52a87e996c2ca1e4150c0f05e17ca9d9c3`,
the base remains `d0186f2f8d37e3b52029a8c3195226e4432a6b43`, the PR
remains mergeable/clean with the same 47-file Task-5C-only scope, and then use
a merge commit without deleting the preserved Task 5D branch. Do not start a
post-merge task until the actual merge commit is known.

## Task Objective

Advance the already approved Task 5C release documentation from the
pre-review state to the post-review state, publish the exact Task-5C-only
branch, and create one non-draft PR to `main` for independent final
verification and Human-controlled merge.

This is a documentation/status and PR-publication task. The Task 5C runtime,
contracts, tests, schemas, packaging and historical commits are already
approved and must not change.

## Background

PMQA-5C-CLOSURE Attempt 1 passed Deep Independent Reviewer and Architect
review. The closure documentation correctly said "ready for independent
cumulative review" when it was written. That review is now complete, so the
status language must move forward exactly once before the final PR.

The Human previously approved the two-PR release strategy: Task 5C enters
`main` first; Task 5D remains on its separate preserved branch and must not
enter this PR.

Work only in the isolated worktree for
`agent/task-5c-cumulative-closure`. Do not switch or modify the primary PMQA
checkout that preserves Task 5D work.

## Required Work

1. Derive the exact Architect publication commit from Git and verify the
   active branch, upstream, clean worktree and ancestry.
2. Update only the seven already-authorized Task 5C product documents so
   they consistently state:
   - Task 5C.1–5C.7 passed checkpoint, cumulative closure, independent and
     final architecture review;
   - the Task-5C-only branch is ready for its final PR;
   - Task 5C remains unmerged and is not yet `Complete` on `main`;
   - the exact main base and approved Task 5C boundary remain unchanged;
   - Task 5D is excluded from this branch and PR; and
   - Usage/Cost remains a foundation, not a live provider adapter, parser,
     pricing calculator, optimizer, CLI summary or UI.
3. Commit that documentation-only status transition without amending prior
   commits.
4. Run the bounded validation below and push the branch.
5. Create one non-draft GitHub PR from
   `agent/task-5c-cumulative-closure` to `main` with a concise title and
   description that identify Task 5C.1–5C.7, the approved boundary, tests,
   Task 5D exclusion and known zero-checks status if GitHub has no checks.
6. Do not merge the PR and do not delete either branch.
7. Replace `agent-handoff/coder-report.md`, commit it separately and push it.
   Report the PR URL, exact base/head SHAs, mergeability/conflicts/checks, all
   validation evidence and the recommended independent review depth.

## Allowed Changes

- `README.md`;
- `docs/Roadmap.md`;
- `docs/architecture.md`;
- `docs/architecture/application-service.md`;
- `docs/architecture/run-contract.md`;
- `docs/architecture/runner-boundary.md`;
- `docs/architecture/usage-cost-contracts.md`;
- `agent-handoff/coder-report.md`.

GitHub-side creation of one PR is authorized. No merge, review dismissal,
branch deletion, label/milestone mutation or unrelated GitHub write is
authorized.

## Out of Scope

Do not:

- modify production code, tests, fixtures, schemas, packaging, dependencies,
  scripts, generated assets, Product Packs or product code;
- modify another role's handoff file;
- alter, rebase, squash, amend, cherry-pick or merge historical commits;
- merge `main`, the Task 5D branch or any other branch into this branch;
- include Task 5D Web, conversation, frontend or TypeScript files;
- start Task 5D.2, Skill Repo/ADO/Copilot integration, Task 5B, Task 6 or
  Task 7;
- merge the PR.

If the PR diff includes any unexplained file, any Task 5D file, or the base is
not the exact main commit above, stop and report a blocker without repairing
history.

## Acceptance Criteria

- only the seven allowed product documents change in the status-transition
  commit;
- all seven documents say cumulative architecture review passed and final PR
  ready, while still unmerged and not Complete on main;
- no stale "ready for independent cumulative review" status remains in the
  active Task 5C documentation;
- exact Task 5C boundaries and capability limitations remain accurate;
- the PR targets exact `main` base `d0186f2...` and contains no Task 5D file;
- the cumulative PR diff remains the known 47-file Task 5C inventory plus
  authorized handoff history, with no runtime change after the approved
  boundary;
- focused, packaging, full and generated-test regressions pass;
- Markdown links and `git diff --check` pass;
- local, upstream and GitHub branch heads agree;
- one non-draft PR exists and is not merged;
- the worktree is clean.

## Validation Commands

Use this worktree's dedicated `.venv`; do not reuse the primary Task 5D
checkout's editable environment.

```bash
.venv/bin/python -m pytest \
  tests/test_run_contracts.py tests/test_run_imports.py \
  tests/test_runner_contracts.py tests/test_runner_imports.py \
  tests/test_mock_runner.py \
  tests/test_application_contracts.py tests/test_application_imports.py \
  tests/test_application_registry.py tests/test_application_service.py \
  tests/test_usage_contracts.py tests/test_usage_imports.py \
  tests/test_usage_pricing.py tests/test_usage_collector.py \
  tests/test_usage_repository.py tests/test_usage_summary.py \
  tests/test_boundary_policy.py -q
.venv/bin/python -m pytest tests/test_packaging.py -q
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest products/demo/generated_tests -q
.venv/bin/python -m compileall -q pmqa products
git diff --check
git status --short
```

Use an isolated bytecode cache for compileall. Validate all tracked Markdown
relative links. Do not use company systems, provider logins, paid models,
browsers or external runtime services during tests.

## Expected Deliverables

- one minimal seven-file documentation status-transition commit;
- one open non-draft Task 5C PR to exact `main`;
- exact PR base/head, mergeability, conflict and checks evidence;
- one separate Coder report commit;
- a clean synchronized branch;
- no merge and no Task 5D change.

## Required Coder Handoff

Replace `agent-handoff/coder-report.md` with a complete report containing:

- Task ID `PMQA-5C-PR`, Attempt `1`, exact branch and Git-derived starting
  HEAD;
- documentation status-transition commit;
- changed files and exact wording transition;
- PR URL/title/base/head/state, mergeability/conflicts/checks;
- proof the PR contains no Task 5D file or post-boundary runtime change;
- every required validation result;
- remaining risks/open items;
- scope confirmation;
- Recommended Review Depth: `Light`, `Standard`, or `Deep`;
- Review Recommendation Reason; and
- Suggested Review Focus.

Do not record the future Coder report commit SHA inside the report. The
Independent Reviewer derives it from Git.

After committing and pushing the report, send the Human a 5–10 line Human
Summary and this exact style of one-sentence Handoff Note.
