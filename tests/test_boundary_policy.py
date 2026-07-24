"""Tests for shared and boundary-specific prohibited-key policy."""

import subprocess
import sys

from pmqa.security.boundary_policy import (
    COMMON_PROHIBITED_KEYS,
    REASONING_PROHIBITED_KEYS,
    RUN_PAYLOAD_PROHIBITED_KEYS,
    RUN_PAYLOAD_PROHIBITED_KEY_EXTENSIONS,
    WORKFLOW_STATE_PROHIBITED_KEYS,
    WORKFLOW_STATE_PROHIBITED_KEY_EXTENSIONS,
)


def test_common_policy_is_included_in_every_boundary() -> None:
    assert COMMON_PROHIBITED_KEYS <= REASONING_PROHIBITED_KEYS
    assert COMMON_PROHIBITED_KEYS <= WORKFLOW_STATE_PROHIBITED_KEYS
    assert COMMON_PROHIBITED_KEYS <= RUN_PAYLOAD_PROHIBITED_KEYS


def test_boundary_specific_policy_differences_are_explicit() -> None:
    assert REASONING_PROHIBITED_KEYS == COMMON_PROHIBITED_KEYS
    assert WORKFLOW_STATE_PROHIBITED_KEYS == (
        COMMON_PROHIBITED_KEYS | WORKFLOW_STATE_PROHIBITED_KEY_EXTENSIONS
    )
    assert WORKFLOW_STATE_PROHIBITED_KEY_EXTENSIONS == {
        "connection",
        "llm_client",
        "locator",
        "provider_instance",
    }
    assert RUN_PAYLOAD_PROHIBITED_KEYS == (
        WORKFLOW_STATE_PROHIBITED_KEYS
        | RUN_PAYLOAD_PROHIBITED_KEY_EXTENSIONS
    )
    assert {
        "command",
        "environment",
        "executable_path",
        "page",
        "prompt",
        "response",
        "stderr",
        "stdout",
    } <= RUN_PAYLOAD_PROHIBITED_KEY_EXTENSIONS


def test_shared_policy_import_has_no_high_level_side_effects() -> None:
    statement = "\n".join(
        [
            "import sys",
            "from pmqa.security.boundary_policy import COMMON_PROHIBITED_KEYS",
            "assert COMMON_PROHIBITED_KEYS",
            "for prefix in ('pmqa.providers', 'pmqa.runtime', 'langgraph', 'playwright'):",
            "    assert not any(name == prefix or name.startswith(prefix + '.') "
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
