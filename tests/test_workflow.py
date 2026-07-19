"""Regression tests for retiring the Task 1 workflow skeleton."""

import importlib.util
import subprocess
import sys


def test_legacy_workflow_graph_is_not_an_active_module() -> None:
    assert importlib.util.find_spec("pmqa.workflow.graph") is None


def test_workflow_module_entry_point_rejects_retired_demo() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "pmqa.workflow"],
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode != 0
    assert "retired" in completed.stderr
    assert "pmqa.orchestration.build_pmqa_graph" in completed.stderr


def test_orchestration_import_loads_langgraph() -> None:
    statement = "\n".join(
        [
            "import sys",
            "from pmqa.orchestration import build_pmqa_graph, run_pmqa_workflow",
            "assert build_pmqa_graph and run_pmqa_workflow",
            "assert any(name == 'langgraph' or name.startswith('langgraph.') "
            "for name in sys.modules)",
        ]
    )
    completed = subprocess.run(
        [sys.executable, "-c", statement],
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
