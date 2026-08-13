"""Import-isolation tests for the canonical PMQA Run Contract."""

import subprocess
import sys


def test_run_contract_import_is_product_neutral_and_side_effect_free() -> None:
    statement = "\n".join(
        [
            "import builtins, importlib, importlib.metadata, os, pathlib, subprocess, sys",
            "from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_serializer, field_validator, model_validator",
            "before_path = tuple(sys.path)",
            "before_environment = dict(os.environ)",
            "original_open = builtins.open",
            "def forbidden(*args, **kwargs): raise AssertionError('import side effect')",
            "builtins.open = forbidden",
            "pathlib.Path.read_text = forbidden",
            "pathlib.Path.write_text = forbidden",
            "os.getenv = forbidden",
            "importlib.metadata.distributions = forbidden",
            "subprocess.Popen = forbidden",
            "run = importlib.import_module('pmqa.run')",
            "assert run.RunRequest and run.RunRecord and run.WorkflowDefinition",
            "assert tuple(sys.path) == before_path",
            "assert os.environ == before_environment",
            "builtins.open = original_open",
            "blocked = (",
            " 'products.demo', 'pmqa_product_pack_saucedemo', 'playwright',",
            " 'langgraph', 'pmqa.workflow', 'pmqa.runtime', 'pmqa.supervisor',",
            " 'pmqa.orchestration', 'pmqa.reasoning', 'pmqa.trace', 'sqlite3',",
            " 'tkinter', 'PySide6', 'streamlit'",
            ")",
            "for prefix in blocked:",
            " assert not any(name == prefix or name.startswith(prefix + '.') for name in sys.modules), prefix",
        ]
    )
    completed = subprocess.run(
        [sys.executable, "-c", statement],
        capture_output=True,
        check=False,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_top_level_pmqa_does_not_export_or_eagerly_import_run_contracts() -> None:
    statement = "\n".join(
        [
            "import sys",
            "import pmqa",
            "assert not hasattr(pmqa, 'RunRecord')",
            "assert 'pmqa.run' not in sys.modules",
        ]
    )
    completed = subprocess.run(
        [sys.executable, "-c", statement],
        capture_output=True,
        check=False,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
