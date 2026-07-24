"""Tests for explicit immutable PMQA application registries."""

import pytest

from pmqa.application import (
    MAX_APPLICATION_REGISTRY_ITEMS,
    ApplicationFailureCode,
    PMQAApplicationError,
    RunnerRegistry,
    WorkflowRegistry,
)
from pmqa.run import (
    ApprovalMode,
    RunRequest,
    StructuredResult,
    WorkflowDefinition,
)
from pmqa.runners import (
    MockRunner,
    RunnerMetadata,
    RunnerRequest,
    RunnerResponse,
)


def _definition(
    workflow_version: str = "1",
    **updates,
) -> WorkflowDefinition:
    values = {
        "schema_version": "1",
        "workflow_id": "workflow.test",
        "workflow_version": workflow_version,
        "display_name": f"Test workflow {workflow_version}",
        "description": "Validate the explicit application registry.",
        "input_schema_id": "schema.input",
        "input_schema_version": "1",
        "result_schema_id": "schema.result",
        "result_schema_version": "1",
        "preview_steps": (),
        "required_runner_capabilities": ("deterministic-execution",),
        "approval_mode": ApprovalMode.NONE,
    }
    values.update(updates)
    return WorkflowDefinition(**values)


class FakeAdapter:
    def __init__(self, definition: WorkflowDefinition) -> None:
        self.current_definition = definition

    @property
    def definition(self) -> WorkflowDefinition:
        return self.current_definition

    def validate_request(self, request: RunRequest) -> None:
        return None

    def validate_result(self, result: StructuredResult) -> None:
        return None


class FakeRunner:
    def __init__(self, metadata: RunnerMetadata) -> None:
        self.current_metadata = metadata

    @property
    def metadata(self) -> RunnerMetadata:
        return self.current_metadata

    def execute(
        self,
        request: RunnerRequest,
        control,
    ) -> RunnerResponse:
        raise AssertionError("registry tests do not execute runners")


class MissingDefinitionAdapter:
    def validate_request(self, request) -> None:
        return None

    def validate_result(self, result) -> None:
        return None


class MissingMetadataRunner:
    def execute(self, request, control):
        return None


class RaisingDefinitionAdapter(MissingDefinitionAdapter):
    @property
    def definition(self):
        raise ValueError("runtime-secret-marker")


class RaisingMetadataRunner:
    @property
    def metadata(self):
        raise ValueError("runtime-secret-marker")

    def execute(self, request, control):
        return None


def _metadata(
    runner_id: str = "runner.mock",
    **updates,
) -> RunnerMetadata:
    values = {
        "schema_version": "1",
        "runner_id": runner_id,
        "runner_version": "1",
        "display_name": runner_id,
        "capabilities": ("deterministic-execution",),
    }
    values.update(updates)
    return RunnerMetadata(**values)


def test_workflow_registry_uses_exact_deterministic_version_lookup() -> None:
    first = FakeAdapter(_definition("1"))
    second = FakeAdapter(_definition("2"))
    registry = WorkflowRegistry((first, second))

    assert registry.resolve("workflow.test", "1").adapter is first
    assert registry.resolve("workflow.test", "2").adapter is second
    assert tuple(item.workflow_version for item in registry.definitions) == (
        "1",
        "2",
    )
    with pytest.raises(PMQAApplicationError) as missing:
        registry.resolve("workflow.test", "3")
    assert missing.value.code is ApplicationFailureCode.WORKFLOW_NOT_FOUND


def test_workflow_registry_rejects_duplicate_and_mutable_collection() -> None:
    adapter = FakeAdapter(_definition())
    for adapters in ((adapter, adapter), [adapter]):
        with pytest.raises(PMQAApplicationError) as captured:
            WorkflowRegistry(adapters)
        assert (
            captured.value.code
            is ApplicationFailureCode.INVALID_WORKFLOW_REGISTRY
        )


def test_workflow_registry_retains_independent_definition_snapshot() -> None:
    definition = _definition()
    adapter = FakeAdapter(definition)
    registry = WorkflowRegistry((adapter,))
    definition.__dict__["display_name"] = "Caller-mutated definition"

    assert registry.definitions[0].display_name == "Test workflow 1"
    assert registry.definitions[0] is not definition


