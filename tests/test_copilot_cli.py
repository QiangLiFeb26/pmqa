"""Offline tests for the GitHub Copilot CLI reasoning transport."""

import json
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from pmqa.reasoning import (
    CliExecutionResult,
    CopilotCliConfig,
    CopilotCliExecutionError,
    CopilotCliReasoningProvider,
    CopilotCliRunner,
    CopilotCliTimeoutError,
    CopilotCliUnavailableError,
    DeterministicReasoningScrubber,
    ManualCopilotReasoningProvider,
    ReasoningDecision,
    ReasoningResponse,
    ReasoningStatus,
    ReasoningValidationError,
    ScrubInput,
    SubprocessCopilotCliRunner,
    build_copilot_command,
)


class FakeCopilotCliRunner(CopilotCliRunner):
    """Returns configured process evidence without invoking an executable."""

    def __init__(
        self,
        result: CliExecutionResult,
        *,
        available: bool = True,
    ) -> None:
        self.result = result
        self.available = available
        self.command = None
        self.prompt = None
        self.timeout_seconds = None

    def is_available(self, executable: str) -> bool:
        return self.available

    def run(self, *, command, prompt, timeout_seconds) -> CliExecutionResult:
        self.command = command
        self.prompt = prompt
        self.timeout_seconds = timeout_seconds
        return self.result


def test_cli_provider_rejects_unsafe_request_before_runner() -> None:
    runner = _runner(_response_json())
    request = _safe_request().model_copy(update={"metadata": {"token": "fake-token"}})

    with pytest.raises(ReasoningValidationError, match="metadata.token"):
        _provider(runner).reason(request)
    assert runner.command is None


def test_prompt_rendering_is_shared_with_manual_provider() -> None:
    request = _safe_request()
    cli_package = _provider(_runner(_response_json())).prepare(request)
    manual_package = ManualCopilotReasoningProvider().prepare(request)

    assert cli_package.request_json == manual_package.request_json
    assert cli_package.response_schema_json == manual_package.response_schema_json
    assert cli_package.request_hash == manual_package.request_hash
    common_instruction = "Use only the structured product knowledge in REQUEST_JSON below."
    assert common_instruction in cli_package.prompt_text
    assert common_instruction in manual_package.prompt_text
    assert 'Set provider to "github-copilot-cli"' in cli_package.prompt_text


def test_command_arguments_are_deterministic_tokens() -> None:
    config = _config(arguments=["reason", "--stdin", "--format=json"])

    assert build_copilot_command(config) == [
        "copilot",
        "reason",
        "--stdin",
        "--format=json",
    ]
    assert build_copilot_command(config) == build_copilot_command(config)


def test_fake_runner_receives_prompt_through_explicit_stdin_boundary() -> None:
    runner = _runner(_response_json())

    response = _provider(runner).reason(_safe_request())

    assert isinstance(response, ReasoningResponse)
    assert isinstance(response.decisions[0], ReasoningDecision)
    assert runner.command == ["copilot", "reason", "--stdin"]
    assert "REQUEST_JSON:" in runner.prompt
    assert runner.timeout_seconds == 30.0


def test_subprocess_runner_uses_argument_list_stdin_and_no_shell() -> None:
    completed = SimpleNamespace(returncode=0, stdout=_response_json(), stderr="")
    runner = SubprocessCopilotCliRunner()

    with patch("pmqa.reasoning.copilot_cli.subprocess.run", return_value=completed) as run:
        result = runner.run(
            command=["copilot", "reason"],
            prompt="safe prompt",
            timeout_seconds=12.0,
        )

    assert result.exit_code == 0
    run.assert_called_once_with(
        ["copilot", "reason"],
        input="safe prompt",
        capture_output=True,
        check=False,
        shell=False,
        text=True,
        timeout=12.0,
    )


def test_valid_fake_cli_output_returns_typed_response() -> None:
    response = _provider(_runner(_response_json())).reason(_safe_request())

    assert response.provider == "github-copilot-cli"
    assert response.model == "copilot-cli"


@pytest.mark.parametrize(
    ("field", "value", "error_type", "message"),
    [
        ("request_id", "wrong", ReasoningValidationError, "must match"),
        ("provider", "github-copilot-manual", CopilotCliExecutionError, "provider"),
        ("model", "another-model", CopilotCliExecutionError, "configured model"),
    ],
)
def test_response_correlation_and_provenance_are_enforced(
    field, value, error_type, message
) -> None:
    payload = _response_payload()
    payload[field] = value

    with pytest.raises(error_type, match=message):
        _provider(_runner(json.dumps(payload))).reason(_safe_request())


@pytest.mark.parametrize(
    "stdout",
    [
        "",
        "{not-json}",
        "Result: " + json.dumps({"not": "accepted"}),
    ],
)
def test_empty_malformed_and_prose_output_are_rejected(stdout: str) -> None:
    with pytest.raises(CopilotCliExecutionError):
        _provider(_runner(stdout)).reason(_safe_request())


