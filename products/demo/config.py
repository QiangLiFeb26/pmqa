"""Loading and validation for the SauceDemo product pack."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


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
