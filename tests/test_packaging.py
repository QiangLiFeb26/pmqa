"""Packaging checks for the installed framework and SauceDemo product pack."""

import json
from pathlib import Path

from setuptools import find_packages

import pmqa
import products
import products.demo


def test_explicit_packages_and_demo_runtime_config_are_present() -> None:
    assert Path(pmqa.__file__).name == "__init__.py"
    assert Path(products.__file__).name == "__init__.py"
    assert Path(products.demo.__file__).name == "__init__.py"

    config_path = Path(products.demo.__file__).parent / "config/product.json"
    raw = json.loads(config_path.read_text(encoding="utf-8"))

    assert raw["product_id"] == "demo"


def test_package_discovery_excludes_runtime_output_directories() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    discovered = set(
        find_packages(
            where=str(repository_root),
            include=("pmqa*", "products*"),
            exclude=(
                "products.demo.artifacts*",
                "products.demo.generated_tests*",
            ),
        )
    )

    assert "pmqa" in discovered
    assert "products" in discovered
    assert "products.demo" in discovered
    assert not any("artifacts" in package for package in discovered)
    assert not any("generated_tests" in package for package in discovered)
