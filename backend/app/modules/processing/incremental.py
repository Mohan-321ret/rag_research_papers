"""Incremental re-indexing planner (Phase 14).

The naive reaction to a changed document is to throw away everything it
produced and start over:

    document changed -> delete the whole index -> re-embed every chunk

Embedding is by far the most expensive step in the pipeline (a
transformer forward pass per chunk), and in a typical enterprise edit —
one clause updated in a fifty-clause policy — all but one chunk are
byte-for-byte identical to what was already indexed. Re-embedding them
buys nothing.

This module is the "identify changed chunks" stage: it diffs the newly
produced chunk drafts against what is already stored and classifies each
one, so the caller can embed only what actually changed.

Matching is by exact chunk content, which is the right granularity here:
chunking is deterministic, so an untouched region of the document
produces byte-identical chunks. Duplicate chunks with identical content
are matched one-for-one rather than collapsed, so counts stay honest and
every draft ends up with its own vector.
"""

import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field

from app.modules.processing.chunking import ChunkDraft


@dataclass(frozen=True, slots=True)
class ExistingChunk:
    """A chunk already persisted (and already embedded) for some version."""

    chunk_id: uuid.UUID
    content: str
    embedding_ref: str | None
    chunk_index: int


@dataclass(frozen=True, slots=True)
class PlannedChunk:
    """One chunk of the new version, and how to satisfy it."""

    draft: ChunkDraft
    # The already-embedded chunk whose vector this draft can reuse.
    # None means its content is new or changed -> it must be embedded.
    reuse_from: ExistingChunk | None

    @property
    def needs_embedding(self) -> bool:
        return self.reuse_from is None


@dataclass(frozen=True, slots=True)
class ReindexPlan:
    """The full incremental plan for one (re)processing run."""

    planned: list[PlannedChunk] = field(default_factory=list)
    obsolete: list[ExistingChunk] = field(default_factory=list)

    @property
    def to_embed(self) -> list[PlannedChunk]:
        return [entry for entry in self.planned if entry.needs_embedding]

    @property
    def reused(self) -> list[PlannedChunk]:
        return [entry for entry in self.planned if not entry.needs_embedding]

    @property
    def embed_count(self) -> int:
        return sum(1 for entry in self.planned if entry.needs_embedding)

    @property
    def reused_count(self) -> int:
        return len(self.planned) - self.embed_count


def _key(content: str) -> str:
    return content.strip()


def plan_reindex(
    drafts: list[ChunkDraft], existing: list[ExistingChunk]
) -> ReindexPlan:
    """Diff freshly chunked ``drafts`` against already-indexed ``existing``.

    An existing chunk with no ``embedding_ref`` has no vector to reuse, so
    it is never offered as a match — the draft is embedded instead.
    """
    available: dict[str, deque[ExistingChunk]] = defaultdict(deque)
    for chunk in existing:
        if chunk.embedding_ref is not None:
            available[_key(chunk.content)].append(chunk)

    planned: list[PlannedChunk] = []
    matched_ids: set[uuid.UUID] = set()
    for draft in drafts:
        bucket = available.get(_key(draft.content))
        match = bucket.popleft() if bucket else None
        if match is not None:
            matched_ids.add(match.chunk_id)
        planned.append(PlannedChunk(draft=draft, reuse_from=match))

    obsolete = [chunk for chunk in existing if chunk.chunk_id not in matched_ids]
    return ReindexPlan(planned=planned, obsolete=obsolete)