def test_workflow_registry_does_not_expose_its_definition_snapshot() -> None:
    adapter = FakeAdapter(_definition())
    registry = WorkflowRegistry((adapter,))
    exposed_property = registry.definitions[0]
    exposed_resolution = registry.resolve("workflow.test", "1")

    exposed_property.__dict__["display_name"] = "Changed property"
    exposed_resolution.definition.__dict__["display_name"] = "Changed lookup"

    assert registry.definitions[0].display_name == "Test workflow 1"
    assert (
        registry.resolve("workflow.test", "1").definition.display_name
        == "Test workflow 1"
    )


@pytest.mark.parametrize(
    "adapter",
    (
        MissingDefinitionAdapter(),
        RaisingDefinitionAdapter(),
        object(),
    ),
)
def test_workflow_registry_rejects_malformed_adapters_safely(adapter) -> None:
    marker = "runtime-secret-marker"
    with pytest.raises(PMQAApplicationError) as captured:
        WorkflowRegistry((adapter,))

    assert (
        captured.value.code
        is ApplicationFailureCode.INVALID_WORKFLOW_REGISTRY
    )
    assert marker not in str(captured.value)
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None


def test_workflow_registry_is_bounded_and_has_no_registration_api() -> None:
    adapter = FakeAdapter(_definition())
    with pytest.raises(PMQAApplicationError):
        WorkflowRegistry(
            tuple(adapter for _ in range(MAX_APPLICATION_REGISTRY_ITEMS + 1))
        )

    registry = WorkflowRegistry((adapter,))
    assert not hasattr(registry, "register")
    assert not hasattr(registry, "discover")


def test_runner_registry_uses_exact_deterministic_lookup() -> None:
    first = FakeRunner(_metadata("runner.first"))
    second = FakeRunner(_metadata("runner.second"))
    registry = RunnerRegistry((first, second))

    assert registry.resolve("runner.first").runner is first
    assert registry.resolve("runner.second").runner is second
    assert tuple(item.runner_id for item in registry.metadata) == (
        "runner.first",
        "runner.second",
    )
    with pytest.raises(PMQAApplicationError) as missing:
        registry.resolve("runner.other")
    assert missing.value.code is ApplicationFailureCode.RUNNER_NOT_FOUND


def test_runner_registry_rejects_duplicate_and_mutable_collection() -> None:
    runner = MockRunner()
    for runners in ((runner, runner), [runner]):
        with pytest.raises(PMQAApplicationError) as captured:
            RunnerRegistry(runners)
        assert (
            captured.value.code
            is ApplicationFailureCode.INVALID_RUNNER_REGISTRY
        )


def test_runner_registry_retains_independent_metadata_snapshot() -> None:
    metadata = _metadata()
    runner = FakeRunner(metadata)
    registry = RunnerRegistry((runner,))
    metadata.__dict__["display_name"] = "Caller-mutated metadata"

    assert registry.metadata[0].display_name == "runner.mock"
    assert registry.metadata[0] is not metadata


def test_runner_registry_does_not_expose_its_metadata_snapshot() -> None:
    runner = FakeRunner(_metadata())
    registry = RunnerRegistry((runner,))
    exposed_property = registry.metadata[0]
    exposed_resolution = registry.resolve("runner.mock")

    exposed_property.__dict__["display_name"] = "Changed property"
    exposed_resolution.metadata.__dict__["display_name"] = "Changed lookup"

    assert registry.metadata[0].display_name == "runner.mock"
    assert (
        registry.resolve("runner.mock").metadata.display_name
        == "runner.mock"
    )


@pytest.mark.parametrize(
    "runner",
    (
        MissingMetadataRunner(),
        RaisingMetadataRunner(),
        object(),
    ),
)
def test_runner_registry_rejects_malformed_runners_safely(runner) -> None:
    marker = "runtime-secret-marker"
    with pytest.raises(PMQAApplicationError) as captured:
        RunnerRegistry((runner,))

    assert (
        captured.value.code
        is ApplicationFailureCode.INVALID_RUNNER_REGISTRY
    )
    assert marker not in str(captured.value)
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None


def test_runner_registry_is_bounded_and_has_no_registration_api() -> None:
    runner = MockRunner()
    with pytest.raises(PMQAApplicationError):
        RunnerRegistry(
            tuple(runner for _ in range(MAX_APPLICATION_REGISTRY_ITEMS + 1))
        )

    registry = RunnerRegistry((runner,))
    assert not hasattr(registry, "register")
    assert not hasattr(registry, "discover")
