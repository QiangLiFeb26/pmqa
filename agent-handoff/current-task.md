# Current Task

Owner: Architect

Task: PMQA Task 5C Cumulative Release-Boundary Closure

Task ID: `PMQA-5C-CLOSURE`

Attempt: `1`

Status: Ready for Coder

Branch: `agent/task-5c-cumulative-closure`

Main base:
`d0186f2f8d37e3b52029a8c3195226e4432a6b43`

Approved Task 5C boundary:
`9d2ba638c9692eb542bb6d1c023388d959573316`

The first Task 5D implementation/documentation commit is not part of this
branch. The complete approved Task 5D.0–5D.1C history remains preserved on
`agent/task-5c-1-canonical-run-contract` at Architect disposition
`9d40cff034190b096a51d1b4deeeac2961205462`.

Coder starting HEAD: derive and record the latest pushed branch commit that
contains this task publication before changing any authorized file.

Repository Markdown and Git history are authoritative. Chat summaries are
informational only.

## Task Objective

Perform one cumulative release-boundary audit of Task 5C.1–5C.7, close stale
documentation, and leave a coherent Task-5C-only branch ready for independent
review and a later bounded PR into `main`.

This is a release-closure and evidence task, not a new implementation task.
Do not redesign or extend the Run, Runner, Application, Usage, AI-team, Task 4,
Task 5, or Product Pack architecture. Do not create a PR or merge.

## Background

Task 5C established, in reviewed checkpoints:

- the canonical provider-neutral PMQA Run Contract;
- the synchronous Runner boundary and deterministic MockRunner;
- explicit Workflow and Runner registries plus the single-attempt Application
  Service;
- provider-neutral AI usage and cost evidence contracts;
- the exactly-once invocation collector;
- the append-only local Usage Repository; and
- deterministic usage summaries that preserve reported, estimated,
  subscription-included, unavailable and zero semantics.

The approved AI-team handoff protocol was introduced during the same branch
history as repository-process infrastructure. It is intentionally included
in this Task 5C PR boundary, but it is not a runtime capability and must remain
provider-neutral and Markdown-only.

Task 5C has passed checkpoint-level architecture review but has never entered
`main`. Task 5D work must not enter this branch or this future PR.

## Required Audit 1 — Exact Git and Scope Boundary

Derive and report, from Git rather than prose:

- `main` base `d0186f2...`;
- Task 5C release boundary `9d2ba63...`;
- the ordered Task 5C.1–5C.7 implementation, remediation, Coder report,
  Reviewer report and Architect disposition commits;
- the AI-team protocol commits included within that history;
- changed-file inventory grouped by Run, Runner, Application, Usage,
  security/import/packaging, tests, documentation and handoff protocol; and
- proof that no Task 5D production, Web, conversation or frontend file is
  present in `main..HEAD` on this closure branch.

Do not rebase, squash, amend, cherry-pick or rewrite any historical commit.
Do not merge the long-running 5D branch into this branch.

If the branch contains any Task 5D implementation or any unexplained file,
stop and report it as a blocker instead of deleting or rewriting history.

## Required Audit 2 — Cumulative Architecture Coherence

Confirm from source and tests that the combined Task 5C surface remains
coherent:

- `pmqa.run` owns application-level request, definition, context, result,
  artifact, error, invocation, run-record and outcome-metric contracts;
- `pmqa.runners` owns the provider-neutral execution boundary, canonical
  request/response correlation and runtime-only cancellation;
- `pmqa.application` owns explicit local Workflow/Runner registration,
  workflow-specific validation and one deterministic attempt;
- `pmqa.usage` remains a separate trust/retention boundary for model/provider
  invocation evidence, pricing evidence, collection, persistence and pure
  summary aggregation;
- Run records do not absorb prompts, provider SDK objects, usage records,
  pricing tables, conversation state, workflow checkpoints or credentials;
- Usage records do not claim workflow success, external effects, complete
  provider-session totals or invented token/cost values;
- reported, CLI-parsed, estimated, subscription-included and unavailable
  evidence remain distinguishable;
- zero remains different from unavailable;
- registries remain explicit and bounded, with no discovery or path scanning;
- generic imports remain product-, provider-, Playwright-, LangGraph-,
  repository- and process-lazy as documented; and
- Task 4/5/Product Pack behavior remains compatible.

This task must not reopen already settled checkpoint design choices merely to
prefer another style. A concrete cumulative defect is a blocker: document it
in the Coder report and stop for Architect direction rather than repairing it
inside this closure task.

## Required Audit 3 — Documentation Closure

Review all current Task 5C status claims and make only the minimum necessary
documentation updates so they consistently state:

