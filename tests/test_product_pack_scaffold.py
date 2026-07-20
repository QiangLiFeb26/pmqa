"""Offline tests for Product Pack scaffolding and source conformance."""

import copy
from dataclasses import FrozenInstanceError
import inspect
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import traceback
import zipfile

import pytest

from pmqa import cli
from pmqa.product_pack import (
    PRODUCT_PACK_SCAFFOLD_VERSION,
    ProductPackBackendSourceState,
    ProductPackCapability,
    ProductPackManifest,
    ProductPackScaffoldError,
    ProductPackScaffoldErrorCode,
    ProductPackScaffoldRequest,
    ProductPackScaffoldResult,
    ProductPackSourceConformanceErrorCode,
    ProductPackSourceConformanceResult,
    scaffold_product_pack,
    validate_product_pack_source,
)
import pmqa.product_pack.scaffold as scaffold_module


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _manifest(**updates) -> ProductPackManifest:
    values = {
        "schema_version": "1",
        "product_pack_api_version": "1",
        "pack_id": "external-demo",
        "pack_version": "1.2.3",
        "product_id": "demo",
        "display_name": "External Demo Pack",
        "capabilities": (
            ProductPackCapability.EXPLORATION_CAPTURE,
            ProductPackCapability.KNOWLEDGE_MAPPING,
        ),
    }
    values.update(updates)
    return ProductPackManifest(**values)


def _scaffold(
    tmp_path: Path,
    name: str = "external-pack",
    *,
    manifest=None,
    distribution_version: str = "2.4.0",
):
    manifest = manifest or _manifest()
    target = tmp_path / name
    request = ProductPackScaffoldRequest(
        manifest,
        str(target),
        distribution_version,
    )
    result = scaffold_product_pack(request)
    return manifest, target, result


def _file_bytes(root: Path):
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _temporary_siblings(parent: Path):
    return tuple(parent.glob(".pmqa-scaffold-*"))


def _assert_private_generated_orphan(parent: Path) -> Path:
    (orphan,) = _temporary_siblings(parent)
    assert orphan.parent == parent
    assert orphan.is_dir()
    assert not orphan.is_symlink()
    assert stat.S_IMODE(orphan.lstat().st_mode) == 0o700
    generated = _file_bytes(orphan)
    assert generated
    forbidden_parts = {
        ".env",
        "credentials",
        "node_modules",
        "artifacts",
        "screenshots",
        "traces",
        "generated_tests",
        "storage_state",
        "__pycache__",
    }
    assert not any(
        forbidden_parts.intersection(Path(name).parts) for name in generated
    )
    assert b"runtime-secret-marker" not in b"\n".join(generated.values())
    return orphan


def _observe_ownership(monkeypatch):
    observed = []
    original_capture = scaffold_module._capture_temporary_directory_ownership

    def capture(path):
        ownership = original_capture(path)
        observed.append(ownership)
        return ownership

    monkeypatch.setattr(
        scaffold_module,
        "_capture_temporary_directory_ownership",
        capture,
    )
    return observed


def _assert_descriptors_closed(ownership) -> None:
    for descriptor in (
        ownership.directory_descriptor,
        ownership.parent_descriptor,
    ):
        with pytest.raises(OSError):
            os.fstat(descriptor)


def _write_bridge_package(target: Path, update) -> None:
    path = target / "bridge/package.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    update(value)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def test_public_contracts_are_exact_frozen_and_path_free(tmp_path) -> None:
    manifest, target, result = _scaffold(tmp_path)

    assert tuple(ProductPackScaffoldRequest.__dataclass_fields__) == (
        "manifest",
        "output_directory",
        "distribution_version",
    )
    assert tuple(ProductPackScaffoldResult.__dataclass_fields__) == (
        "scaffold_version",
        "distribution_name",
        "python_package_name",
        "distribution_version",
        "generated_files",
    )
    assert tuple(ProductPackSourceConformanceResult.__dataclass_fields__) == (
        "is_conformant",
        "error_code",
        "backend_source_state",
        "is_runtime_verified",
    )
    assert result.scaffold_version == PRODUCT_PACK_SCAFFOLD_VERSION == "1"
    assert result.distribution_name == "pmqa-product-pack-external-demo"
    assert result.python_package_name == "pmqa_product_pack_external_demo"
    assert result.distribution_version == "2.4.0"
    assert str(target) not in repr(result)
    with pytest.raises(FrozenInstanceError):
        result.distribution_name = "changed"
    with pytest.raises(FrozenInstanceError):
        ProductPackScaffoldRequest(
            manifest,
            str(tmp_path / "next"),
            "2.4.0",
        ).manifest = None


def test_generation_is_deterministic_and_byte_identical(tmp_path) -> None:
    _, first, first_result = _scaffold(tmp_path, "first")
    _, second, second_result = _scaffold(tmp_path, "second")

    assert first_result.generated_files == second_result.generated_files
    assert _file_bytes(first) == _file_bytes(second)
    combined = b"\n".join(_file_bytes(first).values())
    for forbidden in (
        str(tmp_path).encode(),
        os.environ.get("USER", "runtime-user-marker").encode(),
        b"runtime-secret-marker",
    ):
        assert forbidden not in combined


def test_publication_uses_one_atomic_no_replace_operation(
    tmp_path,
    monkeypatch,
) -> None:
    calls = []
    ownerships = _observe_ownership(monkeypatch)
    release_calls = []
    original_publish = scaffold_module._publish_directory_no_replace
    original_release = scaffold_module._release_temporary_directory_ownership

    def observed_publish(source, target):
        calls.append((Path(source), Path(target)))
        return original_publish(source, target)

    def observed_release(ownership):
        release_calls.append(ownership)
        return original_release(ownership)

    monkeypatch.setattr(
        scaffold_module,
        "_publish_directory_no_replace",
        observed_publish,
    )
    monkeypatch.setattr(
        scaffold_module,
        "_release_temporary_directory_ownership",
        observed_release,
    )
    _, target, _ = _scaffold(tmp_path)

    assert ownerships == release_calls
    assert len(ownerships) == 1
    _assert_descriptors_closed(ownerships[0])
    assert len(calls) == 1
    assert calls[0][0].parent == target.parent
    assert calls[0][0].name.startswith(".pmqa-scaffold-")
    assert calls[0][1] == target
    assert not _temporary_siblings(tmp_path)


