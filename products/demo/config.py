"""Loading and validation for the SauceDemo product pack."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


class DemoConfigValidationError(ValueError):
    """Reports an invalid loaded SauceDemo configuration shape."""


@dataclass(frozen=True)
class DemoConfig:
    """Contains product-owned exploration and output configuration."""

    product_id: str
    base_url: str
    start_path: str
    maximum_exploration_steps: int
    allowed_safe_actions: List[str]
    blocked_destructive_actions: List[str]
    artifact_output_location: Path
    generated_test_output_location: Path
    credential_environment_variables: Dict[str, str]
    demo_only_default_credentials: Dict[str, str]

    def credentials(self) -> Tuple[str, str]:
        """Resolve credentials from environment or explicit public-demo defaults."""

        names = self.credential_environment_variables
        defaults = self.demo_only_default_credentials
        return (
            os.getenv(names["username"], defaults["username"]),
            os.getenv(names["password"], defaults["password"]),
        )


def load_config(repository_root: Path) -> DemoConfig:
    """Load the demo product pack configuration from its JSON file."""

    path = repository_root / "products/demo/config/product.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return DemoConfig(
        product_id=raw["product_id"],
        base_url=raw["base_url"],
        start_path=raw["start_path"],
        maximum_exploration_steps=raw["maximum_exploration_steps"],
        allowed_safe_actions=raw["allowed_safe_actions"],
        blocked_destructive_actions=raw["blocked_destructive_actions"],
        artifact_output_location=repository_root / raw["artifact_output_location"],
        generated_test_output_location=repository_root / raw["generated_test_output_location"],
        credential_environment_variables=raw["credential_environment_variables"],
        demo_only_default_credentials=raw["demo_only_default_credentials"],
    )


def validate_config(config: DemoConfig) -> DemoConfig:
    """Validate the complete product configuration before live capability use."""

    if not isinstance(config, DemoConfig):
        raise DemoConfigValidationError("invalid SauceDemo configuration")
    if config.product_id != "demo":
        raise DemoConfigValidationError("invalid SauceDemo configuration")
    if not _is_nonempty_string(config.base_url):
        raise DemoConfigValidationError("invalid SauceDemo configuration")
    if not _is_nonempty_string(config.start_path):
        raise DemoConfigValidationError("invalid SauceDemo configuration")
    if (
        type(config.maximum_exploration_steps) is not int
        or config.maximum_exploration_steps < 1
    ):
        raise DemoConfigValidationError("invalid SauceDemo configuration")
    if not _is_string_list(config.allowed_safe_actions):
        raise DemoConfigValidationError("invalid SauceDemo configuration")
    if not _is_string_list(config.blocked_destructive_actions):
        raise DemoConfigValidationError("invalid SauceDemo configuration")
    if not isinstance(config.artifact_output_location, Path):
        raise DemoConfigValidationError("invalid SauceDemo configuration")
    if not isinstance(config.generated_test_output_location, Path):
        raise DemoConfigValidationError("invalid SauceDemo configuration")
    if not _is_credential_mapping(config.credential_environment_variables):
        raise DemoConfigValidationError("invalid SauceDemo configuration")
    if not _is_credential_mapping(config.demo_only_default_credentials):
        raise DemoConfigValidationError("invalid SauceDemo configuration")
    return config


def _is_nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_string_list(value: object) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(_is_nonempty_string(item) for item in value)
    )


def _is_credential_mapping(value: object) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"username", "password"}
        and all(_is_nonempty_string(item) for item in value.values())
    )
