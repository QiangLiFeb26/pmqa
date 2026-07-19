"""Unit tests for provider-independent agent and typed patch contracts."""

import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from pmqa.workflow import (
    AGENT_UPDATE_POLICY,
    AgentContractValidationError,
    AgentExecutionStatus,
    AgentRequest,
    AgentResult,
    AgentRole,
    TerminationReason,
    WorkflowPatchField,
    WorkflowState,
    WorkflowStatePatch,
    WorkflowStatus,
    validate_agent_result,
    validate_patch_for_role,
)


def test_agent_request_is_immutable_and_json_round_trips() -> None:
    request = _request()

    restored = AgentRequest.model_validate_json(request.model_dump_json())

    assert restored == request
    assert restored.state == request.state
    with pytest.raises(ValidationError, match="frozen"):
        request.instruction = "changed"
    with pytest.raises(AttributeError):
        request.context_refs.append("context-2")


def test_agent_request_validates_workflow_and_timestamp() -> None:
    with pytest.raises(ValidationError, match="state.workflow_id"):
        _request(workflow_id="another-workflow")
    with pytest.raises(ValidationError, match="timezone"):
        _request(requested_at=datetime(2026, 1, 1))


def test_agent_request_rejects_extra_fields_and_runtime_objects() -> None:
    payload = _request().model_dump(mode="python")
    payload["provider"] = object()

    with pytest.raises(ValidationError, match="provider"):
        AgentRequest.model_validate(payload)

    payload = _request().model_dump(mode="python")
    payload["context_refs"] = [object()]
    with pytest.raises(ValidationError, match="context_refs"):
        AgentRequest.model_validate(payload)


def test_empty_patch_has_stable_omitted_semantics() -> None:
    patch = WorkflowStatePatch()
    restored = WorkflowStatePatch.model_validate_json(patch.model_dump_json())

    assert patch.requested_fields() == frozenset()
    assert restored.requested_fields() == frozenset()
    assert restored == patch


def test_patch_append_and_clear_semantics_survive_json_round_trip() -> None:
    patch = WorkflowStatePatch(
        clear_next_agent=True,
        evidence_to_add=[{"evidence_id": "evidence-1"}],
        reasoning_trace_ids_to_add=["trace-1"],
        warnings_to_add=["review evidence"],
        updated_at=_timestamp(1),
    )

    restored = WorkflowStatePatch.model_validate_json(patch.model_dump_json())

    assert restored == patch
    assert restored.requested_fields() == {
        WorkflowPatchField.NEXT_AGENT,
        WorkflowPatchField.EVIDENCE_TO_ADD,
        WorkflowPatchField.REASONING_TRACE_IDS_TO_ADD,
        WorkflowPatchField.WARNINGS_TO_ADD,
        WorkflowPatchField.UPDATED_AT,
    }


def test_patch_collections_and_nested_payloads_are_deeply_immutable() -> None:
    patch = WorkflowStatePatch(
        evidence_to_add=[{"nested": {"ids": ["evidence-1"]}}],
        warnings_to_add=["warning-1"],
    )

    with pytest.raises(AttributeError):
        patch.evidence_to_add.append({"evidence_id": "evidence-2"})
    with pytest.raises(TypeError, match="immutable"):
        patch.evidence_to_add[0]["changed"] = True
    with pytest.raises(AttributeError):
        patch.evidence_to_add[0]["nested"]["ids"].append("evidence-2")
    with pytest.raises(AttributeError):
        patch.warnings_to_add.append("warning-2")


def test_patch_identity_fields_cannot_be_requested() -> None:
    for field in (
        "workflow_id",
        "workflow_type",
        "product_id",
        "product_version",
        "goal",
        "max_iterations",
        "created_at",
        "product_context",
    ):
        with pytest.raises(ValidationError, match=field):
            WorkflowStatePatch.model_validate({field: "not-allowed"})


