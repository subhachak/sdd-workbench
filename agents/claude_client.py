"""
agents/claude_client.py
Single place that touches the Anthropic API.
All agents import from here — never call httpx directly.
"""

import os
import json
import logging
import httpx

logger = logging.getLogger("sdd.claude")

API_URL = "https://api.anthropic.com/v1/messages"
MODEL   = "claude-sonnet-4-5"


def _key() -> str:
    k = os.getenv("ANTHROPIC_API_KEY", "")
    if not k:
        raise RuntimeError("ANTHROPIC_API_KEY not set in .env")
    return k


async def call(system: str, user: str, max_tokens: int = 2000) -> str:
    """Single Claude call. Returns raw text. Raises RuntimeError on failure."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            API_URL,
            headers={
                "x-api-key": _key(),
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": MODEL,
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
        )

    if r.status_code != 200:
        raise RuntimeError(f"Anthropic {r.status_code}: {r.text[:300]}")

    data = r.json()
    if data.get("stop_reason") == "max_tokens":
        raise RuntimeError("Response truncated — reduce spec complexity or raise max_tokens")

    text = next((b["text"] for b in data.get("content", []) if b.get("type") == "text"), "")
    logger.info(f"Claude → {len(text)} chars  stop={data.get('stop_reason')}")
    return text


def parse_json(raw: str) -> dict:
    """Strip markdown fences and parse JSON. Raises ValueError on failure."""
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[-1]
    if s.endswith("```"):
        s = s.rsplit("```", 1)[0]
    s = s.strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        start, end = s.find("{"), s.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(s[start:end])
        raise ValueError(f"Cannot parse JSON. Preview: {s[:200]}")
