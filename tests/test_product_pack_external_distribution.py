"""Offline integration test for a separately packaged Product Pack manifest."""

import os
from pathlib import Path
import subprocess
import sys
import zipfile


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_real_external_distribution_loads_from_unrelated_directory(tmp_path) -> None:
    source = tmp_path / "external-source"
    package = source / "external_demo_pack"
    wheel_directory = tmp_path / "wheel"
    target = tmp_path / "installed-distribution"
    unrelated = tmp_path / "unrelated-working-directory"
    package.mkdir(parents=True)
    wheel_directory.mkdir()
    target.mkdir()
    unrelated.mkdir()

    (source / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "pmqa-external-demo-fixture"
version = "0.0.1"
requires-python = ">=3.9"

[project.entry-points."pmqa.product_packs"]
external-demo = "external_demo_pack:PRODUCT_PACK_MANIFEST"

[tool.setuptools.packages.find]
include = ["external_demo_pack"]
""",
        encoding="utf-8",
    )
    (package / "__init__.py").write_text(
        """PRODUCT_PACK_MANIFEST = {
    "schema_version": "1",
    "product_pack_api_version": "1",
    "pack_id": "external-demo",
    "pack_version": "1.2.3",
    "product_id": "demo",
    "display_name": "External Demo Pack",
    "capabilities": ["exploration_capture", "knowledge_mapping"],
}
""",
        encoding="utf-8",
    )

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
        archive.extractall(target)

    statement = """
import sys
from importlib import metadata
from pathlib import Path
from pmqa.product_pack import (
    ProductPackCapability,
    ProductPackLoadRequest,
    ProductPackManifest,
    load_product_pack_manifest,
)
import pmqa
import pmqa.product_pack.loader as loader_module

target = Path(sys.argv[1]).resolve()
repository = Path(sys.argv[2]).resolve()
expected = ProductPackManifest(
    schema_version="1",
    product_pack_api_version="1",
    pack_id="external-demo",
    pack_version="1.2.3",
    product_id="demo",
    display_name="External Demo Pack",
    capabilities=(
        ProductPackCapability.EXPLORATION_CAPTURE,
        ProductPackCapability.KNOWLEDGE_MAPPING,
    ),
)
loaded = load_product_pack_manifest(
    ProductPackLoadRequest(
        distribution_name="pmqa-external-demo-fixture",
        expected_manifest=expected,
    )
)
assert loaded.manifest == expected
assert loaded.manifest is not expected
assert "products.demo" not in sys.modules

pmqa_path = Path(pmqa.__file__).resolve()
loader_path = Path(loader_module.__file__).resolve()
pmqa_path.relative_to(repository)
loader_path.relative_to(repository)
assert loader_path == repository / "pmqa/product_pack/loader.py"

import external_demo_pack
module_path = Path(external_demo_pack.__file__).resolve()
module_path.relative_to(target)
distribution_root = Path(
    metadata.distribution("pmqa-external-demo-fixture").locate_file("")
).resolve()
distribution_root.relative_to(target)
try:
    module_path.relative_to(repository)
except ValueError:
    pass
else:
    raise AssertionError("external fixture resolved inside source checkout")
try:
    distribution_root.relative_to(repository)
except ValueError:
    pass
else:
    raise AssertionError("external distribution resolved inside source checkout")
"""
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONHOME", "PYTHONPATH"}
    }
    environment["PYTHONPATH"] = os.pathsep.join(
        (str(REPOSITORY_ROOT), str(target))
    )
    completed = subprocess.run(
        [sys.executable, "-c", statement, str(target), str(REPOSITORY_ROOT)],
        cwd=unrelated,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
