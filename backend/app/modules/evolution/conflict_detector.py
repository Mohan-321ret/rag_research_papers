"""Conflict Detector — does a revision contradict what it replaced?

Reuses Module 9's NLI cross-encoder rather than a second model: the same
"does A entail/contradict/stay neutral toward B" question that catches a
hallucinated answer also catches a substantive policy change, applied to
(old sentence, new sentence) pairs the Diff Detector aligned as
replacements of each other. A high contradiction probability is exactly
the "this revision reversed a fact" signal a research paper on
knowledge evolution wants surfaced, not silently overwritten.

Runs only over ``replaced_pairs`` (not every sentence combination) —
insertions and deletions have nothing to compare against, and diffing
already did the expensive work of aligning what maps to what.
"""

from dataclasses import dataclass

from app.modules.evolution.diff_detector import ReplacedPair
from app.modules.verification.nli_verifier import NliVerifier


@dataclass(frozen=True, slots=True)
class Conflict:
    old_sentence: str
    new_sentence: str
    contradiction_score: float


async def detect_conflicts(
    verifier: NliVerifier, replaced_pairs: list[ReplacedPair], threshold: float
) -> list[Conflict]:
    conflicts: list[Conflict] = []
    for pair in replaced_pairs:
        result = await verifier.score(pair.old_sentence, pair.new_sentence)
        if result.verdict == "contradiction" and result.contradiction >= threshold:
            conflicts.append(
                Conflict(
                    old_sentence=pair.old_sentence,
                    new_sentence=pair.new_sentence,
                    contradiction_score=round(result.contradiction, 4),
                )
            )
    return conflicts
