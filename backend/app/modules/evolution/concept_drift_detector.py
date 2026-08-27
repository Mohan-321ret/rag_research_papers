"""Concept Drift Detection (Phase 12) — chunk-level, embedding-driven
semantic comparison between two document versions.

``VersionComparison``'s existing Drift Detector measures drift as one
number for the whole document (old centroid vs. new centroid); its
Conflict Detector only asks "does this contradict?" over sentence pairs
difflib happened to align. Neither can say *which chunk* changed meaning,
nor tell a contradiction from a broadening of scope. This module closes
both gaps:

    old chunk embedding
           |
    cosine similarity  -> nearest-neighbor match to a new chunk
           |
    new chunk embedding
           |
    drift_score = 1 - cosine_similarity  (reported; also a topic-shift gate)
           |
    bidirectional NLI  -> classify *how* the pair drifted
           |
    flag if not a plain rewording, or if drift_score crosses threshold

Cosine distance alone turns out to be an unreliable gate for *factual*
change: measured on the real embedder, a harmless paraphrase ("25 days
... per year" -> "twenty-five days ... annually") scores drift 0.132,
while a genuine contradiction one digit wide ("2 days" -> "3 days")
scores only 0.037 — *lower* than the harmless rewording. No single
cosine threshold separates those two correctly. So NLI verdict, not
cosine distance, is the primary signal for whether meaning changed;
cosine distance still does the chunk-alignment work (nearest neighbor)
and remains a secondary gate that catches large topic-level shifts NLI's
binary verdict doesn't grade by severity. This also confirms the
module's own motivating example: "confidential info includes customer
records" -> "...customer and employee records" is not a contradiction
(scores ~0 contradiction probability) but bidirectional entailment shows
the broader new statement implies the narrower old one and not the
other way around — a genuine expansion of scope, not a reworded sentence
or a reversed fact.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import numpy as np

from app.modules.verification.nli_verifier import NliVerifier

EmbedFn = Callable[[list[str]], Awaitable[list[list[float]]]]

_ENTAILMENT_THRESHOLD = 0.5

# Most-to-least "surface this first" when a transition has multiple kinds
# of changed chunks — a single contradiction anywhere is more important
# to a reader than five unrelated topic shifts.
_TYPE_PRIORITY = (
    "contradiction",
    "narrowing",
    "expansion",
    "topic_shift",
    "rewording",
    "removed",
    "added",
)


@dataclass(frozen=True, slots=True)
class ChunkPairDrift:
    old_chunk_id: str | None
    new_chunk_id: str | None
    old_content: str | None
    new_content: str | None
    drift_score: float
    drift_type: str


@dataclass(frozen=True, slots=True)
class ConceptDriftResult:
    drift_score: float  # mean over all matched chunk pairs, 0 (no drift) .. 1
    drift_type: str  # dominant type among flagged/changed chunks, else "none"
    changed_chunks: list[ChunkPairDrift] = field(default_factory=list)


def _cosine_similarity_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a_unit = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-9)
    b_unit = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-9)
    return a_unit @ b_unit.T


async def _classify_pair(verifier: NliVerifier, old_text: str, new_text: str) -> str:
    """Bidirectional entailment tells rewording from expansion/narrowing;
    either direction contradicting is a reversed fact."""
    if old_text == new_text:
        return "rewording"  # trivially unchanged; skip the model call

    old_to_new = await verifier.score(old_text, new_text)
    new_to_old = await verifier.score(new_text, old_text)

    if old_to_new.verdict == "contradiction" or new_to_old.verdict == "contradiction":
        return "contradiction"

    old_entails_new = (
        old_to_new.verdict == "entailment" and old_to_new.entailment >= _ENTAILMENT_THRESHOLD
    )
    new_entails_old = (
        new_to_old.verdict == "entailment" and new_to_old.entailment >= _ENTAILMENT_THRESHOLD
    )

    if old_entails_new and new_entails_old:
        return "rewording"  # each implies the other -> same meaning, different words
    if new_entails_old:
        return "expansion"  # the new, broader statement implies the old, narrower one
    if old_entails_new:
        return "narrowing"  # the old, broader statement implies the new, narrower one
    return "topic_shift"  # neither implies the other, no contradiction either


def _dominant_type(changed: list[ChunkPairDrift]) -> str:
    present = {c.drift_type for c in changed}
    for candidate in _TYPE_PRIORITY:
        if candidate in present:
            return candidate
    return "none"


async def detect_concept_drift(
    embed: EmbedFn,
    verifier: NliVerifier,
    old_chunks: list[tuple[str, str]],
    new_chunks: list[tuple[str, str]],
    *,
    threshold: float,
) -> ConceptDriftResult:
    """``old_chunks``/``new_chunks`` are (chunk_id, content) pairs for each
    version. Chunks are paired by *mutual* nearest neighbor in embedding
    space (each is the other's best cosine-similarity match) rather than
    by position, since chunk boundaries can shift between versions.
    """
    if not old_chunks or not new_chunks:
        return ConceptDriftResult(drift_score=0.0, drift_type="none")

    old_ids = [chunk_id for chunk_id, _ in old_chunks]
    old_texts = [content for _, content in old_chunks]
    new_ids = [chunk_id for chunk_id, _ in new_chunks]
    new_texts = [content for _, content in new_chunks]

    old_vectors = np.asarray(await embed(old_texts), dtype=np.float64)
    new_vectors = np.asarray(await embed(new_texts), dtype=np.float64)
    similarity = _cosine_similarity_matrix(old_vectors, new_vectors)

    old_best = similarity.argmax(axis=1)
    new_best = similarity.argmax(axis=0)

    matched_old: set[int] = set()
    matched_new: set[int] = set()
    pair_scores: list[float] = []
    changed: list[ChunkPairDrift] = []

    for i in range(len(old_texts)):
        j = int(old_best[i])
        if int(new_best[j]) != i:
            continue  # not each other's best match -> not a stable pairing
        matched_old.add(i)
        matched_new.add(j)
        drift_score = round(max(0.0, min(1.0, 1.0 - float(similarity[i, j]))), 4)
        pair_scores.append(drift_score)

        # NLI runs on every matched pair, not just ones already over the
        # cosine threshold — that threshold alone would miss narrow
        # factual changes (see module docstring).
        drift_type = await _classify_pair(verifier, old_texts[i], new_texts[j])
        if drift_type != "rewording" or drift_score > threshold:
            changed.append(
                ChunkPairDrift(
                    old_chunk_id=old_ids[i],
                    new_chunk_id=new_ids[j],
                    old_content=old_texts[i],
                    new_content=new_texts[j],
                    drift_score=drift_score,
                    drift_type=drift_type,
                )
            )

    for i in range(len(old_texts)):
        if i not in matched_old:
            changed.append(
                ChunkPairDrift(
                    old_chunk_id=old_ids[i],
                    new_chunk_id=None,
                    old_content=old_texts[i],
                    new_content=None,
                    drift_score=1.0,
                    drift_type="removed",
                )
            )
    for j in range(len(new_texts)):
        if j not in matched_new:
            changed.append(
                ChunkPairDrift(
                    old_chunk_id=None,
                    new_chunk_id=new_ids[j],
                    old_content=None,
                    new_content=new_texts[j],
                    drift_score=1.0,
                    drift_type="added",
                )
            )

    if pair_scores:
        aggregate = round(sum(pair_scores) / len(pair_scores), 4)
    else:
        aggregate = 1.0 if changed else 0.0
    return ConceptDriftResult(
        drift_score=aggregate, drift_type=_dominant_type(changed), changed_chunks=changed
    )
