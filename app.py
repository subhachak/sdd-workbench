"""
app.py — FastAPI routes only. No business logic, no prompts.
Phase 1: sequential agent calls.
Phase 2: replace /api/run with /api/run/stream (SSE + LangGraph).
"""

import os
import json
import uuid
import sqlite3
import webbrowser
import threading
import logging
from pathlib import Path
from typing import AsyncGenerator
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from graph.state import initial_state
from agents import spec_analyst, code_builder, test_writer, drift_monitor
from agents.code_builder import MAX_ITERATIONS
from graph.sdd_graph import sdd_app, CHECKPOINTS_DB

load_dotenv()
logging.basicConfig(level=logging.INFO, format="  %(levelname)s  %(message)s")
logger = logging.getLogger("sdd.app")

app = FastAPI(title="Brillio SDD Workbench")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


class SDDRequest(BaseModel):
    spec: str
    language: str = "Python"
    test_framework: str = "pytest"


@app.get("/")
def index():
    return FileResponse(static_dir / "index.html")


@app.get("/health")
def health():
    return {"status": "ok", "api_key_configured": bool(os.getenv("ANTHROPIC_API_KEY"))}


@app.post("/api/run")
async def run_sdd(req: SDDRequest):
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(500, "ANTHROPIC_API_KEY not set — add to .env and restart")

    logger.info(f"Pipeline start  lang={req.language}  framework={req.test_framework}  spec={len(req.spec)}chars")

    state = initial_state(req.spec, req.language, req.test_framework)

    # Step 1: Spec Analyst
    state = await spec_analyst.run(state)
    if state["status"] == "error":
        raise HTTPException(500, state["error_message"])

    # Step 2: Code Builder with lint retry
    for _ in range(MAX_ITERATIONS):
        state = await code_builder.run(state)
        if state["status"] == "error":
            raise HTTPException(500, state["error_message"])
        if state["lint_passed"]:
            break
    if not state["lint_passed"]:
        logger.warning(f"Lint still failing after {MAX_ITERATIONS} iterations — proceeding")

    # Step 3: Test Writer
    state = await test_writer.run(state)
    if state["status"] == "error":
        raise HTTPException(500, state["error_message"])

    # Step 4: Drift Monitor
    state = await drift_monitor.run(state)
    if state["status"] == "error":
        raise HTTPException(500, state["error_message"])

    logger.info(f"Pipeline done  iterations={state['iteration_count']}  lint_passed={state['lint_passed']}")

    return {
        "spec_breakdown":            state["spec_breakdown"],
        "spec_completeness_comment": state["spec_completeness_comment"],
        "implementation":            state["implementation"],
        "tests":                     state["tests"],
        "drift_analysis":            state["drift_analysis"],
        "_meta": {
            "iterations":   state["iteration_count"],
            "lint_passed":  state["lint_passed"],
            "lint_errors":  state["lint_result"]["errors"] if state.get("lint_result") else [],
        },
    }


def _node_payload(node: str, state: dict) -> dict:
    """Extract the relevant state fields for a given node's SSE payload."""
    if node == "parse_spec":
        return {
            "spec_breakdown":            state.get("spec_breakdown"),
            "spec_completeness_comment": state.get("spec_completeness_comment"),
        }
    if node == "generate_code":
        lr = state.get("lint_result") or {}
        return {
            "lint_passed":     state.get("lint_passed"),
            "iteration_count": state.get("iteration_count"),
            "lint_errors":     lr.get("errors", []),
        }
    if node == "generate_tests":
        tests = state.get("tests") or ""
        return {"tests_length": len(tests)}
    if node == "run_drift":
        return {"drift_analysis": state.get("drift_analysis")}
    return {}


async def _stream_sdd(spec: str, language: str, test_framework: str, thread_id: str) -> AsyncGenerator[str, None]:
    def sse(payload: dict) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    try:
        state = initial_state(spec, language, test_framework)
        latest_state: dict = {}
        config = {"configurable": {"thread_id": thread_id}}

        async for event in sdd_app.astream_events(state, config=config, version="v2"):
            if event["event"] != "on_chain_end":
                continue

            node = event.get("name")
            if node not in ("parse_spec", "generate_code", "generate_tests", "run_drift"):
                continue

            output = event.get("data", {}).get("output") or {}
            latest_state = output

            status = "error" if output.get("status") == "error" else "ok"
            yield sse({
                "type":   "node_done",
                "node":   node,
                "status": status,
                "data":   _node_payload(node, output),
            })

            if status == "error":
                yield sse({"type": "error", "message": output.get("error_message", "unknown error")})
                return

        lr = latest_state.get("lint_result") or {}
        yield sse({
            "type": "done",
            "thread_id": thread_id,
            "data": {
                "spec_breakdown":            latest_state.get("spec_breakdown"),
                "spec_completeness_comment": latest_state.get("spec_completeness_comment"),
                "implementation":            latest_state.get("implementation"),
                "tests":                     latest_state.get("tests"),
                "drift_analysis":            latest_state.get("drift_analysis"),
                "_meta": {
                    "iterations":  latest_state.get("iteration_count"),
                    "lint_passed": latest_state.get("lint_passed"),
                    "lint_errors": lr.get("errors", []),
                },
            },
        })

    except Exception as exc:
        logger.exception("Stream error")
        yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"


@app.get("/api/run/stream")
async def run_sdd_stream(
    spec:           str = Query(...),
    language:       str = Query("Python"),
    test_framework: str = Query("pytest"),
):
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(500, "ANTHROPIC_API_KEY not set — add to .env and restart")

    thread_id = str(uuid.uuid4())
    logger.info(f"Stream start  thread={thread_id}  lang={language}  framework={test_framework}  spec={len(spec)}chars")

    return StreamingResponse(
        _stream_sdd(spec, language, test_framework, thread_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/runs")
def list_runs():
    try:
        conn = sqlite3.connect(CHECKPOINTS_DB)
        rows = conn.execute(
            "SELECT DISTINCT thread_id, created_at FROM checkpoints "
            "ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
        conn.close()
        return [{"thread_id": r[0], "created_at": r[1]} for r in rows]
    except Exception as exc:
        raise HTTPException(500, f"Could not query checkpoints: {exc}")


def _open_browser():
    import time; time.sleep(1.2)
    webbrowser.open(f"http://localhost:{os.getenv('PORT', '8000')}")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    key  = os.getenv("ANTHROPIC_API_KEY", "")

    print(f"\n  Brillio SDD Workbench  →  http://localhost:{port}")
    print(f"  API key: {'✓ loaded' if key else '✗ NOT SET — edit .env'}\n")

    threading.Thread(target=_open_browser, daemon=True).start()
    try:
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    except OSError:
        print(f"  Port {port} in use — try: PORT=8001 python app.py")
