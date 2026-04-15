"""
agents/spec_analyst.py
Step 1: parse natural language spec → structured breakdown.
Phase 4: interrupt() added here for human spec review gate.
"""

import logging
from graph.state import SDDState
from agents import claude_client

logger = logging.getLogger("sdd.spec_analyst")

_SYSTEM = """You are a senior software architect specialising in requirements analysis.
Parse the spec into a structured breakdown.

Respond ONLY with valid JSON — no markdown, no fences, no preamble.

{
  "spec_breakdown": {
    "inputs":               ["each distinct input parameter"],
    "outputs":              ["each distinct return value or side effect"],
    "constraints":          ["rules and invariants that must hold"],
    "edge_cases":           ["boundary conditions and exceptional inputs"],
    "acceptance_criteria":  ["testable: given X, when Y, then Z"],
    "risks_gaps":           ["ambiguities or missing information"]
  },
  "spec_completeness_comment": "2-3 sentences on quality and most critical gap"
}

Rules:
- acceptance_criteria must be concrete and independently testable
- do NOT invent requirements not present in the spec"""


async def run(state: SDDState) -> SDDState:
    logger.info("Spec Analyst: starting")
    try:
        raw = await claude_client.call(
            system=_SYSTEM,
            user=f"SPEC:\n{state['spec']}\n\nLanguage context: {state['language']}",
            max_tokens=2000,
        )
        parsed = claude_client.parse_json(raw)
        state["spec_breakdown"] = parsed["spec_breakdown"]
        state["spec_completeness_comment"] = parsed.get("spec_completeness_comment", "")
        n = len(state["spec_breakdown"].get("acceptance_criteria", []))
        logger.info(f"Spec Analyst: done — {n} acceptance criteria")
    except Exception as e:
        logger.error(f"Spec Analyst: {e}")
        state["status"] = "error"
        state["error_message"] = f"Spec Analyst: {e}"
    return state
