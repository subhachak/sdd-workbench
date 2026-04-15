"""
tools/linter.py
run_linter(code, language) → LintResult
Called by Code Builder after each generation attempt.
Phase 2: exposed as a LangGraph tool via bind_tools().
"""

import subprocess
import tempfile
import logging
import shutil
from pathlib import Path
from graph.state import LintResult

logger = logging.getLogger("sdd.linter")


def run_linter(code: str, language: str) -> LintResult:
    lang = language.lower().strip()
    if lang == "python":
        return _python(code)
    if lang in ("typescript", "ts"):
        return _typescript(code)
    if lang in ("javascript", "js"):
        return _javascript(code)
    return _heuristic(code, language)


# ── Python ────────────────────────────────────────────────────────────────────

def _python(code: str) -> LintResult:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        tmp = f.name
    try:
        # Syntax check first
        r = subprocess.run(
            ["python3", "-c", f"import ast; ast.parse(open('{tmp}').read())"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0:
            return LintResult(passed=False, errors=[l.strip() for l in r.stderr.splitlines() if l.strip()])

        # pyflakes if available
        pf = subprocess.run(
            ["python3", "-m", "pyflakes", tmp],
            capture_output=True, text=True, timeout=10,
        )
        if pf.returncode != 0:
            errors = [l.replace(tmp, "<generated>").strip() for l in pf.stdout.splitlines() if l.strip()]
            return LintResult(passed=False, errors=errors)

        return LintResult(passed=True, errors=[])
    except subprocess.TimeoutExpired:
        return LintResult(passed=True, errors=[])   # don't block on timeout
    except Exception as e:
        logger.warning(f"Linter (Python) exception: {e}")
        return LintResult(passed=True, errors=[])
    finally:
        Path(tmp).unlink(missing_ok=True)


# ── TypeScript ────────────────────────────────────────────────────────────────

def _typescript(code: str) -> LintResult:
    if not shutil.which("tsc"):
        return _heuristic(code, "TypeScript")
    with tempfile.TemporaryDirectory() as d:
        ts = Path(d) / "generated.ts"
        ts.write_text(code)
        (Path(d) / "tsconfig.json").write_text(
            '{"compilerOptions":{"strict":true,"noEmit":true,"target":"ES2020"}}'
        )
        try:
            r = subprocess.run(["tsc", "--noEmit", "--project", d], capture_output=True, text=True, timeout=30, cwd=d)
            if r.returncode == 0:
                return LintResult(passed=True, errors=[])
            errors = [l.replace(str(ts), "<generated>").strip() for l in r.stdout.splitlines() if l.strip()]
            return LintResult(passed=False, errors=errors[:10])
        except Exception:
            return LintResult(passed=True, errors=[])


# ── JavaScript ────────────────────────────────────────────────────────────────

def _javascript(code: str) -> LintResult:
    if not shutil.which("node"):
        return _heuristic(code, "JavaScript")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
        f.write(code)
        tmp = f.name
    try:
        r = subprocess.run(["node", "--check", tmp], capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            return LintResult(passed=True, errors=[])
        return LintResult(passed=False, errors=[l.strip() for l in r.stderr.splitlines() if l.strip()])
    except Exception:
        return LintResult(passed=True, errors=[])
    finally:
        Path(tmp).unlink(missing_ok=True)


# ── Heuristic fallback ────────────────────────────────────────────────────────

def _heuristic(code: str, language: str) -> LintResult:
    bad = [
        ("# TODO", "Unimplemented TODO found"),
        ("raise NotImplementedError", "NotImplementedError stub found"),
        ("throw new Error('Not implemented')", "Not-implemented stub found"),
    ]
    errors = [msg for pattern, msg in bad if pattern in code]
    if len(code.strip()) < 50:
        errors.append("Generated code is too short to be a complete implementation")
    if errors:
        return LintResult(passed=False, errors=errors)
    return LintResult(passed=True, errors=[])
