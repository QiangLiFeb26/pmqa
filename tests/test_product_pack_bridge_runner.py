"""Offline tests for bounded Product Pack bridge process transport."""

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

import pytest

from pmqa.models import ExplorationEvidence, ExplorationSource
from pmqa.product_pack import (
    ProductPackBridgeExecutionError,
    ProductPackBridgeExecutionErrorCode,
    ProductPackBridgeFailureCode,
    ProductPackBridgeOperation,
    ProductPackBridgeProcessConfig,
    ProductPackBridgeRequest,
    ProductPackBridgeResponse,
    ProductPackBridgeStatus,
    run_product_pack_bridge,
)
from pmqa.product_pack.bridge_runner import _ProcessFailure, _ProcessOutcome


def _time(minutes: int = 0) -> datetime:
    return datetime(2026, 7, 20, 12, tzinfo=timezone.utc) + timedelta(
        minutes=minutes
    )


def _request(**updates) -> ProductPackBridgeRequest:
    values = {
        "protocol_version": "1",
        "request_id": "request.1",
        "workflow_id": "workflow.1",
        "product_id": "demo",
        "pack_id": "external-demo",
        "tool_id": "exploration.capture",
        "operation": ProductPackBridgeOperation.EXPLORATION_CAPTURE,
        "requested_at": _time(),
        "action_plan": ("inspect", "click"),
    }
    values.update(updates)
    return ProductPackBridgeRequest(**values)


def _evidence(request=None, **updates) -> ExplorationEvidence:
    request = request or _request()
    values = {
        "schema_version": "1",
        "evidence_id": "evidence.1",
        "workflow_id": request.workflow_id,
        "product_id": request.product_id,
        "source": ExplorationSource(
            source_type="typescript",
            tool_id=request.tool_id,
            capture_id="capture.1",
        ),
        "captured_at": request.requested_at,
    }
    values.update(updates)
    return ExplorationEvidence(**values)


def _response(request=None, **updates) -> ProductPackBridgeResponse:
    request = request or _request()
    values = {
        "protocol_version": request.protocol_version,
        "request_id": request.request_id,
        "workflow_id": request.workflow_id,
        "product_id": request.product_id,
        "pack_id": request.pack_id,
        "tool_id": request.tool_id,
        "operation": request.operation,
        "status": ProductPackBridgeStatus.SUCCEEDED,
        "completed_at": request.requested_at,
        "evidence": _evidence(request),
        "failure_code": None,
    }
    values.update(updates)
    return ProductPackBridgeResponse(**values)


def _failed_response(request=None, **updates) -> ProductPackBridgeResponse:
    request = request or _request()
    values = {
        "status": ProductPackBridgeStatus.FAILED,
        "evidence": None,
        "failure_code": ProductPackBridgeFailureCode.EXPLORATION_FAILED,
    }
    values.update(updates)
    return _response(request, **values)


def _json_bytes(value) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode("utf-8")


def _outcome(response, *, stderr=b"", returncode=0, failure=None):
    stdout = response if type(response) is bytes else _json_bytes(response)
    return _ProcessOutcome(
        stdout=stdout,
        stderr=stderr,
        returncode=returncode,
        failure=failure,
    )


@pytest.fixture
def process_config(tmp_path) -> ProductPackBridgeProcessConfig:
    bridge = tmp_path / "bridge.py"
    bridge.write_text("# test bridge\n", encoding="utf-8")
    return ProductPackBridgeProcessConfig(
        executable_path=os.path.normpath(sys.executable),
        bridge_path=str(bridge),
        timeout_seconds=2,
        max_request_bytes=262144,
        max_stdout_bytes=2097152,
        max_stderr_bytes=262144,
    )


def _assert_error(
    code: ProductPackBridgeExecutionErrorCode,
    request,
    config,
    executor,
) -> ProductPackBridgeExecutionError:
    with pytest.raises(ProductPackBridgeExecutionError) as captured:
        run_product_pack_bridge(request, config, executor=executor)
    assert captured.value.code is code
    return captured.value


