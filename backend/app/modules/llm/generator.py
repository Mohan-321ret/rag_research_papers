"""Enterprise LLM generation pipeline (Module 8).

    Prompt Constructor
           |
    System Prompt + User Query + Retrieved Context
           |
          LLM  (any LLMProvider — Ollama, Anthropic, ...)
           |
    Citation Generator
           |
      Initial Answer

Two ``AnswerGenerator`` implementations:

- ``LLMAnswerGenerator`` — wraps any ``LLMProvider`` (see
  ``app.modules.llm.providers``) with the constructor and citation
  stages. If the provider call fails (e.g. Ollama isn't running), it
  degrades to the extractive baseline for that response instead of
  failing the request — the same graceful-degradation philosophy used
  throughout this codebase (embedding stack, reranker, graph store).
- ``ExtractiveAnswerGenerator`` — a deterministic, LLM-free baseline
  that composes an answer from the top retrieved chunks. Needs no
  external service, so the system is always demoable, and it doubles as
  the paper's no-LLM ablation baseline.
"""

import dataclasses
import re
from dataclasses import dataclass, field

from app.core.config import Settings
from app.core.exceptions import ServiceUnavailableError
from app.core.logging import get_logger
from app.modules.context_fusion.builder import ContextBlock, build_context_text
from app.modules.llm.citation_generator import extract_citations
from app.modules.llm.prompt_constructor import build_prompt
from app.modules.llm.providers import (
    AnthropicProvider,
    LLMProvider,
    OllamaProvider,
    anthropic_available,
    ollama_configured,
)

logger = get_logger(__name__)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

__all__ = [
    "ContextBlock",
    "ExtractiveAnswerGenerator",
    "GenerationOutput",
    "LLMAnswerGenerator",
    "NO_CONTEXT_ANSWER",
    "build_answer_generator",
]


@dataclass(frozen=True, slots=True)
class GenerationOutput:
    """The pipeline's "Initial Answer": text plus which sources it cites.

    ``input_tokens``/``output_tokens`` are not populated for LLM
    providers — the narrow ``LLMProvider.generate(prompt) -> str``
    interface deliberately carries no usage metadata, so any backend can
    implement it uniformly.
    """

    text: str
    model: str
    cited_markers: list[int] = field(default_factory=list)
    invalid_markers: list[int] = field(default_factory=list)
    used_fallback: bool = False  # True when the model produced no [n] markers
    input_tokens: int | None = None
    output_tokens: int | None = None


NO_CONTEXT_ANSWER = (
    "I could not find relevant information in the knowledge base to answer "
    "this question. Try uploading related documents first."
)


class ExtractiveAnswerGenerator:
    """Deterministic baseline: extract leading sentences from top chunks."""

    model_name = "extractive-baseline"

    async def generate(
        self, query: str, blocks: list[ContextBlock]
    ) -> GenerationOutput:
        if not blocks:
            return GenerationOutput(text=NO_CONTEXT_ANSWER, model=self.model_name)

        parts: list[str] = []
        for block in blocks[:3]:
            sentences = _SENTENCE_SPLIT.split(block.content.strip())
            # Mark each excerpted sentence individually (not once for the
            # whole excerpt) so downstream claim-level verification (Module
            # 9) can attribute each sentence to its source.
            excerpt_sentences = [s.strip() for s in sentences[:2] if s.strip()]
            if excerpt_sentences:
                parts.append(" ".join(f"{s} [{block.index}]" for s in excerpt_sentences))
        # No preamble ("Based on the retrieved documents: ...") — a plain
        # excerpt keeps every sentence a clean, independently verifiable
        # claim for Module 9, and reads naturally either way.
        text = " ".join(parts) if parts else NO_CONTEXT_ANSWER

        citations = extract_citations(text, blocks)
        return GenerationOutput(
            text=text,
            model=self.model_name,
            cited_markers=citations.cited_markers,
            invalid_markers=citations.invalid_markers,
            used_fallback=citations.used_fallback,
        )


class LLMAnswerGenerator:
    """Prompt Constructor -> LLMProvider -> Citation Generator."""

    def __init__(self, provider: LLMProvider, fallback: ExtractiveAnswerGenerator) -> None:
        self.provider = provider
        self.fallback = fallback

    async def generate(
        self, query: str, blocks: list[ContextBlock]
    ) -> GenerationOutput:
        if not blocks:
            return GenerationOutput(text=NO_CONTEXT_ANSWER, model=self.provider.model_name)

        prompt = build_prompt(query, build_context_text(blocks))
        try:
            text = await self.provider.generate(prompt)
        except Exception as exc:
            logger.warning(
                "llm_provider_unavailable",
                provider=self.provider.model_name,
                error=type(exc).__name__,
            )
            fallback_result = await self.fallback.generate(query, blocks)
            return dataclasses.replace(
                fallback_result,
                model=f"{self.provider.model_name} (unavailable, used {fallback_result.model})",
            )

        if not text:
            return GenerationOutput(text=NO_CONTEXT_ANSWER, model=self.provider.model_name)

        citations = extract_citations(text, blocks)
        return GenerationOutput(
            text=text,
            model=self.provider.model_name,
            cited_markers=citations.cited_markers,
            invalid_markers=citations.invalid_markers,
            used_fallback=citations.used_fallback,
        )


def build_answer_generator(settings: Settings) -> ExtractiveAnswerGenerator | LLMAnswerGenerator:
    """Pick the generator per LLM_PROVIDER.

    "auto" prefers Anthropic when credentials are configured (backward
    compatible with earlier phases); otherwise Ollama — the
    zero-credential local default this module starts with.
    """
    provider = settings.llm_provider
    fallback = ExtractiveAnswerGenerator()

    if provider == "extractive":
        return fallback

    if provider == "anthropic":
        if not anthropic_available():
            raise ServiceUnavailableError(
                "LLM provider 'anthropic' selected but the anthropic package or "
                "credentials (ANTHROPIC_API_KEY) are not configured"
            )
        return LLMAnswerGenerator(
            AnthropicProvider(settings.llm_model, settings.llm_max_tokens), fallback
        )

    if provider == "ollama":
        if not ollama_configured():
            raise ServiceUnavailableError(
                "LLM provider 'ollama' selected but the required HTTP client "
                "is not available"
            )
        return LLMAnswerGenerator(
            OllamaProvider(
                settings.ollama_base_url, settings.ollama_model, settings.ollama_timeout_seconds
            ),
            fallback,
        )

    # auto
    if anthropic_available():
        return LLMAnswerGenerator(
            AnthropicProvider(settings.llm_model, settings.llm_max_tokens), fallback
        )
    if ollama_configured():
        return LLMAnswerGenerator(
            OllamaProvider(
                settings.ollama_base_url, settings.ollama_model, settings.ollama_timeout_seconds
            ),
            fallback,
        )
    return fallback
