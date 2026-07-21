"""Bounded process transport for Product Pack Bridge Protocol v1."""

from dataclasses import dataclass
from enum import Enum
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
from typing import Callable, Dict, Optional, Tuple

from pmqa.product_pack.bridge_protocol import (
    ProductPackBridgeProtocolError,
    ProductPackBridgeRequest,
    ProductPackBridgeResponse,
    validate_product_pack_bridge_response,
)


DEFAULT_BRIDGE_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_REQUEST_BYTES = 256 * 1024
DEFAULT_MAX_STDOUT_BYTES = 2 * 1024 * 1024
DEFAULT_MAX_STDERR_BYTES = 256 * 1024
_MAX_TIMEOUT_SECONDS = 300.0
_MAX_REQUEST_BYTES = 1024 * 1024
_MAX_STDOUT_BYTES = 8 * 1024 * 1024
_MAX_STDERR_BYTES = 1024 * 1024
_MAX_PATH_LENGTH = 4096
_READ_CHUNK_SIZE = 64 * 1024
_PROCESS_POLL_SECONDS = 0.01
_TERMINATION_GRACE_SECONDS = 1.0


class ProductPackBridgeExecutionErrorCode(str, Enum):
    """Stable failures for bounded Product Pack bridge execution."""

    INVALID_EXECUTION_CONFIGURATION = "invalid_execution_configuration"
    INVALID_REQUEST = "invalid_request"
    REQUEST_TOO_LARGE = "request_too_large"
    PROCESS_LAUNCH_FAILED = "process_launch_failed"
    EXECUTION_TIMEOUT = "execution_timeout"
    STDOUT_LIMIT_EXCEEDED = "stdout_limit_exceeded"
    STDERR_LIMIT_EXCEEDED = "stderr_limit_exceeded"
    NONZERO_EXIT = "nonzero_exit"
    INVALID_STDOUT = "invalid_stdout"
    INVALID_PROTOCOL_RESPONSE = "invalid_protocol_response"
    RESPONSE_CORRELATION_MISMATCH = "response_correlation_mismatch"


_EXECUTION_ERROR_MESSAGES = {
    ProductPackBridgeExecutionErrorCode.INVALID_EXECUTION_CONFIGURATION: (
        "invalid Product Pack bridge execution configuration"
    ),
    ProductPackBridgeExecutionErrorCode.INVALID_REQUEST: (
        "invalid Product Pack bridge execution request"
    ),
    ProductPackBridgeExecutionErrorCode.REQUEST_TOO_LARGE: (
        "Product Pack bridge request exceeds the size limit"
    ),
    ProductPackBridgeExecutionErrorCode.PROCESS_LAUNCH_FAILED: (
        "Product Pack bridge process could not be launched"
    ),
    ProductPackBridgeExecutionErrorCode.EXECUTION_TIMEOUT: (
        "Product Pack bridge execution timed out"
    ),
    ProductPackBridgeExecutionErrorCode.STDOUT_LIMIT_EXCEEDED: (
        "Product Pack bridge stdout exceeds the size limit"
    ),
    ProductPackBridgeExecutionErrorCode.STDERR_LIMIT_EXCEEDED: (
        "Product Pack bridge stderr exceeds the size limit"
    ),
    ProductPackBridgeExecutionErrorCode.NONZERO_EXIT: (
        "Product Pack bridge process failed"
    ),
    ProductPackBridgeExecutionErrorCode.INVALID_STDOUT: (
        "Product Pack bridge stdout is invalid"
    ),
    ProductPackBridgeExecutionErrorCode.INVALID_PROTOCOL_RESPONSE: (
        "Product Pack bridge response is invalid"
    ),
    ProductPackBridgeExecutionErrorCode.RESPONSE_CORRELATION_MISMATCH: (
        "Product Pack bridge response correlation failed"
    ),
}


class ProductPackBridgeExecutionError(RuntimeError):
    """Expose only a fixed execution code and bounded safe message."""

    def __init__(self, code: ProductPackBridgeExecutionErrorCode) -> None:
        self.code = code
        super().__init__(_EXECUTION_ERROR_MESSAGES[code])