def test_process_config_is_frozen_runtime_only_and_exact(process_config) -> None:
    assert tuple(ProductPackBridgeProcessConfig.__dataclass_fields__) == (
        "executable_path",
        "bridge_path",
        "timeout_seconds",
        "max_request_bytes",
        "max_stdout_bytes",
        "max_stderr_bytes",
    )
    assert not hasattr(process_config, "to_dict")
    with pytest.raises(FrozenInstanceError):
        process_config.timeout_seconds = 10


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("executable_path", ""),
        ("executable_path", "python"),
        ("executable_path", "../python"),
        ("executable_path", "/tmp/../runtime-secret-marker"),
        ("executable_path", "/missing/runtime-secret-marker"),
        ("executable_path", object()),
        ("bridge_path", ""),
        ("bridge_path", "bridge.py"),
        ("bridge_path", "../bridge.py"),
        ("bridge_path", "/tmp/../runtime-secret-marker"),
        ("bridge_path", "/missing/runtime-secret-marker"),
        ("bridge_path", object()),
        ("timeout_seconds", 0),
        ("timeout_seconds", float("inf")),
        ("timeout_seconds", True),
        ("max_request_bytes", 0),
        ("max_stdout_bytes", 9 * 1024 * 1024),
        ("max_stderr_bytes", object()),
    ],
)
def test_invalid_configuration_fails_safely_before_launch(
    process_config,
    field: str,
    value,
) -> None:
    values = {
        name: getattr(process_config, name)
        for name in ProductPackBridgeProcessConfig.__dataclass_fields__
    }
    values[field] = value

    with pytest.raises(ProductPackBridgeExecutionError) as captured:
        ProductPackBridgeProcessConfig(**values)

    assert (
        captured.value.code
        is ProductPackBridgeExecutionErrorCode.INVALID_EXECUTION_CONFIGURATION
    )
    assert "runtime-secret-marker" not in str(captured.value)


def test_invalid_request_or_config_type_causes_zero_launches(process_config) -> None:
    calls = []
    for request, config in (({}, process_config), (_request(), {})):
        with pytest.raises(ProductPackBridgeExecutionError):
            run_product_pack_bridge(
                request,
                config,
                executor=lambda *args: calls.append(args),
            )
    assert calls == []


def test_config_is_revalidated_immediately_before_launch(
    process_config,
) -> None:
    Path(process_config.bridge_path).unlink()
    calls = []

    with pytest.raises(ProductPackBridgeExecutionError) as captured:
        run_product_pack_bridge(
            _request(),
            process_config,
            executor=lambda *args: calls.append(args),
        )

    assert (
        captured.value.code
        is ProductPackBridgeExecutionErrorCode.INVALID_EXECUTION_CONFIGURATION
    )
    assert calls == []


def test_child_invoked_once_with_approved_argv_and_request_only_on_stdin(
    process_config,
) -> None:
    request = _request()
    calls = []

    def executor(argv, stdin, timeout, stdout_limit, stderr_limit):
        calls.append((argv, stdin, timeout, stdout_limit, stderr_limit))
        return _outcome(_response(request).to_dict())

    response = run_product_pack_bridge(request, process_config, executor=executor)

    assert response == _response(request)
    assert len(calls) == 1
    argv, stdin, timeout, stdout_limit, stderr_limit = calls[0]
    assert argv == (
        process_config.executable_path,
        process_config.bridge_path,
    )
    assert request.request_id not in argv
    assert stdin == _json_bytes(request.to_dict())
    assert b"\n" not in stdin
    assert b": " not in stdin and b", " not in stdin
    assert timeout == process_config.timeout_seconds
    assert stdout_limit == process_config.max_stdout_bytes
    assert stderr_limit == process_config.max_stderr_bytes


