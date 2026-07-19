"""Strict handoff from completed SauceDemo workflows to durable artifacts."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from pydantic import ValidationError

from pmqa.core import Artifact
from pmqa.models import ArtifactStatus, ExplorationEvidence, KnowledgeArtifact
from pmqa.providers import StorageProvider
from pmqa.workflow import TerminationReason, WorkflowState, WorkflowStatus
from products.demo.config import DemoConfig
from products.demo.generator import generate_tests
from products.demo.knowledge_mapping import (
    KnowledgeCandidateError,
    SauceDemoKnowledgeCandidate,
)
from products.demo.validation import (
    SauceDemoValidationResult,
    ValidationResultError,
    build_validation_result,
)
from products.demo.workflow import SAUCEDEMO_WORKFLOW_TYPE


KNOWLEDGE_STORAGE_KEY = "knowledge"


class SauceDemoArtifactHandoffError(ValueError):
    """Reports a safe product-owned artifact handoff failure."""


def extract_verified_knowledge(
    state: WorkflowState, config: DemoConfig
) -> KnowledgeArtifact:
    """Return a fresh VERIFIED snapshot after strict terminal correlation."""

    try:
        return _extract_verified_knowledge(state, config)
    except SauceDemoArtifactHandoffError:
        raise
    except (
        AttributeError,
        KeyError,
        TypeError,
        ValueError,
        ValidationError,
        KnowledgeCandidateError,
        ValidationResultError,
    ):
        raise SauceDemoArtifactHandoffError(
            "verified knowledge handoff validation failed"
        ) from None


def persist_verified_knowledge(
    state: WorkflowState,
    config: DemoConfig,
    storage: StorageProvider,
) -> Artifact:
    """Persist exactly one verified artifact through StorageProvider."""

    knowledge = extract_verified_knowledge(state, config)
    if not isinstance(storage, StorageProvider):
        raise SauceDemoArtifactHandoffError(
            "verified knowledge storage boundary is invalid"
        )
    artifact = Artifact(
        artifact_id=KNOWLEDGE_STORAGE_KEY,
        data=knowledge.to_dict(),
    )
    try:
        storage.save(artifact)
    except Exception:
        raise SauceDemoArtifactHandoffError(
            "verified knowledge persistence failed"
        ) from None
    return artifact


def generate_tests_from_verified_workflow(
    state: WorkflowState,
    config: DemoConfig,
    output_directory: Path,
) -> Path:
    """Generate deterministic tests from the strictly extracted snapshot."""

    if not isinstance(output_directory, Path):
        raise SauceDemoArtifactHandoffError(
            "generated test output directory is invalid"
        )
    knowledge = extract_verified_knowledge(state, config)
    try:
        return generate_tests(knowledge, output_directory)
    except Exception:
        raise SauceDemoArtifactHandoffError(
            "verified knowledge test generation failed"
        ) from None


def _extract_verified_knowledge(
    state: WorkflowState, config: DemoConfig
) -> KnowledgeArtifact:
    canonical_state = _canonical_state(state)
    _validate_terminal_state(canonical_state, config)

    evidence_by_id = _parse_evidence(canonical_state)
    candidate_by_id = _parse_candidates(canonical_state, evidence_by_id)
    validations = _parse_validations(
        canonical_state, candidate_by_id, evidence_by_id
    )
    latest = validations[-1]
    if latest.status != "passed" or latest.verified_knowledge is None:
        raise SauceDemoArtifactHandoffError(
            "latest knowledge validation did not pass"
        )
    if (
        latest.workflow_id != canonical_state.workflow_id
        or latest.product_id != canonical_state.product_id
    ):
        raise SauceDemoArtifactHandoffError(
            "latest validation workflow correlation is invalid"
        )

    candidate = candidate_by_id.get(latest.candidate_id)
    if candidate is None:
        raise SauceDemoArtifactHandoffError(
            "latest validation candidate correlation is invalid"
        )
    evidence = evidence_by_id.get(latest.source_evidence_id)
    if evidence is None:
        raise SauceDemoArtifactHandoffError(
            "latest validation evidence correlation is invalid"
        )
    if candidate.source_evidence_id != evidence.evidence_id:
        raise SauceDemoArtifactHandoffError(
            "candidate evidence correlation is invalid"
        )

    rebuilt = build_validation_result(
        candidate,
        evidence,
        datetime.fromisoformat(latest.validated_at),
    )
    if rebuilt.to_workflow_payload() != latest.to_workflow_payload():
        raise SauceDemoArtifactHandoffError(
            "latest validation snapshot is inconsistent"
        )
    knowledge = latest.verified_knowledge
    expected_lifecycle = (ArtifactStatus.VERIFIED, latest.validated_at)
    if any(
        (item.lifecycle.state, item.lifecycle.last_verified)
        != expected_lifecycle
        for item in _knowledge_items(knowledge)
    ):
        raise SauceDemoArtifactHandoffError(
            "verified knowledge lifecycle is inconsistent"
        )
    return KnowledgeArtifact.from_dict(
        json.loads(json.dumps(knowledge.to_dict(), allow_nan=False))
    )


def _canonical_state(state: WorkflowState) -> WorkflowState:
    if not isinstance(state, WorkflowState):
        raise SauceDemoArtifactHandoffError(
            "handoff input must be a WorkflowState"
        )
    try:
        return WorkflowState.model_validate(state.model_dump(mode="python"))
    except ValidationError:
        raise SauceDemoArtifactHandoffError(
            "workflow state is invalid for artifact handoff"
        ) from None


def _validate_terminal_state(
    state: WorkflowState, config: DemoConfig
) -> None:
    if not isinstance(config, DemoConfig):
        raise SauceDemoArtifactHandoffError(
            "handoff config must be a DemoConfig"
        )
    if state.workflow_type != SAUCEDEMO_WORKFLOW_TYPE:
        raise SauceDemoArtifactHandoffError(
            "workflow type is invalid for SauceDemo handoff"
        )
    if state.product_id != config.product_id:
        raise SauceDemoArtifactHandoffError(
            "workflow product is invalid for SauceDemo handoff"
        )
    if (
        state.status is not WorkflowStatus.COMPLETED
        or state.termination_reason is not TerminationReason.GOAL_COMPLETED
    ):
        raise SauceDemoArtifactHandoffError(
            "workflow is not successfully completed"
        )
    if state.errors:
        raise SauceDemoArtifactHandoffError(
            "workflow contains a fatal error"
        )
    if not state.validation_results:
        raise SauceDemoArtifactHandoffError(
            "workflow contains no validation result"
        )


def _parse_evidence(
    state: WorkflowState,
) -> Dict[str, ExplorationEvidence]:
    items: List[ExplorationEvidence] = []
    for payload in state.evidence:
        evidence = ExplorationEvidence.from_workflow_payload(payload)
        if (
            evidence.workflow_id != state.workflow_id
            or evidence.product_id != state.product_id
        ):
            raise SauceDemoArtifactHandoffError(
                "workflow evidence correlation is invalid"
            )
        items.append(evidence)
    by_id = {item.evidence_id: item for item in items}
    if len(by_id) != len(items):
        raise SauceDemoArtifactHandoffError(
            "workflow evidence correlation is ambiguous"
        )
    return by_id


def _parse_candidates(
    state: WorkflowState,
    evidence_by_id: Dict[str, ExplorationEvidence],
) -> Dict[str, SauceDemoKnowledgeCandidate]:
    items: List[SauceDemoKnowledgeCandidate] = []
    source_ids = set()
    for payload in state.knowledge_candidates:
        candidate = SauceDemoKnowledgeCandidate.from_workflow_payload(payload)
        if (
            candidate.workflow_id != state.workflow_id
            or candidate.product_id != state.product_id
            or candidate.source_evidence_id not in evidence_by_id
        ):
            raise SauceDemoArtifactHandoffError(
                "workflow candidate correlation is invalid"
            )
        if candidate.source_evidence_id in source_ids:
            raise SauceDemoArtifactHandoffError(
                "workflow candidate correlation is ambiguous"
            )
        source_ids.add(candidate.source_evidence_id)
        items.append(candidate)
    by_id = {item.candidate_id: item for item in items}
    if len(by_id) != len(items):
        raise SauceDemoArtifactHandoffError(
            "workflow candidate correlation is ambiguous"
        )
    return by_id


def _parse_validations(
    state: WorkflowState,
    candidate_by_id: Dict[str, SauceDemoKnowledgeCandidate],
    evidence_by_id: Dict[str, ExplorationEvidence],
) -> List[SauceDemoValidationResult]:
    results = []
    validation_ids = set()
    candidate_ids = set()
    for payload in state.validation_results:
        result = SauceDemoValidationResult.from_workflow_payload(payload)
        if (
            result.workflow_id != state.workflow_id
            or result.product_id != state.product_id
        ):
            raise SauceDemoArtifactHandoffError(
                "workflow validation correlation is invalid"
            )
        candidate = candidate_by_id.get(result.candidate_id)
        evidence = evidence_by_id.get(result.source_evidence_id)
        if (
            candidate is None
            or evidence is None
            or candidate.source_evidence_id != evidence.evidence_id
        ):
            raise SauceDemoArtifactHandoffError(
                "workflow validation references are invalid"
            )
        rebuilt = build_validation_result(
            candidate,
            evidence,
            datetime.fromisoformat(result.validated_at),
        )
        if rebuilt.to_workflow_payload() != result.to_workflow_payload():
            raise SauceDemoArtifactHandoffError(
                "workflow validation content is inconsistent"
            )
        if (
            result.validation_id in validation_ids
            or result.candidate_id in candidate_ids
        ):
            raise SauceDemoArtifactHandoffError(
                "workflow validation correlation is ambiguous"
            )
        validation_ids.add(result.validation_id)
        candidate_ids.add(result.candidate_id)
        results.append(result)
    return results


def _knowledge_items(knowledge: KnowledgeArtifact):
    return (
        *knowledge.pages,
        *knowledge.elements,
        *knowledge.locators,
        *knowledge.interactions,
    )
