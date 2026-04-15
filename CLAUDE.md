# Brillio SDD Workbench — Claude Code Context

## What this is
Spec-Driven Development tool for Brillio's AI CoE.
Write a plain-language spec → get structured breakdown, implementation,
test suite, and drift analysis. All outputs anchored to the original spec.

This is an **agentic retrofit in progress**: clean modular foundation now,
LangGraph wiring in Phase 2, HITL gates in Phase 4.

## Current state: Phase 1 complete
- Four agent modules, each owning one pipeline step
- Sequential execution from app.py
- LangGraph NOT yet wired
- Frontend: vanilla HTML/CSS/JS, no build step

## Stack
| Layer | Tech |
|-------|------|
| Backend | Python 3.9+, FastAPI, uvicorn |
| AI | Anthropic Claude (claude-sonnet-4-5) |
| Linting tool | pyflakes (Python), tsc (TS), heuristic fallback |
| Frontend | Vanilla HTML in static/index.html |
| Phase 2 | langgraph, langchain-anthropic, SSE streaming |
| Phase 3 | LangGraph SqliteSaver checkpointer |
| Phase 4 | LangGraph interrupt() for HITL gates |

## File map
```
app.py                    # FastAPI routes only — NO business logic
graph/
  state.py                # SDDState TypedDict — the only shared state
agents/
  claude_client.py        # ONLY place that calls Anthropic API
  spec_analyst.py         # Step 1: NL spec → structured breakdown
  code_builder.py         # Step 2: code gen + lint retry loop
  test_writer.py          # Step 3: spec-anchored test suite
  drift_monitor.py        # Step 4: per-criterion compliance check
tools/
  linter.py               # run_linter(code, language) → LintResult
static/
  index.html              # Full frontend — single file, no bundler
```

## Hard rules — do not break these
1. Agent signature: `async def run(state: SDDState) -> SDDState`
   This is what LangGraph node functions expect. Do not change it.
2. Agents communicate only through `state`. No direct agent-to-agent calls.
3. `claude_client.py` is the only file that calls the Anthropic API.
4. `app.py` has no prompt strings and no Claude calls.
5. `static/index.html` is a single file — no build step, no bundler.

## SDDState key fields
- Inputs: `spec`, `language`, `test_framework`
- After spec_analyst: `spec_breakdown`, `spec_completeness_comment`
- After code_builder: `implementation`, `lint_result`, `lint_passed`, `iteration_count`
- After test_writer: `tests`
- After drift_monitor: `drift_analysis`
- Control: `status` ("running"|"done"|"error"), `error_message`
- Phase 4 stubs: `human_feedback`, `human_approved`

## Environment
```
ANTHROPIC_API_KEY=sk-ant-...   # required
PORT=8000                       # optional, default 8000
```
Run: `python app.py` — opens browser automatically.

## What Phase 2 needs
1. `pip install langgraph langchain-anthropic`
2. Create `graph/sdd_graph.py` — StateGraph with 4 nodes
3. Conditional edge on `generate_code`: lint_passed → next, else retry (max 3)
4. Replace `POST /api/run` with `GET /api/run/stream` (StreamingResponse + SSE)
5. Frontend: replace progress stepper with live EventSource log

## Commit style
```
feat:     new capability
fix:      bug fix
refactor: restructure without behaviour change
phase1:   phase 1 milestone
phase2:   phase 2 milestone
```
One agent file per commit where possible.
