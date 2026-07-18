"""Tests for the abstract provider boundaries."""

import inspect

from pmqa.providers import ExecutionProvider, ReasoningProvider, StorageProvider


def test_provider_contracts_are_abstract() -> None:
    assert inspect.isabstract(ReasoningProvider)
    assert inspect.isabstract(ExecutionProvider)
    assert inspect.isabstract(StorageProvider)