@dataclass(frozen=True)
class ProductPackBridgeProcessConfig:
    """Runtime-only, explicitly approved bridge process configuration."""

    executable_path: str
    bridge_path: str
    timeout_seconds: float = DEFAULT_BRIDGE_TIMEOUT_SECONDS
    max_request_bytes: int = DEFAULT_MAX_REQUEST_BYTES
    max_stdout_bytes: int = DEFAULT_MAX_STDOUT_BYTES
    max_stderr_bytes: int = DEFAULT_MAX_STDERR_BYTES

    def __post_init__(self) -> None:
        if not _is_valid_process_config(self):
            _raise_execution_error(
                ProductPackBridgeExecutionErrorCode.INVALID_EXECUTION_CONFIGURATION
            )


class _ProcessFailure(str, Enum):
    TIMEOUT = "timeout"
    STDOUT_LIMIT = "stdout_limit"
    STDERR_LIMIT = "stderr_limit"


@dataclass(frozen=True)
class _ProcessOutcome:
    stdout: bytes
    stderr: bytes
    returncode: int
    failure: Optional[_ProcessFailure] = None


_ProcessExecutor = Callable[
    [Tuple[str, str], bytes, float, int, int],
    _ProcessOutcome,
]


def run_product_pack_bridge(
    request: ProductPackBridgeRequest,
    config: ProductPackBridgeProcessConfig,
    *,
    executor: Optional[_ProcessExecutor] = None,
) -> ProductPackBridgeResponse:
    """Execute one bounded bridge exchange and return its correlated response."""

    if type(request) is not ProductPackBridgeRequest:
        _raise_execution_error(ProductPackBridgeExecutionErrorCode.INVALID_REQUEST)
    if (
        type(config) is not ProductPackBridgeProcessConfig
        or not _is_valid_process_config(config)
    ):
        _raise_execution_error(
            ProductPackBridgeExecutionErrorCode.INVALID_EXECUTION_CONFIGURATION
        )
    if executor is not None and not callable(executor):
        _raise_execution_error(
            ProductPackBridgeExecutionErrorCode.INVALID_EXECUTION_CONFIGURATION
        )

    request_bytes = _serialize_request(request)
    if len(request_bytes) > config.max_request_bytes:
        _raise_execution_error(
            ProductPackBridgeExecutionErrorCode.REQUEST_TOO_LARGE
        )

    selected_executor = (
        _execute_bounded_process if executor is None else executor
    )
    argv = (config.executable_path, config.bridge_path)
    try:
        outcome = selected_executor(
            argv,
            request_bytes,
            config.timeout_seconds,
            config.max_stdout_bytes,
            config.max_stderr_bytes,
        )
    except MemoryError:
        raise
    except TimeoutError:
        outcome = None
        execution_failure = ProductPackBridgeExecutionErrorCode.EXECUTION_TIMEOUT
    except OSError:
        outcome = None
        execution_failure = ProductPackBridgeExecutionErrorCode.PROCESS_LAUNCH_FAILED
    else:
        execution_failure = None

    if execution_failure is not None:
        _raise_execution_error(execution_failure)
    if type(outcome) is not _ProcessOutcome:
        raise RuntimeError("Product Pack bridge executor returned an invalid outcome")
    if outcome.failure is _ProcessFailure.TIMEOUT:
        _raise_execution_error(ProductPackBridgeExecutionErrorCode.EXECUTION_TIMEOUT)
    if outcome.failure is _ProcessFailure.STDOUT_LIMIT:
        _raise_execution_error(
            ProductPackBridgeExecutionErrorCode.STDOUT_LIMIT_EXCEEDED
        )
    if outcome.failure is _ProcessFailure.STDERR_LIMIT:
        _raise_execution_error(
            ProductPackBridgeExecutionErrorCode.STDERR_LIMIT_EXCEEDED
        )
    if type(outcome.stdout) is not bytes or type(outcome.stderr) is not bytes:
        raise RuntimeError("Product Pack bridge executor returned invalid output")
    if len(outcome.stdout) > config.max_stdout_bytes:
        _raise_execution_error(
            ProductPackBridgeExecutionErrorCode.STDOUT_LIMIT_EXCEEDED
        )
    if len(outcome.stderr) > config.max_stderr_bytes:
        _raise_execution_error(
            ProductPackBridgeExecutionErrorCode.STDERR_LIMIT_EXCEEDED
        )
    if type(outcome.returncode) is not int:
        raise RuntimeError("Product Pack bridge executor returned invalid status")
    if outcome.returncode != 0:
        _raise_execution_error(ProductPackBridgeExecutionErrorCode.NONZERO_EXIT)

    decoded = _decode_single_json_object(outcome.stdout)
    if decoded is None:
        _raise_execution_error(ProductPackBridgeExecutionErrorCode.INVALID_STDOUT)
    try:
        response = ProductPackBridgeResponse.from_dict(decoded)
    except ProductPackBridgeProtocolError:
        response = None
    if response is None:
        _raise_execution_error(
            ProductPackBridgeExecutionErrorCode.INVALID_PROTOCOL_RESPONSE
        )
    try:
        correlated = validate_product_pack_bridge_response(request, response)
    except ProductPackBridgeProtocolError:
        correlated = None
    if correlated is None:
        _raise_execution_error(
            ProductPackBridgeExecutionErrorCode.RESPONSE_CORRELATION_MISMATCH
        )
    return correlated


