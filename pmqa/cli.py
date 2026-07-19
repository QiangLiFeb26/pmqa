"""Single command-line entry point for PMQA workflows."""

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence
from uuid import uuid4

from pmqa.core import RunContext, Task
from pmqa.models import KnowledgeArtifact
from pmqa.reasoning import (
    CopilotCliConfig,
    CopilotCliReasoningProvider,
    CopilotCliUnavailableError,
    DeterministicReasoningProvider,
    DeterministicReasoningScrubber,
    ManualCopilotReasoningProvider,
    ReasoningDecision,
    ReasoningExecutionService,
    ReasoningRequest,
    ReasoningResponse,
    ReasoningStatus,
    ScrubInput,
    TerminalManualReasoningChannel,
)
from pmqa.storage import JsonFileStorage
from pmqa.trace import SQLiteTraceStore, TraceRecord


_TASK5_DEMO_FAILURE_CODE = "task5_demo_failed"


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


def trace_demo(database: Path) -> int:
    """Save and reload one provider-independent reasoning trace."""

    request = ReasoningRequest(
        request_id=f"trace-demo-request-{uuid4()}",
        workflow_id="trace-demo",
        task_type="contract-demonstration",
        provider_hint=None,
        product_id="demo",
        artifact_version="1",
        constraints={"offline": True},
    )
    response = ReasoningResponse(
        request_id=request.request_id,
        provider="trace-demo",
        model="structured-example-v1",
        status=ReasoningStatus.COMPLETED,
        decisions=[
            ReasoningDecision(
                decision_type="acknowledge",
                value={"workflow_id": request.workflow_id},
                confidence=1.0,
            )
        ],
    )
    record = TraceRecord.from_exchange(
        trace_id=f"trace-demo-{uuid4()}",
        request=request,
        response=response,
        created_at=datetime.now(timezone.utc),
        metadata={"purpose": "offline-demo"},
    )
    with SQLiteTraceStore(database) as store:
        store.save_trace(record)
        restored = store.get_trace(record.trace_id)
    print(
        f"trace_id={restored.trace_id} request_id={restored.request_id} "
        f"provider={restored.provider} status={restored.status.value}"
    )
    return 0


def task3_demo(database: Path) -> int:
    """Run the complete Task 3 reasoning flow without external providers."""

    scrub_input = ScrubInput(
        request_id=f"task3-demo-request-{uuid4()}",
        workflow_id="task3-demo",
        task_type="integration-demonstration",
        provider_hint="deterministic",
        product_id="demo",
        artifact_version="1",
        constraints={"offline": True},
        metadata={
            "source": "task3-demo",
            "token": "removed-before-prompting",
        },
    )
    with SQLiteTraceStore(database) as store:
        result = ReasoningExecutionService(trace_store=store).execute(
            scrub_input=scrub_input,
            provider=DeterministicReasoningProvider(),
        )
        restored = store.get_trace(result.trace.trace_id)
    print(
        f"package_id={result.prompt_package.package_id} "
        f"request_id={result.request.request_id} "
        f"trace_id={restored.trace_id} provider={restored.provider} "
        f"status={restored.status.value}"
    )
    return 0


def task5_demo(
    product: str,
    *,
    workflow_id: str,
    product_version: str,
    goal: str,
    max_iterations: int,
    headed: bool,
    _config_loader=None,
    _application_runner=None,
    _clock=None,
) -> int:
    """Run the real Task 5 workflow, handoff, persistence, and generation."""

    if product != "demo":
        print(_TASK5_DEMO_FAILURE_CODE, file=sys.stderr)
        return 2
    try:
        from products.demo.application import (
            SauceDemoApplicationError,
            run_saucedemo_demo,
        )

        if _config_loader is None:
            from products.demo.config import load_config

            config_loader = load_config
        else:
            config_loader = _config_loader
        if _application_runner is None:
            application_runner = run_saucedemo_demo
        else:
            application_runner = _application_runner
        creation_clock = (
            _clock
            if _clock is not None
            else lambda: datetime.now(timezone.utc)
        )
        created_at = creation_clock()
        config = config_loader(_root())
        result = application_runner(
            config=config,
            workflow_id=workflow_id,
            product_version=product_version,
            goal=goal,
            max_iterations=max_iterations,
            created_at=created_at,
            headless=not headed,
        )
    except (OSError, SauceDemoApplicationError):
        print(_TASK5_DEMO_FAILURE_CODE, file=sys.stderr)
        return 2

    state = result.final_state
    artifact_path = result.persisted_artifact_path
    print(
        f"workflow_id={state.workflow_id} status={state.status.value} "
        f"termination_reason={state.termination_reason.value} "
        f"iteration={state.iteration} evidence_count={len(state.evidence)} "
        f"candidate_count={len(state.knowledge_candidates)} "
        f"validation_result_count={len(state.validation_results)} "
        f"artifact_path={artifact_path} "
        f"generated_test_path={result.generated_test_path}"
    )
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
    trace_parser = subparsers.add_parser("trace-demo")
    trace_parser.add_argument(
        "--database", type=Path, default=Path("pmqa-traces.sqlite3")
    )
    task3_parser = subparsers.add_parser("task3-demo")
    task3_parser.add_argument(
        "--database", type=Path, default=Path("pmqa-traces.sqlite3")
    )
    task5_parser = subparsers.add_parser("task5-demo")
    task5_parser.add_argument("--product", required=True)
    task5_parser.add_argument(
        "--workflow-id", default="saucedemo-task5-demo"
    )
    task5_parser.add_argument("--product-version", default="1")
    task5_parser.add_argument(
        "--goal", default="Build verified SauceDemo product memory"
    )
    task5_parser.add_argument("--max-iterations", type=int, default=1)
    task5_parser.add_argument("--headed", action="store_true")
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
    if args.command == "trace-demo":
        return trace_demo(args.database)
    if args.command == "task3-demo":
        return task3_demo(args.database)
    if args.command == "task5-demo":
        return task5_demo(
            args.product,
            workflow_id=args.workflow_id,
            product_version=args.product_version,
            goal=args.goal,
            max_iterations=args.max_iterations,
            headed=args.headed,
        )
    return reason_copilot_cli(
        args.product,
        args.copilot_executable,
        args.copilot_arg,
        args.timeout,
    )


if __name__ == "__main__":
    raise SystemExit(main())
