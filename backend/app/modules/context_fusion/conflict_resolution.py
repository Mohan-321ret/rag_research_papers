"""Applying precomputed knowledge conflicts (Phase 13) to a candidate set.

Detection (``ConflictService``) already did the expensive work — corpus
search plus NLI — at ingestion time. This module is deliberately pure and
cheap: given today's retrieval candidates and whichever precomputed
conflicts involve two of them, either drop the losing side (authority
resolved it) or keep both and flag the disagreement (it didn't) — the
two options the design calls for: "select the authoritative version or
expose the conflict to the user." No I/O, no model calls, safe to run on
every query.
"""

import uuid
from dataclasses import dataclass

from app.modules.context_fusion.types import EvidenceChunk


@dataclass(frozen=True, slots=True)
class ConflictRecord:
    """The minimal shape this module needs from a ``KnowledgeConflict`` row."""

    claim_a_chunk_id: uuid.UUID
    claim_b_chunk_id: uuid.UUID
    contradiction_score: float
    preferred_chunk_id: uuid.UUID | None
    resolved: bool
    resolution_reason: str


@dataclass(frozen=True, slots=True)
class ConflictNote:
    """What Context Fusion did about one conflict among today's candidates."""

    claim_a_chunk_id: uuid.UUID
    claim_b_chunk_id: uuid.UUID
    contradiction_score: float
    preferred_chunk_id: uuid.UUID | None
    resolved: bool
    reason: str
    dropped_chunk_id: uuid.UUID | None  # None if unresolved (both kept)


def resolve_conflicts(
    items: list[EvidenceChunk], conflicts: list[ConflictRecord]
) -> tuple[list[EvidenceChunk], list[ConflictNote]]:
    """Drop the non-preferred side of each resolved conflict; keep both
    sides of an unresolved one (and note it) so the disagreement is still
    visible to the caller."""
    if not conflicts:
        return items, []

    present_ids = {item.chunk_id for item in items}
    drop_ids: set[uuid.UUID] = set()
    notes: list[ConflictNote] = []

    for conflict in conflicts:
        if conflict.claim_a_chunk_id not in present_ids:
            continue
        if conflict.claim_b_chunk_id not in present_ids:
            continue

        dropped = None
        if conflict.resolved and conflict.preferred_chunk_id is not None:
            dropped = (
                conflict.claim_b_chunk_id
                if conflict.preferred_chunk_id == conflict.claim_a_chunk_id
                else conflict.claim_a_chunk_id
            )
            drop_ids.add(dropped)

        notes.append(
            ConflictNote(
                claim_a_chunk_id=conflict.claim_a_chunk_id,
                claim_b_chunk_id=conflict.claim_b_chunk_id,
                contradiction_score=conflict.contradiction_score,
                preferred_chunk_id=conflict.preferred_chunk_id,
                resolved=conflict.resolved,
                reason=conflict.resolution_reason,
                dropped_chunk_id=dropped,
            )
        )

    filtered = [item for item in items if item.chunk_id not in drop_ids]
    return filtered, notes
