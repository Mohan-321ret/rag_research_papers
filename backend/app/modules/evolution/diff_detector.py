"""Diff Detector — text-level comparison between two versions.

Sentence-granular diff via Python's ``difflib`` (Ratcliff/Obershelp),
which classifies each region as unchanged, inserted, deleted, or
replaced. The "replaced" pairs are the interesting ones for the Conflict
Detector downstream: a 1:1 alignment of an old sentence to the new
sentence that took its place, which is exactly what needs an NLI check
for "did this change contradict what it replaced?"
"""

import difflib
import re
from dataclasses import dataclass, field

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text.strip()) if s.strip()]


@dataclass(frozen=True, slots=True)
class ReplacedPair:
    """An old sentence and the new sentence that took its place."""

    old_sentence: str
    new_sentence: str


@dataclass(frozen=True, slots=True)
class DiffResult:
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    unchanged_count: int = 0
    replaced_pairs: list[ReplacedPair] = field(default_factory=list)
    similarity_ratio: float = 1.0  # difflib ratio over the whole text, 0-1


def compute_diff(old_text: str | None, new_text: str) -> DiffResult:
    """Sentence-level diff. ``old_text`` is None for a brand-new document
    (everything in ``new_text`` counts as added)."""
    old_sentences = _sentences(old_text or "")
    new_sentences = _sentences(new_text)

    matcher = difflib.SequenceMatcher(a=old_sentences, b=new_sentences, autojunk=False)
    added: list[str] = []
    removed: list[str] = []
    replaced_pairs: list[ReplacedPair] = []
    unchanged = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            unchanged += i2 - i1
        elif tag == "insert":
            added.extend(new_sentences[j1:j2])
        elif tag == "delete":
            removed.extend(old_sentences[i1:i2])
        elif tag == "replace":
            old_block = old_sentences[i1:i2]
            new_block = new_sentences[j1:j2]
            paired = min(len(old_block), len(new_block))
            replaced_pairs.extend(
                ReplacedPair(old_block[k], new_block[k]) for k in range(paired)
            )
            # Leftover, unpaired sentences on the longer side are pure adds/removes.
            added.extend(new_block[paired:])
            removed.extend(old_block[paired:])

    return DiffResult(
        added=added,
        removed=removed,
        unchanged_count=unchanged,
        replaced_pairs=replaced_pairs,
        similarity_ratio=round(matcher.ratio(), 4),
    )
