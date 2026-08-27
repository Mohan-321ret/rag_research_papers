"""Tests for applying precomputed conflicts to a candidate set (Phase 13,
Context Fusion side) — pure, no I/O, no model calls.
"""

import uuid

from app.modules.context_fusion.conflict_resolution import ConflictRecord, resolve_conflicts
from app.modules.context_fusion.types import EvidenceChunk

DOC_A = uuid.uuid4()
DOC_B = uuid.uuid4()


def _evidence(chunk_id: uuid.UUID, content: str = "content") -> EvidenceChunk:
    return EvidenceChunk(
        chunk_id=chunk_id,
        document_id=DOC_A,
        document_title="Doc",
        version_number=1,
        page_number=None,
        section=None,
        content=content,
        retrieval_score=1.0,
        retrievers=["vector"],
    )


def _conflict(a_id, b_id, *, preferred=None, resolved=False, reason="tied") -> ConflictRecord:
    return ConflictRecord(
        claim_a_chunk_id=a_id,
        claim_b_chunk_id=b_id,
        contradiction_score=0.9,
        preferred_chunk_id=preferred,
        resolved=resolved,
        resolution_reason=reason,
    )


def test_no_conflicts_returns_items_unchanged() -> None:
    items = [_evidence(uuid.uuid4()), _evidence(uuid.uuid4())]
    filtered, notes = resolve_conflicts(items, [])
    assert filtered == items
    assert notes == []


def test_resolved_conflict_drops_the_losing_chunk() -> None:
    winner, loser = uuid.uuid4(), uuid.uuid4()
    items = [_evidence(winner), _evidence(loser)]
    conflicts = [_conflict(winner, loser, preferred=winner, resolved=True, reason="higher priority")]

    filtered, notes = resolve_conflicts(items, conflicts)

    assert [item.chunk_id for item in filtered] == [winner]
    assert len(notes) == 1
    assert notes[0].dropped_chunk_id == loser
    assert notes[0].resolved is True
    assert notes[0].preferred_chunk_id == winner


def test_unresolved_conflict_keeps_both_and_flags_it() -> None:
    a_id, b_id = uuid.uuid4(), uuid.uuid4()
    items = [_evidence(a_id), _evidence(b_id)]
    conflicts = [_conflict(a_id, b_id, preferred=None, resolved=False, reason="tied — unresolved")]

    filtered, notes = resolve_conflicts(items, conflicts)

    assert {item.chunk_id for item in filtered} == {a_id, b_id}
    assert len(notes) == 1
    assert notes[0].dropped_chunk_id is None
    assert notes[0].resolved is False


def test_conflict_ignored_when_only_one_side_present() -> None:
    """A precomputed conflict references a chunk from elsewhere in the
    corpus that today's retrieval didn't even surface — irrelevant here."""
    present = uuid.uuid4()
    absent = uuid.uuid4()
    items = [_evidence(present)]
    conflicts = [_conflict(present, absent, preferred=present, resolved=True)]

    filtered, notes = resolve_conflicts(items, conflicts)

    assert filtered == items
    assert notes == []


def test_multiple_independent_conflicts_all_applied() -> None:
    winner1, loser1 = uuid.uuid4(), uuid.uuid4()
    winner2, loser2 = uuid.uuid4(), uuid.uuid4()
    items = [_evidence(winner1), _evidence(loser1), _evidence(winner2), _evidence(loser2)]
    conflicts = [
        _conflict(winner1, loser1, preferred=winner1, resolved=True),
        _conflict(winner2, loser2, preferred=winner2, resolved=True),
    ]

    filtered, notes = resolve_conflicts(items, conflicts)

    assert {item.chunk_id for item in filtered} == {winner1, winner2}
    assert len(notes) == 2


def test_preserves_relative_order_of_surviving_items() -> None:
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    items = [_evidence(a), _evidence(b), _evidence(c)]
    conflicts = [_conflict(b, c, preferred=b, resolved=True)]

    filtered, _ = resolve_conflicts(items, conflicts)

    assert [item.chunk_id for item in filtered] == [a, b]
