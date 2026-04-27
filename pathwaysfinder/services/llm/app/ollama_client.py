"""Thin Ollama HTTP client.

Ollama exposes an OpenAI-compatible API on /v1/chat/completions, but for
our needs the native /api/chat is simpler and supports the JSON-mode
output format we want for goal parsing. This client wraps both.
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Optional

import httpx

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self, base_url: str, model: str, request_timeout: float = 180.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.request_timeout = request_timeout

    async def health(self) -> bool:
        """Quick reachability check; doesn't require the model to be loaded."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                r = await c.get(f"{self.base_url}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    async def is_model_present(self) -> bool:
        """Check whether our configured model is in Ollama's local registry."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                r = await c.get(f"{self.base_url}/api/tags")
                if r.status_code != 200:
                    return False
                data = r.json()
                names = {m.get("name", "") for m in data.get("models", [])}
                return self.model in names or any(
                    n.startswith(self.model + ":") for n in names
                )
        except Exception:
            return False

    async def pull_model(self) -> None:
        """Trigger a model pull. Streams progress to logs and blocks until done.

        Used at startup if the configured model isn't already present.
        """
        async with httpx.AsyncClient(timeout=None) as c:
            async with c.stream(
                "POST", f"{self.base_url}/api/pull", json={"name": self.model}
            ) as r:
                async for line in r.aiter_lines():
                    if not line:
                        continue
                    try:
                        evt = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    status = evt.get("status")
                    if status:
                        logger.info(f"ollama pull {self.model}: {status}")

    async def chat(
        self,
        messages: list[dict],
        *,
        format_json: bool = False,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        """Call /api/chat. Returns the full Ollama response dict.

        When format_json=True we ask Ollama for JSON-mode output, which
        makes Gemma far more reliable at producing parseable JSON.
        """
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if format_json:
            payload["format"] = "json"

        async with httpx.AsyncClient(timeout=self.request_timeout) as c:
            r = await c.post(f"{self.base_url}/api/chat", json=payload)
            r.raise_for_status()
            return r.json()

    async def chat_stream(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        """Streaming variant of /api/chat.

        Ollama returns NDJSON lines when stream=true. We yield the
        `message.content` token from each line as a plain string. The
        terminating line carries `done: true` and an empty content; we
        stop before yielding it.
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        async with httpx.AsyncClient(timeout=self.request_timeout) as c:
            async with c.stream(
                "POST", f"{self.base_url}/api/chat", json=payload
            ) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line:
                        continue
                    try:
                        evt = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning(f"ollama stream: skipping non-JSON line: {line[:80]}")
                        continue
                    if evt.get("done"):
                        break
                    msg = evt.get("message") or {}
                    content = msg.get("content")
                    if isinstance(content, str) and content:
                        yield content

    @staticmethod
    def extract_content(response: dict) -> Optional[str]:
        """Pull the assistant message content out of an Ollama response."""
        msg = response.get("message") or {}
        content = msg.get("content")
        if isinstance(content, str):
            return content
        return None
