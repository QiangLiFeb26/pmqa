"""Errors raised by deterministic supervisor policy evaluation."""


class SupervisorPolicyError(ValueError):
    """Reports workflow state that cannot be routed safely."""
