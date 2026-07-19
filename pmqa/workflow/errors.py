"""Errors raised by multi-agent workflow state contracts."""


class WorkflowStateValidationError(ValueError):
    """Reports unsafe or non-serializable workflow state content."""


class AgentContractValidationError(ValueError):
    """Reports an invalid agent request, result, or patch capability."""
