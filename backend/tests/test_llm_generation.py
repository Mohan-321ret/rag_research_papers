"""Tests for the enterprise LLM generation pipeline (Module 8):
Prompt Constructor -> LLMProvider -> Citation Generator -> Initial Answer.
"""

import asyncio

import pytest

from app.core.exceptions import ServiceUnavailableError
from app.modules.context_fusion.builder import ContextBlock
from app.modules.llm.citation_generator import extract_citations
from app.modules.llm.generator import (
    NO_CONTEXT_ANSWER,
    ExtractiveAnswerGenerator,
    LLMAnswerGenerator,
    build_answer_generator,
)
from app.modules.llm.prompt_constructor import DEFAULT_SYSTEM_PROMPT, build_prompt
from app.modules.llm.providers import AnthropicProvider, OllamaProvider


def _block(index: int, content: str = "Some content.", **overrides) -> ContextBlock:
    defaults = dict(
        document_title="Employee Policy",
        version_number=1,
        page_number=1,
        section=None,
        content=content,
    )
    defaults.update(overrides)
    return ContextBlock(index=index, **defaults)


# ---- Prompt Constructor -----------------------------------------------


def test_prompt_constructor_combines_system_context_and_query() -> None:
    prompt = build_prompt("What is the leave policy?", "SOURCE 1\n...")
    assert DEFAULT_SYSTEM_PROMPT in prompt
    assert "SOURCE 1" in prompt
    assert "Question: What is the leave policy?" in prompt
    # System prompt must precede context, which must precede the question.
    assert prompt.index(DEFAULT_SYSTEM_PROMPT) < prompt.index("SOURCE 1")
    assert prompt.index("SOURCE 1") < prompt.index("Question:")


def test_prompt_constructor_custom_system_prompt() -> None:
    prompt = build_prompt("q", "ctx", system_prompt="Custom instructions.")
    assert "Custom instructions." in prompt
    assert DEFAULT_SYSTEM_PROMPT not in prompt


def test_prompt_constructor_empty_context_omits_blank_section() -> None:
    prompt = build_prompt("q", "")
    assert "Question: q" in prompt
    # No dangling blank line where the context section would have been.
    assert "\n\n\n" not in prompt


# ---- Citation Generator -------------------------------------------------


def test_extract_citations_finds_valid_markers_in_order() -> None:
    blocks = [_block(1), _block(2), _block(3)]
    result = extract_citations("Fact A [2]. Fact B [1]. Fact C [2].", blocks)
    assert result.cited_markers == [2, 1]  # first-appearance order, deduped
    assert result.invalid_markers == []
    assert result.used_fallback is False


def test_extract_citations_flags_hallucinated_markers() -> None:
    blocks = [_block(1), _block(2)]
    result = extract_citations("Answer cites [1] and also [99].", blocks)
    assert result.cited_markers == [1]
    assert result.invalid_markers == [99]


def test_extract_citations_falls_back_to_all_sources_when_none_cited() -> None:
    blocks = [_block(1), _block(2), _block(3)]
    result = extract_citations("A plain answer with no markers at all.", blocks)
    assert result.cited_markers == [1, 2, 3]
    assert result.used_fallback is True


def test_extract_citations_no_sources_no_markers() -> None:
    result = extract_citations("No context was available.", [])
    assert result.cited_markers == []
    assert result.used_fallback is True  # vacuously "no markers found"


def test_extract_citations_dedupes_repeated_marker() -> None:
    blocks = [_block(1)]
    result = extract_citations("Cited here [1] and again [1].", blocks)
    assert result.cited_markers == [1]


# ---- ExtractiveAnswerGenerator ------------------------------------------


def test_extractive_generator_no_context() -> None:
    async def scenario() -> None:
        result = await ExtractiveAnswerGenerator().generate("q", [])
        assert result.text == NO_CONTEXT_ANSWER
        assert result.cited_markers == []

    asyncio.run(scenario())


def test_extractive_generator_caps_citations_at_three() -> None:
    """The extractive baseline only excerpts the first 3 blocks, so its
    citations must never exceed 3 — even when 5 were offered. This is
    the concrete case where Module 8's citation generator narrows the
    final citation list below what Module 7 handed to the LLM."""

    async def scenario() -> None:
        blocks = [_block(i, content=f"Distinct fact number {i}.") for i in range(1, 6)]
        result = await ExtractiveAnswerGenerator().generate("q", blocks)
        assert len(result.cited_markers) <= 3
        assert result.cited_markers == sorted(result.cited_markers)
        assert result.used_fallback is False
        for marker in result.cited_markers:
            assert f"[{marker}]" in result.text

    asyncio.run(scenario())


# ---- LLMAnswerGenerator (fake provider) ---------------------------------


class _FakeProvider:
    """Minimal LLMProvider stand-in: satisfies the Protocol duck-typed."""

    def __init__(self, response: str | None = None, error: Exception | None = None) -> None:
        self.model_name = "fake-model"
        self._response = response
        self._error = error
        self.received_prompt: str | None = None

    async def generate(self, prompt: str) -> str:
        self.received_prompt = prompt
        if self._error is not None:
            raise self._error
        return self._response or ""


def test_llm_answer_generator_happy_path_extracts_citations() -> None:
    async def scenario() -> None:
        provider = _FakeProvider(response="Leave is 25 days [1].")
        generator = LLMAnswerGenerator(provider, ExtractiveAnswerGenerator())
        blocks = [_block(1, content="Employees get 25 days of leave.")]

        result = await generator.generate("How many leave days?", blocks)

        assert result.text == "Leave is 25 days [1]."
        assert result.model == "fake-model"
        assert result.cited_markers == [1]
        assert provider.received_prompt is not None
        assert "How many leave days?" in provider.received_prompt

    asyncio.run(scenario())


