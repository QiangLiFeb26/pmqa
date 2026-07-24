"""Tests for append-only local AI invocation persistence."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import errno
import hashlib
import json
from pathlib import Path
import stat
from threading import Barrier, Event
from types import SimpleNamespace
from typing import Any

import pytest

from pmqa.run import RunErrorCategory
from pmqa.usage import (
    MAX_USAGE_QUERY_LIMIT,
    MAX_USAGE_RECORD_BYTES,
    AIInvocationRecord,
    AIInvocationStatus,
    CostEvidence,
    CostType,
    EvidenceUnavailableReason,
    LocalJSONUsageRepository,
    TokenField,
    TokenFieldAbsence,
    TokenUsageEvidence,
    UsageRepository,
    UsageRepositoryError,
    UsageRepositoryErrorCode,
    UsageSource,
)
import pmqa.usage.repository as repository_module


STARTED_AT = datetime(2026, 7, 24, 12, tzinfo=timezone.utc)
COMPLETED_AT = STARTED_AT + timedelta(seconds=1)


def _usage(*, unavailable: bool = False) -> TokenUsageEvidence:
    if unavailable:
        return TokenUsageEvidence(
            schema_version="1",
            source=UsageSource.UNAVAILABLE,
            input_tokens=None,
            output_tokens=None,
            cached_input_tokens=None,
            total_tokens=None,
            unavailable_fields=tuple(
                TokenFieldAbsence(
                    field=field,
                    reason=EvidenceUnavailableReason.NOT_COLLECTED,
                )
                for field in TokenField
            ),
        )
    return TokenUsageEvidence(
        schema_version="1",
        source=UsageSource.PROVIDER_REPORTED,
        input_tokens=0,
        output_tokens=2,
        cached_input_tokens=0,
        total_tokens=2,
        unavailable_fields=(),
    )


def _cost(*, unavailable: bool = False, amount: str = "0") -> CostEvidence:
    if unavailable:
        return CostEvidence(
            schema_version="1",
            cost_type=CostType.UNAVAILABLE,
            amount=None,
            currency=None,
            pricing_source_id=None,
            pricing_version=None,
            pricing_effective_at=None,
            unavailable_reason=EvidenceUnavailableReason.NOT_REPORTED,
        )
    return CostEvidence(
        schema_version="1",
        cost_type=CostType.PROVIDER_REPORTED,
        amount=Decimal(amount),
        currency="USD",
        pricing_source_id=None,
        pricing_version=None,
        pricing_effective_at=None,
        unavailable_reason=None,
    )


def _record(
    invocation_id: str = "ai-invocation.1",
    *,
    session_id: str = "session.1",
    run_id: str = "run.1",
    completed_at: datetime = COMPLETED_AT,
    unavailable: bool = False,
    model_unavailable: bool = False,
    runner_invocation_id: str | None = None,
    attempt_number: int = 1,
    retry_of_invocation_id: str | None = None,
    fallback_from_invocation_id: str | None = None,
    amount: str = "0",
    status: AIInvocationStatus = AIInvocationStatus.SUCCEEDED,
) -> AIInvocationRecord:
    return AIInvocationRecord(
        schema_version="1",
        invocation_id=invocation_id,
        session_id=session_id,
        run_id=run_id,
        runner_invocation_id=runner_invocation_id,
        provider="provider.test",
        model=None if model_unavailable else "model.test-v1",
        model_unavailable_reason=(
            EvidenceUnavailableReason.NOT_REPORTED
            if model_unavailable
            else None
        ),
        operation="reasoning.generate",
        status=status,
        started_at=STARTED_AT,
        completed_at=completed_at,
        duration_ms=1_000,
        attempt_number=attempt_number,
        retry_of_invocation_id=retry_of_invocation_id,
        fallback_from_invocation_id=fallback_from_invocation_id,
        usage=_usage(unavailable=unavailable),
        cost=_cost(unavailable=unavailable, amount=amount),
        error_category=(
            None
            if status is AIInvocationStatus.SUCCEEDED
            else (
                RunErrorCategory.CANCELLED
                if status is AIInvocationStatus.CANCELLED
                else RunErrorCategory.PROVIDER
            )
        ),
    )


def _record_name(invocation_id: str) -> str:
    return (
        hashlib.sha256(invocation_id.encode("utf-8")).hexdigest()
        + ".json"
    )


def _record_path(root: Path, invocation_id: str) -> Path:
    return root / "invocations" / _record_name(invocation_id)


def _canonical_bytes(record: AIInvocationRecord) -> bytes:
    return (
        json.dumps(
            record.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


def _assert_safe_error(
    captured: pytest.ExceptionInfo[UsageRepositoryError],
    code: UsageRepositoryErrorCode,
) -> None:
    assert captured.value.code is code
    assert "runtime-secret-marker" not in str(captured.value)
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None


def test_save_get_round_trip_uses_exact_private_canonical_file(
    tmp_path: Path,
) -> None:
    root = tmp_path / "usage"
    repository = LocalJSONUsageRepository(root)
    record = _record(runner_invocation_id="runner-invocation.1")

    repository.save(record)
    loaded = repository.get(record.invocation_id)

    assert isinstance(repository, UsageRepository)
    assert loaded == record
    assert loaded is not record
    path = _record_path(root, record.invocation_id)
    assert path.read_bytes() == _canonical_bytes(record)
    assert path.name == _record_name(record.invocation_id)
    assert "ai-invocation" not in path.name
    assert stat.S_IMODE(path.stat().st_mode) & 0o077 == 0
    assert stat.S_IMODE(path.parent.stat().st_mode) & 0o077 == 0
    assert not tuple(path.parent.glob(".pmqa-usage-*.tmp"))


@pytest.mark.parametrize(
    "record",
    (
        _record("ai-invocation.zero", amount="0"),
        _record("ai-invocation.unavailable", unavailable=True),
        _record("ai-invocation.model-unavailable", model_unavailable=True),
        _record(
            "ai-invocation.retry",
            attempt_number=2,
            retry_of_invocation_id="ai-invocation.previous",
        ),
        _record(
            "ai-invocation.fallback",
            attempt_number=2,
            fallback_from_invocation_id="ai-invocation.previous",
        ),
        _record(
            "ai-invocation.failed",
            status=AIInvocationStatus.FAILED,
        ),
        _record(
            "ai-invocation.cancelled",
            status=AIInvocationStatus.CANCELLED,
        ),
    ),
)
def test_canonical_optional_and_attempt_evidence_round_trips(
    tmp_path: Path,
    record: AIInvocationRecord,
) -> None:
    repository = LocalJSONUsageRepository(tmp_path / "usage")
    repository.save(record)

    assert repository.get(record.invocation_id) == record


def test_save_snapshots_caller_and_duplicate_never_overwrites(
    tmp_path: Path,
) -> None:
    root = tmp_path / "usage"
    repository = LocalJSONUsageRepository(root)
    record = _record()
    repository.save(record)
    original_bytes = _record_path(root, record.invocation_id).read_bytes()
    record.__dict__["provider"] = "provider.changed"

    assert repository.get("ai-invocation.1").provider == "provider.test"
    for duplicate in (
        _record(),
        _record(amount="1.25"),
    ):
        with pytest.raises(UsageRepositoryError) as captured:
            repository.save(duplicate)
        _assert_safe_error(
            captured,
            UsageRepositoryErrorCode.DUPLICATE_RECORD,
        )
        assert (
            _record_path(root, duplicate.invocation_id).read_bytes()
            == original_bytes
        )


def test_queries_are_newest_first_with_ascending_id_tie_break(
    tmp_path: Path,
) -> None:
    repository = LocalJSONUsageRepository(tmp_path / "usage")
    records = (
        _record(
            "ai-invocation.c",
            session_id="session.other",
            run_id="run.1",
            completed_at=COMPLETED_AT + timedelta(seconds=1),
        ),
        _record("ai-invocation.b"),
        _record("ai-invocation.a"),
        _record(
            "ai-invocation.old",
            completed_at=COMPLETED_AT - timedelta(seconds=1),
        ),
    )
    for record in records:
        repository.save(record)

    assert tuple(
        item.invocation_id for item in repository.list_recent()
    ) == (
        "ai-invocation.c",
        "ai-invocation.a",
        "ai-invocation.b",
        "ai-invocation.old",
    )
    assert tuple(
        item.invocation_id
        for item in repository.find_by_session("session.1")
    ) == (
        "ai-invocation.a",
        "ai-invocation.b",
        "ai-invocation.old",
    )
    assert tuple(
        item.invocation_id
        for item in repository.find_by_run("run.1", limit=2)
    ) == ("ai-invocation.c", "ai-invocation.a")


def test_empty_queries_missing_get_and_independent_query_results(
    tmp_path: Path,
) -> None:
    repository = LocalJSONUsageRepository(tmp_path / "usage")
    assert repository.list_recent() == ()
    assert repository.find_by_session("session.1") == ()
    assert repository.find_by_run("run.1") == ()
    with pytest.raises(UsageRepositoryError) as captured:
        repository.get("ai-invocation.missing")
    _assert_safe_error(captured, UsageRepositoryErrorCode.RECORD_NOT_FOUND)

    repository.save(_record())
    first = repository.list_recent()[0]
    first.__dict__["provider"] = "provider.changed"
    assert repository.list_recent()[0].provider == "provider.test"


@pytest.mark.parametrize("limit", (0, -1, True, 1.0, "1", 1_001))
def test_query_limits_are_exact_bounded_positive_integers(
    tmp_path: Path,
    limit: Any,
) -> None:
    repository = LocalJSONUsageRepository(tmp_path / "usage")
    with pytest.raises(UsageRepositoryError) as captured:
        repository.list_recent(limit=limit)
    _assert_safe_error(captured, UsageRepositoryErrorCode.INVALID_LIMIT)
    assert MAX_USAGE_QUERY_LIMIT == 1_000


@pytest.mark.parametrize(
    "method,value",
    (
        ("get", "Runtime Secret Marker/path"),
        ("session", "Runtime Secret Marker/path"),
        ("run", ""),
    ),
)
def test_query_identifiers_fail_safely(
    tmp_path: Path,
    method: str,
    value: str,
) -> None:
    repository = LocalJSONUsageRepository(tmp_path / "usage")
    with pytest.raises(UsageRepositoryError) as captured:
        if method == "get":
            repository.get(value)
        elif method == "session":
            repository.find_by_session(value)
        else:
            repository.find_by_run(value)
    _assert_safe_error(
        captured,
        UsageRepositoryErrorCode.INVALID_IDENTIFIER,
    )


@pytest.mark.parametrize("root", (Path("."), Path("/"), "runtime-secret-marker"))
def test_repository_requires_an_explicit_absolute_non_root_path(root) -> None:
    with pytest.raises(UsageRepositoryError) as captured:
        LocalJSONUsageRepository(root)
    _assert_safe_error(
        captured,
        UsageRepositoryErrorCode.INVALID_CONFIGURATION,
    )


@pytest.mark.parametrize("root_kind", ("file", "symlink"))
def test_unsafe_existing_root_fails_safely(
    tmp_path: Path,
    root_kind: str,
) -> None:
    root = tmp_path / "runtime-secret-marker"
    if root_kind == "file":
        root.write_text("not a directory", encoding="utf-8")
    else:
        target = tmp_path / "target"
        target.mkdir()
        root.symlink_to(target, target_is_directory=True)
    repository = LocalJSONUsageRepository(root)

    with pytest.raises(UsageRepositoryError) as captured:
        repository.save(_record())

    _assert_safe_error(
        captured,
        UsageRepositoryErrorCode.INVALID_CONFIGURATION,
    )


def test_invalid_record_fails_before_filesystem_effects(tmp_path: Path) -> None:
    root = tmp_path / "usage"
    repository = LocalJSONUsageRepository(root)
    record = _record()
    record.__dict__["provider"] = object()

    with pytest.raises(UsageRepositoryError) as captured:
        repository.save(record)

    _assert_safe_error(captured, UsageRepositoryErrorCode.INVALID_RECORD)
    assert not root.exists()


def test_non_record_value_fails_before_filesystem_effects(
    tmp_path: Path,
) -> None:
    root = tmp_path / "usage"
    repository = LocalJSONUsageRepository(root)

    with pytest.raises(UsageRepositoryError) as captured:
        repository.save(_record().to_dict())  # type: ignore[arg-type]

    _assert_safe_error(captured, UsageRepositoryErrorCode.INVALID_RECORD)
    assert not root.exists()


def test_concurrent_instances_publish_exactly_once(tmp_path: Path) -> None:
    root = tmp_path / "usage"
    repositories = tuple(
        LocalJSONUsageRepository(root) for _ in range(8)
    )
    barrier = Barrier(len(repositories))

    def publish(repository: LocalJSONUsageRepository):
        barrier.wait()
        try:
            repository.save(_record())
        except UsageRepositoryError as error:
            return error.code
        return None

    with ThreadPoolExecutor(max_workers=len(repositories)) as executor:
        outcomes = tuple(executor.map(publish, repositories))

    assert outcomes.count(None) == 1
    assert outcomes.count(UsageRepositoryErrorCode.DUPLICATE_RECORD) == 7
    assert LocalJSONUsageRepository(root).get("ai-invocation.1") == _record()
    assert not tuple((root / "invocations").glob(".pmqa-usage-*.tmp"))


def test_reader_observes_absent_then_complete_atomic_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "usage"
    writer = LocalJSONUsageRepository(root)
    reader = LocalJSONUsageRepository(root)
    reached_publication = Event()
    allow_publication = Event()
    original_link = repository_module.os.link

    def controlled_link(source, target):
        reached_publication.set()
        allow_publication.wait()
        return original_link(source, target)

    monkeypatch.setattr(repository_module.os, "link", controlled_link)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(writer.save, _record())
        try:
            assert reached_publication.wait(timeout=5)
            assert reader.list_recent() == ()
        finally:
            allow_publication.set()
        future.result()

    assert reader.list_recent() == (_record(),)


def test_non_record_and_private_incomplete_siblings_are_ignored(
    tmp_path: Path,
) -> None:
    root = tmp_path / "usage"
    repository = LocalJSONUsageRepository(root)
    repository.save(_record())
    directory = root / "invocations"
    (directory / ".pmqa-usage-orphan.tmp").write_text(
        "runtime-secret-marker",
        encoding="utf-8",
    )
    (directory / "notes.json").write_text("{}", encoding="utf-8")
    (directory / ("A" * 64 + ".json")).write_text("{}", encoding="utf-8")

    assert repository.list_recent() == (_record(),)


def test_publication_failure_preserves_existing_target_and_hides_detail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "runtime-secret-marker"
    repository = LocalJSONUsageRepository(root)
    repository.save(_record())
    original = _record_path(root, "ai-invocation.1").read_bytes()

    def fail_link(_source, _target):
        raise OSError(errno.EIO, "runtime-secret-marker")

    monkeypatch.setattr(repository_module.os, "link", fail_link)
    with pytest.raises(UsageRepositoryError) as captured:
        repository.save(_record())

    _assert_safe_error(
        captured,
        UsageRepositoryErrorCode.PERSISTENCE_FAILURE,
    )
    assert _record_path(root, "ai-invocation.1").read_bytes() == original


def test_unsupported_publication_is_distinct_and_leaves_no_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "usage"
    repository = LocalJSONUsageRepository(root)

    unsupported_errno = errno.ENOTSUP

    def unsupported(_source, _target):
        raise OSError(unsupported_errno, "runtime-secret-marker")

    monkeypatch.setattr(repository_module.os, "link", unsupported)
    with pytest.raises(UsageRepositoryError) as captured:
        repository.save(_record())

    _assert_safe_error(
        captured,
        UsageRepositoryErrorCode.UNSUPPORTED_PUBLICATION,
    )
    assert not _record_path(root, "ai-invocation.1").exists()


def test_post_publication_failure_keeps_complete_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "usage"
    repository = LocalJSONUsageRepository(root)

    def fail_directory_sync(_directory):
        raise OSError("runtime-secret-marker")

    monkeypatch.setattr(
        repository_module.LocalJSONUsageRepository,
        "_fsync_directory",
        staticmethod(fail_directory_sync),
    )
    with pytest.raises(UsageRepositoryError) as captured:
        repository.save(_record())

    _assert_safe_error(
        captured,
        UsageRepositoryErrorCode.PERSISTENCE_FAILURE,
    )
    assert _record_path(root, "ai-invocation.1").read_bytes() == (
        _canonical_bytes(_record())
    )


def test_cleanup_never_unlinks_changed_temporary_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "usage"
    repository = LocalJSONUsageRepository(root)
    original_lstat = repository_module.os.lstat
    original_unlink = repository_module.os.unlink
    unlink_calls = []

    def changed_identity(path):
        result = original_lstat(path)
        if Path(path).name.startswith(".pmqa-usage-"):
            return SimpleNamespace(
                st_dev=result.st_dev,
                st_ino=result.st_ino + 1,
                st_mode=result.st_mode,
                st_size=result.st_size,
            )
        return result

    def tracked_unlink(path):
        unlink_calls.append(Path(path))
        return original_unlink(path)

    monkeypatch.setattr(repository_module.os, "lstat", changed_identity)
    monkeypatch.setattr(repository_module.os, "unlink", tracked_unlink)
    repository.save(_record())

    assert _record_path(root, "ai-invocation.1").exists()
    assert unlink_calls == []
    assert len(tuple((root / "invocations").glob(".pmqa-usage-*.tmp"))) == 1


@pytest.mark.parametrize(
    "failure",
    (MemoryError(), KeyboardInterrupt(), SystemExit(), GeneratorExit()),
)
def test_release_control_flow_failure_propagates_after_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: BaseException,
) -> None:
    root = tmp_path / "usage"
    repository = LocalJSONUsageRepository(root)
    original_mkstemp = repository_module.tempfile.mkstemp
    original_close = repository_module.os.close
    temporary_descriptor = []
    close_attempts = []

    def capture_mkstemp(**kwargs):
        descriptor, path = original_mkstemp(**kwargs)
        temporary_descriptor.append(descriptor)
        return descriptor, path

    def fail_after_close(descriptor):
        close_attempts.append(descriptor)
        original_close(descriptor)
        if descriptor == temporary_descriptor[0]:
            raise failure

    monkeypatch.setattr(
        repository_module.tempfile,
        "mkstemp",
        capture_mkstemp,
    )
    monkeypatch.setattr(repository_module.os, "close", fail_after_close)

    with pytest.raises(type(failure)) as captured:
        repository.save(_record())

    assert captured.value is failure
    assert close_attempts.count(temporary_descriptor[0]) == 1
    assert _record_path(root, "ai-invocation.1").read_bytes() == (
        _canonical_bytes(_record())
    )
    assert not tuple((root / "invocations").glob(".pmqa-usage-*.tmp"))


@pytest.mark.parametrize(
    "raw",
    (
        b"{",
        b'{"schema_version":"1","schema_version":"1"}\n',
        b'{"value":NaN}\n',
        b"\xff\n",
        b'{"unknown":"field"}\n',
        b"{}\n",
        b'{"nested":' + (b"[" * 1_100) + b"0" + (b"]" * 1_100) + b"}\n",
    ),
    ids=(
        "malformed",
        "duplicate-key",
        "non-finite",
        "non-utf8",
        "unknown-field",
        "missing-fields",
        "excessive-nesting",
    ),
)
def test_corrupt_record_forms_fail_safely(
    tmp_path: Path,
    raw: bytes,
) -> None:
    root = tmp_path / "runtime-secret-marker"
    directory = root / "invocations"
    directory.mkdir(parents=True, mode=0o700)
    path = _record_path(root, "ai-invocation.1")
    path.write_bytes(raw)
    repository = LocalJSONUsageRepository(root)

    with pytest.raises(UsageRepositoryError) as captured:
        repository.get("ai-invocation.1")

    _assert_safe_error(captured, UsageRepositoryErrorCode.CORRUPT_DATA)


def test_noncanonical_and_oversized_records_are_corrupt(
    tmp_path: Path,
) -> None:
    root = tmp_path / "usage"
    directory = root / "invocations"
    directory.mkdir(parents=True, mode=0o700)
    path = _record_path(root, "ai-invocation.1")
    path.write_text(
        json.dumps(_record().to_dict(), sort_keys=False, indent=2) + "\n",
        encoding="utf-8",
    )
    repository = LocalJSONUsageRepository(root)
    with pytest.raises(UsageRepositoryError) as noncanonical:
        repository.get("ai-invocation.1")
    _assert_safe_error(
        noncanonical,
        UsageRepositoryErrorCode.CORRUPT_DATA,
    )

    path.write_bytes(b"x" * (MAX_USAGE_RECORD_BYTES + 1))
    with pytest.raises(UsageRepositoryError) as oversized:
        repository.get("ai-invocation.1")
    _assert_safe_error(oversized, UsageRepositoryErrorCode.CORRUPT_DATA)


def test_filename_content_digest_mismatch_is_corrupt(tmp_path: Path) -> None:
    root = tmp_path / "usage"
    repository = LocalJSONUsageRepository(root)
    repository.save(_record("ai-invocation.1"))
    original = _record_path(root, "ai-invocation.1")
    mismatch = _record_path(root, "ai-invocation.other")
    original.rename(mismatch)

    with pytest.raises(UsageRepositoryError) as captured:
        repository.get("ai-invocation.other")

    _assert_safe_error(captured, UsageRepositoryErrorCode.CORRUPT_DATA)


@pytest.mark.parametrize("entry_kind", ("symlink", "directory"))
def test_symlink_and_non_regular_record_entries_are_corrupt(
    tmp_path: Path,
    entry_kind: str,
) -> None:
    root = tmp_path / "usage"
    directory = root / "invocations"
    directory.mkdir(parents=True, mode=0o700)
    path = _record_path(root, "ai-invocation.1")
    if entry_kind == "symlink":
        target = tmp_path / "outside.json"
        target.write_bytes(_canonical_bytes(_record()))
        path.symlink_to(target)
    else:
        path.mkdir()
    repository = LocalJSONUsageRepository(root)

    with pytest.raises(UsageRepositoryError) as captured:
        repository.get("ai-invocation.1")

    _assert_safe_error(captured, UsageRepositoryErrorCode.CORRUPT_DATA)


def test_corrupt_matching_record_fails_entire_query(tmp_path: Path) -> None:
    root = tmp_path / "usage"
    repository = LocalJSONUsageRepository(root)
    repository.save(_record())
    _record_path(root, "ai-invocation.corrupt").write_text(
        "runtime-secret-marker",
        encoding="utf-8",
    )

    with pytest.raises(UsageRepositoryError) as captured:
        repository.list_recent()

    _assert_safe_error(captured, UsageRepositoryErrorCode.CORRUPT_DATA)


def test_operational_read_failure_differs_from_empty_query(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "usage"
    repository = LocalJSONUsageRepository(root)
    repository.save(_record())

    def fail_scan(_path):
        raise OSError("runtime-secret-marker")

    monkeypatch.setattr(repository_module.os, "scandir", fail_scan)
    with pytest.raises(UsageRepositoryError) as captured:
        repository.list_recent()

    _assert_safe_error(captured, UsageRepositoryErrorCode.READ_FAILURE)


@pytest.mark.parametrize(
    "failure",
    (MemoryError(), KeyboardInterrupt(), SystemExit(), GeneratorExit()),
)
def test_resource_and_control_flow_failures_propagate_before_io(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: BaseException,
) -> None:
    root = tmp_path / "usage"
    repository = LocalJSONUsageRepository(root)

    def fail_from_dict(_value):
        raise failure

    monkeypatch.setattr(
        repository_module.AIInvocationRecord,
        "from_dict",
        fail_from_dict,
    )
    with pytest.raises(type(failure)) as captured:
        repository.save(_record())

    assert captured.value is failure
    assert not root.exists()


@pytest.mark.parametrize(
    "failure",
    (MemoryError(), KeyboardInterrupt(), SystemExit(), GeneratorExit()),
)
def test_resource_and_control_flow_read_failures_propagate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: BaseException,
) -> None:
    repository = LocalJSONUsageRepository(tmp_path / "usage")
    repository.save(_record())

    def fail_read(_descriptor, _size):
        raise failure

    monkeypatch.setattr(repository_module.os, "read", fail_read)
    with pytest.raises(type(failure)) as captured:
        repository.get("ai-invocation.1")

    assert captured.value is failure


def test_owned_descriptors_are_closed_once_and_success_cleans_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = LocalJSONUsageRepository(tmp_path / "usage")
    original_close = repository_module.os.close
    close_counts = {}

    def counted_close(descriptor):
        close_counts[descriptor] = close_counts.get(descriptor, 0) + 1
        return original_close(descriptor)

    monkeypatch.setattr(repository_module.os, "close", counted_close)
    repository.save(_record())
    repository.get("ai-invocation.1")

    assert sum(close_counts.values()) == 3
    assert not tuple(
        (tmp_path / "usage/invocations").glob(".pmqa-usage-*.tmp")
    )
