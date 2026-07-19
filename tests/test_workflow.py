"""Tests for the executable workflow skeleton."""

from pmqa.core import PMQAState, RunContext
from pmqa.workflow.graph import build_graph


def test_workflow_executes_and_preserves_state() -> None:
    initial = PMQAState(context=RunContext(run_id="run-1", product="demo"))

    result = build_graph().invoke(initial)

    assert result["context"] == initial.context
    assert result["tasks"] == []
    assert result["artifacts"] == []
    assert result["results"] == []
