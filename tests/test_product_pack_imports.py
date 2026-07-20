"""Import-isolation tests for the neutral Product Pack contract package."""

import subprocess
import sys


def test_product_pack_import_is_neutral_and_side_effect_free() -> None:
    statement = "\n".join(
        [
            "import sys",
            "import pmqa.product_pack",
            "assert pmqa.product_pack.ProductPackManifest",
            "assert pmqa.product_pack.ProductPackCapability",
            "assert pmqa.product_pack.ProductPackManifestValidationError",
            "assert pmqa.product_pack.ProductPackLoadRequest",
            "assert pmqa.product_pack.LoadedProductPack",
            "assert pmqa.product_pack.ProductPackLoadError",
            "assert pmqa.product_pack.ProductPackLoadFailureCode",
            "assert pmqa.product_pack.load_product_pack_manifest",
            "assert pmqa.product_pack.ProductPackBridgeRequest",
            "assert pmqa.product_pack.ProductPackBridgeResponse",
            "assert pmqa.product_pack.validate_product_pack_bridge_response",
            "assert pmqa.product_pack.ProductPackBridgeProcessConfig",
            "assert pmqa.product_pack.run_product_pack_bridge",
            "assert pmqa.product_pack.ProductPackScaffoldRequest",
            "assert pmqa.product_pack.ProductPackScaffoldResult",
            "assert pmqa.product_pack.ProductPackBackendSourceState",
            "assert pmqa.product_pack.scaffold_product_pack",
            "assert pmqa.product_pack.ProductPackSourceConformanceResult",
            "assert pmqa.product_pack.validate_product_pack_source",
            "blocked = ('products.demo', 'playwright', 'langgraph', "
            "'pmqa.runtime', 'pmqa.supervisor', 'pmqa.orchestration')",
            "for prefix in blocked:",
            "    assert not any(name == prefix or name.startswith(prefix + '.') "
            "for name in sys.modules), prefix",
            "assert 'external_demo_pack' not in sys.modules",
        ]
    )

    completed = subprocess.run(
        [sys.executable, "-c", statement],
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_bridge_protocol_import_has_no_external_side_effects() -> None:
    statement = "\n".join(
        [
            "import sys",
            "before_path = tuple(sys.path)",
            "import pmqa.product_pack.bridge_protocol as protocol",
            "assert protocol.BRIDGE_PROTOCOL_VERSION == '1'",
            "assert tuple(sys.path) == before_path",
            "blocked = ('products.demo', 'playwright', 'langgraph', ",
            "'pmqa.runtime', 'pmqa.supervisor', 'pmqa.orchestration')",
            "for prefix in blocked:",
            "    assert not any(name == prefix or name.startswith(prefix + '.') ",
            "for name in sys.modules), prefix",
            "assert 'external_demo_pack' not in sys.modules",
        ]
    )

    completed = subprocess.run(
        [sys.executable, "-c", statement],
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_bridge_runner_import_launches_nothing_and_remains_product_lazy() -> None:
    statement = "\n".join(
        [
            "import sys",
            "before_path = tuple(sys.path)",
            "import pmqa.product_pack.bridge_runner as runner",
            "assert runner.run_product_pack_bridge",
            "assert tuple(sys.path) == before_path",
            "blocked = ('products.demo', 'playwright', 'langgraph', ",
            "'pmqa.runtime', 'pmqa.supervisor', 'pmqa.orchestration')",
            "for prefix in blocked:",
            "    assert not any(name == prefix or name.startswith(prefix + '.') ",
            "for name in sys.modules), prefix",
            "assert 'external_demo_pack' not in sys.modules",
        ]
    )

    completed = subprocess.run(
        [sys.executable, "-c", statement],
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_scaffold_import_reads_nothing_and_remains_product_lazy() -> None:
    statement = "\n".join(
        [
            "import builtins, importlib, os, pathlib, subprocess, sys, tempfile",
            "import pmqa.product_pack",
            "sys.modules.pop('pmqa.product_pack.scaffold', None)",
            "original_open = builtins.open",
            "def forbidden(*args, **kwargs): raise AssertionError('side effect')",
            "builtins.open = forbidden",
            "pathlib.Path.read_text = forbidden",
            "pathlib.Path.write_text = forbidden",
            "os.getenv = forbidden",
            "tempfile.mkdtemp = forbidden",
            "subprocess.Popen = forbidden",
            "scaffold = importlib.import_module('pmqa.product_pack.scaffold')",
            "assert scaffold.scaffold_product_pack",
            "builtins.open = original_open",
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