def _serialize_request(request: ProductPackBridgeRequest) -> bytes:
    return json.dumps(
        request.to_dict(),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _decode_single_json_object(stdout: bytes) -> Optional[Dict[str, object]]:
    if not stdout or stdout.startswith(b"\xef\xbb\xbf"):
        return None
    try:
        text = stdout.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return None
    if not text.strip():
        return None
    try:
        value = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
    except (ValueError, RecursionError, OverflowError):
        return None
    if type(value) is not dict:
        return None
    return value


class _InvalidJSON(ValueError):
    pass


def _unique_object(pairs) -> Dict[str, object]:
    result: Dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _InvalidJSON()
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    _ = value
    raise _InvalidJSON()


def _execute_bounded_process(
    argv: Tuple[str, str],
    request_bytes: bytes,
    timeout_seconds: float,
    max_stdout_bytes: int,
    max_stderr_bytes: int,
) -> _ProcessOutcome:
    process = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        start_new_session=(os.name == "posix"),
    )
    if process.stdin is None or process.stdout is None or process.stderr is None:
        _terminate_and_wait(process)
        raise OSError()

    stdout_buffer = bytearray()
    stderr_buffer = bytearray()
    stop_event = threading.Event()
    failure_lock = threading.Lock()
    failures = []
    thread_errors = []

    def record_failure(failure: _ProcessFailure) -> None:
        with failure_lock:
            if not failures:
                failures.append(failure)
        stop_event.set()

    def read_stream(stream, buffer: bytearray, limit: int, failure) -> None:
        try:
            while True:
                try:
                    chunk = stream.read(_READ_CHUNK_SIZE)
                except OSError:
                    return
                if not chunk:
                    return
                remaining = limit - len(buffer)
                if len(chunk) > remaining:
                    if remaining > 0:
                        buffer.extend(chunk[:remaining])
                    record_failure(failure)
                    return
                buffer.extend(chunk)
        finally:
            try:
                stream.close()
            except OSError:
                pass

    def write_request() -> None:
        try:
            process.stdin.write(request_bytes)
            process.stdin.flush()
        except OSError:
            pass
        finally:
            try:
                process.stdin.close()
            except OSError:
                pass

    def guarded_thread(target, *args) -> None:
        try:
            target(*args)
        except BaseException as error:
            with failure_lock:
                if not thread_errors:
                    thread_errors.append(error)
            stop_event.set()

    threads = (
        threading.Thread(
            target=guarded_thread,
            args=(write_request,),
            daemon=True,
        ),
        threading.Thread(
            target=guarded_thread,
            args=(
                read_stream,
                process.stdout,
                stdout_buffer,
                max_stdout_bytes,
                _ProcessFailure.STDOUT_LIMIT,
            ),
            daemon=True,
        ),
        threading.Thread(
            target=guarded_thread,
            args=(
                read_stream,
                process.stderr,
                stderr_buffer,
                max_stderr_bytes,
                _ProcessFailure.STDERR_LIMIT,
            ),
            daemon=True,
        ),
    )
    try:
        for thread in threads:
            thread.start()

        deadline = time.monotonic() + timeout_seconds
        while process.poll() is None:
            if stop_event.is_set():
                _terminate_and_wait(process)
                break
            if time.monotonic() >= deadline:
                record_failure(_ProcessFailure.TIMEOUT)
                _terminate_and_wait(process)
                break
            time.sleep(_PROCESS_POLL_SECONDS)

        process.wait()
        _terminate_descendants(process, signal.SIGTERM)
    except BaseException:
        if process.poll() is None:
            _terminate_and_wait(process)
        _terminate_descendants(process, signal.SIGKILL)
        raise
    for thread in threads:
        thread.join(timeout=_TERMINATION_GRACE_SECONDS)
    if any(thread.is_alive() for thread in threads):
        _terminate_descendants(process, signal.SIGKILL)
        for thread in threads:
            thread.join(timeout=_TERMINATION_GRACE_SECONDS)
    if thread_errors:
        raise thread_errors[0]
    return _ProcessOutcome(
        stdout=bytes(stdout_buffer),
        stderr=bytes(stderr_buffer),
        returncode=process.returncode,
        failure=failures[0] if failures else None,
    )