def test_patch_rejects_invalid_values_and_unsafe_payloads() -> None:
    with pytest.raises(ValidationError, match="iteration"):
        WorkflowStatePatch(iteration=-1)
    with pytest.raises(ValidationError, match="status"):
        WorkflowStatePatch(status="unknown")
    with pytest.raises(ValidationError, match="timezone"):
        WorkflowStatePatch(updated_at=datetime(2026, 1, 1))
    with pytest.raises(ValidationError, match="api_key") as captured:
        WorkflowStatePatch(
            evidence_to_add=[{"api_key": "patch-secret-marker"}]
        )
    assert "patch-secret-marker" not in str(captured.value)
    with pytest.raises(ValidationError, match="api_key"):
        WorkflowStatePatch().model_copy(
            update={"evidence_to_add": [{"api_key": "copy-secret"}]}
        )


def test_patch_enforces_clear_and_termination_correlation() -> None:
    with pytest.raises(ValidationError, match="set and cleared"):
        WorkflowStatePatch(
            next_agent=AgentRole.EXPLORER,
            clear_next_agent=True,
        )
    with pytest.raises(ValidationError, match="requires termination_reason"):
        WorkflowStatePatch(status=WorkflowStatus.COMPLETED)
    with pytest.raises(ValidationError, match="requires a terminal status"):
        WorkflowStatePatch(
            termination_reason=TerminationReason.GOAL_COMPLETED
        )
    patch = WorkflowStatePatch(
        status=WorkflowStatus.COMPLETED,
        termination_reason=TerminationReason.GOAL_COMPLETED,
    )
    assert WorkflowPatchField.TERMINATION_REASON in patch.requested_fields()


@pytest.mark.parametrize(
    ("role", "patch"),
    [
        (AgentRole.EXPLORER, WorkflowStatePatch(evidence_to_add=[{"id": "e1"}])),
        (
            AgentRole.KNOWLEDGE,
            WorkflowStatePatch(knowledge_candidates_to_add=[{"id": "k1"}]),
        ),
        (
            AgentRole.VALIDATOR,
            WorkflowStatePatch(validation_results_to_add=[{"id": "v1"}]),
        ),
        (
            AgentRole.SUPERVISOR,
            WorkflowStatePatch(
                status=WorkflowStatus.RUNNING,
                next_agent=AgentRole.EXPLORER,
                iteration=1,
            ),
        ),
    ],
)
def test_role_capabilities_allow_owned_operations(
    role: AgentRole, patch: WorkflowStatePatch
) -> None:
    assert validate_patch_for_role(role, patch) is patch


@pytest.mark.parametrize(
    ("role", "patch", "field"),
    [
        (
            AgentRole.EXPLORER,
            WorkflowStatePatch(next_agent=AgentRole.VALIDATOR),
            "next_agent",
        ),
        (
            AgentRole.KNOWLEDGE,
            WorkflowStatePatch(evidence_to_add=[{"id": "e1"}]),
            "evidence_to_add",
        ),
        (
            AgentRole.VALIDATOR,
            WorkflowStatePatch(status=WorkflowStatus.RUNNING),
            "status",
        ),
    ],
)
def test_role_capabilities_reject_unowned_operations(
    role: AgentRole, patch: WorkflowStatePatch, field: str
) -> None:
    with pytest.raises(AgentContractValidationError, match=field):
        validate_patch_for_role(role, patch)


def test_capability_metadata_is_deeply_immutable() -> None:
    capabilities = AGENT_UPDATE_POLICY[AgentRole.EXPLORER]

    with pytest.raises(TypeError):
        AGENT_UPDATE_POLICY[AgentRole.EXPLORER] = capabilities
    with pytest.raises(AttributeError):
        capabilities.allowed_patch_fields.add(WorkflowPatchField.NEXT_AGENT)


