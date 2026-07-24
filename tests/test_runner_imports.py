"""Import-isolation tests for the provider-neutral runner boundary."""

import subprocess
import sys


def test_runner_imports_are_product_neutral_and_side_effect_free() -> None:
    statement = "\n".join(
        [
            "import builtins, importlib, importlib.metadata, os, pathlib, sys",
            "from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_serializer, field_validator, model_validator",
            "before_path = tuple(sys.path)",
            "before_environment = dict(os.environ)",
            "original_open = builtins.open",
            "def forbidden(*args, **kwargs): raise AssertionError('import side effect')",
            "def audit(event, args):",
            " if event in ('subprocess.Popen', 'os.system'): forbidden()",
            "sys.addaudithook(audit)",
            "builtins.open = forbidden",
            "pathlib.Path.read_text = forbidden",
            "pathlib.Path.write_text = forbidden",
            "os.getenv = forbidden",
            "importlib.metadata.distributions = forbidden",
            "runners = importlib.import_module('pmqa.runners')",
            "mock = importlib.import_module('pmqa.runners.mock')",
            "assert runners.PMQARunner and runners.RunnerRequest and mock.MockRunner",
            "assert tuple(sys.path) == before_path",
            "assert os.environ == before_environment",
            "builtins.open = original_open",
            "blocked = (",
            " 'products.demo', 'pmqa_product_pack_saucedemo', 'playwright',",
            " 'langgraph', 'pmqa.workflow', 'pmqa.runtime', 'pmqa.supervisor',",
            " 'pmqa.orchestration', 'pmqa.reasoning', 'pmqa.trace', 'sqlite3',",
            " 'subprocess', 'tkinter', 'PySide6', 'streamlit'",
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


def test_top_level_pmqa_does_not_export_or_import_runners() -> None:
    statement = "\n".join(
        [
            "import sys",
            "import pmqa",
            "assert not hasattr(pmqa, 'PMQARunner')",
            "assert 'pmqa.runners' not in sys.modules",
        ]
    )
    completed = subprocess.run(
        [sys.executable, "-c", statement],
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
