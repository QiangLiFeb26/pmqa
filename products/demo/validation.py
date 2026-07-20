"""Strict deterministic SauceDemo knowledge-validation results."""

import hashlib
import json
from dataclasses import dataclass, fields, replace
from datetime import datetime
from typing import Any, Dict, Mapping, Optional, Tuple, Type

from pydantic import ValidationError

from pmqa.models import (
    ArtifactStatus,
    Element,
    ExplorationEvidence,
    KnowledgeArtifact,
    Lifecycle,
)
from products.demo.knowledge_mapping import (
    KnowledgeCandidateError,
    SauceDemoKnowledgeCandidate,
    build_knowledge_candidate,
    candidate_id_for,
)


VALIDATION_SCHEMA_VERSION = "1"
CANDIDATE_MATCH_CHECK = "candidate_matches_source_evidence"
_VALIDATION_STATUSES = frozenset({"passed", "failed"})
_CHECK_CODES = frozenset({CANDIDATE_MATCH_CHECK})


class ValidationResultError(ValueError):
    """Reports invalid validation inputs or result-envelope data."""


@dataclass(frozen=True)
class ValidationCheck:
    """Records one safe deterministic validation decision."""

    code: str
    status: str


@dataclass(frozen=True)
class SauceDemoValidationResult:
    """Correlates one strict validation decision to a knowledge candidate."""

    schema_version: str
    validation_id: str
    workflow_id: str
    product_id: str
    candidate_id: str
    source_evidence_id: str
    status: str
    validated_at: str
    checks: Tuple[ValidationCheck, ...]
    verified_knowledge: Optional[KnowledgeArtifact]

    def to_workflow_payload(self) -> Dict[str, Any]:
        """Return fresh JSON-compatible data for append-only WorkflowState."""

        return {
            "schema_version": self.schema_version,
            "validation_id": self.validation_id,
            "workflow_id": self.workflow_id,
            "product_id": self.product_id,
            "candidate_id": self.candidate_id,
            "source_evidence_id": self.source_evidence_id,
            "status": self.status,
            "validated_at": self.validated_at,
            "checks": [
                {"code": check.code, "status": check.status}
                for check in self.checks
            ],
            "verified_knowledge": (
                self.verified_knowledge.to_dict()
                if self.verified_knowledge is not None
                else None
            ),
        }

    @classmethod
    def from_workflow_payload(
        cls, payload: Mapping[str, Any]
    ) -> "SauceDemoValidationResult":
        """Strictly validate and reconstruct one validation result."""

        cloned = _json_clone(payload)
        if not isinstance(cloned, dict):
            raise ValidationResultError("validation result must be an object")
        _require_exact_keys(cloned, SauceDemoValidationResult)
        for field_name in (
            "schema_version",
            "validation_id",
            "workflow_id",
            "product_id",
            "candidate_id",
            "source_evidence_id",
            "status",
            "validated_at",
        ):
            _require_nonempty_string(cloned[field_name], field_name)
        if cloned["schema_version"] != VALIDATION_SCHEMA_VERSION:
            raise ValidationResultError("validation schema version is unsupported")
        if cloned["status"] not in _VALIDATION_STATUSES:
            raise ValidationResultError("validation status is unsupported")
        validated_at = _parse_timestamp(cloned["validated_at"])
        checks = _parse_checks(cloned["checks"])
        if len(checks) != 1 or checks[0].code != CANDIDATE_MATCH_CHECK:
            raise ValidationResultError("validation checks are incomplete")
        if checks[0].status != cloned["status"]:
            raise ValidationResultError("validation check status is inconsistent")

        verified_payload = cloned["verified_knowledge"]
        if cloned["status"] == "passed":
            if verified_payload is None:
                raise ValidationResultError(
                    "passed validation requires verified knowledge"
                )
            verified_knowledge = _parse_verified_knowledge(
                verified_payload,
                workflow_id=cloned["workflow_id"],
                product_id=cloned["product_id"],
                candidate_id=cloned["candidate_id"],
                source_evidence_id=cloned["source_evidence_id"],
                validated_at=validated_at,
            )
        else:
            if verified_payload is not None:
                raise ValidationResultError(
                    "failed validation cannot contain verified knowledge"
                )
            verified_knowledge = None

        result = cls(
            schema_version=cloned["schema_version"],
            validation_id=cloned["validation_id"],
            workflow_id=cloned["workflow_id"],
            product_id=cloned["product_id"],
            candidate_id=cloned["candidate_id"],
            source_evidence_id=cloned["source_evidence_id"],
            status=cloned["status"],
            validated_at=cloned["validated_at"],
            checks=checks,
            verified_knowledge=verified_knowledge,
        )
        _validate_result_id(result)
        if result.to_workflow_payload() != cloned:
            raise ValidationResultError("validation result is not canonical")
        return result