def test_agent_result_is_typed_immutable_and_json_round_trips() -> None:
    result = _result()

    restored = AgentResult.model_validate_json(result.model_dump_json())

    assert restored == result
    assert "state" not in AgentResult.model_fields
    with pytest.raises(ValidationError, match="frozen"):
        result.outcome_status = AgentExecutionStatus.FAILED
    with pytest.raises(TypeError, match="immutable"):
        result.summary["changed"] = True
    with pytest.raises(AttributeError):
        result.warnings.append("changed")


def test_agent_result_validates_identity_timestamp_and_capability() -> None:
    with pytest.raises(ValidationError, match="workflow_id"):
        _result(workflow_id="")
    with pytest.raises(ValidationError, match="invocation_id"):
        _result(invocation_id="")
    with pytest.raises(ValidationError, match="timezone"):
        _result(completed_at=datetime(2026, 1, 1))
    with pytest.raises(ValidationError, match="next_agent"):
        _result(patch=WorkflowStatePatch(next_agent=AgentRole.VALIDATOR))
    with pytest.raises(ValidationError, match="outcome_status"):
        _result(outcome_status="unknown")
    payload = _result().model_dump(mode="python")
    payload["state"] = _state()
    with pytest.raises(ValidationError, match="state"):
        AgentResult.model_validate(payload)


def test_request_result_correlation() -> None:
    request = _request()
    result = _result()

    assert validate_agent_result(request, result) is result
    with pytest.raises(AgentContractValidationError, match="workflow_id"):
        validate_agent_result(request, _result(workflow_id="another-workflow"))
    with pytest.raises(AgentContractValidationError, match="role"):
        validate_agent_result(
            request,
            _result(agent=AgentRole.KNOWLEDGE, patch=WorkflowStatePatch()),
        )
    with pytest.raises(AgentContractValidationError, match="invocation_id"):
        validate_agent_result(request, _result(invocation_id="another"))
    with pytest.raises(AgentContractValidationError, match="precede"):
        validate_agent_result(
            request,
            _result(completed_at=request.requested_at - timedelta(seconds=1)),
        )


def test_agent_contract_imports_do_not_load_runtime_dependencies() -> None:
    statement = "\n".join(
        [
            "import sys",
            "from pmqa.workflow import AgentRequest, AgentResult, PMQAAgent",
            "assert AgentRequest and AgentResult and PMQAAgent",
            "assert 'pmqa.workflow.graph' not in sys.modules",
            "assert not any(name == 'langgraph' or name.startswith('langgraph.') "
            "for name in sys.modules)",
            "assert not any(name == 'playwright' or name.startswith('playwright.') "
            "for name in sys.modules)",
        ]
    )
    completed = subprocess.run(
        [sys.executable, "-c", statement],
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def _request(**updates) -> AgentRequest:
    values = {
        "workflow_id": "workflow-1",
        "agent": AgentRole.EXPLORER,
        "state": _state(),
        "invocation_id": "invocation-1",
        "requested_at": _timestamp(),
        "instruction": "Collect structured evidence",
        "context_refs": ["page.login"],
    }
    values.update(updates)
    return AgentRequest(**values)


def _result(**updates) -> AgentResult:
    values = {
        "workflow_id": "workflow-1",
        "agent": AgentRole.EXPLORER,
        "invocation_id": "invocation-1",
        "patch": WorkflowStatePatch(
            evidence_to_add=[{"evidence_id": "evidence-1"}]
        ),
        "completed_at": _timestamp(1),
        "outcome_status": AgentExecutionStatus.SUCCEEDED,
        "summary": {"evidence_ids": ["evidence-1"]},
        "reasoning_trace_id": "trace-1",
        "warnings": [],
        "errors": [],
    }
    values.update(updates)
    return AgentResult(**values)


def _state() -> WorkflowState:
    return WorkflowState(
        workflow_id="workflow-1",
        workflow_type="product-analysis",
        product_id="demo",
        product_version="1",
        goal="Collect evidence",
        max_iterations=3,
        created_at=_timestamp(),
        updated_at=_timestamp(),
    )


def _timestamp(seconds: int = 0) -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=seconds)
