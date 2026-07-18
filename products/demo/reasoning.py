"""Reasoning providers supported by the demo product pack."""

from pmqa.core import Artifact, RunContext, Task
from pmqa.providers import ReasoningProvider


class DeterministicDemoReasoningProvider(ReasoningProvider):
    """Returns a bounded, auditable safe plan without an external AI service."""

    provenance = "deterministic-rule-based"

    def reason(self, task: Task, context: RunContext) -> Artifact:
        """Produce the fixed public-demo plan through the provider contract."""

        return Artifact(
            artifact_id="exploration-plan",
            data={
                "provenance": self.provenance,
                "actions": [
                    "inspect_login_page",
                    "login",
                    "verify_inventory_page",
                    "inspect_inventory_item",
                ],
            },
        )


class ApprovedReasoningProviderAdapter(ReasoningProvider):
    """Marks the approved extension point for a future Copilot integration."""

    def reason(self, task: Task, context: RunContext) -> Artifact:
        """Reject use until an approved integration is supplied."""

        raise NotImplementedError("No approved Copilot reasoning integration is configured")
