"""
graph/state.py
Shared state schema. Every agent reads from and writes to this dict.
Phase 2: passed directly to LangGraph nodes.
"""

from typing import TypedDict, Optional


class SpecBreakdown(TypedDict):
    inputs: list[str]
    outputs: list[str]
    constraints: list[str]
    edge_cases: list[str]
    acceptance_criteria: list[str]
    risks_gaps: list[str]


class DriftItem(TypedDict):
    spec_clause: str
    status: str   # "OK" | "WARN" | "FAIL"
    finding: str


class LintResult(TypedDict):
    passed: bool
    errors: list[str]


class SDDState(TypedDict):
    # Inputs
    spec: str
    language: str
    test_framework: str

    # Spec Analyst
    spec_breakdown: Optional[SpecBreakdown]
    spec_completeness_comment: Optional[str]

    # Code Builder
    implementation: Optional[str]
    lint_result: Optional[LintResult]
    lint_passed: bool
    iteration_count: int

    # Test Writer
    tests: Optional[str]

    # Drift Monitor
    drift_analysis: Optional[list[DriftItem]]

    # Control
    status: str   # "running" | "done" | "error"
    error_message: Optional[str]

    # Phase 4 HITL placeholders
    human_feedback: Optional[str]
    human_approved: bool


def initial_state(spec: str, language: str, test_framework: str) -> SDDState:
    return SDDState(
        spec=spec,
        language=language,
        test_framework=test_framework,
        spec_breakdown=None,
        spec_completeness_comment=None,
        implementation=None,
        lint_result=None,
        lint_passed=False,
        iteration_count=0,
        tests=None,
        drift_analysis=None,
        status="running",
        error_message=None,
        human_feedback=None,
        human_approved=False,
    )