@pytest.mark.parametrize(
    "target_kind",
    ["empty-directory", "nonempty-directory", "file", "symlink"],
)
def test_publication_race_never_clobbers_a_new_target(
    tmp_path,
    monkeypatch,
    target_kind: str,
) -> None:
    ownerships = _observe_ownership(monkeypatch)
    target = tmp_path / "racing-target"
    symlink_destination = tmp_path / "symlink-destination"
    original_publish = scaffold_module._publish_directory_no_replace
    observed = {}

    def publish_after_race(source, destination):
        if target_kind == "empty-directory":
            destination.mkdir(mode=0o750)
        elif target_kind == "nonempty-directory":
            destination.mkdir(mode=0o750)
            (destination / "owned.txt").write_text("owned", encoding="utf-8")
        elif target_kind == "file":
            destination.write_text("owned", encoding="utf-8")
            destination.chmod(0o640)
        else:
            symlink_destination.mkdir()
            destination.symlink_to(symlink_destination, target_is_directory=True)
        target_stat = destination.lstat()
        observed["inode"] = target_stat.st_ino
        observed["mode"] = stat.S_IMODE(target_stat.st_mode)
        return original_publish(source, destination)

    monkeypatch.setattr(
        scaffold_module,
        "_publish_directory_no_replace",
        publish_after_race,
    )
    with pytest.raises(ProductPackScaffoldError) as captured:
        scaffold_product_pack(
            ProductPackScaffoldRequest(_manifest(), str(target), "2.4.0")
        )

    assert captured.value.code is ProductPackScaffoldErrorCode.TARGET_EXISTS
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
    assert target.lstat().st_ino == observed["inode"]
    assert stat.S_IMODE(target.lstat().st_mode) == observed["mode"]
    if target_kind == "empty-directory":
        assert tuple(target.iterdir()) == ()
    elif target_kind == "nonempty-directory":
        assert _file_bytes(target) == {"owned.txt": b"owned"}
    elif target_kind == "file":
        assert target.read_text(encoding="utf-8") == "owned"
    else:
        assert target.is_symlink()
        assert target.readlink() == symlink_destination
        assert tuple(symlink_destination.iterdir()) == ()
    _assert_private_generated_orphan(tmp_path)
    _assert_descriptors_closed(ownerships[0])


@pytest.mark.parametrize(
    "error_type",
    [MemoryError, KeyboardInterrupt, SystemExit, GeneratorExit],
)
def test_publication_memory_and_control_flow_errors_propagate(
    tmp_path,
    monkeypatch,
    error_type,
) -> None:
    target = tmp_path / "target"
    ownerships = _observe_ownership(monkeypatch)

    def fail_publication(source, destination):
        raise error_type()

    monkeypatch.setattr(
        scaffold_module,
        "_publish_directory_no_replace",
        fail_publication,
    )
    with pytest.raises(error_type):
        scaffold_product_pack(
            ProductPackScaffoldRequest(_manifest(), str(target), "2.4.0")
        )
    assert not target.exists()
    _assert_private_generated_orphan(tmp_path)
    _assert_descriptors_closed(ownerships[0])


@pytest.mark.parametrize(
    "replacement_kind",
    ["empty-directory", "nonempty-directory", "file", "symlink"],
)
def test_late_temporary_root_substitution_performs_no_destructive_cleanup(
    tmp_path,
    monkeypatch,
    replacement_kind: str,
) -> None:
    target = tmp_path / "target"
    moved_original = tmp_path / ("moved-original-" + replacement_kind)
    symlink_destination = tmp_path / "external-directory"
    observed = {}
    destructive_calls = []
    cleanup_guard = pytest.MonkeyPatch()

    def forbidden_destructive_operation(*args, **kwargs):
        destructive_calls.append((args, kwargs))
        raise AssertionError("failure handling attempted a destructive operation")

    def substitute_then_fail(source, destination):
        source.rename(moved_original)
        if replacement_kind == "empty-directory":
            source.mkdir(mode=0o750)
        elif replacement_kind == "nonempty-directory":
            source.mkdir(mode=0o750)
            (source / "operator-owned.txt").write_text(
                "operator-owned-marker",
                encoding="utf-8",
            )
        elif replacement_kind == "file":
            source.write_text("operator-owned-marker", encoding="utf-8")
            source.chmod(0o640)
        else:
            symlink_destination.mkdir()
            (symlink_destination / "operator-owned.txt").write_text(
                "operator-owned-marker",
                encoding="utf-8",
            )
            source.symlink_to(symlink_destination, target_is_directory=True)
        identity = source.lstat()
        observed["path"] = source
        observed["inode"] = identity.st_ino
        observed["mode"] = stat.S_IMODE(identity.st_mode)
        for name in ("unlink", "remove", "rmdir", "rename", "replace"):
            cleanup_guard.setattr(os, name, forbidden_destructive_operation)
        cleanup_guard.setattr(shutil, "rmtree", forbidden_destructive_operation)
        raise OSError("runtime-secret-marker publication detail")

    monkeypatch.setattr(
        scaffold_module,
        "_publish_directory_no_replace",
        substitute_then_fail,
    )

    try:
        with pytest.raises(ProductPackScaffoldError) as captured:
            scaffold_product_pack(
                ProductPackScaffoldRequest(_manifest(), str(target), "2.4.0")
            )
    finally:
        cleanup_guard.undo()

    replacement = observed["path"]
    formatted = "".join(
        traceback.format_exception(
            type(captured.value),
            captured.value,
            captured.value.__traceback__,
        )
    )
    assert captured.value.code is ProductPackScaffoldErrorCode.GENERATION_FAILED
    assert captured.value.args == ("Product Pack scaffold generation failed",)
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
    assert "runtime-secret-marker" not in formatted
    assert "operator-owned-marker" not in formatted
    assert str(replacement) not in formatted
    assert replacement.lstat().st_ino == observed["inode"]
    assert stat.S_IMODE(replacement.lstat().st_mode) == observed["mode"]
    if replacement_kind == "empty-directory":
        assert tuple(replacement.iterdir()) == ()
    elif replacement_kind == "nonempty-directory":
        assert _file_bytes(replacement) == {
            "operator-owned.txt": b"operator-owned-marker"
        }
    elif replacement_kind == "file":
        assert replacement.read_text(encoding="utf-8") == (
            "operator-owned-marker"
        )
    else:
        assert replacement.is_symlink()
        assert replacement.readlink() == symlink_destination
        assert _file_bytes(symlink_destination) == {
            "operator-owned.txt": b"operator-owned-marker"
        }
    assert destructive_calls == []
    assert moved_original.is_dir()
    assert target.exists() is False


