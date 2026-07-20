"""Task 5.9 tests for retired unvalidated SauceDemo CLI paths."""

import builtins
import subprocess
import sys
from pathlib import Path

import pytest

from pmqa import cli


RETIRED_COMMANDS = ("explore", "generate")


@pytest.mark.parametrize("command_name", RETIRED_COMMANDS)
def test_retired_cli_commands_are_static_and_have_no_side_effects(
    command_name, tmp_path, monkeypatch, capsys
) -> None:
    artifact = tmp_path / "products/demo/artifacts/knowledge.json"
    generated = (
        tmp_path
        / "products/demo/generated_tests/test_saucedemo_generated.py"
    )
    artifact.parent.mkdir(parents=True)
    artifact.write_text("sentinel-artifact", encoding="utf-8")
    original_import = builtins.__import__

    def forbidden_capability(*args, **kwargs):
        raise AssertionError("retired command reached a product capability")

    def guarded_import(name, *args, **kwargs):
        if name == "products.demo" or name.startswith("products.demo."):
            raise AssertionError("retired command imported products.demo")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(cli, "_root", forbidden_capability)
    monkeypatch.setattr(cli, "JsonFileStorage", forbidden_capability)

    product_marker = "runtime-secret-product-marker"
    code = cli.main(
        [command_name, "--product", product_marker]
    )

    output = capsys.readouterr()
    assert code == 2
    assert output.out == ""
    assert output.err == cli.LEGACY_SAUCEDEMO_CLI_RETIREMENT_MESSAGE + "\n"
    assert product_marker not in output.err
    assert artifact.read_text(encoding="utf-8") == "sentinel-artifact"
    assert not generated.exists()


@pytest.mark.parametrize("command", (cli.explore, cli.generate))
def test_direct_legacy_call_has_no_callable_bypass(
    command, monkeypatch, capsys
) -> None:
    original_import = builtins.__import__

    def forbidden_capability(*args, **kwargs):
        raise AssertionError("direct retired call reached a capability")

    def guarded_import(name, *args, **kwargs):
        if name == "products.demo" or name.startswith("products.demo."):
            raise AssertionError("direct retired call imported products.demo")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(cli, "_root", forbidden_capability)
    monkeypatch.setattr(cli, "JsonFileStorage", forbidden_capability)
    with pytest.raises(cli.LegacySauceDemoCommandRetiredError) as captured:
        command("runtime-secret-product-marker")

    output = capsys.readouterr()
    assert str(captured.value) == cli.LEGACY_SAUCEDEMO_CLI_RETIREMENT_MESSAGE
    assert "runtime-secret-product-marker" not in str(captured.value)
    assert output.out == ""
    assert output.err == ""


def test_retired_calls_do_not_import_product_in_fresh_interpreter() -> None:
    statement = """
import contextlib
import io
import sys
from pmqa import cli

for name in ("explore", "generate"):
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = cli.main([name, "--product", "runtime-secret-product-marker"])
    assert code == 2
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == cli.LEGACY_SAUCEDEMO_CLI_RETIREMENT_MESSAGE + "\\n"

for command in (cli.explore, cli.generate):
    try:
        command("runtime-secret-product-marker")
    except cli.LegacySauceDemoCommandRetiredError as error:
        assert str(error) == cli.LEGACY_SAUCEDEMO_CLI_RETIREMENT_MESSAGE
    else:
        raise AssertionError("retired direct call returned")

assert not any(
    name == "products.demo" or name.startswith("products.demo.")
    for name in sys.modules
)
"""
    completed = subprocess.run(
        [sys.executable, "-c", statement],
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_fresh_checkout_has_no_legacy_authoritative_artifact() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    artifact_directory = repository_root / "products/demo/artifacts"

    assert (artifact_directory / ".gitkeep").is_file()
    assert not (artifact_directory / "knowledge.json").exists()