def build_validation_result(
    candidate: SauceDemoKnowledgeCandidate,
    evidence: ExplorationEvidence,
    validated_at: datetime,
) -> SauceDemoValidationResult:
    """Compare one canonical candidate with its source evidence."""

    timestamp = _canonical_timestamp(validated_at)
    try:
        canonical_candidate = SauceDemoKnowledgeCandidate.from_workflow_payload(
            candidate.to_workflow_payload()
        )
        canonical_evidence = ExplorationEvidence.from_workflow_payload(
            evidence.to_workflow_payload()
        )
    except (KnowledgeCandidateError, TypeError, ValidationError) as error:
        raise ValidationResultError("validation inputs are invalid") from error
    if (
        canonical_candidate.workflow_id != canonical_evidence.workflow_id
        or canonical_candidate.product_id != canonical_evidence.product_id
        or canonical_candidate.source_evidence_id != canonical_evidence.evidence_id
    ):
        raise ValidationResultError("validation input correlation is invalid")

    expected = build_knowledge_candidate(canonical_evidence)
    status = (
        "passed"
        if canonical_candidate.to_workflow_payload()
        == expected.to_workflow_payload()
        else "failed"
    )
    verified_knowledge = (
        _build_verified_snapshot(canonical_candidate.knowledge, timestamp)
        if status == "passed"
        else None
    )
    return SauceDemoValidationResult(
        schema_version=VALIDATION_SCHEMA_VERSION,
        validation_id=_validation_id(
            canonical_candidate.workflow_id,
            canonical_candidate.product_id,
            canonical_candidate.candidate_id,
            canonical_candidate.source_evidence_id,
        ),
        workflow_id=canonical_candidate.workflow_id,
        product_id=canonical_candidate.product_id,
        candidate_id=canonical_candidate.candidate_id,
        source_evidence_id=canonical_candidate.source_evidence_id,
        status=status,
        validated_at=timestamp,
        checks=(ValidationCheck(CANDIDATE_MATCH_CHECK, status),),
        verified_knowledge=verified_knowledge,
    )


def _build_verified_snapshot(
    knowledge: KnowledgeArtifact, validated_at: str
) -> KnowledgeArtifact:
    lifecycle = Lifecycle(ArtifactStatus.VERIFIED, validated_at)
    return KnowledgeArtifact(
        artifact_id=knowledge.artifact_id,
        product_id=knowledge.product_id,
        reasoning_provenance=knowledge.reasoning_provenance,
        pages=[replace(item, lifecycle=lifecycle) for item in knowledge.pages],
        elements=[
            Element(
                id=item.id,
                lifecycle=lifecycle,
                page_id=item.page_id,
                role=item.role,
                accessible_name=item.accessible_name,
                visible_text=item.visible_text,
                attributes=dict(item.attributes),
            )
            for item in knowledge.elements
        ],
        locators=[replace(item, lifecycle=lifecycle) for item in knowledge.locators],
        interactions=[
            replace(item, lifecycle=lifecycle) for item in knowledge.interactions
        ],
    )