def test_non_zero_exit_is_rejected_without_stderr_disclosure() -> None:
    fake_stderr = "authentication failed with fake-secret-value"
    runner = FakeCopilotCliRunner(
        CliExecutionResult(
            command=["copilot"],
            exit_code=7,
            stdout="",
            stderr=fake_stderr,
        )
    )

    with pytest.raises(CopilotCliExecutionError) as captured:
        _provider(runner).reason(_safe_request())

    assert "code 7" in str(captured.value)
    assert fake_stderr not in str(captured.value)


def test_timeout_is_rejected() -> None:
    runner = FakeCopilotCliRunner(
        CliExecutionResult(
            command=["copilot"],
            exit_code=-1,
            stdout="",
            stderr="",
            timed_out=True,
        )
    )

    with pytest.raises(CopilotCliTimeoutError, match="timed out"):
        _provider(runner).reason(_safe_request())


def test_unavailable_executable_is_rejected_without_fallback() -> None:
    runner = _runner(_response_json(), available=False)

    with pytest.raises(CopilotCliUnavailableError, match="unavailable"):
        _provider(runner).reason(_safe_request())
    assert runner.command is None


def test_executable_not_found_is_handled_clearly() -> None:
    runner = SubprocessCopilotCliRunner()

    with patch(
        "pmqa.reasoning.copilot_cli.subprocess.run",
        side_effect=FileNotFoundError,
    ):
        with pytest.raises(CopilotCliUnavailableError, match="not found"):
            runner.run(
                command=["missing-copilot"],
                prompt="safe prompt",
                timeout_seconds=1.0,
            )


def test_availability_check_only_resolves_executable() -> None:
    runner = SubprocessCopilotCliRunner()

    with patch(
        "pmqa.reasoning.copilot_cli.shutil.which",
        return_value="/approved/bin/copilot",
    ) as which:
        assert runner.is_available("copilot") is True

    which.assert_called_once_with("copilot")


def test_subprocess_timeout_returns_typed_timeout_result() -> None:
    runner = SubprocessCopilotCliRunner()

    with patch(
        "pmqa.reasoning.copilot_cli.subprocess.run",
        side_effect=subprocess.TimeoutExpired(["copilot"], 1.0),
    ):
        result = runner.run(
            command=["copilot"],
            prompt="safe prompt",
            timeout_seconds=1.0,
        )

    assert result.timed_out is True
    assert result.stdout == ""
    assert result.stderr == ""


def test_stderr_does_not_replace_successful_stdout() -> None:
    runner = FakeCopilotCliRunner(
        CliExecutionResult(
            command=["copilot"],
            exit_code=0,
            stdout=_response_json(),
            stderr="warning with fake-secret-value",
        )
    )

    response = _provider(runner).reason(_safe_request())

    assert response.status is ReasoningStatus.COMPLETED


def test_errors_do_not_include_prompt_or_environment_content() -> None:
    marker = "unique-safe-prompt-marker"
    request = _safe_request().model_copy(update={"metadata": {"note": marker}})
    runner = FakeCopilotCliRunner(
        CliExecutionResult(
            command=["copilot"],
            exit_code=2,
            stdout="",
            stderr="PATH=/private fake-secret-value",
        )
    )

    with pytest.raises(CopilotCliExecutionError) as captured:
        _provider(runner).reason(request)

    message = str(captured.value)
    assert marker not in message
    assert "PATH" not in message
    assert "fake-secret-value" not in message


def _provider(runner: CopilotCliRunner) -> CopilotCliReasoningProvider:
    return CopilotCliReasoningProvider(_config(), runner)


def _config(arguments=None) -> CopilotCliConfig:
    return CopilotCliConfig(
        executable="copilot",
        arguments=arguments or ["reason", "--stdin"],
        timeout_seconds=30.0,
        model_name="copilot-cli",
    )


def _runner(stdout: str, *, available: bool = True) -> FakeCopilotCliRunner:
    return FakeCopilotCliRunner(
        CliExecutionResult(
            command=["copilot", "reason", "--stdin"],
            exit_code=0,
            stdout=stdout,
            stderr="",
        ),
        available=available,
    )


def _safe_request():
    return DeterministicReasoningScrubber().scrub(
        ScrubInput(
            request_id="request-1",
            workflow_id="workflow-1",
            task_type="analyze",
            provider_hint="github-copilot-cli",
            product_id="demo",
            artifact_version="1",
            constraints={"return_json_only": True},
            metadata={"source": "unit-test"},
        )
    ).request


def _response_payload():
    return {
        "request_id": "request-1",
        "provider": "github-copilot-cli",
        "model": "copilot-cli",
        "status": "completed",
        "decisions": [
            {
                "decision_type": "recommendation",
                "value": {"action": "inspect"},
                "reason_summary": "Structured evidence supports inspection",
                "evidence_ids": [],
                "confidence": 0.8,
            }
        ],
        "confidence": 0.8,
        "warnings": [],
        "metadata": {"transport": "cli"},
    }


def _response_json() -> str:
    return json.dumps(_response_payload(), sort_keys=True)
