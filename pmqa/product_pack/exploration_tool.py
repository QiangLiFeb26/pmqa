"""Product-neutral PMQA Tool adapter for explicit Product Pack capture."""

from typing import Callable, Optional, Tuple

from pydantic import ValidationError

from pmqa.models import ExplorationEvidence
from pmqa.product_pack.bridge_protocol import (
    BRIDGE_PROTOCOL_VERSION,
    MAX_BRIDGE_ACTION_COUNT,
    ProductPackBridgeOperation,
    ProductPackBridgeRequest,
    ProductPackBridgeResponse,
    ProductPackBridgeStatus,
    validate_product_pack_bridge_response,
)
from pmqa.product_pack.bridge_runner import (
    ProductPackBridgeExecutionError,
    ProductPackBridgeProcessConfig,
    run_product_pack_bridge,
)
from pmqa.product_pack.loader import LoadedProductPack
from pmqa.product_pack.manifest import (
    PRODUCT_PACK_API_VERSION,
    ProductPackCapability,
    ProductPackManifest,
    validate_product_pack_identifier,
)
from pmqa.security.boundary_policy import (
    WORKFLOW_STATE_PROHIBITED_KEYS,
    is_prohibited_key,
)
from pmqa.workflow.tools import (
    ToolCategory,
    ToolError,
    ToolExecutionStatus,
    ToolMetadata,
    ToolRequest,
    ToolResult,
)
from pmqa.workflow.models import AgentRole


PRODUCT_PACK_EXPLORATION_FAILURE_CODE = "product_pack_exploration_failed"
PRODUCT_PACK_EXPLORATION_FAILURE_MESSAGE = (
    "Product Pack exploration failed"
)


class ProductPackExplorationToolError(ValueError):
    """Report invalid trusted adapter construction without sensitive values."""

    def __init__(self) -> None:
        super().__init__("invalid Product Pack exploration Tool configuration")


BridgeRunner = Callable[
    [ProductPackBridgeRequest, ProductPackBridgeProcessConfig],
    ProductPackBridgeResponse,
]


