"""HTTP client for the in-stack LLM service (port 8003).

Talks to `services/llm/app/main.py` over the docker network. Mirrors
the pattern of `external_apis/kegg.py` (httpx async, narrow surface).
"""

from __future__ import annotations

import os
from typing import Any

import httpx

LLM_SERVICE_URL = os.environ.get("LLM_SERVICE_URL", "http://localhost:8003")


class LLMServiceError(RuntimeError):
    """Raised when the LLM service is unreachable or returns an error."""


async def parse_goal(
    query: str,
    candidate_kegg_ids: list[dict] | None = None,
    candidate_uniprot_ids: list[dict] | None = None,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """Call POST /goal/parse and return the parsed response dict.

    The candidate_* lists are pre-fetched grounding context. The LLM
    service further validates that any IDs in the output appear in
    these lists; this function does not do that validation again.
    """
    payload = {
        "query": query,
        "candidate_kegg_ids": candidate_kegg_ids or [],
        "candidate_uniprot_ids": candidate_uniprot_ids or [],
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.post(f"{LLM_SERVICE_URL}/goal/parse", json=payload)
    except httpx.ConnectError as e:
        raise LLMServiceError(f"LLM service unreachable: {e}") from e

    if r.status_code != 200:
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        raise LLMServiceError(f"LLM service error ({r.status_code}): {detail}")
    return r.json()


async def health() -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(f"{LLM_SERVICE_URL}/health")
            return r.json() if r.status_code == 200 else {"status": "degraded"}
    except Exception:
        return {"status": "unreachable"}
