"""
agents/drift_monitor.py
Step 4: check implementation compliance against every acceptance criterion.
Phase 3: runs continuously, alerts on regressions.
Phase 4: output surfaced at HITL review gate.
"""

import logging
from graph.state import SDDState
from agents import claude_client

logger = logging.getLogger("sdd.drift_monitor")

_SYSTEM = """You are a code reviewer specialising in specification compliance.
For each acceptance criterion, determine whether the implementation satisfies it.

Respond ONLY with valid JSON — no markdown, no fences.

{"drift_analysis": [
  {
    "spec_clause": "exact criterion text",
    "status": "OK",
    "finding": "one sentence: what the code does relative to this criterion"
  }
]}

Status values:
- OK:   criterion is fully implemented — default to this if evidence is present in the code
- WARN: criterion is only partially implemented or implementation is ambiguous
- FAIL: criterion is completely absent from the implementation — only use this if there is NO evidence of the criterion in the code

Rules:
- One entry per criterion — no more, no less
- Findings must be specific — reference actual code behaviour"""


async def run(state: SDDState) -> SDDState:
    logger.info("Drift Monitor: starting")

    if not state.get("implementation"):
        state["status"] = "error"
        state["error_message"] = "Drift Monitor: implementation missing"
        return state

    logger.info(f"Drift Monitor: implementation length = {len(state.get('implementation', ''))}")
    logger.info(f"Drift Monitor: acceptance criteria count = {len(state.get('spec_breakdown', {}).get('acceptance_criteria', []))}")

    sb = state["spec_breakdown"]
    ac_numbered = "\n".join(
        f"  {i+1}. {a}"
        for i, a in enumerate(sb.get("acceptance_criteria", []))
    )

    try:
        raw = await claude_client.call(
            system=_SYSTEM,
            user=f"Acceptance Criteria:\n{ac_numbered}\n\nImplementation:\n{state['implementation']}",
            max_tokens=2000,
        )
        parsed = claude_client.parse_json(raw)
        drift = parsed.get("drift_analysis", [])
        state["drift_analysis"] = drift

        ok   = sum(1 for d in drift if d["status"] == "OK")
        warn = sum(1 for d in drift if d["status"] == "WARN")
        fail = sum(1 for d in drift if d["status"] == "FAIL")
        logger.info(f"Drift Monitor: OK={ok} WARN={warn} FAIL={fail}")

        if state["status"] == "running":
            state["status"] = "done"

    except Exception as e:
        logger.error(f"Drift Monitor: {e}")
        state["status"] = "error"
        state["error_message"] = f"Drift Monitor: {e}"

    return state
