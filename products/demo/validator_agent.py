"""Product-owned deterministic SauceDemo knowledge Validator agent."""

from datetime import datetime
from typing import Dict, List, Set, Tuple

from pydantic import ValidationError

from pmqa.models import ExplorationEvidence
from pmqa.workflow import (
    AGENT_UPDATE_POLICY,
    AgentCapabilities,
    AgentExecutionStatus,
    AgentInvocation,
    AgentInvocationStatus,
    AgentRequest,
    AgentResult,
    AgentRole,
    WorkflowStatePatch,
)
from products.demo.knowledge_mapping import (
    KnowledgeCandidateError,
    SauceDemoKnowledgeCandidate,
)
from products.demo.validation import (
    VALIDATION_SCHEMA_VERSION,
    SauceDemoValidationResult,
    ValidationResultError,
    build_validation_result,
)


_FAILURE_CODE = "validator_execution_failed"


class ValidatorSelectionError(ValueError):
    """Reports malformed or ambiguous append-only validation state."""


class SauceDemoValidatorAgent:
    """Validate exactly one unvalidated deterministic knowledge candidate."""

    @property
    def role(self) -> AgentRole:
        """Declare the canonical Validator role."""

        return AgentRole.VALIDATOR

    @property
    def capabilities(self) -> AgentCapabilities:
        """Return the canonical Validator patch capabilities."""

        return AGENT_UPDATE_POLICY[AgentRole.VALIDATOR]

    def invoke(self, request: AgentRequest) -> AgentResult:
        """Validate one candidate without mutating workflow state."""

        try:
            candidate, evidence = _select_unvalidated_candidate(request)
            validation = build_validation_result(
                candidate, evidence, request.requested_at
            )
        except (ValidationResultError, ValidatorSelectionError):
            return self._failure(request)

        summary = _validation_summary(validation)
        history = AgentInvocation(
            agent=self.role,
            started_at=request.requested_at,
            completed_at=request.requested_at,
            status=AgentInvocationStatus.COMPLETED,
            input_summary={
                "candidate_id": validation.candidate_id,
                "source_evidence_id": validation.source_evidence_id,
                "validation_schema_version": VALIDATION_SCHEMA_VERSION,
            },
            output_summary=summary,
        )
        return AgentResult(
            workflow_id=request.workflow_id,
            agent=self.role,
            invocation_id=request.invocation_id,
            patch=WorkflowStatePatch(
                validation_results_to_add=(validation.to_workflow_payload(),),
                step_history_to_add=(history,),
                updated_at=request.requested_at,
            ),
            completed_at=request.requested_at,
            outcome_status=AgentExecutionStatus.SUCCEEDED,
            summary=summary,
        )

    def _failure(self, request: AgentRequest) -> AgentResult:
        summary = {
            "validation_schema_version": VALIDATION_SCHEMA_VERSION,
            "error_code": _FAILURE_CODE,
        }
        history = AgentInvocation(
            agent=self.role,
            started_at=request.requested_at,
            completed_at=request.requested_at,
            status=AgentInvocationStatus.FAILED,
            input_summary={
                "evidence_count": len(request.state.evidence),
                "candidate_count": len(request.state.knowledge_candidates),
                "validation_result_count": len(request.state.validation_results),
                "validation_schema_version": VALIDATION_SCHEMA_VERSION,
            },
            output_summary=summary,
        )
        return AgentResult(
            workflow_id=request.workflow_id,
            agent=self.role,
            invocation_id=request.invocation_id,
            patch=WorkflowStatePatch(
                step_history_to_add=(history,),
                errors_to_add=(_FAILURE_CODE,),
                updated_at=request.requested_at,
            ),
            completed_at=request.requested_at,
            outcome_status=AgentExecutionStatus.FAILED,
            summary=summary,
            errors=(_FAILURE_CODE,),
        )