def test_late_child_substitutions_survive_without_destructive_cleanup(
    tmp_path,
    monkeypatch,
) -> None:
    target = tmp_path / "target"
    observed = {}
    destructive_calls = []
    cleanup_guard = pytest.MonkeyPatch()

    def forbidden_destructive_operation(*args, **kwargs):
        destructive_calls.append((args, kwargs))
        raise AssertionError("failure handling attempted a destructive operation")

    def substitute_children_then_fail(source, destination):
        original_file = source / "product-pack.json"
        saved_file = source / "saved-product-pack.json"
        original_file.rename(saved_file)
        original_file.write_text("operator-file-marker", encoding="utf-8")
        original_file.chmod(0o640)

        original_directory = source / "bridge"
        saved_directory = source / "saved-bridge"
        original_directory.rename(saved_directory)
        original_directory.mkdir(mode=0o750)
        (original_directory / "operator-owned.txt").write_text(
            "operator-directory-marker",
            encoding="utf-8",
        )
        observed.update(
            root=source,
            file_inode=original_file.lstat().st_ino,
            directory_inode=original_directory.lstat().st_ino,
        )
        for name in ("unlink", "remove", "rmdir", "rename", "replace"):
            cleanup_guard.setattr(os, name, forbidden_destructive_operation)
        cleanup_guard.setattr(shutil, "rmtree", forbidden_destructive_operation)
        raise OSError("runtime-secret-marker publication detail")

    monkeypatch.setattr(
        scaffold_module,
        "_publish_directory_no_replace",
        substitute_children_then_fail,
    )

    try:
        with pytest.raises(ProductPackScaffoldError) as captured:
            scaffold_product_pack(
                ProductPackScaffoldRequest(_manifest(), str(target), "2.4.0")
            )
    finally:
        cleanup_guard.undo()

    orphan = observed["root"]
    assert captured.value.code is ProductPackScaffoldErrorCode.GENERATION_FAILED
    assert destructive_calls == []
    assert orphan.lstat().st_ino == _temporary_siblings(tmp_path)[0].lstat().st_ino
    assert (orphan / "product-pack.json").lstat().st_ino == observed["file_inode"]
    assert (orphan / "product-pack.json").read_text(encoding="utf-8") == (
        "operator-file-marker"
    )
    assert (orphan / "bridge").lstat().st_ino == observed["directory_inode"]
    assert (orphan / "bridge/operator-owned.txt").read_text(encoding="utf-8") == (
        "operator-directory-marker"
    )
    assert (orphan / "saved-product-pack.json").is_file()
    assert (orphan / "saved-bridge/src/main.ts").is_file()
    assert not target.exists()


def test_ordinary_publication_failure_preserves_one_private_orphan(
    tmp_path,
    monkeypatch,
) -> None:
    target = tmp_path / "target"
    ownerships = _observe_ownership(monkeypatch)

    def fail_publication(source, destination):
        raise OSError("runtime-secret-marker")

    monkeypatch.setattr(
        scaffold_module,
        "_publish_directory_no_replace",
        fail_publication,
    )
    with pytest.raises(ProductPackScaffoldError) as captured:
        scaffold_product_pack(
            ProductPackScaffoldRequest(_manifest(), str(target), "2.4.0")
        )

    assert captured.value.code is ProductPackScaffoldErrorCode.GENERATION_FAILED
    _assert_private_generated_orphan(tmp_path)
    _assert_descriptors_closed(ownerships[0])
    assert not target.exists()


def test_post_creation_capture_failure_preserves_one_private_orphan(
    tmp_path,
    monkeypatch,
) -> None:
    target = tmp_path / "target"
    created = []
    original_mkdtemp = scaffold_module.tempfile.mkdtemp

    def observed_mkdtemp(*args, **kwargs):
        path = original_mkdtemp(*args, **kwargs)
        created.append(Path(path))
        return path

    def fail_capture(path):
        raise OSError("runtime-secret-marker capture detail")

    monkeypatch.setattr(
        scaffold_module.tempfile,
        "mkdtemp",
        observed_mkdtemp,
    )
    monkeypatch.setattr(
        scaffold_module,
        "_capture_temporary_directory_ownership",
        fail_capture,
    )

    with pytest.raises(ProductPackScaffoldError) as captured:
        scaffold_product_pack(
            ProductPackScaffoldRequest(_manifest(), str(target), "2.4.0")
        )

    assert captured.value.code is ProductPackScaffoldErrorCode.GENERATION_FAILED
    assert _temporary_siblings(tmp_path) == tuple(created)
    assert stat.S_IMODE(created[0].lstat().st_mode) == 0o700
    assert not target.exists()


def test_descriptor_release_error_does_not_mask_active_control_flow(
    tmp_path,
    monkeypatch,
) -> None:
    target = tmp_path / "target"
    ownerships = _observe_ownership(monkeypatch)
    original_close = scaffold_module.os.close
    close_calls = []

    def interrupt_publication(source, destination):
        raise SystemExit("active-control-flow")

    def interrupt_after_close(descriptor):
        close_calls.append(descriptor)
        original_close(descriptor)
        if len(close_calls) == 1:
            raise KeyboardInterrupt("release-control-flow")

    monkeypatch.setattr(
        scaffold_module,
        "_publish_directory_no_replace",
        interrupt_publication,
    )
    monkeypatch.setattr(scaffold_module.os, "close", interrupt_after_close)

    with pytest.raises(SystemExit, match="active-control-flow"):
        scaffold_product_pack(
            ProductPackScaffoldRequest(_manifest(), str(target), "2.4.0")
        )
    assert close_calls == [
        ownerships[0].directory_descriptor,
        ownerships[0].parent_descriptor,
    ]
    _assert_private_generated_orphan(tmp_path)
    assert not target.exists()


