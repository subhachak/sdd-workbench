"""
agents/test_writer.py
Step 3: generate spec-anchored test suite.
Every test maps explicitly to an acceptance criterion.
"""

import logging
from graph.state import SDDState
from agents import claude_client

logger = logging.getLogger("sdd.test_writer")

_SYSTEM = """You are a senior QA engineer.
Write a complete test suite. Every test must be anchored to an acceptance criterion.

Respond ONLY with raw test code — no markdown, no fences, no explanation.

Rules:
- Every acceptance criterion needs at least one test
- Each test function has a comment: # AC: <criterion text>
- Test name pattern: test_<what>_<condition>_<expected>
- Cover happy paths AND all listed edge cases
- Self-contained — no external state dependencies
- Python/pytest: plain assert statements
- TypeScript/Jest: describe/it blocks"""


async def run(state: SDDState) -> SDDState:
    logger.info("Test Writer: starting")

    if not state.get("implementation"):
        state["status"] = "error"
        state["error_message"] = "Test Writer: implementation missing"
        return state

    sb = state["spec_breakdown"]
    ac_list = "\n".join(f"  - {a}" for a in sb.get("acceptance_criteria", []))
    edge_list = "\n".join(f"  - {e}" for e in sb.get("edge_cases", []))

    try:
        raw = await claude_client.call(
            system=_SYSTEM,
            user=(
                f"Framework: {state['test_framework']}\n"
                f"Language: {state['language']}\n\n"
                f"Acceptance Criteria:\n{ac_list}\n\n"
                f"Edge Cases:\n{edge_list}\n\n"
                f"Implementation:\n{state['implementation']}"
            ),
            max_tokens=8000,
        )
        tests = raw.strip()
        if tests.startswith("```"):
            tests = tests.split("\n", 1)[-1]
        if tests.endswith("```"):
            tests = tests.rsplit("```", 1)[0]
        state["tests"] = tests.strip()

        n = tests.count("def test_") + tests.count("it(") + tests.count("it('") + tests.count('it("')
        logger.info(f"Test Writer: done — {n} test functions")
    except Exception as e:
        logger.error(f"Test Writer: {e}")
        state["status"] = "error"
        state["error_message"] = f"Test Writer: {e}"

    return state
