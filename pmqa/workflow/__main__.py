"""Run the PMQA workflow skeleton from the command line."""

from pmqa.core.models import PMQAState, RunContext
from pmqa.workflow.graph import build_graph


def main() -> None:
    """Execute one empty demo-product run."""

    state = PMQAState(context=RunContext(run_id="quick-start", product="demo"))
    build_graph().invoke(state)


if __name__ == "__main__":
    main()
