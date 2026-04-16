# graph/sdd_graph.py
# Phase 2: LangGraph StateGraph wiring for the SDD pipeline.
# Phase 3: SqliteSaver checkpointer for conversation persistence.
#
# Setup (run once):
#   pip install langgraph langchain-anthropic

import asyncio
import aiosqlite
from pathlib import Path

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from graph.state import SDDState
from agents import spec_analyst, code_builder, test_writer, drift_monitor
from agents.code_builder import MAX_ITERATIONS

CHECKPOINTS_DB = "checkpoints/sdd.db"
GATE1_NODE = "parse_spec"
GATE2_NODE = "generate_tests"

Path("checkpoints").mkdir(exist_ok=True)


async def _init_checkpointer() -> AsyncSqliteSaver:
    conn = await aiosqlite.connect(CHECKPOINTS_DB)
    saver = AsyncSqliteSaver(conn)
    await saver.setup()
    return saver


checkpointer = asyncio.run(_init_checkpointer())


# ---------------------------------------------------------------------------
# Node wrappers
# Each agent already satisfies the LangGraph node contract:
#   async def run(state: SDDState) -> SDDState
# ---------------------------------------------------------------------------

def _should_retry(state: SDDState) -> str:
    """Routing function after generate_code.

    Returns:
        "generate_tests"  — lint passed, iteration cap reached, or agent errored
        "generate_code"   — lint failed and retries remain
    """
    if (
        state["lint_passed"]
        or state["iteration_count"] >= MAX_ITERATIONS
        or state.get("status") == "error"
    ):
        return "generate_tests"
    return "generate_code"


# ---------------------------------------------------------------------------
# Graph definition
# ---------------------------------------------------------------------------

_builder = StateGraph(SDDState)

_builder.add_node("parse_spec",     spec_analyst.run)
_builder.add_node("generate_code",  code_builder.run)
_builder.add_node("generate_tests", test_writer.run)
_builder.add_node("run_drift",      drift_monitor.run)

_builder.set_entry_point("parse_spec")

_builder.add_edge("parse_spec", "generate_code")

_builder.add_conditional_edges(
    "generate_code",
    _should_retry,
    {
        "generate_code":  "generate_code",
        "generate_tests": "generate_tests",
    },
)

_builder.add_edge("generate_tests", "run_drift")
_builder.add_edge("run_drift", END)

# Compiled app — import this in app.py and anywhere the graph is invoked.
sdd_app = _builder.compile(
    checkpointer=checkpointer,
    interrupt_after=[GATE1_NODE, GATE2_NODE],
)