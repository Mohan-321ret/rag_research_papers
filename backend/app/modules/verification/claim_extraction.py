"""Claim Extraction — the first stage of evidence verification.

Splits a generated answer into individual sentence-level claims, each
carrying the citation markers ([n]) it references and its exact span in
the original answer text. The span (not just the cleaned text) is what
lets Response Refinement insert annotations at the right place without
fragile substring search-and-replace.
"""

import re
from dataclasses import dataclass

_SENTENCE = re.compile(r"[^.!?]*[.!?]+")
_CITATION_MARKER = re.compile(r"\[(\d+)\]")
_MARKER_WITH_LEADING_SPACE = re.compile(r"\s*\[(\d+)\]")
_TRAILING_MARKERS = re.compile(r"(?:\s*\[\d+\])+")
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class Claim:
    """One sentence-level factual claim extracted from an answer."""

    text: str  # cleaned: markers stripped, whitespace collapsed
    markers: list[int]  # [n] citation markers found in this sentence
    start: int  # span in the ORIGINAL answer text
    end: int  # end index, right after the terminal punctuation (no trailing ws)


def _clean(raw_sentence: str) -> str:
    without_markers = _MARKER_WITH_LEADING_SPACE.sub("", raw_sentence)
    return _WHITESPACE.sub(" ", without_markers).strip()


def _skip_leading_whitespace(text: str, start: int, end: int) -> int:
    while start < end and text[start].isspace():
        start += 1
    return start


def extract_claims(answer_text: str) -> list[Claim]:
    """Split an answer into per-sentence claims with precise source spans.

    A [n] marker is written right after the statement it supports, which
    puts it *after* the sentence's terminal punctuation — outside the
    sentence match itself. A trailing run of markers is pulled forward
    into the current claim's span (and the scan resumes past it) so it
    isn't misattributed to the next sentence.

    A claim with no non-whitespace, non-marker content (e.g. a lone "[1].")
    carries no verifiable assertion and is skipped.
    """
    claims: list[Claim] = []
    pos = 0
    length = len(answer_text)

    while pos < length:
        match = _SENTENCE.match(answer_text, pos)
        if not match:
            break
        start = _skip_leading_whitespace(answer_text, match.start(), match.end())
        end = match.end()
        trailing = _TRAILING_MARKERS.match(answer_text, end)
        if trailing:
            end = trailing.end()

        raw = answer_text[start:end]
        cleaned = _clean(raw)
        if cleaned:
            markers = [int(m.group(1)) for m in _CITATION_MARKER.finditer(raw)]
            claims.append(Claim(text=cleaned, markers=markers, start=start, end=end))
        pos = end

    # Trailing fragment with no terminal punctuation.
    if pos < length:
        start = _skip_leading_whitespace(answer_text, pos, length)
        raw = answer_text[start:]
        cleaned = _clean(raw)
        if cleaned:
            markers = [int(m.group(1)) for m in _CITATION_MARKER.finditer(raw)]
            claims.append(Claim(text=cleaned, markers=markers, start=start, end=length))

    return claims