def test_oversized_request_causes_zero_launches(process_config) -> None:
    config = ProductPackBridgeProcessConfig(
        executable_path=process_config.executable_path,
        bridge_path=process_config.bridge_path,
        max_request_bytes=1,
    )
    calls = []

    error = _assert_error(
        ProductPackBridgeExecutionErrorCode.REQUEST_TOO_LARGE,
        _request(),
        config,
        lambda *args: calls.append(args),
    )

    assert calls == []
    assert error.__cause__ is None
    assert error.__context__ is None


def test_valid_failed_protocol_response_is_returned_normally(process_config) -> None:
    request = _request()
    expected = _failed_response(request)

    actual = run_product_pack_bridge(
        request,
        process_config,
        executor=lambda *args: _outcome(expected.to_dict()),
    )

    assert actual == expected
    assert actual.status is ProductPackBridgeStatus.FAILED


@pytest.mark.parametrize(
    "field",
    ["request_id", "workflow_id", "product_id", "pack_id", "tool_id"],
)
def test_identity_correlation_mismatches_are_safe(process_config, field: str) -> None:
    request = _request()
    values = _response(request).to_dict()
    values[field] = "another-id"
    if field in {"workflow_id", "product_id"}:
        values["evidence"][field] = "another-id"
    if field == "tool_id":
        values["evidence"]["source"]["tool_id"] = "another-id"

    _assert_error(
        ProductPackBridgeExecutionErrorCode.RESPONSE_CORRELATION_MISMATCH,
        request,
        process_config,
        lambda *args: _outcome(values),
    )


@pytest.mark.parametrize("field", ["protocol_version", "operation"])
def test_unsupported_identity_values_are_invalid_protocol_responses(
    process_config,
    field: str,
) -> None:
    payload = _response().to_dict()
    payload[field] = "2" if field == "protocol_version" else "generate"

    _assert_error(
        ProductPackBridgeExecutionErrorCode.INVALID_PROTOCOL_RESPONSE,
        _request(),
        process_config,
        lambda *args: _outcome(payload),
    )


def test_response_timestamp_correlations_are_safe(process_config) -> None:
    request = _request()
    before = request.requested_at - timedelta(minutes=1)
    responses = (
        _failed_response(request, completed_at=before),
        _response(
            request,
            evidence=_evidence(request, captured_at=before),
        ),
    )
    for response in responses:
        _assert_error(
            ProductPackBridgeExecutionErrorCode.RESPONSE_CORRELATION_MISMATCH,
            request,
            process_config,
            lambda *args, response=response: _outcome(response.to_dict()),
        )


@pytest.mark.parametrize(
    "stdout",
    [
        b"",
        b"   \n",
        b"\xff",
        b"\xef\xbb\xbf{}",
        b"null",
        b"[]",
        b"{} {}",
        b"{} trailing",
        b'{"status":NaN}',
        b'{"status":Infinity}',
        b'{"status":-Infinity}',
    ],
)
def test_invalid_stdout_encoding_or_framing_is_rejected(
    process_config,
    stdout: bytes,
) -> None:
    _assert_error(
        ProductPackBridgeExecutionErrorCode.INVALID_STDOUT,
        _request(),
        process_config,
        lambda *args: _outcome(stdout),
    )


@pytest.mark.parametrize(
    "stdout",
    [
        b'{"request_id":"one","request_id":"two"}',
        b'{"evidence":{"pages":[],"pages":[]}}',
    ],
)
def test_duplicate_json_keys_are_rejected_at_every_level(
    process_config,
    stdout: bytes,
) -> None:
    _assert_error(
        ProductPackBridgeExecutionErrorCode.INVALID_STDOUT,
        _request(),
        process_config,
        lambda *args: _outcome(stdout),
    )


