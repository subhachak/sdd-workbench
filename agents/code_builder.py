"""
agents/code_builder.py
Step 2: generate implementation from structured spec.
Calls linter after each attempt. Retries up to MAX_ITERATIONS.
Phase 2: becomes a LangGraph node with conditional retry edge.
Phase 4: escalates to human if lint still failing after MAX_ITERATIONS.
"""

import logging
from graph.state import SDDState
from agents import claude_client
from tools.linter import run_linter

logger = logging.getLogger("sdd.code_builder")

MAX_ITERATIONS = 3

_SYSTEM = """You are a senior software engineer.
Write a complete, production-quality implementation from the structured spec.

Respond ONLY with raw code — no markdown, no fences, no explanation.
Start from the first import or function definition.

Rules:
- Complete and runnable — no TODOs, no stubs, no placeholders
- Handle every edge case listed
- Clear variable names that reflect spec terminology
- Brief docstring on main function referencing the spec"""

_RETRY = """The code has lint errors. Return ONLY the corrected code.
No markdown. No explanation. Just the fixed code.

Errors:
{errors}

Code:
{code}"""


async def run(state: SDDState) -> SDDState:
    logger.info(f"Code Builder: iteration {state['iteration_count'] + 1}")

    if not state.get("spec_breakdown"):
        state["status"] = "error"
        state["error_message"] = "Code Builder: spec_breakdown missing — run Spec Analyst first"
        return state

    sb = state["spec_breakdown"]

    def bullet(items): return "\n".join(f"  - {i}" for i in items)

    has_feedback   = bool(state.get("human_feedback"))
    has_lint_error = state["iteration_count"] > 0 and state.get("lint_result")

    if not has_feedback and not has_lint_error:
        user = (
            f"Language: {state['language']}\n\n"
            f"Acceptance Criteria:\n{bullet(sb.get('acceptance_criteria', []))}\n\n"
            f"Edge Cases:\n{bullet(sb.get('edge_cases', []))}\n\n"
            f"Constraints:\n{bullet(sb.get('constraints', []))}\n\n"
            f"Inputs:  {', '.join(sb.get('inputs', []))}\n"
            f"Outputs: {', '.join(sb.get('outputs', []))}"
        )
    else:
        if has_lint_error:
            errors = "\n".join(state["lint_result"]["errors"])
        else:
            errors = ""

        feedback = state.get("human_feedback", "")
        if feedback:
            errors = (errors + f"\n\nReviewer feedback:\n{feedback}") if errors else f"Reviewer feedback:\n{feedback}"

        state["human_feedback"] = None
        user = _RETRY.format(errors=errors, code=state.get("implementation", ""))

    try:
        raw = await claude_client.call(system=_SYSTEM, user=user, max_tokens=4000)
        code = raw.strip()
        if code.startswith("```"):
            code = code.split("\n", 1)[-1]
        if code.endswith("```"):
            code = code.rsplit("```", 1)[0]
        code = code.strip()

        state["implementation"] = code
        state["iteration_count"] += 1

        lint = run_linter(code, state["language"])
        state["lint_result"] = lint
        state["lint_passed"] = lint["passed"]

        if lint["passed"]:
            logger.info(f"Code Builder: lint passed on iteration {state['iteration_count']}")
        else:
            logger.warning(f"Code Builder: lint failed — {len(lint['errors'])} error(s)")

    except Exception as e:
        logger.error(f"Code Builder: {e}")
        state["status"] = "error"
        state["error_message"] = f"Code Builder: {e}"

    return state
