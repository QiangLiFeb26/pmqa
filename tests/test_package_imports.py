"""Regression tests for package-level public import order."""

import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    "statement",
    [
        (
            "import pmqa.trace; "
            "from pmqa.reasoning import ReasoningExecutionService; "
            "assert ReasoningExecutionService.__name__ == "
            "'ReasoningExecutionService'"
        ),
        (
            "import pmqa.reasoning; "
            "from pmqa.trace import TraceRecord; "
            "assert TraceRecord.__name__ == 'TraceRecord'"
        ),
    ],
)
def test_reasoning_and_trace_imports_are_order_independent(statement: str) -> None:
    completed = subprocess.run(
        [sys.executable, "-c", statement],
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