def test_expected_descriptor_close_errors_are_suppressed_once_per_descriptor(
    tmp_path,
    monkeypatch,
) -> None:
    target = tmp_path / "target"
    ownerships = _observe_ownership(monkeypatch)
    original_close = scaffold_module.os.close
    close_calls = []

    def fail_publication(source, destination):
        raise OSError("runtime-secret-marker publication detail")

    def error_after_close(descriptor):
        close_calls.append(descriptor)
        original_close(descriptor)
        raise OSError("runtime-secret-marker close detail")

    monkeypatch.setattr(
        scaffold_module,
        "_publish_directory_no_replace",
        fail_publication,
    )
    monkeypatch.setattr(scaffold_module.os, "close", error_after_close)

    with pytest.raises(ProductPackScaffoldError) as captured:
        scaffold_product_pack(
            ProductPackScaffoldRequest(_manifest(), str(target), "2.4.0")
        )

    assert captured.value.code is ProductPackScaffoldErrorCode.GENERATION_FAILED
    assert close_calls == [
        ownerships[0].directory_descriptor,
        ownerships[0].parent_descriptor,
    ]
    _assert_private_generated_orphan(tmp_path)


@pytest.mark.parametrize(
    "release_error",
    [MemoryError, KeyboardInterrupt, SystemExit, GeneratorExit],
)
def test_descriptor_release_control_flow_propagates_without_active_control_flow(
    tmp_path,
    monkeypatch,
    release_error,
) -> None:
    target = tmp_path / "target"
    original_close = scaffold_module.os.close
    close_calls = []

    def fail_publication(source, destination):
        raise OSError()

    def interrupt_after_close(descriptor):
        close_calls.append(descriptor)
        original_close(descriptor)
        if len(close_calls) == 1:
            raise release_error()

    monkeypatch.setattr(
        scaffold_module,
        "_publish_directory_no_replace",
        fail_publication,
    )
    monkeypatch.setattr(scaffold_module.os, "close", interrupt_after_close)

    with pytest.raises(release_error):
        scaffold_product_pack(
            ProductPackScaffoldRequest(_manifest(), str(target), "2.4.0")
        )
    assert len(close_calls) == 2
    _assert_private_generated_orphan(tmp_path)


def test_recursive_cleanup_machinery_is_absent() -> None:
    assert not hasattr(scaffold_module, "_remove_owned_directory_contents")
    assert not hasattr(scaffold_module, "_remove_owned_temporary_directory")
    assert not hasattr(scaffold_module, "_cleanup_temporary_directory_safely")
    failure_sources = "\n".join(
        (
            inspect.getsource(scaffold_module.scaffold_product_pack),
            inspect.getsource(
                scaffold_module._release_temporary_directory_ownership
            ),
        )
    )
    for destructive_call in (
        "os.unlink(",
        "os.remove(",
        "os.rmdir(",
        "os.rename(",
        "os.replace(",
        "shutil.rmtree(",
    ):
        assert destructive_call not in failure_sources


def test_platform_without_no_replace_primitive_fails_closed(
    tmp_path,
    monkeypatch,
) -> None:
    target = tmp_path / "target"
    ownerships = _observe_ownership(monkeypatch)
    monkeypatch.setattr(scaffold_module.sys, "platform", "unsupported-os")

    with pytest.raises(ProductPackScaffoldError) as captured:
        scaffold_product_pack(
            ProductPackScaffoldRequest(_manifest(), str(target), "2.4.0")
        )

    assert captured.value.code is ProductPackScaffoldErrorCode.GENERATION_FAILED
    assert not target.exists()
    _assert_private_generated_orphan(tmp_path)
    _assert_descriptors_closed(ownerships[0])


