"""Unit tests for the BM25 sparse index (no DB, no app dependencies)."""

import asyncio
import uuid

from app.modules.retrieval.bm25_index import Bm25Index

DOC_A = uuid.uuid4()
DOC_B = uuid.uuid4()
DOC_C = uuid.uuid4()

CORPUS = [
    (DOC_A, "Employees receive 25 days of paid annual leave per year."),
    (DOC_B, "The remote work policy requires two office days per week."),
    (DOC_C, "Security incidents must be reported within 24 hours per policy POL-4521."),
]


async def _loader():
    return CORPUS


def test_search_ranks_exact_term_match_first() -> None:
    async def scenario() -> None:
        index = Bm25Index()
        await index.ensure_built((len(CORPUS), "v1"), _loader)

        hits = await index.search("POL-4521 security incident", k=3)
        assert hits
        assert hits[0].chunk_id == DOC_C

    asyncio.run(scenario())


def test_search_no_match_returns_empty() -> None:
    async def scenario() -> None:
        index = Bm25Index()
        await index.ensure_built((len(CORPUS), "v1"), _loader)
        assert await index.search("quantum entanglement telescope", k=3) == []

    asyncio.run(scenario())


def test_search_before_build_returns_empty() -> None:
    async def scenario() -> None:
        index = Bm25Index()
        assert await index.search("leave", k=3) == []

    asyncio.run(scenario())


def test_fingerprint_change_triggers_rebuild() -> None:
    async def scenario() -> None:
        calls = 0

        async def counting_loader():
            nonlocal calls
            calls += 1
            return CORPUS

        index = Bm25Index()
        await index.ensure_built((3, "a"), counting_loader)
        await index.ensure_built((3, "a"), counting_loader)  # unchanged: no rebuild
        assert calls == 1

        await index.ensure_built((4, "b"), counting_loader)  # changed: rebuild
        assert calls == 2

    asyncio.run(scenario())


def test_empty_corpus_search_is_empty() -> None:
    async def scenario() -> None:
        async def empty_loader():
            return []

        index = Bm25Index()
        await index.ensure_built((0, ""), empty_loader)
        assert await index.search("anything", k=5) == []

    asyncio.run(scenario())