class ProductPackExplorationTool:
    """Map one PMQA Tool invocation to one explicit Bridge v1 exchange."""

    def __init__(
        self,
        loaded_product_pack: LoadedProductPack,
        process_config: ProductPackBridgeProcessConfig,
        tool_id: str,
        *,
        bridge_runner: Optional[BridgeRunner] = None,
    ) -> None:
        if (
            type(loaded_product_pack) is not LoadedProductPack
            or type(process_config) is not ProductPackBridgeProcessConfig
            or type(tool_id) is not str
        ):
            raise ProductPackExplorationToolError() from None
        try:
            validate_product_pack_identifier(tool_id)
        except ValueError:
            raise ProductPackExplorationToolError() from None
        manifest = loaded_product_pack.manifest
        if (
            manifest.product_pack_api_version != PRODUCT_PACK_API_VERSION
            or ProductPackCapability.EXPLORATION_CAPTURE
            not in manifest.capabilities
        ):
            raise ProductPackExplorationToolError() from None
        if bridge_runner is not None and not callable(bridge_runner):
            raise ProductPackExplorationToolError() from None

        try:
            validated_pack = LoadedProductPack(
                loaded_product_pack.distribution_name,
                ProductPackManifest.from_dict(manifest.to_dict()),
            )
            validated_config = ProductPackBridgeProcessConfig(
                **{
                    name: getattr(process_config, name)
                    for name in ProductPackBridgeProcessConfig.__dataclass_fields__
                }
            )
        except (
            AttributeError,
            TypeError,
            ValueError,
            ProductPackBridgeExecutionError,
        ):
            raise ProductPackExplorationToolError() from None

        self._loaded_product_pack = validated_pack
        self._process_config = validated_config
        self._bridge_runner = bridge_runner or run_product_pack_bridge
        self._metadata = ToolMetadata(
            tool_id=tool_id,
            category=ToolCategory.PLAYWRIGHT,
            description=(
                "Capture bounded exploration evidence through an explicit "
                "Product Pack"
            ),
            input_schema_version="1",
            output_schema_version="1",
        )

    @property
    def metadata(self) -> ToolMetadata:
        """Return the immutable generic Tool metadata."""

        return self._metadata

    def invoke(self, request: ToolRequest) -> ToolResult:
        """Perform at most one correlated external bridge invocation."""

        if type(request) is not ToolRequest:
            raise ProductPackExplorationToolError() from None
        actions = _validated_actions(request)
        if (
            request.requested_by_agent is not AgentRole.EXPLORER
            or request.tool_id != self.metadata.tool_id
            or request.category is not self.metadata.category
            or request.input.get("product_id")
            != self._loaded_product_pack.manifest.product_id
            or actions is None
        ):
            return self._failure(request, request.requested_at)

        try:
            bridge_request = ProductPackBridgeRequest(
                protocol_version=BRIDGE_PROTOCOL_VERSION,
                request_id=request.invocation_id,
                workflow_id=request.workflow_id,
                product_id=self._loaded_product_pack.manifest.product_id,
                pack_id=self._loaded_product_pack.manifest.pack_id,
                tool_id=self.metadata.tool_id,
                operation=ProductPackBridgeOperation.EXPLORATION_CAPTURE,
                requested_at=request.requested_at,
                action_plan=actions,
            )
        except (TypeError, ValueError, ValidationError):
            return self._failure(request, request.requested_at)

        try:
            response = self._bridge_runner(
                bridge_request,
                self._process_config,
            )
            correlated = validate_product_pack_bridge_response(
                bridge_request,
                response,
            )
        except (MemoryError, KeyboardInterrupt, SystemExit, GeneratorExit):
            raise
        except Exception:
            return self._failure(request, request.requested_at)

        if (
            correlated.status is not ProductPackBridgeStatus.SUCCEEDED
            or correlated.evidence is None
        ):
            return self._failure(request, correlated.completed_at)
        try:
            evidence = ExplorationEvidence.from_workflow_payload(
                correlated.evidence.to_workflow_payload()
            )
        except (TypeError, ValidationError):
            return self._failure(request, correlated.completed_at)
        return ToolResult(
            tool_id=request.tool_id,
            workflow_id=request.workflow_id,
            invocation_id=request.invocation_id,
            completed_at=correlated.completed_at,
            status=ToolExecutionStatus.SUCCEEDED,
            output={"evidence": evidence.to_workflow_payload()},
            summary={
                "page_count": len(evidence.pages),
                "element_count": len(evidence.elements),
                "locator_candidate_count": len(evidence.locator_candidates),
                "interaction_count": len(evidence.interactions),
            },
        )

    def _failure(self, request: ToolRequest, completed_at) -> ToolResult:
        return ToolResult(
            tool_id=request.tool_id,
            workflow_id=request.workflow_id,
            invocation_id=request.invocation_id,
            completed_at=max(completed_at, request.requested_at),
            status=ToolExecutionStatus.FAILED,
            errors=(
                ToolError(
                    code=PRODUCT_PACK_EXPLORATION_FAILURE_CODE,
                    message=PRODUCT_PACK_EXPLORATION_FAILURE_MESSAGE,
                ),
            ),
        )


def _validated_actions(request: ToolRequest) -> Optional[Tuple[str, ...]]:
    if set(request.input) != {"product_id", "actions"}:
        return None
    actions = request.input.get("actions")
    if (
        not isinstance(actions, tuple)
        or not actions
        or len(actions) > MAX_BRIDGE_ACTION_COUNT
    ):
        return None
    validated = []
    for action in actions:
        if type(action) is not str or is_prohibited_key(
            action, WORKFLOW_STATE_PROHIBITED_KEYS
        ):
            return None
        try:
            validated.append(validate_product_pack_identifier(action))
        except ValueError:
            return None
    if len(set(validated)) != len(validated):
        return None
    return tuple(validated)


__all__ = [
    "BridgeRunner",
    "PRODUCT_PACK_EXPLORATION_FAILURE_CODE",
    "PRODUCT_PACK_EXPLORATION_FAILURE_MESSAGE",
    "ProductPackExplorationTool",
    "ProductPackExplorationToolError",
]
