"""Parallel SauceDemo composition through an explicit external Product Pack."""

from typing import Optional

from pmqa.product_pack import (
    BridgeRunner,
    LoadedProductPack,
    ProductPackBridgeProcessConfig,
    ProductPackCapability,
    ProductPackExplorationTool,
    ProductPackExplorationToolError,
    ProductPackManifest,
)
from pmqa.workflow import WorkflowState
from products.demo.config import DemoConfig
from products.demo.exploration_contracts import SAUCEDEMO_EXPLORATION_TOOL_ID
from products.demo.workflow import (
    SauceDemoWorkflowCompositionError,
    _run_saucedemo_tool_workflow,
    _validate_config,
    _validate_initial_state,
)


SAUCEDEMO_PRODUCT_PACK_DISTRIBUTION = "pmqa-product-pack-saucedemo"
SAUCEDEMO_PRODUCT_PACK_MANIFEST = ProductPackManifest(
    schema_version="1",
    product_pack_api_version="1",
    pack_id="saucedemo",
    pack_version="0.1.0",
    product_id="demo",
    display_name="SauceDemo Product Pack",
    capabilities=(ProductPackCapability.EXPLORATION_CAPTURE,),
)
_DEFAULT_RECURSION_LIMIT = 64


class SauceDemoProductPackWorkflowCompositionError(ValueError):
    """Report only stable external Product Pack composition failures."""

    def __init__(self) -> None:
        super().__init__("SauceDemo Product Pack workflow configuration is invalid")


def run_saucedemo_product_pack_workflow(
    config: DemoConfig,
    initial_state: WorkflowState,
    loaded_product_pack: LoadedProductPack,
    process_config: ProductPackBridgeProcessConfig,
    *,
    bridge_runner: Optional[BridgeRunner] = None,
    recursion_limit: int = _DEFAULT_RECURSION_LIMIT,
) -> WorkflowState:
    """Run the existing SauceDemo agents and graph through one external pack."""

    try:
        _validate_config(config)
        _validate_initial_state(initial_state, config)
    except SauceDemoWorkflowCompositionError:
        raise SauceDemoProductPackWorkflowCompositionError() from None
    if (
        type(loaded_product_pack) is not LoadedProductPack
        or loaded_product_pack.distribution_name
        != SAUCEDEMO_PRODUCT_PACK_DISTRIBUTION
        or loaded_product_pack.manifest != SAUCEDEMO_PRODUCT_PACK_MANIFEST
        or type(process_config) is not ProductPackBridgeProcessConfig
        or type(recursion_limit) is not int
        or recursion_limit < 1
        or (bridge_runner is not None and not callable(bridge_runner))
    ):
        raise SauceDemoProductPackWorkflowCompositionError() from None
    try:
        tool = ProductPackExplorationTool(
            loaded_product_pack,
            process_config,
            SAUCEDEMO_EXPLORATION_TOOL_ID,
            bridge_runner=bridge_runner,
        )
    except ProductPackExplorationToolError:
        raise SauceDemoProductPackWorkflowCompositionError() from None
    return _run_saucedemo_tool_workflow(
        initial_state,
        tool,
        recursion_limit=recursion_limit,
    )


__all__ = [
    "SAUCEDEMO_PRODUCT_PACK_DISTRIBUTION",
    "SAUCEDEMO_PRODUCT_PACK_MANIFEST",
    "SauceDemoProductPackWorkflowCompositionError",
    "run_saucedemo_product_pack_workflow",
]
