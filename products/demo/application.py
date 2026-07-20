"""Product-owned application composition for the real Task 5 demo."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from pydantic import ValidationError

from pmqa.providers import StorageProvider
from pmqa.storage import JsonFileStorage
from pmqa.workflow import WorkflowState
from products.demo.artifact_handoff import (
    SauceDemoArtifactHandoffError,
    generate_tests_from_verified_workflow,
    persist_verified_knowledge,
)
from products.demo.capture import SauceDemoCaptureRunner
from products.demo.config import (
    DemoConfig,
    DemoConfigValidationError,
    validate_config,
)
from products.demo.workflow import (
    SauceDemoWorkflowCompositionError,
    create_saucedemo_workflow_state,
    run_saucedemo_workflow,
)


TASK5_DEMO_FAILURE_CODE = "task5_demo_failed"
_DEFAULT_RECURSION_LIMIT = 64


class SauceDemoApplicationError(ValueError):
    """Reports a stable safe Task 5 demo application failure."""


@dataclass(frozen=True)
class SauceDemoApplicationResult:
    """Returns only bounded outputs from one completed Task 5 demo run."""

    final_state: WorkflowState
    stored_artifact_id: str
    persisted_artifact_path: Optional[Path]
    generated_test_path: Path


def run_saucedemo_demo(
    *,
    config: DemoConfig,
    workflow_id: str,
    product_version: str,
    goal: str,
    max_iterations: int,
    created_at: datetime,
    headless: bool,
    recursion_limit: int = _DEFAULT_RECURSION_LIMIT,
    capture_runner: Optional[SauceDemoCaptureRunner] = None,
    tool_clock: Optional[Callable[[], datetime]] = None,
    storage: Optional[StorageProvider] = None,
    generated_test_output_directory: Optional[Path] = None,
) -> SauceDemoApplicationResult:
    """Run, persist, and generate without executing the generated tests.

    ``created_at`` initializes WorkflowState only. An injected ``tool_clock``
    is independently sampled exactly once by ``run_saucedemo_workflow``.
    """

    _validate_application_dependencies(
        config=config,
        headless=headless,
        recursion_limit=recursion_limit,
        storage=storage,
        generated_test_output_directory=generated_test_output_directory,
    )
    try:
        initial_state = create_saucedemo_workflow_state(
            config,
            workflow_id=workflow_id,
            product_version=product_version,
            goal=goal,
            max_iterations=max_iterations,
            created_at=created_at,
        )
        final_state = run_saucedemo_workflow(
            config,
            initial_state,
            capture_runner=capture_runner,
            clock=tool_clock,
            headless=headless,
            recursion_limit=recursion_limit,
        )
        selected_storage = (
            storage
            if storage is not None
            else JsonFileStorage(config.artifact_output_location)
        )
        stored = persist_verified_knowledge(
            final_state, config, selected_storage
        )
        output_directory = (
            generated_test_output_directory
            if generated_test_output_directory is not None
            else config.generated_test_output_location
        )
        generated_path = generate_tests_from_verified_workflow(
            final_state, config, output_directory
        )
    except (
        SauceDemoWorkflowCompositionError,
        SauceDemoArtifactHandoffError,
        ValidationError,
    ):
        raise SauceDemoApplicationError(TASK5_DEMO_FAILURE_CODE) from None

    persisted_path = (
        config.artifact_output_location / "knowledge.json"
        if storage is None
        else None
    )
    return SauceDemoApplicationResult(
        final_state=final_state,
        stored_artifact_id=stored.artifact_id,
        persisted_artifact_path=persisted_path,
        generated_test_path=generated_path,
    )


def _validate_application_dependencies(
    *,
    config: DemoConfig,
    headless: bool,
    recursion_limit: int,
    storage: Optional[StorageProvider],
    generated_test_output_directory: Optional[Path],
) -> None:
    try:
        validate_config(config)
    except DemoConfigValidationError:
        raise SauceDemoApplicationError(TASK5_DEMO_FAILURE_CODE)
    if type(headless) is not bool:
        raise SauceDemoApplicationError(TASK5_DEMO_FAILURE_CODE)
    if type(recursion_limit) is not int or recursion_limit < 1:
        raise SauceDemoApplicationError(TASK5_DEMO_FAILURE_CODE)
    if storage is not None and not isinstance(storage, StorageProvider):
        raise SauceDemoApplicationError(TASK5_DEMO_FAILURE_CODE)
    if (
        generated_test_output_directory is not None
        and not isinstance(generated_test_output_directory, Path)
    ):
        raise SauceDemoApplicationError(TASK5_DEMO_FAILURE_CODE)
