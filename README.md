# SDD Workbench

Spec-Driven Development tool · Brillio AI CoE

Write a plain-language spec. Get a structured breakdown, implementation,
test suite, and drift analysis — all anchored to the original spec.

## Setup

```bash
git clone <repo>
cd sdd-workbench
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then add your Anthropic API key
python app.py               # opens http://localhost:8000
```

## Structure

```
app.py          FastAPI routes only
graph/          Shared SDDState schema
agents/         One file per pipeline step
tools/          Linter tool
static/         Frontend (vanilla HTML, no build step)
CLAUDE.md       Context file for Claude Code / Cursor
```

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| 1 | ✅ Done | Modular agents, lint retry, clean state schema |
| 2 | Next | LangGraph graph, SSE streaming, live UI |
| 3 | Planned | Observability, run history, token tracking |
| 4 | Planned | HITL gates, human-agent pod demo |
