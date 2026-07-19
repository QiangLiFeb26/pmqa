"""Product-owned Knowledge agent for deterministic SauceDemo candidates."""

from typing import Dict, List, Set

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
    CANDIDATE_SCHEMA_VERSION,
    MAPPING_PROVENANCE,
    KnowledgeCandidateError,
    SauceDemoKnowledgeCandidate,
    build_knowledge_candidate,
)


_FAILURE_CODE = "knowledge_mapping_failed"


class KnowledgeSelectionError(ValueError):
    """Reports invalid or ambiguous append-only workflow candidate state."""


class SauceDemoKnowledgeAgent:
    """Map exactly one unprocessed evidence batch into a knowledge candidate."""

    @property
    def role(self) -> AgentRole:
        """Declare the canonical Knowledge role."""

        return AgentRole.KNOWLEDGE

    @property
    def capabilities(self) -> AgentCapabilities:
        """Return the canonical Knowledge patch capabilities."""

        return AGENT_UPDATE_POLICY[AgentRole.KNOWLEDGE]

    def invoke(self, request: AgentRequest) -> AgentResult:
        """Select and map one evidence batch without mutating workflow state."""

        try:
            evidence = _select_unprocessed_evidence(request)
            candidate = build_knowledge_candidate(evidence)
        except (KnowledgeCandidateError, KnowledgeSelectionError):
            return self._failure(request)

        completed_at = request.requested_at
        payload = candidate.to_workflow_payload()
        summary = _candidate_summary(candidate)
        history = AgentInvocation(
            agent=self.role,
            started_at=request.requested_at,
            completed_at=completed_at,
            status=AgentInvocationStatus.COMPLETED,
            input_summary={
                "source_evidence_id": candidate.source_evidence_id,
                "mapping_version": CANDIDATE_SCHEMA_VERSION,
            },
            output_summary=summary,
        )
        return AgentResult(
            workflow_id=request.workflow_id,
            agent=self.role,
            invocation_id=request.invocation_id,
            patch=WorkflowStatePatch(
                knowledge_candidates_to_add=(payload,),
                step_history_to_add=(history,),
                updated_at=completed_at,
            ),
            completed_at=completed_at,
            outcome_status=AgentExecutionStatus.SUCCEEDED,
            summary=summary,
        )

    def _failure(self, request: AgentRequest) -> AgentResult:
        completed_at = request.requested_at
        history = AgentInvocation(
            agent=self.role,
            started_at=request.requested_at,
            completed_at=completed_at,
            status=AgentInvocationStatus.FAILED,
            input_summary={
                "evidence_count": len(request.state.evidence),
                "candidate_count": len(request.state.knowledge_candidates),
                "mapping_version": CANDIDATE_SCHEMA_VERSION,
            },
            output_summary={"error_code": _FAILURE_CODE},
        )
        return AgentResult(
            workflow_id=request.workflow_id,
            agent=self.role,
            invocation_id=request.invocation_id,
            patch=WorkflowStatePatch(
                step_history_to_add=(history,),
                errors_to_add=(_FAILURE_CODE,),
                updated_at=completed_at,
            ),
            completed_at=completed_at,
            outcome_status=AgentExecutionStatus.FAILED,
            summary={
                "mapping_version": CANDIDATE_SCHEMA_VERSION,
                "error_code": _FAILURE_CODE,
            },
            errors=(_FAILURE_CODE,),
        )


def _select_unprocessed_evidence(request: AgentRequest) -> ExplorationEvidence:
    if not request.state.evidence:
        raise KnowledgeSelectionError("workflow contains no evidence")
    evidence_items: List[ExplorationEvidence] = []
    for payload in request.state.evidence:
        try:
            evidence = ExplorationEvidence.from_workflow_payload(payload)
        except (TypeError, ValidationError) as error:
            raise KnowledgeSelectionError("workflow evidence is invalid") from error
        if (
            evidence.workflow_id != request.workflow_id
            or evidence.product_id != request.state.product_id
        ):
            raise KnowledgeSelectionError("workflow evidence correlation is invalid")
        evidence_items.append(evidence)
    evidence_by_id: Dict[str, ExplorationEvidence] = {
        item.evidence_id: item for item in evidence_items
    }
    if len(evidence_by_id) != len(evidence_items):
        raise KnowledgeSelectionError("workflow contains duplicate evidence IDs")

    candidate_ids: Set[str] = set()
    processed_evidence_ids: Set[str] = set()
    for payload in request.state.knowledge_candidates:
        try:
            candidate = SauceDemoKnowledgeCandidate.from_workflow_payload(payload)
        except KnowledgeCandidateError as error:
            raise KnowledgeSelectionError("existing candidate is invalid") from error
        if (
            candidate.workflow_id != request.workflow_id
            or candidate.product_id != request.state.product_id
        ):
            raise KnowledgeSelectionError("existing candidate correlation is invalid")
        if candidate.source_evidence_id not in evidence_by_id:
            raise KnowledgeSelectionError("candidate references missing evidence")
        if candidate.candidate_id in candidate_ids:
            raise KnowledgeSelectionError("workflow contains duplicate candidate IDs")
        if candidate.source_evidence_id in processed_evidence_ids:
            raise KnowledgeSelectionError(
                "workflow contains duplicate candidate evidence correlation"
            )
        candidate_ids.add(candidate.candidate_id)
        processed_evidence_ids.add(candidate.source_evidence_id)

    unprocessed = [
        item
        for item in evidence_items
        if item.evidence_id not in processed_evidence_ids
    ]
    if len(unprocessed) != 1:
        raise KnowledgeSelectionError(
            "workflow must contain exactly one unprocessed evidence batch"
        )
    return unprocessed[0]


def _candidate_summary(candidate: SauceDemoKnowledgeCandidate):
    knowledge = candidate.knowledge
    return {
        "candidate_id": candidate.candidate_id,
        "source_evidence_id": candidate.source_evidence_id,
        "mapping_version": CANDIDATE_SCHEMA_VERSION,
        "mapping_provenance": MAPPING_PROVENANCE,
        "page_count": len(knowledge.pages),
        "element_count": len(knowledge.elements),
        "locator_count": len(knowledge.locators),
        "interaction_count": len(knowledge.interactions),
    }