def test_llm_answer_generator_no_context_never_calls_provider() -> None:
    async def scenario() -> None:
        provider = _FakeProvider(response="should not be used")
        generator = LLMAnswerGenerator(provider, ExtractiveAnswerGenerator())

        result = await generator.generate("q", [])

        assert result.text == NO_CONTEXT_ANSWER
        assert provider.received_prompt is None  # provider never invoked

    asyncio.run(scenario())


def test_llm_answer_generator_falls_back_on_provider_failure() -> None:
    """A dead/unreachable provider (e.g. Ollama not running) degrades to
    the extractive baseline instead of failing the whole request."""

    async def scenario() -> None:
        provider = _FakeProvider(error=ConnectionError("connection refused"))
        generator = LLMAnswerGenerator(provider, ExtractiveAnswerGenerator())
        blocks = [_block(1, content="Fallback content sentence one. Sentence two.")]

        result = await generator.generate("q", blocks)

        assert result.text != NO_CONTEXT_ANSWER
        assert "[1]" in result.text
        assert "fake-model" in result.model
        assert "unavailable" in result.model
        assert result.cited_markers == [1]

    asyncio.run(scenario())


def test_llm_answer_generator_empty_response_treated_as_no_answer() -> None:
    async def scenario() -> None:
        provider = _FakeProvider(response="")
        generator = LLMAnswerGenerator(provider, ExtractiveAnswerGenerator())
        result = await generator.generate("q", [_block(1)])
        assert result.text == NO_CONTEXT_ANSWER

    asyncio.run(scenario())


# ---- build_answer_generator factory -------------------------------------


def test_factory_extractive_explicit() -> None:
    settings = _settings(llm_provider="extractive")
    generator = build_answer_generator(settings)
    assert isinstance(generator, ExtractiveAnswerGenerator)


def test_factory_ollama_explicit_wires_ollama_provider() -> None:
    settings = _settings(llm_provider="ollama")
    generator = build_answer_generator(settings)
    assert isinstance(generator, LLMAnswerGenerator)
    assert isinstance(generator.provider, OllamaProvider)
    assert generator.provider.model_name == settings.ollama_model


def test_factory_anthropic_explicit_without_credentials_raises() -> None:
    settings = _settings(llm_provider="anthropic")
    with pytest.raises(ServiceUnavailableError):
        build_answer_generator(settings)


def test_factory_auto_without_anthropic_credentials_prefers_ollama() -> None:
    settings = _settings(llm_provider="auto", groq_api_key="")
    generator = build_answer_generator(settings)
    assert isinstance(generator, LLMAnswerGenerator)
    assert isinstance(generator.provider, OllamaProvider)


def _settings(**overrides):
    from app.core.config import Settings

    return Settings(**overrides)


# ---- Ollama provider: real local model (skips cleanly if not running) ---


def _ollama_reachable() -> bool:
    try:
        import httpx

        httpx.get("http://localhost:11434/api/tags", timeout=2.0).raise_for_status()
        return True
    except Exception:
        return False


OLLAMA_UP = _ollama_reachable()


@pytest.mark.skipif(not OLLAMA_UP, reason="Ollama is not running on localhost:11434")
def test_ollama_provider_generates_real_text() -> None:
    """Exercises the actual starting provider this module specifies:
    Ollama -> a local Llama/Gemma model."""

    async def scenario() -> None:
        provider = OllamaProvider("http://localhost:11434", "gemma3:4b", 60.0)
        text = await provider.generate("Reply with exactly the word: hello")
        assert isinstance(text, str)
        assert len(text) > 0

    asyncio.run(scenario())


def test_anthropic_provider_is_a_valid_llm_provider_shape() -> None:
    """Structural check only (no live call — no credentials in this env):
    confirms AnthropicProvider satisfies the same narrow interface as
    OllamaProvider, so the pipeline is genuinely provider-agnostic."""
    provider = AnthropicProvider("claude-opus-5", 1024)
    assert hasattr(provider, "model_name")
    assert hasattr(provider, "generate")
    assert provider.model_name == "claude-opus-5"


@pytest.mark.skipif(not OLLAMA_UP, reason="Ollama is not running on localhost:11434")
def test_chat_query_end_to_end_with_real_ollama(client, auth_headers, monkeypatch) -> None:
    """The whole pipeline — retrieval -> fusion -> Prompt Constructor ->
    real Ollama/Gemma -> Citation Generator -> answer — with an actual
    local model in the loop, not a stub."""
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "llm_provider", "ollama")

    upload = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={
            "file": (
                "ollama_policy.txt",
                b"1. Annual Leave Policy\n"
                b"Full-time employees receive exactly 25 days of paid annual "
                b"leave per calendar year.",
                "text/plain",
            )
        },
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["id"]

    chunk_text = client.get(
        f"/api/v1/documents/{document_id}/chunks", headers=auth_headers
    ).json()["items"][0]["content"]

    response = client.post(
        "/api/v1/chat/query", headers=auth_headers, json={"query": chunk_text}
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["model"] == "gemma3:4b"
    assert body["answer"]
    assert body["citation_generation"]["cited"] >= 0  # generator ran to completion
    assert "unavailable" not in body["model"]  # confirms it did NOT fall back