def _select_unvalidated_candidate(
    request: AgentRequest,
) -> Tuple[SauceDemoKnowledgeCandidate, ExplorationEvidence]:
    evidence_by_id = _parse_evidence(request)
    candidates = _parse_candidates(request, evidence_by_id)
    candidate_by_id = {item.candidate_id: item for item in candidates}

    validation_ids: Set[str] = set()
    validated_candidate_ids: Set[str] = set()
    for payload in request.state.validation_results:
        try:
            result = SauceDemoValidationResult.from_workflow_payload(payload)
        except ValidationResultError as error:
            raise ValidatorSelectionError(
                "existing validation result is invalid"
            ) from error
        if (
            result.workflow_id != request.workflow_id
            or result.product_id != request.state.product_id
        ):
            raise ValidatorSelectionError(
                "validation result correlation is invalid"
            )
        candidate = candidate_by_id.get(result.candidate_id)
        if candidate is None:
            raise ValidatorSelectionError(
                "validation result references missing candidate"
            )
        if result.source_evidence_id != candidate.source_evidence_id:
            raise ValidatorSelectionError(
                "validation result evidence correlation is invalid"
            )
        evidence = evidence_by_id[candidate.source_evidence_id]
        expected = build_validation_result(
            candidate,
            evidence,
            _validated_at(result),
        )
        if expected.to_workflow_payload() != result.to_workflow_payload():
            raise ValidatorSelectionError(
                "validation result content is inconsistent"
            )
        if result.validation_id in validation_ids:
            raise ValidatorSelectionError("duplicate validation ID")
        if result.candidate_id in validated_candidate_ids:
            raise ValidatorSelectionError(
                "candidate has duplicate validation results"
            )
        validation_ids.add(result.validation_id)
        validated_candidate_ids.add(result.candidate_id)

    unvalidated = [
        candidate
        for candidate in candidates
        if candidate.candidate_id not in validated_candidate_ids
    ]
    if len(unvalidated) != 1:
        raise ValidatorSelectionError(
            "workflow must contain exactly one unvalidated candidate"
        )
    candidate = unvalidated[0]
    return candidate, evidence_by_id[candidate.source_evidence_id]


def _parse_evidence(request: AgentRequest) -> Dict[str, ExplorationEvidence]:
    if not request.state.evidence:
        raise ValidatorSelectionError("workflow contains no evidence")
    items: List[ExplorationEvidence] = []
    for payload in request.state.evidence:
        try:
            evidence = ExplorationEvidence.from_workflow_payload(payload)
        except (TypeError, ValidationError) as error:
            raise ValidatorSelectionError("workflow evidence is invalid") from error
        if (
            evidence.workflow_id != request.workflow_id
            or evidence.product_id != request.state.product_id
        ):
            raise ValidatorSelectionError(
                "workflow evidence correlation is invalid"
            )
        items.append(evidence)
    result = {item.evidence_id: item for item in items}
    if len(result) != len(items):
        raise ValidatorSelectionError("workflow contains duplicate evidence IDs")
    return result


def _parse_candidates(
    request: AgentRequest,
    evidence_by_id: Dict[str, ExplorationEvidence],
) -> List[SauceDemoKnowledgeCandidate]:
    if not request.state.knowledge_candidates:
        raise ValidatorSelectionError("workflow contains no knowledge candidate")
    items = []
    candidate_ids: Set[str] = set()
    source_ids: Set[str] = set()
    for payload in request.state.knowledge_candidates:
        try:
            candidate = SauceDemoKnowledgeCandidate.from_workflow_payload(payload)
        except KnowledgeCandidateError as error:
            raise ValidatorSelectionError("knowledge candidate is invalid") from error
        if (
            candidate.workflow_id != request.workflow_id
            or candidate.product_id != request.state.product_id
        ):
            raise ValidatorSelectionError(
                "knowledge candidate correlation is invalid"
            )
        if candidate.source_evidence_id not in evidence_by_id:
            raise ValidatorSelectionError("candidate references missing evidence")
        if candidate.candidate_id in candidate_ids:
            raise ValidatorSelectionError("workflow contains duplicate candidate IDs")
        if candidate.source_evidence_id in source_ids:
            raise ValidatorSelectionError(
                "workflow contains duplicate candidate evidence correlation"
            )
        candidate_ids.add(candidate.candidate_id)
        source_ids.add(candidate.source_evidence_id)
        items.append(candidate)
    return items


def _validated_at(result: SauceDemoValidationResult) -> datetime:
    return datetime.fromisoformat(result.validated_at)


def _validation_summary(result: SauceDemoValidationResult):
    knowledge = result.verified_knowledge
    return {
        "validation_id": result.validation_id,
        "candidate_id": result.candidate_id,
        "source_evidence_id": result.source_evidence_id,
        "status": result.status,
        "check_codes": tuple(check.code for check in result.checks),
        "validation_schema_version": VALIDATION_SCHEMA_VERSION,
        "verified_entity_count": (
            len(knowledge.pages)
            + len(knowledge.elements)
            + len(knowledge.locators)
            + len(knowledge.interactions)
            if knowledge is not None
            else 0
        ),
    }
