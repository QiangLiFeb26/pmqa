"""Single command-line entry point for PMQA workflows."""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from pmqa.core import RunContext, Task
from pmqa.models import KnowledgeArtifact
from pmqa.reasoning import (
    CopilotCliConfig,
    CopilotCliReasoningProvider,
    CopilotCliUnavailableError,
    DeterministicReasoningScrubber,
    ManualCopilotReasoningProvider,
    ScrubInput,
    TerminalManualReasoningChannel,
)
from pmqa.storage import JsonFileStorage


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def explore(product: str) -> Path:
    """Run bounded exploration for a configured product."""

    if product != "demo":
        raise ValueError("Only the demo product pack is configured")
    from products.demo.config import load_config
    from products.demo.execution import SauceDemoExecutionProvider
    from products.demo.reasoning import DeterministicDemoReasoningProvider

    config = load_config(_root())
    context = RunContext(run_id="demo-exploration", product=product)
    task = Task("explore", "Explore the configured product within its safe bounds")
    reasoning = DeterministicDemoReasoningProvider()
    scrub_result = DeterministicReasoningScrubber().scrub(
        ScrubInput(
            request_id="demo-exploration-plan",
            workflow_id=context.run_id,
            task_type=task.task_id,
            provider_hint="deterministic",
            product_id=product,
            artifact_version="1",
            constraints={
                "maximum_steps": config.maximum_exploration_steps,
                "allowed_safe_actions": config.allowed_safe_actions,
                "blocked_destructive_actions": config.blocked_destructive_actions,
            },
        )
    )
    plan = reasoning.reason(scrub_result.request)
    provider = SauceDemoExecutionProvider(
        config=config,
        actions=[decision.value["action"] for decision in plan.decisions],
        provenance=plan.provider,
    )
    result = provider.execute(task, context)
    if not result.succeeded or result.artifact is None:
        raise RuntimeError("Exploration did not produce an artifact")
    JsonFileStorage(config.artifact_output_location).save(result.artifact)
    return config.artifact_output_location / "knowledge.json"


def generate(product: str) -> Path:
    """Generate product tests from the latest persisted artifact."""

    if product != "demo":
        raise ValueError("Only the demo product pack is configured")
    from products.demo.config import load_config
    from products.demo.generator import generate_tests

    config = load_config(_root())
    stored = JsonFileStorage(config.artifact_output_location).load("knowledge")
    if stored is None:
        raise FileNotFoundError("Run explore before generate; knowledge.json is missing")
    return generate_tests(
        KnowledgeArtifact.from_dict(stored.data),
        config.generated_test_output_location,
    )


def test_generated(product: str) -> int:
    """Run the generated tests for a configured product."""

    if product != "demo":
        raise ValueError("Only the demo product pack is configured")
    from products.demo.config import load_config

    config = load_config(_root())
    command = [sys.executable, "-m", "pytest", "-q", str(config.generated_test_output_location)]
    return subprocess.run(command, cwd=_root(), check=False).returncode


def reason_manual(product: str) -> int:
    """Demonstrate scrubbed manual GitHub Copilot reasoning for a product."""

    if product != "demo":
        raise ValueError("Only the demo product pack is configured")
    from products.demo.config import load_config

    config = load_config(_root())
    stored = JsonFileStorage(config.artifact_output_location).load("knowledge")
    if stored is None:
        raise FileNotFoundError("Run explore before reason-manual; knowledge.json is missing")
    knowledge = KnowledgeArtifact.from_dict(stored.data)
    scrubbed = DeterministicReasoningScrubber().scrub(
        ScrubInput(
            request_id="demo-manual-reasoning",
            workflow_id="demo-manual-reasoning",
            task_type="manual-analysis",
            provider_hint="github-copilot-manual",
            product_id=product,
            artifact_version="1",
            pages=knowledge.pages,
            elements=knowledge.elements,
            interactions=knowledge.interactions,
            constraints={"return_json_only": True},
            metadata={"reasoning_provenance": knowledge.reasoning_provenance},
        )
    )
    provider = ManualCopilotReasoningProvider(TerminalManualReasoningChannel())
    response = provider.reason(scrubbed.request)
    print(response.model_dump_json(indent=2))
    return 0


def reason_copilot_cli(
    product: str,
    executable: str,
    arguments: Sequence[str],
    timeout_seconds: float,
) -> int:
    """Demonstrate scrubbed reasoning through an explicit Copilot CLI command."""

    if product != "demo":
        raise ValueError("Only the demo product pack is configured")
    from products.demo.config import load_config

    config = load_config(_root())
    stored = JsonFileStorage(config.artifact_output_location).load("knowledge")
    if stored is None:
        raise FileNotFoundError(
            "Run explore before reason-copilot-cli; knowledge.json is missing"
        )
    knowledge = KnowledgeArtifact.from_dict(stored.data)
    scrubbed = DeterministicReasoningScrubber().scrub(
        ScrubInput(
            request_id="demo-copilot-cli-reasoning",
            workflow_id="demo-copilot-cli-reasoning",
            task_type="automated-analysis",
            provider_hint="github-copilot-cli",
            product_id=product,
            artifact_version="1",
            pages=knowledge.pages,
            elements=knowledge.elements,
            interactions=knowledge.interactions,
            constraints={"return_json_only": True},
            metadata={"reasoning_provenance": knowledge.reasoning_provenance},
        )
    )
    provider = CopilotCliReasoningProvider(
        CopilotCliConfig(
            executable=executable,
            arguments=list(arguments),
            timeout_seconds=timeout_seconds,
        )
    )
    if not provider.is_available():
        raise CopilotCliUnavailableError(
            "Configured Copilot CLI executable is unavailable"
        )
    response = provider.reason(scrubbed.request)
    print(response.model_dump_json(indent=2))
    return 0


def main(argv: Sequence[str] = ()) -> int:
    """Parse and execute one PMQA command."""

    parser = argparse.ArgumentParser(prog="python -m pmqa.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("explore", "generate", "test-generated", "reason-manual"):
        command = subparsers.add_parser(name)
        command.add_argument("--product", required=True)
    copilot_cli = subparsers.add_parser("reason-copilot-cli")
    copilot_cli.add_argument("--product", required=True)
    copilot_cli.add_argument("--copilot-executable", required=True)
    copilot_cli.add_argument("--copilot-arg", action="append", default=[])
    copilot_cli.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args(list(argv) if argv else None)
    if args.command == "explore":
        print(explore(args.product))
        return 0
    if args.command == "generate":
        print(generate(args.product))
        return 0
    if args.command == "test-generated":
        return test_generated(args.product)
    if args.command == "reason-manual":
        return reason_manual(args.product)
    return reason_copilot_cli(
        args.product,
        args.copilot_executable,
        args.copilot_arg,
        args.timeout,
    )


if __name__ == "__main__":
    raise SystemExit(main())
