"""Lightweight product contracts shared by SauceDemo exploration adapters."""

from typing import Literal, Tuple

from pydantic import BaseModel, ConfigDict, Field


SAUCEDEMO_EXPLORATION_TOOL_ID = "playwright.saucedemo_explore"
SAUCEDEMO_EXPLORATION_ACTIONS = (
    "inspect_login_page",
    "login",
    "verify_inventory_page",
    "inspect_inventory_item",
)

SauceDemoExplorationAction = Literal[
    "inspect_login_page",
    "login",
    "verify_inventory_page",
    "inspect_inventory_item",
]


class SauceDemoExplorationInput(BaseModel):
    """Strict product-owned input for the bounded SauceDemo action plan."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
    )

    product_id: str = Field(min_length=1)
    actions: Tuple[SauceDemoExplorationAction, ...] = Field(min_length=1)
