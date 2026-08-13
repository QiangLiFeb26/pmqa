"""Append-only local persistence for canonical AI invocation records."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
from typing import Any, Callable, Optional, Protocol, Tuple, runtime_checkable

from pmqa.run import validate_run_identifier
from pmqa.usage.contracts import (
    AIInvocationRecord,
    UsageContractValidationError,
)


DEFAULT_USAGE_QUERY_LIMIT = 100
MAX_USAGE_QUERY_LIMIT = 1_000
MAX_USAGE_RECORD_BYTES = 1_048_576
_RECORD_NAME_PATTERN = re.compile(r"^[a-f0-9]{64}\.json$", flags=re.ASCII)
_TEMPORARY_PREFIX = ".pmqa-usage-"
_TEMPORARY_SUFFIX = ".tmp"
_RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS = (
    MemoryError,
    KeyboardInterrupt,
    SystemExit,
    GeneratorExit,
)
_UNSUPPORTED_LINK_ERRNOS = frozenset(
    value
    for value in (
        getattr(errno, "ENOSYS", None),
        getattr(errno, "ENOTSUP", None),
        getattr(errno, "EOPNOTSUPP", None),
        getattr(errno, "EXDEV", None),
    )
    if value is not None
)


@dataclass(frozen=True)
class _PublicationCapabilities:
    mkstemp: Callable[..., tuple[int, str]]
    makedirs: Callable[..., Any]
    fchmod: Callable[..., Any]
    fstat: Callable[..., Any]
    write: Callable[..., Any]
    fsync: Callable[..., Any]
    link: Callable[..., Any]
    open: Callable[..., Any]
    lstat: Callable[..., Any]
    unlink: Callable[..., Any]
    close: Callable[..., Any]


class UsageRepositoryErrorCode(str, Enum):
    """Fixed failure vocabulary for local usage persistence."""

    INVALID_CONFIGURATION = "invalid_configuration"
    INVALID_RECORD = "invalid_record"
    INVALID_IDENTIFIER = "invalid_identifier"
    INVALID_LIMIT = "invalid_limit"
    DUPLICATE_RECORD = "duplicate_record"
    RECORD_NOT_FOUND = "record_not_found"
    PERSISTENCE_FAILURE = "persistence_failure"
    READ_FAILURE = "read_failure"
    CORRUPT_DATA = "corrupt_data"
    UNSUPPORTED_PUBLICATION = "unsupported_publication"


_ERROR_MESSAGES = {
    UsageRepositoryErrorCode.INVALID_CONFIGURATION:
        "Invalid usage repository configuration.",
    UsageRepositoryErrorCode.INVALID_RECORD:
        "Invalid AI invocation record.",
    UsageRepositoryErrorCode.INVALID_IDENTIFIER:
        "Invalid usage repository identifier.",
    UsageRepositoryErrorCode.INVALID_LIMIT:
        "Invalid usage repository limit.",
    UsageRepositoryErrorCode.DUPLICATE_RECORD:
        "AI invocation record already exists.",
    UsageRepositoryErrorCode.RECORD_NOT_FOUND:
        "AI invocation record was not found.",
    UsageRepositoryErrorCode.PERSISTENCE_FAILURE:
        "Usage repository persistence failed.",
    UsageRepositoryErrorCode.READ_FAILURE:
        "Usage repository read failed.",
    UsageRepositoryErrorCode.CORRUPT_DATA:
        "Usage repository data is corrupt.",
    UsageRepositoryErrorCode.UNSUPPORTED_PUBLICATION:
        "Safe usage repository publication is unsupported.",
}


class UsageRepositoryError(RuntimeError):
    """Expected fixed, marker-safe repository failure."""

    def __init__(self, code: UsageRepositoryErrorCode) -> None:
        if type(code) is not UsageRepositoryErrorCode:
            raise TypeError("code must be a UsageRepositoryErrorCode")
        self.code = code
        super().__init__(_ERROR_MESSAGES[code])


@runtime_checkable
class UsageRepository(Protocol):
    """Synchronous append-only persistence for canonical invocation records."""

    def save(self, record: AIInvocationRecord) -> None:
        """Publish one canonical invocation exactly once."""

    def get(self, invocation_id: str) -> AIInvocationRecord:
        """Return one independently reconstructed invocation."""

    def find_by_session(
        self,
        session_id: str,
        *,
        limit: int = DEFAULT_USAGE_QUERY_LIMIT,
    ) -> Tuple[AIInvocationRecord, ...]:
        """Return matching records newest-first."""

    def find_by_run(
        self,
        run_id: str,
        *,
        limit: int = DEFAULT_USAGE_QUERY_LIMIT,
    ) -> Tuple[AIInvocationRecord, ...]:
        """Return matching records newest-first."""

    def list_recent(
        self,
        *,
        limit: int = DEFAULT_USAGE_QUERY_LIMIT,
    ) -> Tuple[AIInvocationRecord, ...]:
        """Return all records newest-first."""


class LocalJSONUsageRepository:
    """One canonical immutable JSON file per invocation."""

    __slots__ = ("_invocations_directory", "_root")

    def __init__(self, root: Path) -> None:
        self._root = self._canonical_root(root)
        self._invocations_directory = self._root / "invocations"

    def save(self, record: AIInvocationRecord) -> None:
        snapshot = self._snapshot_record(record)
        payload = self._canonical_bytes(snapshot)
        if len(payload) > MAX_USAGE_RECORD_BYTES:
            raise UsageRepositoryError(
                UsageRepositoryErrorCode.INVALID_RECORD
            ) from None
        capabilities = self._publication_capabilities()
        directory = self._prepare_write_directory(capabilities)
        self._preflight_directory_sync(directory, capabilities)
        target = directory / self._record_name(snapshot.invocation_id)
        descriptor: Optional[int] = None
        temporary_path: Optional[Path] = None
        identity: Optional[tuple[int, int]] = None
        failure_code: Optional[UsageRepositoryErrorCode] = None
        published = False
        try:
            descriptor, raw_temporary_path = capabilities.mkstemp(
                dir=directory,
                prefix=_TEMPORARY_PREFIX,
                suffix=_TEMPORARY_SUFFIX,
            )
            temporary_path = Path(raw_temporary_path)
            descriptor_stat = capabilities.fstat(descriptor)
            identity = (descriptor_stat.st_dev, descriptor_stat.st_ino)
            capabilities.fchmod(descriptor, 0o600)
            secured_stat = capabilities.fstat(descriptor)
            if (
                (secured_stat.st_dev, secured_stat.st_ino) != identity
                or stat.S_IMODE(secured_stat.st_mode) & 0o077
            ):
                raise NotImplementedError
            self._write_all(descriptor, payload, capabilities.write)
            capabilities.fsync(descriptor)
            try:
                capabilities.link(temporary_path, target)
            except FileExistsError:
                failure_code = UsageRepositoryErrorCode.DUPLICATE_RECORD
            except NotImplementedError:
                failure_code = (
                    UsageRepositoryErrorCode.UNSUPPORTED_PUBLICATION
                )
            except OSError as error:
                failure_code = (
                    UsageRepositoryErrorCode.UNSUPPORTED_PUBLICATION
                    if error.errno in _UNSUPPORTED_LINK_ERRNOS
                    else UsageRepositoryErrorCode.PERSISTENCE_FAILURE
                )
            else:
                published = True
                self._fsync_directory(directory, capabilities)
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except NotImplementedError:
            failure_code = (
                UsageRepositoryErrorCode.PERSISTENCE_FAILURE
                if published
                else UsageRepositoryErrorCode.UNSUPPORTED_PUBLICATION
            )
        except (OSError, ValueError, TypeError, AttributeError):
            failure_code = UsageRepositoryErrorCode.PERSISTENCE_FAILURE
        finally:
            if descriptor is not None:
                owned_descriptor = descriptor
                descriptor = None
                self._release_temporary_ownership(
                    owned_descriptor,
                    temporary_path,
                    identity,
                    capabilities,
                )
        if failure_code is not None:
            raise UsageRepositoryError(failure_code) from None

    @staticmethod
    def _canonical_root(root: Path) -> Path:
        failed = False
        snapshot: Optional[Path] = None
        try:
            if not isinstance(root, Path):
                raise ValueError
            raw_root = os.fspath(root)
            if type(raw_root) is not str or "\x00" in raw_root:
                raise ValueError
            os.fsencode(raw_root)
            candidate = Path(raw_root)
            if (
                not candidate.is_absolute()
                or ".." in candidate.parts
                or not candidate.anchor
            ):
                raise ValueError
            anchor = Path(candidate.anchor)
            normalized = Path(os.path.normpath(raw_root))
            if candidate == anchor or normalized == anchor:
                raise ValueError
            try:
                root_stat = os.lstat(candidate)
            except FileNotFoundError:
                pass
            else:
                if (
                    not stat.S_ISDIR(root_stat.st_mode)
                    or stat.S_ISLNK(root_stat.st_mode)
                ):
                    raise ValueError
            snapshot = Path(raw_root)
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except Exception:
            failed = True
        if failed or snapshot is None:
            raise UsageRepositoryError(
                UsageRepositoryErrorCode.INVALID_CONFIGURATION
            ) from None
        return snapshot

    @staticmethod
    def _publication_capabilities() -> _PublicationCapabilities:
        failed = os.name != "posix"
        values = {
            "mkstemp": getattr(tempfile, "mkstemp", None),
            "makedirs": getattr(os, "makedirs", None),
            "fchmod": getattr(os, "fchmod", None),
            "fstat": getattr(os, "fstat", None),
            "write": getattr(os, "write", None),
            "fsync": getattr(os, "fsync", None),
            "link": getattr(os, "link", None),
            "open": getattr(os, "open", None),
            "lstat": getattr(os, "lstat", None),
            "unlink": getattr(os, "unlink", None),
            "close": getattr(os, "close", None),
        }
        if failed or any(not callable(value) for value in values.values()):
            raise UsageRepositoryError(
                UsageRepositoryErrorCode.UNSUPPORTED_PUBLICATION
            ) from None
        return _PublicationCapabilities(**values)

    @staticmethod
    def _preflight_directory_sync(
        directory: Path,
        capabilities: _PublicationCapabilities,
    ) -> None:
        failure_code: Optional[UsageRepositoryErrorCode] = None
        try:
            LocalJSONUsageRepository._fsync_directory(
                directory,
                capabilities,
            )
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except NotImplementedError:
            failure_code = UsageRepositoryErrorCode.UNSUPPORTED_PUBLICATION
        except OSError as error:
            failure_code = (
                UsageRepositoryErrorCode.UNSUPPORTED_PUBLICATION
                if error.errno in _UNSUPPORTED_LINK_ERRNOS
                else UsageRepositoryErrorCode.PERSISTENCE_FAILURE
            )
        except (ValueError, TypeError, AttributeError):
            failure_code = UsageRepositoryErrorCode.PERSISTENCE_FAILURE
        if failure_code is not None:
            raise UsageRepositoryError(failure_code) from None

    def get(self, invocation_id: str) -> AIInvocationRecord:
        canonical_id = self._canonical_identifier(invocation_id)
        directory = self._read_directory_or_none()
        if directory is None:
            raise UsageRepositoryError(
                UsageRepositoryErrorCode.RECORD_NOT_FOUND
            ) from None
        target = directory / self._record_name(canonical_id)
        failure_code = None
        try:
            os.lstat(target)
        except FileNotFoundError:
            failure_code = UsageRepositoryErrorCode.RECORD_NOT_FOUND
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except OSError:
            failure_code = UsageRepositoryErrorCode.READ_FAILURE
        if failure_code is not None:
            raise UsageRepositoryError(failure_code) from None
        return self._read_record(target)

    def find_by_session(
        self,
        session_id: str,
        *,
        limit: int = DEFAULT_USAGE_QUERY_LIMIT,
    ) -> Tuple[AIInvocationRecord, ...]:
        canonical_id = self._canonical_identifier(session_id)
        return self._query(
            lambda record: record.session_id == canonical_id,
            self._canonical_limit(limit),
        )

    def find_by_run(
        self,
        run_id: str,
        *,
        limit: int = DEFAULT_USAGE_QUERY_LIMIT,
    ) -> Tuple[AIInvocationRecord, ...]:
        canonical_id = self._canonical_identifier(run_id)
        return self._query(
            lambda record: record.run_id == canonical_id,
            self._canonical_limit(limit),
        )

    def list_recent(
        self,
        *,
        limit: int = DEFAULT_USAGE_QUERY_LIMIT,
    ) -> Tuple[AIInvocationRecord, ...]:
        return self._query(
            lambda _record: True,
            self._canonical_limit(limit),
        )

    @staticmethod
    def _snapshot_record(record: AIInvocationRecord) -> AIInvocationRecord:
        failed = False
        snapshot = None
        try:
            if type(record) is not AIInvocationRecord:
                raise ValueError
            snapshot = AIInvocationRecord.from_dict(record.to_dict())
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except Exception:
            failed = True
        if failed or snapshot is None:
            raise UsageRepositoryError(
                UsageRepositoryErrorCode.INVALID_RECORD
            ) from None
        return snapshot

    @staticmethod
    def _canonical_bytes(record: AIInvocationRecord) -> bytes:
        failed = False
        payload = None
        try:
            payload = (
                json.dumps(
                    record.to_dict(),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")
                + b"\n"
            )
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except Exception:
            failed = True
        if failed or payload is None:
            raise UsageRepositoryError(
                UsageRepositoryErrorCode.INVALID_RECORD
            ) from None
        return payload

    @staticmethod
    def _canonical_identifier(value: str) -> str:
        failed = False
        canonical = None
        try:
            canonical = validate_run_identifier(value)
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except ValueError:
            failed = True
        if failed or canonical is None:
            raise UsageRepositoryError(
                UsageRepositoryErrorCode.INVALID_IDENTIFIER
            ) from None
        return canonical

    @staticmethod
    def _canonical_limit(value: int) -> int:
        if (
            type(value) is not int
            or not 1 <= value <= MAX_USAGE_QUERY_LIMIT
        ):
            raise UsageRepositoryError(
                UsageRepositoryErrorCode.INVALID_LIMIT
            ) from None
        return value

    @staticmethod
    def _record_name(invocation_id: str) -> str:
        digest = hashlib.sha256(invocation_id.encode("utf-8")).hexdigest()
        return f"{digest}.json"

    def _prepare_write_directory(
        self,
        capabilities: _PublicationCapabilities,
    ) -> Path:
        failed = False
        operational_failure = False
        unsupported = False
        try:
            root_stat = None
            try:
                root_stat = capabilities.lstat(self._root)
            except FileNotFoundError:
                pass
            if root_stat is not None:
                if (
                    not stat.S_ISDIR(root_stat.st_mode)
                    or stat.S_ISLNK(root_stat.st_mode)
                ):
                    failed = True
            if not failed:
                capabilities.makedirs(
                    self._invocations_directory,
                    mode=0o700,
                    exist_ok=True,
                )
                directory_stat = capabilities.lstat(
                    self._invocations_directory
                )
                if (
                    not stat.S_ISDIR(directory_stat.st_mode)
                    or stat.S_ISLNK(directory_stat.st_mode)
                    or stat.S_IMODE(directory_stat.st_mode) & 0o077
                ):
                    failed = True
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except NotImplementedError:
            unsupported = True
        except OSError:
            operational_failure = True
        except (ValueError, TypeError, AttributeError):
            operational_failure = True
        if unsupported:
            raise UsageRepositoryError(
                UsageRepositoryErrorCode.UNSUPPORTED_PUBLICATION
            ) from None
        if operational_failure:
            raise UsageRepositoryError(
                UsageRepositoryErrorCode.PERSISTENCE_FAILURE
            ) from None
        if failed:
            raise UsageRepositoryError(
                UsageRepositoryErrorCode.INVALID_CONFIGURATION
            ) from None
        return self._invocations_directory

    def _read_directory_or_none(self) -> Optional[Path]:
        root_missing = False
        root_failure = False
        root_stat = None
        try:
            root_stat = os.lstat(self._root)
        except FileNotFoundError:
            root_missing = True
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except OSError:
            root_failure = True
        if root_missing:
            return None
        if root_failure or root_stat is None:
            raise UsageRepositoryError(
                UsageRepositoryErrorCode.READ_FAILURE
            ) from None
        if (
            not stat.S_ISDIR(root_stat.st_mode)
            or stat.S_ISLNK(root_stat.st_mode)
        ):
            raise UsageRepositoryError(
                UsageRepositoryErrorCode.READ_FAILURE
            ) from None
        directory_missing = False
        directory_failure = False
        directory_stat = None
        try:
            directory_stat = os.lstat(self._invocations_directory)
        except FileNotFoundError:
            directory_missing = True
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except OSError:
            directory_failure = True
        if directory_missing:
            return None
        if directory_failure or directory_stat is None:
            raise UsageRepositoryError(
                UsageRepositoryErrorCode.READ_FAILURE
            ) from None
        if (
            not stat.S_ISDIR(directory_stat.st_mode)
            or stat.S_ISLNK(directory_stat.st_mode)
        ):
            raise UsageRepositoryError(
                UsageRepositoryErrorCode.READ_FAILURE
            ) from None
        return self._invocations_directory

    def _query(
        self,
        predicate: Callable[[AIInvocationRecord], bool],
        limit: int,
    ) -> Tuple[AIInvocationRecord, ...]:
        directory = self._read_directory_or_none()
        if directory is None:
            return ()
        records = []
        scan_failed = False
        entries = ()
        try:
            entries = tuple(os.scandir(directory))
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except OSError:
            scan_failed = True
        if scan_failed:
            raise UsageRepositoryError(
                UsageRepositoryErrorCode.READ_FAILURE
            ) from None
        for entry in entries:
            if _RECORD_NAME_PATTERN.fullmatch(entry.name) is None:
                continue
            record = self._read_record(Path(entry.path))
            if predicate(record):
                records.append(record)
        records.sort(key=lambda record: record.invocation_id)
        records.sort(key=lambda record: record.completed_at, reverse=True)
        return tuple(
            AIInvocationRecord.from_dict(record.to_dict())
            for record in records[:limit]
        )

    def _read_record(self, path: Path) -> AIInvocationRecord:
        descriptor: Optional[int] = None
        failed_code: Optional[UsageRepositoryErrorCode] = None
        raw = b""
        try:
            path_stat = os.lstat(path)
            if (
                not stat.S_ISREG(path_stat.st_mode)
                or stat.S_ISLNK(path_stat.st_mode)
                or path_stat.st_size > MAX_USAGE_RECORD_BYTES
            ):
                failed_code = UsageRepositoryErrorCode.CORRUPT_DATA
            else:
                flags = os.O_RDONLY
                if hasattr(os, "O_NOFOLLOW"):
                    flags |= os.O_NOFOLLOW
                descriptor = os.open(path, flags)
                descriptor_stat = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(descriptor_stat.st_mode)
                    or (
                        descriptor_stat.st_dev,
                        descriptor_stat.st_ino,
                    ) != (path_stat.st_dev, path_stat.st_ino)
                    or descriptor_stat.st_size > MAX_USAGE_RECORD_BYTES
                ):
                    failed_code = UsageRepositoryErrorCode.CORRUPT_DATA
                else:
                    raw = self._read_exact(
                        descriptor,
                        descriptor_stat.st_size,
                    )
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except OSError:
            if failed_code is None:
                failed_code = UsageRepositoryErrorCode.READ_FAILURE
        finally:
            if descriptor is not None:
                owned_descriptor = descriptor
                descriptor = None
                self._close_descriptor(owned_descriptor)
        if failed_code is not None:
            raise UsageRepositoryError(failed_code) from None
        return self._parse_record(path.name, raw)

    @staticmethod
    def _read_exact(descriptor: int, expected_size: int) -> bytes:
        chunks = []
        remaining = expected_size
        while remaining:
            chunk = os.read(descriptor, min(remaining, 65_536))
            if not chunk:
                raise OSError("unexpected end of usage record")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise OSError("usage record changed during read")
        return b"".join(chunks)

    def _parse_record(self, filename: str, raw: bytes) -> AIInvocationRecord:
        failed = False
        record = None
        try:
            text = raw.decode("utf-8")
            value = json.loads(
                text,
                object_pairs_hook=self._unique_object,
                parse_constant=self._reject_constant,
            )
            if type(value) is not dict:
                raise ValueError
            record = AIInvocationRecord.from_dict(value)
            if record.to_dict() != value:
                raise ValueError
            if self._record_name(record.invocation_id) != filename:
                raise ValueError
            if self._canonical_bytes(record) != raw:
                raise ValueError
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except (
            UnicodeError,
            json.JSONDecodeError,
            UsageContractValidationError,
            ValueError,
            OverflowError,
            RecursionError,
        ):
            failed = True
        if failed or record is None:
            raise UsageRepositoryError(
                UsageRepositoryErrorCode.CORRUPT_DATA
            ) from None
        return AIInvocationRecord.from_dict(record.to_dict())

    @staticmethod
    def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate JSON key")
            value[key] = item
        return value

    @staticmethod
    def _reject_constant(_value: str) -> Any:
        raise ValueError("non-finite JSON constant")

    @staticmethod
    def _write_all(
        descriptor: int,
        payload: bytes,
        write: Callable[..., Any] = os.write,
    ) -> None:
        offset = 0
        while offset < len(payload):
            written = write(descriptor, payload[offset:])
            if written <= 0:
                raise OSError("usage record write failed")
            offset += written

    @staticmethod
    def _fsync_directory(
        directory: Path,
        capabilities: Optional[_PublicationCapabilities] = None,
    ) -> None:
        if capabilities is None:
            capabilities = LocalJSONUsageRepository._publication_capabilities()
        descriptor: Optional[int] = None
        try:
            descriptor = capabilities.open(directory, os.O_RDONLY)
            capabilities.fsync(descriptor)
        finally:
            if descriptor is not None:
                owned_descriptor = descriptor
                descriptor = None
                try:
                    capabilities.close(owned_descriptor)
                except OSError:
                    pass

    @staticmethod
    def _release_temporary_ownership(
        descriptor: int,
        temporary_path: Optional[Path],
        identity: Optional[tuple[int, int]],
        capabilities: _PublicationCapabilities,
    ) -> None:
        active_exception = sys.exc_info()[1]
        release_exception: Optional[BaseException] = None
        try:
            if temporary_path is not None and identity is not None:
                try:
                    temporary_stat = capabilities.lstat(temporary_path)
                    if (
                        temporary_stat.st_dev,
                        temporary_stat.st_ino,
                    ) == identity:
                        capabilities.unlink(temporary_path)
                except (OSError, NotImplementedError):
                    pass
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS as error:
            if active_exception is None:
                release_exception = error
        try:
            capabilities.close(descriptor)
        except (OSError, NotImplementedError):
            pass
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS as error:
            if active_exception is None and release_exception is None:
                release_exception = error
        if release_exception is not None:
            raise release_exception

    @staticmethod
    def _close_descriptor(descriptor: int) -> None:
        try:
            os.close(descriptor)
        except OSError:
            pass


__all__ = [
    "DEFAULT_USAGE_QUERY_LIMIT",
    "MAX_USAGE_QUERY_LIMIT",
    "MAX_USAGE_RECORD_BYTES",
    "LocalJSONUsageRepository",
    "UsageRepository",
    "UsageRepositoryError",
    "UsageRepositoryErrorCode",
]