def _terminate_and_wait(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        process.wait()
        return
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        process.wait(timeout=_TERMINATION_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.wait()
    except ProcessLookupError:
        process.wait()


def _terminate_descendants(
    process: subprocess.Popen,
    termination_signal: signal.Signals,
) -> None:
    if os.name != "posix":
        return
    try:
        os.killpg(process.pid, termination_signal)
    except ProcessLookupError:
        return


def _is_valid_executable_path(value: object) -> bool:
    return (
        _is_canonical_absolute_path(value)
        and Path(value).is_file()
        and os.access(value, os.X_OK)
    )


def _is_valid_bridge_path(value: object) -> bool:
    return _is_canonical_absolute_path(value) and Path(value).is_file()


def _is_canonical_absolute_path(value: object) -> bool:
    return (
        type(value) is str
        and 0 < len(value) <= _MAX_PATH_LENGTH
        and "\x00" not in value
        and os.path.isabs(value)
        and os.path.normpath(value) == value
    )


def _is_valid_timeout(value: object) -> bool:
    return (
        type(value) in {int, float}
        and not isinstance(value, bool)
        and math.isfinite(value)
        and 0 < value <= _MAX_TIMEOUT_SECONDS
    )


def _is_valid_process_config(config: ProductPackBridgeProcessConfig) -> bool:
    if not _is_valid_executable_path(config.executable_path):
        return False
    if not _is_valid_bridge_path(config.bridge_path):
        return False
    if not _is_valid_timeout(config.timeout_seconds):
        return False
    return all(
        type(value) is int and 1 <= value <= upper_bound
        for value, upper_bound in (
            (config.max_request_bytes, _MAX_REQUEST_BYTES),
            (config.max_stdout_bytes, _MAX_STDOUT_BYTES),
            (config.max_stderr_bytes, _MAX_STDERR_BYTES),
        )
    )


def _raise_execution_error(code: ProductPackBridgeExecutionErrorCode) -> None:
    raise ProductPackBridgeExecutionError(code) from None


__all__ = [
    "DEFAULT_BRIDGE_TIMEOUT_SECONDS",
    "DEFAULT_MAX_REQUEST_BYTES",
    "DEFAULT_MAX_STDERR_BYTES",
    "DEFAULT_MAX_STDOUT_BYTES",
    "ProductPackBridgeExecutionError",
    "ProductPackBridgeExecutionErrorCode",
    "ProductPackBridgeProcessConfig",
    "run_product_pack_bridge",
]
