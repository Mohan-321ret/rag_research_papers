"""Citation Generator — the stage between the raw LLM output and the
"Initial Answer".

Parses [n] markers out of the generated text and validates them against
the SOURCE blocks that were actually offered to the model, so the final
citation list reflects what the answer *actually used* — not just
everything that was retrieved.
"""

import re
from dataclasses import dataclass, field

from app.modules.context_fusion.builder import ContextBlock

_CITATION_MARKER = re.compile(r"\[(\d+)\]")


@dataclass(frozen=True, slots=True)
class CitationResult:
    """Which sources the answer cites, in order of first appearance."""

    cited_markers: list[int] = field(default_factory=list)
    invalid_markers: list[int] = field(default_factory=list)  # cited but unknown — hallucinated
    used_fallback: bool = False  # True when the text had no markers at all


def extract_citations(answer_text: str, blocks: list[ContextBlock]) -> CitationResult:
    """Extract and validate citation markers from generated text.

    If the text contains no [n] markers at all — a model that forgot to
    cite — every offered source is kept rather than silently dropping the
    grounding evidence. Markers referencing a SOURCE number outside the
    provided blocks are reported separately as ``invalid_markers``
    (a hallucinated citation) instead of being treated as real evidence.
    """
    valid_markers = {block.index for block in blocks}
    cited: list[int] = []
    invalid: list[int] = []
    seen: set[int] = set()

    for match in _CITATION_MARKER.finditer(answer_text):
        marker = int(match.group(1))
        if marker in seen:
            continue
        seen.add(marker)
        (cited if marker in valid_markers else invalid).append(marker)

    if not cited:
        return CitationResult(
            cited_markers=[block.index for block in blocks],
            invalid_markers=invalid,
            used_fallback=True,
        )
    return CitationResult(cited_markers=cited, invalid_markers=invalid)
