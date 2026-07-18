"""Deterministic reasoning used by the SauceDemo product pack."""

from pmqa.reasoning import ReasoningProvider, ReasoningRequest, ReasoningResponse, ReasoningStatus


class DeterministicDemoReasoningProvider(ReasoningProvider):
    """Returns the bounded SauceDemo plan through the canonical contract."""

    provider_name = "deterministic-rule-based"
    model_name = "saucedemo-safe-plan-v1"

    def _reason(self, request: ReasoningRequest) -> ReasoningResponse:
        """Produce a fixed safe plan for the public demo product pack."""

        actions = [
            "inspect_login_page",
            "login",
            "verify_inventory_page",
            "inspect_inventory_item",
        ]
        return ReasoningResponse(
            request_id=request.request_id,
            provider=self.provider_name,
            model=self.model_name,
            status=ReasoningStatus.COMPLETED,
            decisions=[{"decision_type": "action", "action": action} for action in actions],
            confidence=1.0,
            metadata={"mode": "offline"},
        )
