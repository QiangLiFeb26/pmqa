"""Import-isolation tests for the provider-neutral conversation package."""

import subprocess
import sys


def test_conversation_import_is_side_effect_free_and_runtime_isolated(
    tmp_path,
) -> None:
    statement = "\n".join(
        [
            "import pathlib, sys",
            "root = pathlib.Path(sys.argv[1])",
            "before = set(root.iterdir())",
            "import pmqa.conversation",
            "after = set(root.iterdir())",
            "assert before == after",
            "blocked = (",
            " 'fastapi', 'uvicorn', 'playwright', 'products',",
            " 'pmqa.orchestration', 'pmqa.workflow', 'pmqa.runtime',",
            " 'pmqa.supervisor', 'pmqa.reasoning', 'pmqa.trace',",
            " 'pmqa.application', 'pmqa.runners', 'pmqa.product_pack',",
            " 'langgraph', 'subprocess', 'tkinter', 'PySide6', 'streamlit',",
            " 'node', 'react'",
            ")",
            "for prefix in blocked:",
            " assert not any(name == prefix or name.startswith(prefix + '.') for name in sys.modules), prefix",
        ]
    )
    completed = subprocess.run(
        [sys.executable, "-c", statement, str(tmp_path)],
        cwd=tmp_path,
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert tuple(tmp_path.iterdir()) == ()


def test_generic_pmqa_and_cli_imports_remain_conversation_lazy() -> None:
    for import_statement in ("import pmqa", "import pmqa.cli"):
        statement = "\n".join(
            [
                "import sys",
                import_statement,
                "assert 'pmqa.conversation' not in sys.modules",
                "assert not hasattr(sys.modules['pmqa'], 'ConversationSession')",
            ]
        )
        completed = subprocess.run(
            [sys.executable, "-c", statement],
            capture_output=True,
            check=False,
            text=True,
        )

        assert completed.returncode == 0, completed.stderr


def test_conversation_import_does_not_open_sqlite_database() -> None:
    statement = "\n".join(
        [
            "import sqlite3",
            "def fail(*args, **kwargs):",
            " raise AssertionError('sqlite connect called during import')",
            "sqlite3.connect = fail",
            "import pmqa.conversation",
        ]
    )
    completed = subprocess.run(
        [sys.executable, "-c", statement],
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
