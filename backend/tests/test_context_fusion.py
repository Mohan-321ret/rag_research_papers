"""Tests for context fusion (Module 7): dedup -> rerank -> compress -> build."""

import asyncio
import uuid

from app.modules.context_fusion.builder import build_context_blocks, build_context_text
from app.modules.context_fusion.compressor import compress_to_top_k
from app.modules.context_fusion.dedup import deduplicate
from app.modules.context_fusion.reranker import PassthroughReranker
from app.modules.context_fusion.types import EvidenceChunk

DOC_A = uuid.uuid4()
DOC_B = uuid.uuid4()


def _evidence(
    *,
    chunk_id: uuid.UUID | None = None,
    document_id: uuid.UUID = DOC_A,
    document_title: str = "Employee Policy",
    version_number: int = 1,
    page_number: int | None = 4,
    section: str | None = "Leave",
    content: str = "Employees receive 25 days of annual leave.",
    retrieval_score: float = 1.0,
    retrievers: list[str] | None = None,
) -> EvidenceChunk:
    return EvidenceChunk(
        chunk_id=chunk_id or uuid.uuid4(),
        document_id=document_id,
        document_title=document_title,
        version_number=version_number,
        page_number=page_number,
        section=section,
        content=content,
        retrieval_score=retrieval_score,
        retrievers=retrievers or ["vector"],
    )


# ---- deduplication ----------------------------------------------------


def test_dedup_removes_same_chunk_id() -> None:
    shared_id = uuid.uuid4()
    items = [
        _evidence(chunk_id=shared_id, retrieval_score=0.9, retrievers=["bm25"]),
        _evidence(chunk_id=shared_id, retrieval_score=0.8, retrievers=["vector"]),
    ]
    deduped = deduplicate(items)
    assert len(deduped) == 1
    assert deduped[0].retrievers == ["bm25"]  # first (best-ranked) occurrence kept


def test_dedup_removes_duplicate_content_different_chunk_ids() -> None:
    """Same paragraph duplicated under two different chunk rows (e.g. two
    documents containing the same boilerplate section) collapses to one."""
    items = [
        _evidence(content="Remote work requires manager approval.  "),
        _evidence(
            document_id=DOC_B,
            document_title="Remote Work Addendum",
            content="remote work requires manager approval.",  # same, different case/whitespace
        ),
    ]
    deduped = deduplicate(items)
    assert len(deduped) == 1
    assert deduped[0].document_title == "Employee Policy"  # first occurrence kept


def test_dedup_keeps_distinct_content() -> None:
    items = [
        _evidence(content="Annual leave is 25 days."),
        _evidence(content="Sick leave is 10 days."),
    ]
    assert len(deduplicate(items)) == 2


def test_dedup_preserves_relative_order() -> None:
    items = [_evidence(content=f"Distinct content {i}") for i in range(5)]
    deduped = deduplicate(items)
    assert [item.chunk_id for item in deduped] == [item.chunk_id for item in items]


def test_dedup_empty_input() -> None:
    assert deduplicate([]) == []


# ---- compression --------------------------------------------------------


def test_compress_truncates_to_top_k() -> None:
    items = [_evidence(content=f"chunk {i}") for i in range(10)]
    assert len(compress_to_top_k(items, 6)) == 6


def test_compress_keeps_fewer_than_k_unchanged() -> None:
    items = [_evidence(content=f"chunk {i}") for i in range(3)]
    assert len(compress_to_top_k(items, 8)) == 3


def test_compress_preserves_order() -> None:
    items = [_evidence(content=f"chunk {i}") for i in range(10)]
    compressed = compress_to_top_k(items, 5)
    assert compressed == items[:5]


def test_compress_zero_top_k() -> None:
    items = [_evidence()]
    assert compress_to_top_k(items, 0) == []


# ---- context builder ------------------------------------------------------


def test_builder_matches_spec_format() -> None:
    items = [
        _evidence(
            document_title="Employee Policy",
            version_number=3,
            page_number=4,
            section=None,
            content="...",
        ),
        _evidence(
            document_title="Leave Policy",
            version_number=2,
            page_number=7,
            section=None,
            content="...",
        ),
    ]
    blocks = build_context_blocks(items)
    text = build_context_text(blocks)

    expected = (
        "SOURCE 1\n"
        "Document: Employee Policy\n"
        "Version: 3\n"
        "Page: 4\n"
        "\n"
        "CONTENT:\n"
        "...\n"
        "\n"
        "SOURCE 2\n"
        "Document: Leave Policy\n"
        "Version: 2\n"
        "Page: 7\n"
        "\n"
        "CONTENT:\n"
        "..."
    )
    assert text == expected


def test_builder_numbers_sources_from_one() -> None:
    blocks = build_context_blocks([_evidence(), _evidence(), _evidence()])
    assert [b.index for b in blocks] == [1, 2, 3]


def test_builder_handles_missing_page() -> None:
    blocks = build_context_blocks([_evidence(page_number=None)])
    text = build_context_text(blocks)
    assert "Page: N/A" in text


def test_builder_includes_section_when_present() -> None:
    blocks = build_context_blocks([_evidence(section="Annual Leave")])
    text = build_context_text(blocks)
    assert "Section: Annual Leave" in text


def test_builder_omits_section_line_when_absent() -> None:
    blocks = build_context_blocks([_evidence(section=None)])
    text = build_context_text(blocks)
    assert "Section:" not in text


def test_builder_empty_input() -> None:
    assert build_context_text(build_context_blocks([])) == ""


# ---- rerankers --------------------------------------------------------


def test_passthrough_reranker_preserves_order_and_uses_retrieval_score() -> None:
    async def scenario() -> None:
        items = [
            _evidence(content="a", retrieval_score=0.5),
            _evidence(content="b", retrieval_score=0.9),
        ]
        reranked = await PassthroughReranker().rerank("query", items)
        assert [r.content for r in reranked] == ["a", "b"]  # order untouched
        assert [r.rerank_score for r in reranked] == [0.5, 0.9]

    asyncio.run(scenario())


def test_passthrough_reranker_empty_input() -> None:
    async def scenario() -> None:
        assert await PassthroughReranker().rerank("query", []) == []

    asyncio.run(scenario())


def test_cross_encoder_reranks_relevant_chunk_above_irrelevant() -> None:
    """Real cross-encoder/ms-marco-MiniLM-L-6-v2 model: verify it actually
    re-scores by query-chunk relevance, not just echoes retrieval order."""
    from app.modules.context_fusion.reranker import CrossEncoderReranker

    async def scenario() -> None:
        reranker = CrossEncoderReranker("cross-encoder/ms-marco-MiniLM-L-6-v2")
        # Deliberately give the irrelevant chunk the *better* retrieval score,
        # so a passing test proves the cross-encoder overrode it.
        relevant = _evidence(
            content="Employees are entitled to 25 days of paid annual leave per year.",
            retrieval_score=0.4,
        )
        irrelevant = _evidence(
            content="The office kitchen is restocked with coffee every Monday.",
            retrieval_score=0.9,
        )
        reranked = await reranker.rerank(
            "How many days of annual leave do employees get?", [irrelevant, relevant]
        )
        assert reranked[0].content == relevant.content
        assert reranked[0].rerank_score > reranked[1].rerank_score

    asyncio.run(scenario())
