"""Duplicate removal — the first stage of context fusion.

Reciprocal Rank Fusion already merges the same chunk_id found by
multiple retrievers into a single entry (see
app.modules.retrieval.fusion), so this is chiefly a safety net for that
guarantee plus a second, independent check: near-identical *content*
appearing under different chunk ids (e.g. the same paragraph duplicated
across two uploaded documents). Highest-scored occurrence wins either
way, and relative order is otherwise preserved.
"""

import hashlib
import re
import uuid

from app.modules.context_fusion.types import EvidenceChunk

_WHITESPACE = re.compile(r"\s+")


def _content_fingerprint(content: str) -> str:
    normalized = _WHITESPACE.sub(" ", content).strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def deduplicate(items: list[EvidenceChunk]) -> list[EvidenceChunk]:
    """Drop duplicate chunk ids and duplicate chunk content.

    Input order is assumed best-first (as produced by the retrieval
    router); the first — i.e. best-scored — occurrence of each chunk id
    or content fingerprint is kept.
    """
    seen_ids: set[uuid.UUID] = set()
    seen_content: set[str] = set()
    deduped: list[EvidenceChunk] = []

    for candidate in items:
        if candidate.chunk_id in seen_ids:
            continue
        fingerprint = _content_fingerprint(candidate.content)
        if fingerprint in seen_content:
            continue
        seen_ids.add(candidate.chunk_id)
        seen_content.add(fingerprint)
        deduped.append(candidate)

    return deduped