- Task 5C.1–5C.7 passed checkpoint-level and cumulative closure verification;
- the branch is ready for independent cumulative review and a later final PR;
- Task 5C is not yet merged and therefore is not yet `Complete` on `main`;
- exact main base and approved Task 5C boundary SHAs;
- Task 5D is excluded from this release branch;
- Usage/Cost remains a foundation, not a live Copilot/Azure/OpenAI adapter,
  parser, calculator, optimizer, CLI summary or UI; and
- Task 5B, Task 6 and Task 7 remain not started.

Likely documentation surfaces are `README.md`, `docs/Roadmap.md`,
`docs/architecture.md`, and the existing Task 5C architecture documents.
Change only files with genuinely stale or incomplete cumulative status. Do
not rewrite historical checkpoint wording when it is clearly labeled as
historical context.

Do not describe Task 5D work as merged, included or delivered by this branch.

## Required Audit 4 — Release and Packaging Evidence

Verify the real PMQA wheel and source tree expose the intended Task 5C Python
packages and exclude tests, build debris, runtime artifacts, usage records,
credentials and unrelated files according to the existing packaging policy.

Confirm all default tests remain offline and no new validation requires a
company system, paid model, provider login, browser or external network.

## Allowed Changes

Only when needed to close cumulative status wording:

- `README.md`;
- `docs/Roadmap.md`;
- `docs/architecture.md`;
- existing Task 5C architecture Markdown under `docs/architecture/`;
- `agent-handoff/coder-report.md`.

Do not modify:

- production Python or TypeScript;
- tests, fixtures or schemas;
- dependency or packaging configuration;
- generated or packaged assets;
- Product Pack or product code;
- another role's handoff file.

If a production, test, schema or packaging change appears necessary, stop and
report the exact blocker. The Architect will define a separate remediation
attempt if warranted.

Use one minimal documentation closure commit and one separate report-only
Coder handoff commit. Do not amend prior commits.

## Out of Scope

Do not:

- add or change runtime behavior;
- start Task 5D.2 or any Skill Repo/ADO/Copilot integration;
- add a real runner, provider adapter, CLI parser, cost calculator, pricing
  table, optimizer, usage CLI or usage UI;
- modify conversation, Web, frontend or Task 5D files;
- create, update or merge a PR;
- merge `main` or another branch;
- rebase, squash, cherry-pick or rewrite history;
- start Task 5B, Task 6 or Task 7.

## Acceptance Criteria

- branch history is exactly based on `d0186f2...` and stops at the approved
  Task 5C boundary plus this closure work;
- no Task 5D production/Web/conversation/frontend change appears in the
  cumulative diff;
- all Task 5C.1–5C.7 checkpoint surfaces and the AI-team protocol are
  inventoried and explained;
- no cumulative contract, correlation, security, import-isolation or
  packaging defect is found, or any genuine defect is reported without an
  unauthorized repair;
- documentation consistently says Task 5C is cumulative-review/PR-ready but
  unmerged;
- no live usage/provider capability is overstated;
- focused, packaging, full and generated-test regressions pass;
- Markdown links and `git diff --check` pass;
- only allowed documentation/report files change;
- local and remote branch heads agree and the worktree is clean;
- no PR is created and nothing is merged.

## Validation Commands

Run and report at minimum:

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

Use an isolated bytecode cache for `compileall`. Validate tracked Markdown
relative links with the existing repository method or an equivalent read-only
check. Do not access a company system, provider, paid model, browser or
external network during tests.

## Expected Deliverables

- a Git-derived cumulative Task 5C checkpoint and changed-file inventory;
- a cumulative architecture, isolation, packaging and regression audit;
- minimal accurate Task 5C status documentation;
- one documentation-only closure commit;
- one separate report-only Coder handoff commit;
- a clean synchronized `agent/task-5c-cumulative-closure` branch;
- no PR, merge or Task 5D work.

## Required Coder Handoff

Replace `agent-handoff/coder-report.md` with a complete report containing:

- Task ID, Attempt and exact branch;
- Git-derived starting HEAD;
- documentation closure implementation commit;
- exact Task 5C boundary and cumulative commit/file inventory;
- changed files and status wording before/after;
- cumulative architecture findings;
- focused, packaging, full, generated-test, compileall, Markdown-link and Git
  validation results;
- remaining risks or open items;
- explicit scope confirmation;
- Recommended Review Depth: `Light`, `Standard`, or `Deep`;
- Review Recommendation Reason; and
- Suggested Review Focus.

End the report with the mandatory 5–10 line Human Summary and one-sentence
Handoff Note defined by `agent-handoff/README.md`.
