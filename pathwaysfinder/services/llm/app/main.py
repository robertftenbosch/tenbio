"""FastAPI app for the LLM service.

Wraps a local Ollama instance running Gemma (default: gemma3:9b; override
via LLM_MODEL env var to e.g. gemma4:9b once available).

Endpoints:
- POST /goal/parse  -> structured DesignIntent JSON
- POST /chat        -> general chat
- GET  /health      -> liveness + model loaded
- GET  /models      -> what's in the local Ollama registry
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from app.ollama_client import OllamaClient
from app.schemas import (
    ChatRequest,
    ChatResponse,
    DesignIntent,
    GoalParseRequest,
    GoalParseResponse,
    HealthResponse,
)
from app.system_prompts import GOAL_PARSER_SYSTEM_PROMPT, build_user_message

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
LLM_MODEL = os.environ.get("LLM_MODEL", "gemma3:9b")
PRELOAD = os.environ.get("LLM_PRELOAD", "false").lower() in {"1", "true", "yes"}


_client = OllamaClient(OLLAMA_URL, LLM_MODEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if PRELOAD:
        try:
            present = await _client.is_model_present()
            if not present:
                logger.info(f"Pulling {LLM_MODEL} from Ollama (first run)...")
                await _client.pull_model()
            else:
                logger.info(f"Model {LLM_MODEL} already present.")
        except Exception as e:
            # Don't crash startup -- the service can still serve /health
            # so docker-compose health checks work, and the user gets a
            # clearer error from /goal/parse.
            logger.warning(f"Model preload failed: {e}")
    yield


app = FastAPI(
    title="Tenbio LLM Service",
    description=(
        "Goal parser and chat backend for the Tenbio synthetic biology "
        "platform. See pathwaysfinder/docs/llm-service-plan.md for "
        "design rationale."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse)
async def health():
    reachable = await _client.health()
    loaded = await _client.is_model_present() if reachable else False
    return HealthResponse(
        status="healthy" if reachable else "degraded",
        model_loaded=loaded,
        model_name=LLM_MODEL,
        ollama_reachable=reachable,
    )


@app.get("/models")
async def list_models():
    """Pass through Ollama's local model registry."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(f"{OLLAMA_URL}/api/tags")
            r.raise_for_status()
            return r.json()
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Ollama not reachable.")


@app.post("/goal/parse", response_model=GoalParseResponse)
async def parse_goal(req: GoalParseRequest):
    """Translate a natural-language goal into a DesignIntent.

    The candidate_kegg_ids and candidate_uniprot_ids in the request are
    the grounding step: the main API has already done a keyword search
    against KEGG/UniProt and only those IDs are presented to the LLM.
    The LLM picks from them rather than inventing.
    """
    user_msg = build_user_message(
        req.query, req.candidate_kegg_ids, req.candidate_uniprot_ids
    )
    messages = [
        {"role": "system", "content": GOAL_PARSER_SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]

    try:
        ollama_response = await _client.chat(
            messages, format_json=True, temperature=0.2, max_tokens=1024
        )
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Ollama call failed: {e}. Is the LLM service up and the model pulled?",
        )

    raw = OllamaClient.extract_content(ollama_response) or ""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=502,
            detail=f"LLM did not return valid JSON: {e}. Raw: {raw[:500]}",
        )

    # The model should always include raw_query, but defensively backfill
    # it in case it forgot.
    data.setdefault("raw_query", req.query)

    try:
        intent = DesignIntent(**data)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"LLM output didn't match DesignIntent schema: {e}. Raw: {raw[:500]}",
        )

    # Strip hallucinated IDs that aren't in the candidate list. This is
    # the second line of defense; the system prompt is the first.
    candidate_kegg = {c["id"] for c in req.candidate_kegg_ids}
    candidate_uniprot = {c["accession"] for c in req.candidate_uniprot_ids}
    if intent.target.kegg_id and candidate_kegg and intent.target.kegg_id not in candidate_kegg:
        logger.warning(
            f"LLM produced KEGG ID '{intent.target.kegg_id}' not in candidates; nulling it."
        )
        intent.target.kegg_id = None
    if (
        intent.target.uniprot_id
        and candidate_uniprot
        and intent.target.uniprot_id not in candidate_uniprot
    ):
        logger.warning(
            f"LLM produced UniProt accession '{intent.target.uniprot_id}' not in candidates; nulling it."
        )
        intent.target.uniprot_id = None

    return GoalParseResponse(intent=intent, model_used=LLM_MODEL, raw_llm_output=raw)


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """General chat endpoint. Currently non-streaming; streaming is a v2 task."""
    messages = [m.model_dump() for m in req.messages]
    try:
        ollama_response = await _client.chat(
            messages,
            format_json=False,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Ollama call failed: {e}")

    content = OllamaClient.extract_content(ollama_response) or ""
    return ChatResponse(content=content, model_used=LLM_MODEL)
