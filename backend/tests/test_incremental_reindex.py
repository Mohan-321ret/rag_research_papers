"""Tests for incremental re-indexing (Phase 14): the plan diff, vector
reconstruction, and the end-to-end "only changed chunks get embedded"
guarantee through the API.
"""

import asyncio
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from app.modules.processing.chunking import ChunkDraft
from app.modules.processing.incremental import ExistingChunk, plan_reindex
from app.modules.repository.vector_store import NumpyVectorStore, faiss_available

# ---- Plan diff -----------------------------------------------------------


def _draft(index: int, content: str) -> ChunkDraft:
    return ChunkDraft(
        chunk_index=index,
        content=content,
        token_estimate=max(1, len(content) // 4),
        page_number=1,
        section=None,
    )


def _existing(index: int, content: str, ref: str | None = "1") -> ExistingChunk:
    return ExistingChunk(
        chunk_id=uuid.uuid4(), content=content, embedding_ref=ref, chunk_index=index
    )


def test_no_previous_state_embeds_everything() -> None:
    drafts = [_draft(0, "A."), _draft(1, "B.")]
    plan = plan_reindex(drafts, [])
    assert plan.embed_count == 2
    assert plan.reused_count == 0
    assert plan.obsolete == []


def test_identical_content_reuses_everything() -> None:
    drafts = [_draft(0, "A."), _draft(1, "B.")]
    existing = [_existing(0, "A.", "10"), _existing(1, "B.", "11")]
    plan = plan_reindex(drafts, existing)
    assert plan.embed_count == 0
    assert plan.reused_count == 2
    assert plan.obsolete == []
    assert [e.reuse_from.embedding_ref for e in plan.planned] == ["10", "11"]


def test_single_changed_chunk_embeds_only_that_one() -> None:
    """The headline case: one clause edited in a long policy."""
    drafts = [_draft(0, "A."), _draft(1, "B CHANGED."), _draft(2, "C.")]
    existing = [_existing(0, "A.", "10"), _existing(1, "B.", "11"), _existing(2, "C.", "12")]
    plan = plan_reindex(drafts, existing)

    assert plan.embed_count == 1
    assert plan.reused_count == 2
    assert [e.draft.content for e in plan.to_embed] == ["B CHANGED."]
    # The replaced chunk is the only one retired.
    assert [c.content for c in plan.obsolete] == ["B."]


def test_reordered_unchanged_chunks_are_still_reused() -> None:
    """Chunk order changed but content didn't — matching is by content, so
    nothing needs re-embedding."""
    drafts = [_draft(0, "B."), _draft(1, "A.")]
    existing = [_existing(0, "A.", "10"), _existing(1, "B.", "11")]
    plan = plan_reindex(drafts, existing)
    assert plan.embed_count == 0
    assert [e.reuse_from.embedding_ref for e in plan.planned] == ["11", "10"]
    assert plan.obsolete == []


def test_inserted_chunk_only_embeds_the_insertion() -> None:
    drafts = [_draft(0, "A."), _draft(1, "NEW."), _draft(2, "B.")]
    existing = [_existing(0, "A.", "10"), _existing(1, "B.", "11")]
    plan = plan_reindex(drafts, existing)
    assert plan.embed_count == 1
    assert plan.reused_count == 2
    assert plan.obsolete == []


def test_deleted_chunk_becomes_obsolete() -> None:
    drafts = [_draft(0, "A.")]
    existing = [_existing(0, "A.", "10"), _existing(1, "B.", "11")]
    plan = plan_reindex(drafts, existing)
    assert plan.embed_count == 0
    assert [c.embedding_ref for c in plan.obsolete] == ["11"]


def test_duplicate_content_matched_one_for_one() -> None:
    """Two identical chunks must consume two distinct stored vectors, not
    both alias the same one."""
    drafts = [_draft(0, "SAME."), _draft(1, "SAME.")]
    existing = [_existing(0, "SAME.", "10"), _existing(1, "SAME.", "11")]
    plan = plan_reindex(drafts, existing)
    assert plan.embed_count == 0
    assert sorted(e.reuse_from.embedding_ref for e in plan.planned) == ["10", "11"]


def test_duplicate_content_beyond_supply_is_embedded() -> None:
    drafts = [_draft(0, "SAME."), _draft(1, "SAME.")]
    existing = [_existing(0, "SAME.", "10")]
    plan = plan_reindex(drafts, existing)
    assert plan.embed_count == 1
    assert plan.reused_count == 1


def test_existing_chunk_without_vector_is_never_reused() -> None:
    """No embedding_ref means there is no vector to reuse — e.g. a chunk
    embedded by a different model, which the service masks this way."""
    drafts = [_draft(0, "A.")]
    existing = [_existing(0, "A.", None)]
    plan = plan_reindex(drafts, existing)
    assert plan.embed_count == 1
    assert [c.content for c in plan.obsolete] == ["A."]


def test_whitespace_only_difference_still_matches() -> None:
    drafts = [_draft(0, "  A.  ")]
    existing = [_existing(0, "A.", "10")]
    plan = plan_reindex(drafts, existing)
    assert plan.embed_count == 0


# ---- Vector reconstruction ----------------------------------------------


def _store(tmp_path: Path) -> NumpyVectorStore:
    return NumpyVectorStore(tmp_path / "vectors", 3, "test-model")


def test_reconstruct_returns_stored_vectors(tmp_path: Path) -> None:
    async def scenario() -> None:
        store = _store(tmp_path)
        ids = await store.add([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
        found = await store.reconstruct(ids)
        assert found[ids[0]] == [1.0, 0.0, 0.0]
        assert found[ids[1]] == [0.0, 1.0, 0.0]

    asyncio.run(scenario())


def test_reconstruct_skips_missing_ids(tmp_path: Path) -> None:
    """A removed id is absent rather than an error, so the caller can fall
    back to embedding that chunk."""

    async def scenario() -> None:
        store = _store(tmp_path)
        ids = await store.add([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
        await store.remove([ids[0]])
        found = await store.reconstruct(ids)
        assert ids[0] not in found
        assert ids[1] in found

    asyncio.run(scenario())


def test_reconstruct_empty_input(tmp_path: Path) -> None:
    async def scenario() -> None:
        assert await _store(tmp_path).reconstruct([]) == {}

    asyncio.run(scenario())


def test_faiss_and_numpy_reconstruct_agree(tmp_path: Path) -> None:
    """Both backends must round-trip the same vectors, since which one is
    active depends only on whether faiss has wheels for this interpreter."""
    if not faiss_available():
        return

    from app.modules.repository.vector_store import FaissVectorStore

    async def scenario() -> None:
        vectors = [[1.0, 0.0, 0.0], [0.0, 0.6, 0.8]]
        numpy_store = NumpyVectorStore(tmp_path / "np", 3, "m")
        faiss_store = FaissVectorStore(tmp_path / "faiss", 3, "m")
        numpy_ids = await numpy_store.add(vectors)
        faiss_ids = await faiss_store.add(vectors)

        from_numpy = await numpy_store.reconstruct(numpy_ids)
        from_faiss = await faiss_store.reconstruct(faiss_ids)
        for numpy_id, faiss_id in zip(numpy_ids, faiss_ids):
            assert from_numpy[numpy_id] == [
                round(v, 6) for v in from_faiss[faiss_id]
            ] or from_numpy[numpy_id] == from_faiss[faiss_id]

    asyncio.run(scenario())


# ---- End to end through the API -----------------------------------------

# Numbered headings make each clause its own chunk (the chunker starts a
# new chunk on a section change), so a one-clause edit is a one-chunk edit.
POLICY_V1 = (
    b"1. Annual Leave\nAnnual leave is 25 days per year.\n\n"
    b"2. Sick Leave\nSick leave is 10 days per year.\n\n"
    b"3. Remote Work\nRemote work requires manager approval.\n\n"
    b"4. Expenses\nExpenses must be filed within 30 days.\n"
)
# Only the second clause differs.
POLICY_V2 = (
    b"1. Annual Leave\nAnnual leave is 25 days per year.\n\n"
    b"2. Sick Leave\nSick leave is 15 days per year.\n\n"
    b"3. Remote Work\nRemote work requires manager approval.\n\n"
    b"4. Expenses\nExpenses must be filed within 30 days.\n"
)
# Every clause differs.
POLICY_REWRITTEN = (
    b"1. Annual Leave\nStaff accrue thirty vacation days annually.\n\n"
    b"2. Sick Leave\nMedical absence allowance totals twenty days.\n\n"
    b"3. Remote Work\nHybrid attendance is mandatory on Tuesdays.\n\n"
    b"4. Expenses\nReimbursement claims close after one quarter.\n"
)


def _upload(client: TestClient, headers, filename: str, content: bytes):
    response = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": (filename, content, "text/plain")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _chunks(client: TestClient, headers, document_id: str, version: int | None = None):
    url = f"/api/v1/documents/{document_id}/chunks"
    if version is not None:
        url += f"?version={version}"
    return client.get(url, headers=headers).json()["items"]


def _manual_processing(monkeypatch) -> None:
    """Turn off auto-processing so each /process call is the *first* run for
    its version — otherwise upload already did the work and the explicit
    call would measure a redundant second pass over unchanged content."""
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "auto_process_on_upload", False)


def test_fully_rewritten_version_reuses_nothing(
    client: TestClient, auth_headers, monkeypatch
) -> None:
    """Guards against the planner trivially "reusing" everything: when every
    clause really did change, every chunk must be re-embedded."""
    _manual_processing(monkeypatch)
    document_id = _upload(client, auth_headers, "rewritten.txt", POLICY_V1)["id"]
    client.post(f"/api/v1/documents/{document_id}/process", headers=auth_headers)

    _upload(client, auth_headers, "rewritten.txt", POLICY_REWRITTEN)
    result = client.post(
        f"/api/v1/documents/{document_id}/process", headers=auth_headers
    ).json()

    assert result["chunk_count"] >= 2
    assert result["chunks_reused"] == 0
    assert result["embedded_count"] == result["chunk_count"]


def test_new_version_embeds_only_changed_chunks(
    client: TestClient, auth_headers, monkeypatch
) -> None:
    """The core Phase 14 guarantee, end to end: a one-clause edit must not
    re-embed the untouched clauses."""
    _manual_processing(monkeypatch)
    document_id = _upload(client, auth_headers, "policy.txt", POLICY_V1)["id"]

    first = client.post(
        f"/api/v1/documents/{document_id}/process", headers=auth_headers
    ).json()
    assert first["chunk_count"] >= 2, "need multiple chunks for this test to mean anything"
    assert first["chunks_reused"] == 0  # brand new document: nothing to reuse
    assert first["embedded_count"] == first["chunk_count"]

    upload = _upload(client, auth_headers, "policy.txt", POLICY_V2)
    assert upload["new_version_created"] is True
    result = client.post(
        f"/api/v1/documents/{document_id}/process", headers=auth_headers
    ).json()

    assert result["incremental"] is True
    assert result["chunk_count"] == first["chunk_count"]
    # One clause changed -> exactly one chunk re-embedded.
    assert result["embedded_count"] == 1
    assert result["chunks_reused"] == result["chunk_count"] - 1
    # A new version needs its own rows, so every chunk gets a vector — but
    # the reused ones were copied from the index, not recomputed.
    assert result["vectors_added"] == result["chunk_count"]
    # The previous version's vectors are never retired: they back
    # historical ("as of") retrieval.
    assert result["vectors_removed"] == 0


def test_old_version_vectors_survive_incremental_update(
    client: TestClient, auth_headers
) -> None:
    document_id = _upload(client, auth_headers, "survive.txt", POLICY_V1)["id"]
    v1_refs = {c["embedding_ref"] for c in _chunks(client, auth_headers, document_id, 1)}

    _upload(client, auth_headers, "survive.txt", POLICY_V2)

    still_there = {c["embedding_ref"] for c in _chunks(client, auth_headers, document_id, 1)}
    assert still_there == v1_refs
    v2_refs = {c["embedding_ref"] for c in _chunks(client, auth_headers, document_id, 2)}
    # New rows get their own vector ids — no aliasing across versions.
    assert v1_refs.isdisjoint(v2_refs)


def test_full_rebuild_baseline_reuses_nothing(
    client: TestClient, auth_headers, monkeypatch
) -> None:
    """The ablation baseline the paper compares against: with incremental
    re-indexing off, the same edit re-embeds every chunk."""
    from app.core.config import get_settings

    _manual_processing(monkeypatch)
    document_id = _upload(client, auth_headers, "ablation.txt", POLICY_V1)["id"]
    client.post(f"/api/v1/documents/{document_id}/process", headers=auth_headers)
    _upload(client, auth_headers, "ablation.txt", POLICY_V2)

    monkeypatch.setattr(get_settings(), "incremental_reindex_enabled", False)
    result = client.post(
        f"/api/v1/documents/{document_id}/process", headers=auth_headers
    ).json()

    assert result["incremental"] is False
    # Same one-clause edit as the incremental test, which re-embedded 1 —
    # the baseline re-embeds all of them.
    assert result["chunks_reused"] == 0
    assert result["embedded_count"] == result["chunk_count"]