def test_windows_publication_uses_native_no_replace_rename(
    tmp_path,
    monkeypatch,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    calls = []
    monkeypatch.setattr(scaffold_module.os, "name", "nt")
    monkeypatch.setattr(
        scaffold_module.os,
        "rename",
        lambda old, new: calls.append((old, new)),
    )

    scaffold_module._publish_directory_no_replace(source, target)

    assert calls == [(str(source), str(target))]


@pytest.mark.parametrize(
    ("platform", "function_name", "expected_flag"),
    [
        ("darwin", "renamex_np", 0x00000004),
        ("linux", "renameat2", 0x00000001),
    ],
)
def test_posix_publication_keeps_atomic_no_replace_policy(
    tmp_path,
    monkeypatch,
    platform: str,
    function_name: str,
    expected_flag: int,
) -> None:
    calls = []

    class FakeFunction:
        argtypes = None
        restype = None

        def __call__(self, *args):
            calls.append(args)
            return 0

    class FakeLibC:
        pass

    function = FakeFunction()
    libc = FakeLibC()
    setattr(libc, function_name, function)
    monkeypatch.setattr(scaffold_module.os, "name", "posix")
    monkeypatch.setattr(scaffold_module.sys, "platform", platform)
    monkeypatch.setattr(scaffold_module.ctypes, "CDLL", lambda *args, **kwargs: libc)

    scaffold_module._publish_directory_no_replace(
        tmp_path / "source",
        tmp_path / "target",
    )

    assert len(calls) == 1
    assert calls[0][-1] == expected_flag


@pytest.mark.parametrize("existing_kind", ["file", "empty-directory", "nonempty"])
def test_existing_target_is_rejected_without_modification(
    tmp_path,
    existing_kind: str,
) -> None:
    target = tmp_path / "existing"
    if existing_kind == "file":
        target.write_text("original", encoding="utf-8")
    else:
        target.mkdir()
        if existing_kind == "nonempty":
            (target / "original.txt").write_text("original", encoding="utf-8")
    before = (
        target.read_bytes()
        if target.is_file()
        else _file_bytes(target)
    )

    with pytest.raises(ProductPackScaffoldError) as captured:
        scaffold_product_pack(
            ProductPackScaffoldRequest(_manifest(), str(target), "2.4.0")
        )

    assert captured.value.code is ProductPackScaffoldErrorCode.TARGET_EXISTS
    after = target.read_bytes() if target.is_file() else _file_bytes(target)
    assert after == before
    assert not _temporary_siblings(tmp_path)


@pytest.mark.parametrize(
    "path_factory",
    [
        lambda root: "relative/output",
        lambda root: str(root / "child" / ".." / "output"),
        lambda root: "/" + "x" * 4097,
        lambda root: str(root / "bad\x00path"),
        lambda root: Path(root / "runtime-object"),
    ],
)
def test_invalid_output_paths_fail_before_writes(tmp_path, path_factory) -> None:
    before = set(tmp_path.iterdir())
    with pytest.raises(ProductPackScaffoldError) as captured:
        ProductPackScaffoldRequest(
            _manifest(),
            path_factory(tmp_path),
            "2.4.0",
        )
    assert captured.value.code is ProductPackScaffoldErrorCode.INVALID_REQUEST
    assert set(tmp_path.iterdir()) == before


def test_symlink_target_and_parent_are_rejected(tmp_path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    target_link = tmp_path / "target-link"
    target_link.symlink_to(real, target_is_directory=True)
    parent_link = tmp_path / "parent-link"
    parent_link.symlink_to(real, target_is_directory=True)

    for target in (target_link, parent_link / "output"):
        with pytest.raises(ProductPackScaffoldError) as captured:
            scaffold_product_pack(
                ProductPackScaffoldRequest(_manifest(), str(target), "2.4.0")
            )
        assert captured.value.code in {
            ProductPackScaffoldErrorCode.TARGET_EXISTS,
            ProductPackScaffoldErrorCode.UNSAFE_OUTPUT_PATH,
        }
    assert tuple(real.iterdir()) == ()


def test_expected_write_failure_preserves_only_generated_private_orphan(
    tmp_path,
    monkeypatch,
) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("untouched", encoding="utf-8")
    target = tmp_path / "target"
    ownerships = _observe_ownership(monkeypatch)

    original_write = scaffold_module._write_files

    def fail_write(root, files):
        original_write(root, files)
        raise OSError("runtime-secret-marker")

    monkeypatch.setattr(scaffold_module, "_write_files", fail_write)
    with pytest.raises(ProductPackScaffoldError) as captured:
        scaffold_product_pack(
            ProductPackScaffoldRequest(_manifest(), str(target), "2.4.0")
        )

    assert captured.value.code is ProductPackScaffoldErrorCode.GENERATION_FAILED
    assert captured.value.args == ("Product Pack scaffold generation failed",)
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
    assert not target.exists()
    assert outside.read_text(encoding="utf-8") == "untouched"
    orphan = _assert_private_generated_orphan(tmp_path)
    _assert_descriptors_closed(ownerships[0])
    assert tuple(sorted(_file_bytes(orphan))) == tuple(
        sorted(scaffold_module._render_files(_manifest(), "2.4.0"))
    )


def test_generated_tree_has_exact_allowlist_and_no_runtime_outputs(tmp_path) -> None:
    _, target, result = _scaffold(tmp_path)
    actual = tuple(sorted(_file_bytes(target)))

    assert actual == result.generated_files
    assert actual == (
        ".gitignore",
        "README.md",
        "bridge/package.json",
        "bridge/src/capture_backend.ts",
        "bridge/src/main.ts",
        "bridge/src/product_backend.ts",
        "bridge/src/protocol.ts",
        "bridge/tsconfig.json",
        "product-pack.json",
        "pyproject.toml",
        "src/pmqa_product_pack_external_demo/__init__.py",
        "src/pmqa_product_pack_external_demo/manifest.py",
        "tests/test_manifest.py",
    )
    forbidden_names = {
        ".env",
        "node_modules",
        "package-lock.json",
        "artifacts",
        "screenshots",
        "traces",
        "generated_tests",
        "storage_state",
        "__pycache__",
    }
    assert not any(forbidden_names.intersection(path.parts) for path in target.rglob("*"))


def test_manifest_identity_entry_point_and_plain_dictionary_are_exact(
    tmp_path,
) -> None:
    manifest, target, result = _scaffold(tmp_path)
    manifest_text = target.joinpath("product-pack.json").read_text(encoding="utf-8")
    assert manifest_text == json.dumps(
        manifest.to_dict(), ensure_ascii=False, separators=(",", ":")
    ) + "\n"
    pyproject = target.joinpath("pyproject.toml").read_text(encoding="utf-8")
    assert pyproject.count('[project.entry-points."pmqa.product_packs"]') == 1
    assert (
        '"external-demo" = "pmqa_product_pack_external_demo.manifest:'
        'PRODUCT_PACK_MANIFEST"'
    ) in pyproject
    assert 'namespaces = false' in pyproject
    assert 'include = ["pmqa_product_pack_external_demo"]' in pyproject

    statement = "\n".join(
        [
            "import sys",
            f"sys.path.insert(0, {str(target / 'src')!r})",
            "from pmqa_product_pack_external_demo.manifest import PRODUCT_PACK_MANIFEST",
            "assert type(PRODUCT_PACK_MANIFEST) is dict",
            f"assert PRODUCT_PACK_MANIFEST == {manifest.to_dict()!r}",
        ]
    )
    completed = subprocess.run(
        [sys.executable, "-c", statement],
        cwd=tmp_path,
        capture_output=True,
        check=False,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert result.distribution_name == "pmqa-product-pack-external-demo"
    assert 'version = "2.4.0"' in pyproject
    assert json.loads(manifest_text)["pack_version"] == "1.2.3"


def test_typescript_scaffold_is_direct_fail_closed_and_has_no_mcp(tmp_path) -> None:
    _, target, _ = _scaffold(tmp_path)
    protocol = target.joinpath("bridge/src/protocol.ts").read_text(encoding="utf-8")
    backend = target.joinpath("bridge/src/capture_backend.ts").read_text(encoding="utf-8")
    main = target.joinpath("bridge/src/main.ts").read_text(encoding="utf-8")
    product_backend = target.joinpath(
        "bridge/src/product_backend.ts"
    ).read_text(encoding="utf-8")
    control = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            target / "bridge/package.json",
            target / "bridge/tsconfig.json",
            target / "bridge/src/protocol.ts",
            target / "bridge/src/capture_backend.ts",
            target / "bridge/src/main.ts",
            target / "bridge/src/product_backend.ts",
            target / "pyproject.toml",
        )
    ).casefold()

    assert 'BRIDGE_PROTOCOL_VERSION = "1"' in protocol
    assert 'BridgeOperation = "exploration_capture"' in protocol
    assert 'BridgeStatus = "succeeded" | "failed"' in protocol
    assert set(("exploration_failed", "action_plan_rejected", "protocol_failure")) <= set(
        code for code in ("exploration_failed", "action_plan_rejected", "protocol_failure") if code in protocol
    )
    assert "interface ProductCaptureBackend" in backend
    assert 'status: "failed"' in backend
    assert 'failure_code: "protocol_failure"' in backend
    assert "evidence: null" in backend
    assert 'status: "succeeded"' not in backend
    assert "process.stdout.write(JSON.stringify(response))" in main
    assert "createProductCaptureBackend().capture(request)" in main
    assert "return new UnimplementedCaptureBackend()" in product_backend
    for forbidden in (
        "mcp",
        "@playwright/mcp",
        "playwright-mcp",
        "mcpservers",
        "npx ",
        '"latest"',
        '"preinstall"',
        '"postinstall"',
        '"prepare"',
        "child_process",
        "eval(",
    ):
        assert forbidden not in control


def test_legitimate_custom_backend_is_source_conformant_but_not_verified(
    tmp_path,
) -> None:
    _, target, _ = _scaffold(tmp_path)
    target.joinpath("bridge/src/product_backend.ts").write_text(
        '''import type { ProductCaptureBackend } from "./capture_backend.js";

class ApprovedDirectBackend {
  async capture(request: unknown): Promise<never> {
    void request;
    throw new Error("consumer implementation is tested separately");
  }
}

export function createProductCaptureBackend(): ProductCaptureBackend {
  return new ApprovedDirectBackend() as ProductCaptureBackend;
}
''',
        encoding="utf-8",
    )

    result = validate_product_pack_source(str(target))

    assert result.is_conformant is True
    assert result.backend_source_state is ProductPackBackendSourceState.CUSTOM
    assert result.is_runtime_verified is False
    assert "runtime" not in result.message.casefold()


def test_direct_exact_playwright_dependency_is_source_conformant(tmp_path) -> None:
    _, target, _ = _scaffold(tmp_path)
    _write_bridge_package(
        target,
        lambda value: value.update(
            {"dependencies": {"playwright": "1.45.2"}}
        ),
    )

    result = validate_product_pack_source(str(target))

    assert result.is_conformant is True
    assert result.backend_source_state is ProductPackBackendSourceState.PLACEHOLDER


@pytest.mark.parametrize(
    "update",
    [
        lambda value: value.update(
            {"dependencies": {"@playwright/mcp": "1.0.0"}}
        ),
        lambda value: value["scripts"].update(
            {"postinstall": "npx playwright install"}
        ),
        lambda value: value["scripts"].update({"build": "arbitrary command"}),
        lambda value: value.update(
            {"dependencies": {"playwright": "latest"}}
        ),
        lambda value: value.update(
            {"dependencies": {"playwright": "file:../runtime"}}
        ),
        lambda value: value.update(
            {"dependencies": {"playwright": "https://example.invalid/a"}}
        ),
        lambda value: value.update(
            {"dependencies": {"playwright": "git+https://example.invalid/a"}}
        ),
        lambda value: value.update(
            {"dependencies": {"playwright": "workspace:*"}}
        ),
    ],
)
def test_unsafe_bridge_dependency_and_script_controls_are_rejected(
    tmp_path,
    update,
) -> None:
    _, target, _ = _scaffold(tmp_path)
    _write_bridge_package(target, update)

    result = validate_product_pack_source(str(target))

    assert result.error_code is ProductPackSourceConformanceErrorCode.INVALID_BRIDGE_SOURCE
    assert result.backend_source_state is None
    assert result.is_runtime_verified is False


@pytest.mark.parametrize(
    "package_text",
    [
        '{"name":"one","name":"two"}\n',
        "{malformed\n",
        '{"name":"pmqa-product-pack-external-demo-bridge"}\n',
    ],
)
def test_duplicate_malformed_or_noncanonical_bridge_package_is_rejected(
    tmp_path,
    package_text: str,
) -> None:
    _, target, _ = _scaffold(tmp_path)
    target.joinpath("bridge/package.json").write_text(
        package_text,
        encoding="utf-8",
    )

    result = validate_product_pack_source(str(target))

    assert result.error_code is ProductPackSourceConformanceErrorCode.INVALID_BRIDGE_SOURCE


def test_source_conformance_succeeds_and_does_not_mutate_manifest(tmp_path) -> None:
    manifest, target, _ = _scaffold(tmp_path)
    before = copy.deepcopy(manifest.to_dict())

    result = validate_product_pack_source(str(target), manifest)

    assert result == ProductPackSourceConformanceResult(
        True,
        None,
        ProductPackBackendSourceState.PLACEHOLDER,
        False,
    )
    assert result.backend_source_state is ProductPackBackendSourceState.PLACEHOLDER
    assert result.is_runtime_verified is False
    assert result.message == "Product Pack source conforms"
    assert manifest.to_dict() == before
    with pytest.raises(FrozenInstanceError):
        result.is_conformant = False


def test_distribution_version_can_change_independently_and_remain_conformant(
    tmp_path,
) -> None:
    manifest, target, _ = _scaffold(tmp_path)
    pyproject = target.joinpath("pyproject.toml")
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8").replace(
            'version = "2.4.0"',
            'version = "3.1.0"',
        ),
        encoding="utf-8",
    )

    result = validate_product_pack_source(str(target), manifest)

    assert result.is_conformant is True
    assert json.loads(
        target.joinpath("product-pack.json").read_text(encoding="utf-8")
    )["pack_version"] == "1.2.3"


