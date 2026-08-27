"""LLM providers — the swappable backend behind the generation pipeline.

Every provider implements the same narrow interface:

    class LLMProvider(Protocol):
        async def generate(self, prompt: str) -> str: ...

(async rather than the sync form in the spec, since this is an async
FastAPI app throughout — a blocking network call here would stall the
event loop). Callers depend only on this shape, never on a concrete
provider — swapping Ollama for Anthropic, or adding OpenAI/Groq later,
touches this file only. Nothing in the retrieval, fusion, or citation
pipeline changes.
"""

import importlib.util
import os
from typing import Protocol

from app.core.logging import get_logger

logger = get_logger(__name__)


class LLMProvider(Protocol):
    """The single contract every backend must satisfy."""

    model_name: str

    async def generate(self, prompt: str) -> str: ...


class OllamaProvider:
    """Local inference via Ollama — the module's starting/default provider.

    Talks to Ollama's REST API (``POST /api/generate``); works with any
    pulled model (Llama, Gemma, Mistral, ...). No API key required.
    """

    def __init__(self, base_url: str, model: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self.model_name = model
        self._timeout = timeout_seconds

    async def generate(self, prompt: str) -> str:
        import httpx

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/api/generate",
                json={"model": self.model_name, "prompt": prompt, "stream": False},
            )
            response.raise_for_status()
            return response.json().get("response", "").strip()


class AnthropicProvider:
    """Claude via the official Anthropic SDK.

    The prompt constructor has already embedded the system instructions
    and retrieved context into a single string, so the whole thing is
    sent as one user message — keeping this provider as narrow as the
    interface it implements.
    """

    def __init__(self, model: str, max_tokens: int) -> None:
        self.model_name = model
        self._max_tokens = max_tokens
        self._client = None

    def _get_client(self):
        if self._client is None:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic()
        return self._client

    async def generate(self, prompt: str) -> str:
        client = self._get_client()
        response = await client.beta.messages.create(
            model=self.model_name,
            max_tokens=self._max_tokens,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": prompt}],
        )

        if response.stop_reason == "refusal":
            logger.warning("llm_refusal", model=response.model)
            return (
                "The language model declined to answer this question. "
                "Please rephrase or contact an administrator."
            )
        return "".join(
            block.text for block in response.content if block.type == "text"
        ).strip()


def ollama_configured() -> bool:
    """Cheap, local check — package present, no network probe.

    Actual reachability is verified by the real request; a dead Ollama
    server surfaces as a connection error at generate() time, handled by
    the orchestrator's fallback (see generator.py).
    """
    return importlib.util.find_spec("httpx") is not None


def anthropic_available() -> bool:
    if importlib.util.find_spec("anthropic") is None:
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