def test_unknown_and_noncanonical_protocol_payloads_are_rejected(
    process_config,
) -> None:
    payloads = []
    unknown = _response().to_dict()
    unknown["runtime"] = "runtime-secret-marker"
    payloads.append(unknown)
    missing_default = _response().to_dict()
    del missing_default["evidence"]["pages"]
    payloads.append(missing_default)

    for payload in payloads:
        error = _assert_error(
            ProductPackBridgeExecutionErrorCode.INVALID_PROTOCOL_RESPONSE,
            _request(),
            process_config,
            lambda *args, payload=payload: _outcome(payload),
        )
        assert "runtime-secret-marker" not in str(error)


def test_nonzero_exit_hides_stderr_and_exit_details(process_config) -> None:
    marker = b"runtime-secret-marker"
    error = _assert_error(
        ProductPackBridgeExecutionErrorCode.NONZERO_EXIT,
        _request(),
        process_config,
        lambda *args: _outcome(b"", stderr=marker, returncode=73),
    )
    formatted = "".join(
        traceback.format_exception(type(error), error, error.__traceback__)
    )
    assert "runtime-secret-marker" not in formatted
    assert "73" not in str(error)
    assert error.args == ("Product Pack bridge process failed",)
    assert vars(error) == {
        "code": ProductPackBridgeExecutionErrorCode.NONZERO_EXIT
    }
    assert error.__cause__ is None
    assert error.__context__ is None


@pytest.mark.parametrize(
    ("failure", "code"),
    [
        (_ProcessFailure.TIMEOUT, ProductPackBridgeExecutionErrorCode.EXECUTION_TIMEOUT),
        (
            _ProcessFailure.STDOUT_LIMIT,
            ProductPackBridgeExecutionErrorCode.STDOUT_LIMIT_EXCEEDED,
        ),
        (
            _ProcessFailure.STDERR_LIMIT,
            ProductPackBridgeExecutionErrorCode.STDERR_LIMIT_EXCEEDED,
        ),
    ],
)
def test_execution_seam_limit_failures_are_safe(
    process_config,
    failure,
    code,
) -> None:
    _assert_error(
        code,
        _request(),
        process_config,
        lambda *args: _outcome(b"", failure=failure),
    )


def test_executor_output_limits_cannot_be_bypassed(process_config) -> None:
    configs = (
        ("stdout", ProductPackBridgeExecutionErrorCode.STDOUT_LIMIT_EXCEEDED),
        ("stderr", ProductPackBridgeExecutionErrorCode.STDERR_LIMIT_EXCEEDED),
    )
    for stream, code in configs:
        values = {"stdout": b"", "stderr": b""}
        values[stream] = b"x" * (getattr(process_config, f"max_{stream}_bytes") + 1)
        _assert_error(
            code,
            _request(),
            process_config,
            lambda *args, values=values: _ProcessOutcome(
                returncode=0,
                **values,
            ),
        )


@pytest.mark.parametrize("error", [OSError("runtime-secret-marker"), TimeoutError()])
def test_expected_executor_errors_are_safely_classified(process_config, error) -> None:
    code = (
        ProductPackBridgeExecutionErrorCode.PROCESS_LAUNCH_FAILED
        if isinstance(error, OSError) and not isinstance(error, TimeoutError)
        else ProductPackBridgeExecutionErrorCode.EXECUTION_TIMEOUT
    )

    def executor(*args):
        raise error

    captured = _assert_error(code, _request(), process_config, executor)
    assert "runtime-secret-marker" not in str(captured)
    assert captured.__cause__ is None
    assert captured.__context__ is None


@pytest.mark.parametrize(
    "error_type",
    [KeyboardInterrupt, SystemExit, GeneratorExit, MemoryError],
)
def test_control_flow_and_memory_errors_propagate(process_config, error_type) -> None:
    def executor(*args):
        raise error_type()

    with pytest.raises(error_type):
        run_product_pack_bridge(_request(), process_config, executor=executor)


