"""Drift Detector — semantic-level comparison between two versions.

The Diff Detector catches *wording* changes; it can't tell a rephrasing
from a substantive policy change. Drift is measured in embedding space
instead: each version's chunks are mean-pooled into a single centroid
vector, and drift is 1 minus the cosine similarity between the old and
new centroids. A large wording diff with near-zero drift is just a
rewrite; a small wording diff with high drift is a substantive change
hiding in a minor-looking edit.
"""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

import numpy as np

_MINOR = 0.05
_MODERATE = 0.15
_MAJOR = 0.35

EmbedFn = Callable[[list[str]], Awaitable[list[list[float]]]]


@dataclass(frozen=True, slots=True)
class DriftResult:
    score: float  # 0 (same meaning) .. 1 (unrelated meaning)
    magnitude: str  # "none" | "minor" | "moderate" | "major" | "unknown"


def classify_magnitude(score: float) -> str:
    if score < _MINOR:
        return "none"
    if score < _MODERATE:
        return "minor"
    if score < _MAJOR:
        return "moderate"
    return "major"


def _centroid(vectors: Sequence[Sequence[float]]) -> np.ndarray:
    matrix = np.asarray(vectors, dtype=np.float64)
    mean = matrix.mean(axis=0)
    norm = np.linalg.norm(mean)
    return mean / norm if norm > 0 else mean


async def detect_drift(
    embed: EmbedFn, old_texts: list[str], new_texts: list[str]
) -> DriftResult:
    """``old_texts``/``new_texts`` are each version's chunk contents (or a
    single-item list of raw text as a fallback when chunks aren't
    available). An empty ``old_texts`` means there's nothing prior to
    drift from — treated as maximal (a brand-new document)."""
    if not old_texts or not any(t.strip() for t in old_texts):
        return DriftResult(score=1.0, magnitude="major")
    if not new_texts or not any(t.strip() for t in new_texts):
        return DriftResult(score=1.0, magnitude="major")

    old_vectors = await embed(old_texts)
    new_vectors = await embed(new_texts)
    old_centroid = _centroid(old_vectors)
    new_centroid = _centroid(new_vectors)

    cosine = float(np.dot(old_centroid, new_centroid))
    score = round(max(0.0, min(1.0, 1.0 - cosine)), 4)
    return DriftResult(score=score, magnitude=classify_magnitude(score))
