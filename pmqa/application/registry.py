"""Explicit immutable application workflow and runner registries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Tuple

from pmqa.application.contracts import (
    ApplicationFailureCode,
    PMQAApplicationError,
)
from pmqa.run import RunRequest, StructuredResult, WorkflowDefinition
from pmqa.runners.base import PMQARunner
from pmqa.runners.contracts import RunnerMetadata


MAX_APPLICATION_REGISTRY_ITEMS = 256
_RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS = (
    MemoryError,
    KeyboardInterrupt,
    SystemExit,
    GeneratorExit,
)


class PMQAWorkflowAdapter(Protocol):
    """Runtime workflow-specific validation without execution or persistence."""

    @property
    def definition(self) -> WorkflowDefinition:
        ...

    def validate_request(self, request: RunRequest) -> None:
        ...

    def validate_result(self, result: StructuredResult) -> None:
        ...


@dataclass(frozen=True)
class _WorkflowRegistration:
    definition: WorkflowDefinition
    adapter: PMQAWorkflowAdapter


@dataclass(frozen=True)
class _RunnerRegistration:
    metadata: RunnerMetadata
    runner: PMQARunner


class WorkflowRegistry:
    """Bounded explicit workflow registrations with canonical snapshots."""

    __slots__ = ("_registrations",)

    def __init__(self, adapters: Tuple[PMQAWorkflowAdapter, ...]) -> None:
        if (
            type(adapters) is not tuple
            or len(adapters) > MAX_APPLICATION_REGISTRY_ITEMS
        ):
            raise PMQAApplicationError(
                ApplicationFailureCode.INVALID_WORKFLOW_REGISTRY
            ) from None

        failed = False
        registrations = []
        try:
            for adapter in adapters:
                definition = adapter.definition
                if (
                    type(definition) is not WorkflowDefinition
                    or not callable(adapter.validate_request)
                    or not callable(adapter.validate_result)
                ):
                    failed = True
                    break
                snapshot = WorkflowDefinition.from_dict(definition.to_dict())
                registrations.append(
                    _WorkflowRegistration(snapshot, adapter)
                )
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except Exception:
            failed = True
        if failed:
            raise PMQAApplicationError(
                ApplicationFailureCode.INVALID_WORKFLOW_REGISTRY
            ) from None

        identities = tuple(
            (
                registration.definition.workflow_id,
                registration.definition.workflow_version,
            )
            for registration in registrations
        )
        if len(identities) != len(set(identities)):
            raise PMQAApplicationError(
                ApplicationFailureCode.INVALID_WORKFLOW_REGISTRY
            ) from None
        self._registrations = tuple(registrations)

    @property
    def definitions(self) -> Tuple[WorkflowDefinition, ...]:
        return tuple(
            WorkflowDefinition.from_dict(registration.definition.to_dict())
            for registration in self._registrations
        )

    def resolve(
        self,
        workflow_id: str,
        workflow_version: str,
    ) -> _WorkflowRegistration:
        if type(workflow_id) is not str or type(workflow_version) is not str:
            raise PMQAApplicationError(
                ApplicationFailureCode.WORKFLOW_NOT_FOUND
            ) from None
        for registration in self._registrations:
            if (
                registration.definition.workflow_id == workflow_id
                and registration.definition.workflow_version
                == workflow_version
            ):
                return _WorkflowRegistration(
                    WorkflowDefinition.from_dict(
                        registration.definition.to_dict()
                    ),
                    registration.adapter,
                )
        raise PMQAApplicationError(
            ApplicationFailureCode.WORKFLOW_NOT_FOUND
        ) from None


class RunnerRegistry:
    """Bounded explicit runner registrations with canonical snapshots."""

    __slots__ = ("_registrations",)

    def __init__(self, runners: Tuple[PMQARunner, ...]) -> None:
        if (
            type(runners) is not tuple
            or len(runners) > MAX_APPLICATION_REGISTRY_ITEMS
        ):
            raise PMQAApplicationError(
                ApplicationFailureCode.INVALID_RUNNER_REGISTRY
            ) from None

        failed = False
        registrations = []
        try:
            for runner in runners:
                metadata = runner.metadata
                if (
                    type(metadata) is not RunnerMetadata
                    or not callable(runner.execute)
                ):
                    failed = True
                    break
                snapshot = RunnerMetadata.from_dict(metadata.to_dict())
                registrations.append(_RunnerRegistration(snapshot, runner))
        except _RESOURCE_AND_CONTROL_FLOW_EXCEPTIONS:
            raise
        except Exception:
            failed = True
        if failed:
            raise PMQAApplicationError(
                ApplicationFailureCode.INVALID_RUNNER_REGISTRY
            ) from None

        runner_ids = tuple(
            registration.metadata.runner_id
            for registration in registrations
        )
        if len(runner_ids) != len(set(runner_ids)):
            raise PMQAApplicationError(
                ApplicationFailureCode.INVALID_RUNNER_REGISTRY
            ) from None
        self._registrations = tuple(registrations)

    @property
    def metadata(self) -> Tuple[RunnerMetadata, ...]:
        return tuple(
            RunnerMetadata.from_dict(registration.metadata.to_dict())
            for registration in self._registrations
        )

    def resolve(self, runner_id: str) -> _RunnerRegistration:
        if type(runner_id) is not str:
            raise PMQAApplicationError(
                ApplicationFailureCode.RUNNER_NOT_FOUND
            ) from None
        for registration in self._registrations:
            if registration.metadata.runner_id == runner_id:
                return _RunnerRegistration(
                    RunnerMetadata.from_dict(registration.metadata.to_dict()),
                    registration.runner,
                )
        raise PMQAApplicationError(
            ApplicationFailureCode.RUNNER_NOT_FOUND
        ) from None


__all__ = [
    "MAX_APPLICATION_REGISTRY_ITEMS",
    "PMQAWorkflowAdapter",
    "RunnerRegistry",
    "WorkflowRegistry",
]
