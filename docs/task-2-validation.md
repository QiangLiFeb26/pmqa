# Task 2 Validation

> **Historical record only.** This document records the Task 2 milestone as it
> behaved on 2026-07-18. The `explore` and `generate` commands shown below are
> retired compatibility stubs as of Task 5.9 and must not be used as current
> workflow instructions. They now return exit code 2 and perform no product,
> storage, or generator access. The current authoritative command is
> `pmqa task5-demo --product demo`; `test-generated` only executes existing
> generated regressions.

This record validates implementation commit
`a4dc889da605cc387e25f4832e6c971e55305d7c`. The tracked working tree was
clean when validation began. Pre-existing, unrelated planning documents were
untracked and excluded from the remediation.

## Environment

- Date: 2026-07-18
- Operating system: macOS 26.5.2 (build 25F84)
- Python: 3.9.6
- Browser: Playwright Chromium 1223

## Installation

The existing `.venv` was activated and the following documented installation
commands were validated:

```bash
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m playwright install chromium
```

Result: successful. Pip was upgraded from 21.2.4 to 26.0.1 before the editable
PEP 517 installation.

## Historical exploration result

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pmqa.cli explore --product demo
```

Result: successful. The artifact was written to
`products/demo/artifacts/knowledge.json`.

## Historical generation result

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pmqa.cli generate --product demo
```

Result: successful. Two tests were generated in
`products/demo/generated_tests/test_saucedemo_generated.py`.

## Offline tests

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests
```

Result: `11 passed` in 0.14 seconds. One dependency deprecation warning was
reported by LangGraph; it did not affect execution.

## Generated Playwright tests (still supported)

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pmqa.cli test-generated --product demo
```

Result: `2 passed` in 1.04 seconds.

The generated tests cover successful login and inventory-page verification.

## Provenance and outputs

- Reasoning provenance: `deterministic-rule-based`
- Artifact: `products/demo/artifacts/knowledge.json`
- Generated tests: `products/demo/generated_tests/test_saucedemo_generated.py`
- Generated test count: 2

## Known limitations

- Exploration is a bounded four-step SauceDemo product-pack flow, not a crawler.
- The historical Task 2 CLI vertical slice was not orchestrated by LangGraph
  and is now retired; its underlying libraries remain available for direct
  regression coverage.
- The normalizer is a basic sensitive-key boundary, not an enterprise scrubber.
- GitHub Copilot and external LLM reasoning are not implemented.
- Patrol and stale detection remain Task 3 work and were not started here.
