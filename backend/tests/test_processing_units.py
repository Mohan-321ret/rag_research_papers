"""Unit tests for cleaning, language detection, chunking and vector stores."""

import asyncio

import pytest

from app.modules.processing.chunking import SemanticChunker
from app.modules.processing.cleaning import clean_text
from app.modules.processing.language import detect_language
from app.modules.repository.vector_store import FaissVectorStore, NumpyVectorStore

# ---- cleaning -------------------------------------------------------------


def test_cleaning_rejoins_hyphenated_linebreaks() -> None:
    assert "adaptive" in clean_text("adap-\ntive retrieval").text


def test_cleaning_removes_noise_lines() -> None:
    raw = "Real content here.\nPage 3 of 10\n42\n----------\nMore content."
    result = clean_text(raw)
    assert "Page 3" not in result.text
    assert "----" not in result.text
    assert result.noise_lines_removed == 3
    assert "Real content here." in result.text
    assert "More content." in result.text


def test_cleaning_removes_consecutive_duplicate_lines() -> None:
    raw = "ACME Corp Confidential\nACME Corp Confidential\nBody text."
    assert clean_text(raw).text.count("ACME Corp Confidential") == 1


def test_cleaning_preserves_page_breaks() -> None:
    assert clean_text("page one text\fpage two text").text.count("\f") == 1


def test_cleaning_strips_control_chars_and_normalizes() -> None:
    result = clean_text("café\x00\x01  ① spaced   out")
    assert "\x00" not in result.text
    assert "café" in result.text


# ---- language -------------------------------------------------------------


def test_detects_english() -> None:
    result = detect_language(
        "Retrieval augmented generation combines search with language models "
        "to answer questions using enterprise knowledge."
    )
    assert result.language == "en"
    assert result.confidence > 0.9


def test_detects_spanish() -> None:
    result = detect_language(
        "La gestión del conocimiento empresarial requiere sistemas que "
        "detecten cambios en los documentos a lo largo del tiempo."
    )
    assert result.language == "es"


def test_short_text_is_unknown() -> None:
    assert detect_language("hi").language == "unknown"


# ---- chunking -------------------------------------------------------------


def test_chunker_tracks_sections_and_pages() -> None:
    text = (
        "1. Introduction\nThis paper studies drift in enterprise knowledge bases."
        "\f2. Methods\nWe measure semantic distance between document versions."
    )
    chunks = SemanticChunker(target_tokens=100).split(text)

    assert len(chunks) == 2
    assert chunks[0].section == "Introduction"
    assert chunks[0].page_number == 1
    assert chunks[1].section == "Methods"
    assert chunks[1].page_number == 2
    assert [c.chunk_index for c in chunks] == [0, 1]


def test_chunker_splits_long_text_with_overlap() -> None:
    sentences = " ".join(
        f"Sentence number {i} talks about adaptive retrieval systems." for i in range(60)
    )
    chunks = SemanticChunker(target_tokens=80, overlap_sentences=1).split(sentences)

    assert len(chunks) > 1
    # Overlap: the first sentence of chunk N appears at the end of chunk N-1.
    lead = chunks[1].content.split(".")[0]
    assert lead.strip() in chunks[0].content


def test_chunker_handles_markdown_and_sheet_headings() -> None:
    text = "# Overview\nSome intro text.\n\n[Sheet: metrics]\ndrift_score\t0.42"
    chunks = SemanticChunker(target_tokens=50).split(text)
    assert chunks[0].section == "Overview"
    assert chunks[-1].section == "metrics"


def test_chunker_empty_text() -> None:
    assert SemanticChunker().split("") == []


# ---- vector stores --------------------------------------------------------


@pytest.mark.parametrize("backend", [FaissVectorStore, NumpyVectorStore])
def test_vector_store_roundtrip(tmp_path, backend) -> None:
    async def scenario() -> None:
        store = backend(tmp_path / "idx", 4, "test-model")
        ids = await store.add([[1, 0, 0, 0], [0, 1, 0, 0], [0.9, 0.1, 0, 0]])
        assert ids == [1, 2, 3]
        assert await store.count() == 3

        hits = await store.search([1, 0, 0, 0], k=2)
        assert hits[0].chunk_id == "1"  # exact match ranks first
        assert hits[0].score == pytest.approx(1.0)
        assert hits[1].chunk_id == "3"

        await store.remove([1])
        assert await store.count() == 2
        assert (await store.search([1, 0, 0, 0], k=1))[0].chunk_id == "3"

        # Persistence: a fresh instance sees the same data and id counter.
        reloaded = backend(tmp_path / "idx", 4, "test-model")
        assert await reloaded.count() == 2
        assert await reloaded.add([[0, 0, 1, 0]]) == [4]

    asyncio.run(scenario())


def test_vector_store_dimension_mismatch_rejected(tmp_path) -> None:
    async def scenario() -> None:
        store = NumpyVectorStore(tmp_path / "idx", 4, "m")
        await store.add([[1, 0, 0, 0]])
        with pytest.raises(RuntimeError, match="dimension"):
            NumpyVectorStore(tmp_path / "idx", 8, "m")

    asyncio.run(scenario())
