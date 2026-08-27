"""Query parsing: normalization, tokenization, keyword extraction."""

import re
from dataclasses import dataclass

_PUNCTUATION = re.compile(r"[^\w\s\-']")
_WHITESPACE = re.compile(r"\s+")

QUESTION_WORDS = frozenset(
    {"what", "who", "whom", "whose", "where", "when", "why", "how", "which", "is", "are", "was", "were", "do", "does", "did", "can", "could", "should"}
)

STOPWORDS = frozenset(
    """a an the of in on at to for from by with about as into over under and or
    but if then than so because is are was were be been being have has had do
    does did will would could should can may might must this that these those
    it its they them their there here i you we he she my your our his her
    what who whom whose where when why how which me us him need want get got
    tell show give please any some all much many more most
    before after since until till during ago within between prior"""
    .split()
)


@dataclass(frozen=True, slots=True)
class ParsedQuery:
    original: str
    normalized: str
    tokens: list[str]
    keywords: list[str]
    question_word: str | None


def parse_query(query: str) -> ParsedQuery:
    """Normalize the raw query and extract tokens/keywords."""
    original = query.strip()
    normalized = _WHITESPACE.sub(" ", _PUNCTUATION.sub(" ", original.lower())).strip()
    tokens = normalized.split()

    question_word = tokens[0] if tokens and tokens[0] in QUESTION_WORDS else None
    keywords = [t for t in tokens if t not in STOPWORDS and len(t) > 1]

    return ParsedQuery(
        original=original,
        normalized=normalized,
        tokens=tokens,
        keywords=keywords,
        question_word=question_word,
    )