def _write_bridge(tmp_path: Path, source: str, **config_updates):
    script = tmp_path / "bridge.py"
    script.write_text(source, encoding="utf-8")
    values = {
        "executable_path": os.path.normpath(sys.executable),
        "bridge_path": str(script),
        "timeout_seconds": 2,
        "max_request_bytes": 262144,
        "max_stdout_bytes": 2097152,
        "max_stderr_bytes": 262144,
    }
    values.update(config_updates)
    return ProductPackBridgeProcessConfig(**values)


def test_real_process_round_trip_is_bounded_offline_and_shell_free(
    tmp_path,
    monkeypatch,
) -> None:
    script = """
import json
import sys
request = json.load(sys.stdin)
response = {
    "protocol_version": request["protocol_version"],
    "request_id": request["request_id"],
    "workflow_id": request["workflow_id"],
    "product_id": request["product_id"],
    "pack_id": request["pack_id"],
    "tool_id": request["tool_id"],
    "operation": request["operation"],
    "status": "succeeded",
    "completed_at": request["requested_at"],
    "evidence": {
        "schema_version": "1",
        "evidence_id": "evidence.1",
        "workflow_id": request["workflow_id"],
        "product_id": request["product_id"],
        "source": {
            "source_type": "typescript",
            "tool_id": request["tool_id"],
            "capture_id": "capture.1"
        },
        "captured_at": request["requested_at"],
        "pages": [],
        "elements": [],
        "locator_candidates": [],
        "interactions": []
    },
    "failure_code": None
}
json.dump(response, sys.stdout, separators=(",", ":"))
"""
    config = _write_bridge(tmp_path, script)
    original_popen = subprocess.Popen
    calls = []

    def observed_popen(*args, **kwargs):
        calls.append((args, kwargs))
        return original_popen(*args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", observed_popen)
    response = run_product_pack_bridge(_request(), config)

    assert response.status is ProductPackBridgeStatus.SUCCEEDED
    assert len(calls) == 1
    assert calls[0][0][0] == (config.executable_path, config.bridge_path)
    assert calls[0][1]["shell"] is False
    assert "env" not in calls[0][1]
    assert "cwd" not in calls[0][1]


@pytest.mark.parametrize(
    ("source", "config_updates", "code"),
    [
        (
            "import time; time.sleep(10)",
            {"timeout_seconds": 0.1},
            ProductPackBridgeExecutionErrorCode.EXECUTION_TIMEOUT,
        ),
        (
            "import sys,time; sys.stdout.buffer.write(b'x'*1000000); "
            "sys.stdout.flush(); time.sleep(10)",
            {"max_stdout_bytes": 1024},
            ProductPackBridgeExecutionErrorCode.STDOUT_LIMIT_EXCEEDED,
        ),
        (
            "import sys,time; sys.stderr.buffer.write(b'runtime-secret-marker'*"
            "100000); sys.stderr.flush(); time.sleep(10)",
            {"max_stderr_bytes": 1024},
            ProductPackBridgeExecutionErrorCode.STDERR_LIMIT_EXCEEDED,
        ),
    ],
)
def test_real_process_timeout_and_stream_limits_terminate_promptly(
    tmp_path,
    source: str,
    config_updates,
    code,
) -> None:
    config = _write_bridge(tmp_path, source, **config_updates)
    started = time.monotonic()

    error = _assert_error(code, _request(), config, None)

    assert time.monotonic() - started < 3
    assert "runtime-secret-marker" not in str(error)


def test_request_and_config_remain_unchanged(process_config) -> None:
    request = _request()
    request_before = request.to_dict()
    config_before = {
        name: getattr(process_config, name)
        for name in ProductPackBridgeProcessConfig.__dataclass_fields__
    }

    run_product_pack_bridge(
        request,
        process_config,
        executor=lambda *args: _outcome(_response(request).to_dict()),
    )

    assert request.to_dict() == request_before
    assert {
        name: getattr(process_config, name)
        for name in ProductPackBridgeProcessConfig.__dataclass_fields__
    } == config_before