@pytest.mark.parametrize(
    "invalid_version",
    [
        "v2.4.0",
        "2.4.0+LOCAL",
        "1.2.3-foo.1",
        "https://runtime-secret-marker.invalid/version",
        object(),
    ],
)
def test_invalid_distribution_version_fails_before_any_write(
    tmp_path,
    invalid_version,
) -> None:
    before = set(tmp_path.iterdir())
    with pytest.raises(ProductPackScaffoldError) as captured:
        ProductPackScaffoldRequest(
            _manifest(),
            str(tmp_path / "target"),
            invalid_version,
        )
    formatted = "".join(
        traceback.format_exception(
            type(captured.value),
            captured.value,
            captured.value.__traceback__,
        )
    )
    assert captured.value.code is ProductPackScaffoldErrorCode.INVALID_REQUEST
    assert set(tmp_path.iterdir()) == before
    assert "runtime-secret-marker" not in formatted


def test_source_conformance_rejects_missing_malformed_and_mismatched_controls(
    tmp_path,
) -> None:
    manifest, missing, _ = _scaffold(tmp_path, "missing")
    missing.joinpath("bridge/src/main.ts").unlink()
    assert validate_product_pack_source(str(missing)).error_code is (
        ProductPackSourceConformanceErrorCode.INVALID_LAYOUT
    )

    _, malformed, _ = _scaffold(tmp_path, "malformed")
    malformed.joinpath("product-pack.json").write_text("{bad", encoding="utf-8")
    assert validate_product_pack_source(str(malformed)).error_code is (
        ProductPackSourceConformanceErrorCode.INVALID_MANIFEST
    )

    _, mismatch, _ = _scaffold(tmp_path, "mismatch")
    different = _manifest(pack_version="2.0.0")
    assert validate_product_pack_source(str(mismatch), different).error_code is (
        ProductPackSourceConformanceErrorCode.MANIFEST_MISMATCH
    )
    assert manifest.pack_version == "1.2.3"


