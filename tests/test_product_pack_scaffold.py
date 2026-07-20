"""Offline tests for Product Pack scaffolding and source conformance."""

import copy
from dataclasses import FrozenInstanceError
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback
import zipfile

import pytest

from pmqa import cli
from pmqa.product_pack import (
    PRODUCT_PACK_SCAFFOLD_VERSION,
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


def _scaffold(tmp_path: Path, name: str = "external-pack"):
    manifest = _manifest()
    target = tmp_path / name
    request = ProductPackScaffoldRequest(manifest, str(target))
    result = scaffold_product_pack(request)
    return manifest, target, result


def _file_bytes(root: Path):
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_public_contracts_are_exact_frozen_and_path_free(tmp_path) -> None:
    manifest, target, result = _scaffold(tmp_path)

    assert tuple(ProductPackScaffoldRequest.__dataclass_fields__) == (
        "manifest",
        "output_directory",
    )
    assert tuple(ProductPackScaffoldResult.__dataclass_fields__) == (
        "scaffold_version",
        "distribution_name",
        "python_package_name",
        "generated_files",
    )
    assert tuple(ProductPackSourceConformanceResult.__dataclass_fields__) == (
        "is_conformant",
        "error_code",
    )
    assert result.scaffold_version == PRODUCT_PACK_SCAFFOLD_VERSION == "1"
    assert result.distribution_name == "pmqa-product-pack-external-demo"
    assert result.python_package_name == "pmqa_product_pack_external_demo"
    assert str(target) not in repr(result)
    with pytest.raises(FrozenInstanceError):
        result.distribution_name = "changed"
    with pytest.raises(FrozenInstanceError):
        ProductPackScaffoldRequest(manifest, str(tmp_path / "next")).manifest = None


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


def test_publication_uses_one_final_rename(tmp_path, monkeypatch) -> None:
    calls = []
    original_rename = scaffold_module.os.rename

    def observed_rename(source, target):
        calls.append((Path(source), Path(target)))
        return original_rename(source, target)

    monkeypatch.setattr(scaffold_module.os, "rename", observed_rename)
    _, target, _ = _scaffold(tmp_path)

    assert len(calls) == 1
    assert calls[0][0].parent == target.parent
    assert calls[0][0].name.startswith(".pmqa-scaffold-")
    assert calls[0][1] == target


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
        scaffold_product_pack(ProductPackScaffoldRequest(_manifest(), str(target)))

    assert captured.value.code is ProductPackScaffoldErrorCode.TARGET_EXISTS
    after = target.read_bytes() if target.is_file() else _file_bytes(target)
    assert after == before


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
        ProductPackScaffoldRequest(_manifest(), path_factory(tmp_path))
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
                ProductPackScaffoldRequest(_manifest(), str(target))
            )
        assert captured.value.code in {
            ProductPackScaffoldErrorCode.TARGET_EXISTS,
            ProductPackScaffoldErrorCode.UNSAFE_OUTPUT_PATH,
        }
    assert tuple(real.iterdir()) == ()


def test_expected_generation_failure_cleans_only_private_temporary_directory(
    tmp_path,
    monkeypatch,
) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("untouched", encoding="utf-8")
    target = tmp_path / "target"

    def fail_write(root, files):
        (root / "partial.txt").write_text("partial", encoding="utf-8")
        raise OSError("runtime-secret-marker")

    monkeypatch.setattr(scaffold_module, "_write_files", fail_write)
    with pytest.raises(ProductPackScaffoldError) as captured:
        scaffold_product_pack(ProductPackScaffoldRequest(_manifest(), str(target)))

    assert captured.value.code is ProductPackScaffoldErrorCode.GENERATION_FAILED
    assert captured.value.args == ("Product Pack scaffold generation failed",)
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
    assert not target.exists()
    assert outside.read_text(encoding="utf-8") == "untouched"
    assert not tuple(tmp_path.glob(".pmqa-scaffold-*"))


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


def test_typescript_scaffold_is_direct_fail_closed_and_has_no_mcp(tmp_path) -> None:
    _, target, _ = _scaffold(tmp_path)
    protocol = target.joinpath("bridge/src/protocol.ts").read_text(encoding="utf-8")
    backend = target.joinpath("bridge/src/capture_backend.ts").read_text(encoding="utf-8")
    main = target.joinpath("bridge/src/main.ts").read_text(encoding="utf-8")
    control = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            target / "bridge/package.json",
            target / "bridge/tsconfig.json",
            target / "bridge/src/protocol.ts",
            target / "bridge/src/capture_backend.ts",
            target / "bridge/src/main.ts",
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


def test_source_conformance_succeeds_and_does_not_mutate_manifest(tmp_path) -> None:
    manifest, target, _ = _scaffold(tmp_path)
    before = copy.deepcopy(manifest.to_dict())

    result = validate_product_pack_source(str(target), manifest)

    assert result == ProductPackSourceConformanceResult(True, None)
    assert result.message == "Product Pack source conforms"
    assert manifest.to_dict() == before
    with pytest.raises(FrozenInstanceError):
        result.is_conformant = False


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


def test_safe_scaffold_error_and_conformance_result_do_not_leak_markers(
    tmp_path,
) -> None:
    target = tmp_path / "runtime-secret-marker"
    target.mkdir()
    with pytest.raises(ProductPackScaffoldError) as captured:
        scaffold_product_pack(ProductPackScaffoldRequest(_manifest(), str(target)))
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
    request = ProductPackScaffoldRequest(manifest, str(tmp_path / "target"))
    manifest_before = copy.deepcopy(manifest.to_dict())
    request_before = (request.manifest, request.output_directory)

    scaffold_product_pack(request)

    assert manifest.to_dict() == manifest_before
    assert (request.manifest, request.output_directory) == request_before


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
    assert scaffold_output.out == "product_pack_scaffold_created file_count=12\n"
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
    manifest, source, scaffold_result = _scaffold(tmp_path, "wheel-source")
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
    with zipfile.ZipFile(wheels[0]) as archive:
        names = set(archive.namelist())
        assert "pmqa_product_pack_external_demo/__init__.py" in names
        assert "pmqa_product_pack_external_demo/manifest.py" in names
        assert not any(name.startswith("tests/") for name in names)
        assert not any(name.startswith("bridge/") for name in names)
        assert "product-pack.json" not in names
        archive.extractall(installed_target)

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
