"""Explain why the workflow contract package is not directly executable."""

import sys


def main() -> int:
    """Reject the retired Task 1 demo without constructing fake dependencies."""

    print(
        "The Task 1 workflow demo has been retired.\n"
        "The active workflow assembly is pmqa.orchestration.build_pmqa_graph, "
        "which requires explicit Explorer, Knowledge, Validator, and "
        "ToolRegistry dependencies.\n"
        "Task 5 will provide real domain agents and tools.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