@pytest.mark.parametrize(
    "manifest_text",
    [
        '{"schema_version":"1","schema_version":"1"}\n',
        json.dumps(_manifest().to_dict(), indent=2) + "\n",
        '{"schema_version":NaN}\n',
    ],
)
def test_source_conformance_rejects_duplicate_or_noncanonical_manifest_json(
    tmp_path,
    manifest_text: str,
) -> None:
    _, target, _ = _scaffold(tmp_path)
    target.joinpath("product-pack.json").write_text(
        manifest_text,
        encoding="utf-8",
    )
    result = validate_product_pack_source(str(target))
    assert result.error_code is ProductPackSourceConformanceErrorCode.INVALID_MANIFEST


@pytest.mark.parametrize(
    ("relative_path", "replacement", "code"),
    [
        (
            "pyproject.toml",
            "\n[project.entry-points.\"pmqa.product_packs\"]\nother='x:y'\n",
            ProductPackSourceConformanceErrorCode.INVALID_PYTHON_DISTRIBUTION,
        ),
        (
            "src/pmqa_product_pack_external_demo/manifest.py",
            "PRODUCT_PACK_MANIFEST = {}\n",
            ProductPackSourceConformanceErrorCode.INVALID_PYTHON_DISTRIBUTION,
        ),
        (
            "bridge/src/protocol.ts",
            'export const BRIDGE_PROTOCOL_VERSION = "2";\n',
            ProductPackSourceConformanceErrorCode.INVALID_BRIDGE_SOURCE,
        ),
        (
            "bridge/src/capture_backend.ts",
            'const status = "succeeded";\n',
            ProductPackSourceConformanceErrorCode.INVALID_BRIDGE_SOURCE,
        ),
        (
            "bridge/src/product_backend.ts",
            "export function wrongFactory() {}\n",
            ProductPackSourceConformanceErrorCode.INVALID_BRIDGE_SOURCE,
        ),
        (
            "bridge/src/product_backend.ts",
            "// export function createProductCaptureBackend(): ProductCaptureBackend {}\n",
            ProductPackSourceConformanceErrorCode.INVALID_BRIDGE_SOURCE,
        ),
        (
            "bridge/package.json",
            '{"scripts":{"postinstall":"npx runtime-secret-marker"}}\n',
            ProductPackSourceConformanceErrorCode.INVALID_BRIDGE_SOURCE,
        ),
    ],
)
def test_source_conformance_rejects_distribution_and_bridge_drift(
    tmp_path,
    relative_path: str,
    replacement: str,
    code,
) -> None:
    _, target, _ = _scaffold(tmp_path)
    target.joinpath(relative_path).write_text(replacement, encoding="utf-8")

    result = validate_product_pack_source(str(target))

    assert result.error_code is code
    assert "runtime-secret-marker" not in result.message
    assert str(target) not in result.message


def test_source_conformance_rejects_symlinked_control_path_without_following(
    tmp_path,
) -> None:
    _, target, _ = _scaffold(tmp_path)
    outside = tmp_path / "outside"
    shutil.copytree(target / "bridge", outside)
    shutil.rmtree(target / "bridge")
    (target / "bridge").symlink_to(outside, target_is_directory=True)

    result = validate_product_pack_source(str(target))

    assert result.error_code is ProductPackSourceConformanceErrorCode.INVALID_LAYOUT


@pytest.mark.parametrize("failure", ["missing", "symlink", "oversized"])
def test_consumer_backend_must_be_a_bounded_regular_file(
    tmp_path,
    failure: str,
) -> None:
    _, target, _ = _scaffold(tmp_path)
    backend = target / "bridge/src/product_backend.ts"
    if failure == "missing":
        backend.unlink()
    elif failure == "symlink":
        outside = tmp_path / "outside.ts"
        outside.write_text("runtime-secret-marker", encoding="utf-8")
        backend.unlink()
        backend.symlink_to(outside)
    else:
        backend.write_bytes(b"x" * (256 * 1024 + 1))

    result = validate_product_pack_source(str(target))

    assert result.error_code is ProductPackSourceConformanceErrorCode.INVALID_LAYOUT
    assert "runtime-secret-marker" not in result.message


def test_safe_scaffold_error_and_conformance_result_do_not_leak_markers(
    tmp_path,
) -> None:
    target = tmp_path / "runtime-secret-marker"
    target.mkdir()
    with pytest.raises(ProductPackScaffoldError) as captured:
        scaffold_product_pack(
            ProductPackScaffoldRequest(_manifest(), str(target), "2.4.0")
        )
    formatted = "".join(
        traceback.format_exception(
            type(captured.value), captured.value, captured.value.__traceback__
        )
    )
    assert "runtime-secret-marker" not in formatted
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None

    invalid = validate_product_pack_source(str(target))
    assert "runtime-secret-marker" not in invalid.message
    assert str(target) not in invalid.message


@pytest.mark.parametrize(
    "source",
    ["relative", object(), Path("runtime-object")],
)
def test_source_conformance_invalid_requests_are_fixed_and_safe(source) -> None:
    result = validate_product_pack_source(source)
    assert result.error_code is ProductPackSourceConformanceErrorCode.INVALID_REQUEST
    assert result.message == "invalid Product Pack source validation request"


def test_request_and_manifest_are_unchanged_after_scaffolding(tmp_path) -> None:
    manifest = _manifest()
    request = ProductPackScaffoldRequest(
        manifest,
        str(tmp_path / "target"),
        "2.4.0",
    )
    manifest_before = copy.deepcopy(manifest.to_dict())
    request_before = (
        request.manifest,
        request.output_directory,
        request.distribution_version,
    )

    scaffold_product_pack(request)

    assert manifest.to_dict() == manifest_before
    assert (
        request.manifest,
        request.output_directory,
        request.distribution_version,
    ) == request_before


