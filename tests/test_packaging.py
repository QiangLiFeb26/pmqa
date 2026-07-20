"""Offline distribution tests for PMQA and the SauceDemo product pack."""

import configparser
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_PRODUCT_MODULES = {
    "products/__init__.py",
    "products/demo/__init__.py",
    "products/demo/application.py",
    "products/demo/artifact_handoff.py",
    "products/demo/capture.py",
    "products/demo/config.py",
    "products/demo/execution.py",
    "products/demo/exploration_contracts.py",
    "products/demo/exploration_tool.py",
    "products/demo/explorer_agent.py",
    "products/demo/generator.py",
    "products/demo/knowledge_agent.py",
    "products/demo/knowledge_mapping.py",
    "products/demo/reasoning.py",
    "products/demo/validation.py",
    "products/demo/validator_agent.py",
    "products/demo/workflow.py",
}
FORBIDDEN_EXACT_ENTRIES = {
    "products/demo/artifacts/knowledge.json",
    "products/demo/generated_tests/test_saucedemo_generated.py",
}
FORBIDDEN_DIRECTORY_NAMES = {
    "__pycache__",
    ".cache",
    "artifacts",
    "blob-report",
    "browser-cache",
    "generated_tests",
    "ms-playwright",
    "playwright-cache",
    "playwright-report",
    "screenshots",
    "test-results",
    "traces",
}
ALLOWED_DIST_INFO_FILES = {
    "METADATA",
    "RECORD",
    "WHEEL",
    "entry_points.txt",
    "top_level.txt",
}


@pytest.fixture(scope="session")
def built_wheel(tmp_path_factory) -> Path:
    """Build the real pyproject distribution offline outside the repository."""

    workspace = tmp_path_factory.mktemp("packaging-build")
    source = workspace / "source"
    wheel_directory = workspace / "wheel"
    wheel_directory.mkdir()
    shutil.copytree(
        REPOSITORY_ROOT,
        source,
        ignore=shutil.ignore_patterns(
            ".git",
            ".venv",
            ".pytest_cache",
            "__pycache__",
            "*.pyc",
            "*.egg-info",
            ".DS_Store",
            "build",
            "dist",
        ),
    )
    completed = subprocess.run(
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
        cwd=workspace,
        capture_output=True,
        check=False,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    wheels = tuple(wheel_directory.glob("*.whl"))
    assert len(wheels) == 1
    return wheels[0]


def test_actual_wheel_contains_product_pack_config_and_entry_point(
    built_wheel,
) -> None:
    with zipfile.ZipFile(built_wheel) as archive:
        names = set(archive.namelist())
        entry_point_files = [
            name
            for name in names
            if name.endswith(".dist-info/entry_points.txt")
        ]

        assert "pmqa/__init__.py" in names
        assert "pmqa/product_pack/__init__.py" in names
        assert "pmqa/product_pack/manifest.py" in names
        assert "pmqa/product_pack/loader.py" in names
        assert REQUIRED_PRODUCT_MODULES <= names
        assert "products/demo/config/product.json" in names
        assert len(entry_point_files) == 1

        entry_points = configparser.ConfigParser()
        entry_points.read_string(
            archive.read(entry_point_files[0]).decode("utf-8")
        )
        assert entry_points["console_scripts"]["pmqa"] == "pmqa.cli:main"


def test_actual_wheel_excludes_runtime_outputs_and_unrelated_files(
    built_wheel,
) -> None:
    with zipfile.ZipFile(built_wheel) as archive:
        names = set(archive.namelist())

    assert FORBIDDEN_EXACT_ENTRIES.isdisjoint(names)
    assert not any("external_demo_pack" in name for name in names)
    assert not any("external-demo-fixture" in name for name in names)
    for name in names:
        path = PurePosixPath(name)
        root = path.parts[0]
        assert not FORBIDDEN_DIRECTORY_NAMES.intersection(path.parts)
        assert path.suffix not in {".pyc", ".sqlite", ".sqlite3"}
        assert path.name != ".env" and not path.name.startswith(".env.")
        assert "credential" not in path.name.casefold()
        if root == "pmqa":
            assert path.suffix == ".py"
        elif root == "products":
            assert name in REQUIRED_PRODUCT_MODULES | {
                "products/demo/config/product.json"
            }
        else:
            assert root.endswith(".dist-info")
            assert len(path.parts) == 2
            assert path.name in ALLOWED_DIST_INFO_FILES


def test_built_distribution_imports_and_loads_config_outside_checkout(
    built_wheel, tmp_path
) -> None:
    distribution = tmp_path / "distribution"
    unrelated_working_directory = tmp_path / "outside"
    distribution.mkdir()
    unrelated_working_directory.mkdir()
    with zipfile.ZipFile(built_wheel) as archive:
        archive.extractall(distribution)

    statement = """
import json
import sys
from pathlib import Path

distribution = Path(sys.argv[1]).resolve()
repository = Path(sys.argv[2]).resolve()

def outside_repository(entry):
    resolved = Path(entry).resolve()
    if "site-packages" in resolved.parts:
        return True
    try:
        resolved.relative_to(repository)
    except ValueError:
        return True
    return False

sys.path[:] = [str(distribution)] + [
    entry for entry in sys.path if entry and outside_repository(entry)
]
sys.meta_path[:] = [
    finder
    for finder in sys.meta_path
    if "__editable__" not in getattr(finder, "__module__", "")
]

import pmqa
import pmqa.product_pack
import products.demo
import products.demo.application
from products.demo.config import load_config, validate_config

assert pmqa.product_pack.ProductPackManifest
assert pmqa.product_pack.ProductPackCapability
assert pmqa.product_pack.ProductPackManifestValidationError
modules = (pmqa, pmqa.product_pack, products.demo, products.demo.application)
for module in modules:
    module_path = Path(module.__file__).resolve()
    module_path.relative_to(distribution)
    try:
        module_path.relative_to(repository)
    except ValueError:
        pass
    else:
        raise AssertionError("source-checkout module was imported")

product_root = Path(products.demo.__file__).resolve().parents[2]
config = validate_config(load_config(product_root))
assert config.product_id == "demo"
config_path = Path(products.demo.__file__).parent / "config/product.json"
assert json.loads(config_path.read_text(encoding="utf-8"))["product_id"] == "demo"
"""
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            statement,
            str(distribution),
            str(REPOSITORY_ROOT),
        ],
        cwd=unrelated_working_directory,
        env={
            key: value
            for key, value in os.environ.items()
            if key not in {"PYTHONHOME", "PYTHONPATH"}
        },
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