def _parse_verified_knowledge(
    payload: Any,
    *,
    workflow_id: str,
    product_id: str,
    candidate_id: str,
    source_evidence_id: str,
    validated_at: datetime,
) -> KnowledgeArtifact:
    if not isinstance(payload, dict):
        raise ValidationResultError("verified knowledge must be an object")
    try:
        verified = KnowledgeArtifact.from_dict(payload)
    except (KeyError, TypeError, ValueError) as error:
        raise ValidationResultError("verified knowledge is malformed") from error
    expected_lifecycle = Lifecycle(
        ArtifactStatus.VERIFIED, validated_at.isoformat()
    )
    items = (
        *verified.pages,
        *verified.elements,
        *verified.locators,
        *verified.interactions,
    )
    if any(item.lifecycle != expected_lifecycle for item in items):
        raise ValidationResultError("verified knowledge lifecycle is invalid")

    new_knowledge = KnowledgeArtifact(
        artifact_id=verified.artifact_id,
        product_id=verified.product_id,
        reasoning_provenance=verified.reasoning_provenance,
        pages=[replace(item, lifecycle=Lifecycle()) for item in verified.pages],
        elements=[
            Element(
                id=item.id,
                lifecycle=Lifecycle(),
                page_id=item.page_id,
                role=item.role,
                accessible_name=item.accessible_name,
                visible_text=item.visible_text,
                attributes=dict(item.attributes),
            )
            for item in verified.elements
        ],
        locators=[replace(item, lifecycle=Lifecycle()) for item in verified.locators],
        interactions=[
            replace(item, lifecycle=Lifecycle())
            for item in verified.interactions
        ],
    )
    try:
        SauceDemoKnowledgeCandidate.from_workflow_payload(
            {
                "schema_version": "1",
                "candidate_id": candidate_id,
                "workflow_id": workflow_id,
                "product_id": product_id,
                "source_evidence_id": source_evidence_id,
                "knowledge": new_knowledge.to_dict(),
            }
        )
    except KnowledgeCandidateError as error:
        raise ValidationResultError("verified knowledge is noncanonical") from error
    if verified.to_dict() != payload:
        raise ValidationResultError("verified knowledge is noncanonical")
    return verified


def _parse_checks(value: Any) -> Tuple[ValidationCheck, ...]:
    if not isinstance(value, list) or not value:
        raise ValidationResultError("validation checks must be a non-empty list")
    checks = []
    seen = set()
    for item in value:
        if not isinstance(item, dict):
            raise ValidationResultError("validation check must be an object")
        _require_exact_keys(item, ValidationCheck)
        _require_nonempty_string(item["code"], "check code")
        _require_nonempty_string(item["status"], "check status")
        if item["code"] not in _CHECK_CODES:
            raise ValidationResultError("validation check code is unsupported")
        if item["status"] not in _VALIDATION_STATUSES:
            raise ValidationResultError("validation check status is unsupported")
        if item["code"] in seen:
            raise ValidationResultError("duplicate validation check code")
        seen.add(item["code"])
        checks.append(ValidationCheck(item["code"], item["status"]))
    return tuple(checks)


def _validate_result_id(result: SauceDemoValidationResult) -> None:
    expected_candidate_id = candidate_id_for(
        result.workflow_id,
        result.product_id,
        result.source_evidence_id,
    )
    if result.candidate_id != expected_candidate_id:
        raise ValidationResultError("validation candidate ID is inconsistent")
    expected = _validation_id(
        result.workflow_id,
        result.product_id,
        result.candidate_id,
        result.source_evidence_id,
    )
    if result.validation_id != expected:
        raise ValidationResultError("validation ID is inconsistent")


def _validation_id(
    workflow_id: str,
    product_id: str,
    candidate_id: str,
    source_evidence_id: str,
) -> str:
    correlation = "\0".join(
        (
            VALIDATION_SCHEMA_VERSION,
            workflow_id,
            product_id,
            candidate_id,
            source_evidence_id,
        )
    ).encode()
    return "validation.saucedemo." + hashlib.sha256(correlation).hexdigest()[:24]


def _canonical_timestamp(value: datetime) -> str:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValidationResultError("validated_at must include timezone information")
    return value.isoformat()


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValidationResultError("validated_at is invalid") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValidationResultError("validated_at must include timezone information")
    if parsed.isoformat() != value:
        raise ValidationResultError("validated_at is not canonical")
    return parsed


def _json_clone(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, allow_nan=False))
    except (TypeError, ValueError) as error:
        raise ValidationResultError("validation result must be JSON data") from error


def _require_exact_keys(value: Mapping[str, Any], model_type: Type) -> None:
    expected = {item.name for item in fields(model_type)}
    if set(value) != expected:
        raise ValidationResultError(
            "validation result contains unexpected or missing fields"
        )


def _require_nonempty_string(value: Any, label: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValidationResultError(f"{label} must be a non-empty string")