def test_cli_scaffold_and_validate_source_success(tmp_path, capsys) -> None:
    target = tmp_path / "cli-pack"
    scaffold_code = cli.main(
        [
            "product-pack",
            "scaffold",
            "--output",
            str(target),
            "--pack-id",
            "external-demo",
            "--pack-version",
            "1.2.3",
            "--distribution-version",
            "2.4.0",
            "--product-id",
            "demo",
            "--display-name",
            "External Demo Pack",
            "--capability",
            "exploration_capture",
        ]
    )
    scaffold_output = capsys.readouterr()
    assert scaffold_code == 0
    assert scaffold_output.out == "product_pack_scaffold_created file_count=13\n"
    assert scaffold_output.err == ""
    assert str(target) not in scaffold_output.out

    validation_code = cli.main(
        ["product-pack", "validate-source", "--source", str(target)]
    )
    validation_output = capsys.readouterr()
    assert validation_code == 0
    assert validation_output.out == "product_pack_source_valid\n"
    assert validation_output.err == ""


@pytest.mark.parametrize(
    "arguments",
    [
        [
            "product-pack", "scaffold", "--output", "relative-marker",
            "--pack-id", "BAD-runtime-secret-marker", "--pack-version", "1.2.3",
            "--distribution-version", "2.4.0",
            "--product-id", "demo", "--display-name", "Name",
            "--capability", "exploration_capture",
        ],
        [
            "product-pack", "scaffold", "--output", "/runtime-output",
            "--pack-id", "external-demo", "--pack-version", "1.2.3",
            "--distribution-version", "v-runtime-secret-marker",
            "--product-id", "demo", "--display-name", "Name",
            "--capability", "exploration_capture",
        ],
        ["product-pack", "validate-source", "--source", "relative-marker"],
    ],
)
def test_cli_expected_failures_are_fixed_and_safe(arguments, capsys) -> None:
    assert cli.main(arguments) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == "product_pack_command_failed\n"
    assert "runtime-secret-marker" not in output.err
    assert "relative-marker" not in output.err


def test_cli_product_pack_commands_are_product_lazy_and_launch_nothing() -> None:
    statement = "\n".join(
        [
            "import subprocess, sys",
            "def forbidden(*args, **kwargs): raise AssertionError('launched')",
            "subprocess.Popen = forbidden",
            "subprocess.run = forbidden",
            "import pmqa.cli as cli",
            "code = cli.main(['product-pack', 'validate-source', '--source', 'relative'])",
            "assert code == 2",
            "blocked = ('products.demo', 'playwright', 'langgraph', 'pmqa.runtime', 'pmqa.supervisor', 'pmqa.orchestration')",
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
    assert completed.stderr == "product_pack_command_failed\n"


def test_unsupported_product_pack_subcommand_remains_product_lazy() -> None:
    statement = "\n".join(
        [
            "import sys",
            "import pmqa.cli as cli",
            "try: cli.main(['product-pack', 'unsupported'])",
            "except SystemExit as error: assert error.code == 2",
            "else: raise AssertionError('unsupported command was accepted')",
            "assert not any(name == 'products.demo' or name.startswith('products.demo.') for name in sys.modules)",
        ]
    )
    completed = subprocess.run(
        [sys.executable, "-c", statement],
        capture_output=True,
        check=False,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_generated_external_wheel_loads_explicitly_outside_checkout(
    tmp_path,
) -> None:
    manifest = _manifest(pack_version="1.2.3-foo.1")
    manifest, source, scaffold_result = _scaffold(
        tmp_path,
        "wheel-source",
        manifest=manifest,
        distribution_version="2.4.0",
    )
    wheel_directory = tmp_path / "wheel-output"
    installed_target = tmp_path / "installed-target"
    unrelated = tmp_path / "unrelated-working-directory"
    wheel_directory.mkdir()
    installed_target.mkdir()
    unrelated.mkdir()

    build = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            str(wheel_directory),
            str(source),
        ],
        cwd=tmp_path,
        capture_output=True,
        check=False,
        text=True,
    )
    assert build.returncode == 0, build.stdout + build.stderr
    wheels = tuple(wheel_directory.glob("*.whl"))
    assert len(wheels) == 1
    assert "2.4.0" in wheels[0].name
    assert "foo" not in wheels[0].name
    with zipfile.ZipFile(wheels[0]) as archive:
        names = set(archive.namelist())
        assert "pmqa_product_pack_external_demo/__init__.py" in names
        assert "pmqa_product_pack_external_demo/manifest.py" in names
        assert not any(name.startswith("tests/") for name in names)
        assert not any(name.startswith("bridge/") for name in names)
        assert "product-pack.json" not in names
        archive.extractall(installed_target)
    assert manifest.pack_version == "1.2.3-foo.1"
    assert scaffold_result.distribution_version == "2.4.0"

    statement = """
import sys
from importlib import metadata
from pathlib import Path
from pmqa.product_pack import (
    ProductPackLoadRequest,
    ProductPackManifest,
    load_product_pack_manifest,
)
import pmqa

target = Path(sys.argv[1]).resolve()
repository = Path(sys.argv[2]).resolve()
distribution_name = sys.argv[3]
expected = ProductPackManifest.from_dict(__import__("json").loads(sys.argv[4]))
loaded = load_product_pack_manifest(
    ProductPackLoadRequest(distribution_name, expected)
)
assert loaded.manifest == expected
assert loaded.manifest is not expected
assert "products.demo" not in sys.modules

import pmqa_product_pack_external_demo
import pmqa_product_pack_external_demo.manifest as pack_manifest
for module in (pmqa_product_pack_external_demo, pack_manifest):
    module_path = Path(module.__file__).resolve()
    module_path.relative_to(target)
    try:
        module_path.relative_to(repository)
    except ValueError:
        pass
    else:
        raise AssertionError("generated pack imported from source checkout")
distribution_root = Path(metadata.distribution(distribution_name).locate_file("")).resolve()
distribution_root.relative_to(target)
Path(pmqa.__file__).resolve().relative_to(repository)
"""
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONHOME", "PYTHONPATH"}
    }
    environment["PYTHONPATH"] = os.pathsep.join(
        (str(REPOSITORY_ROOT), str(installed_target))
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            statement,
            str(installed_target),
            str(REPOSITORY_ROOT),
            scaffold_result.distribution_name,
            json.dumps(manifest.to_dict()),
        ],
        cwd=unrelated,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
