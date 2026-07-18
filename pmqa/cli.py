"""Single command-line entry point for PMQA workflows."""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from pmqa.core import RunContext, Task
from pmqa.models import KnowledgeArtifact
from pmqa.reasoning import ReasoningRequest
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
    plan = reasoning.reason(
        ReasoningRequest(
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
    provider = SauceDemoExecutionProvider(
        config=config,
        actions=[decision["action"] for decision in plan.decisions],
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


def main(argv: Sequence[str] = ()) -> int:
    """Parse and execute one PMQA command."""

    parser = argparse.ArgumentParser(prog="python -m pmqa.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("explore", "generate", "test-generated"):
        command = subparsers.add_parser(name)
        command.add_argument("--product", required=True)
    args = parser.parse_args(list(argv) if argv else None)
    if args.command == "explore":
        print(explore(args.product))
        return 0
    if args.command == "generate":
        print(generate(args.product))
        return 0
    return test_generated(args.product)


if __name__ == "__main__":
    raise SystemExit(main())
