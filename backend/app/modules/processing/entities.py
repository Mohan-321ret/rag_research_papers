"""Lightweight rule-based entity and topic extraction.

Feeds the knowledge graph (Chunk-MENTIONS->Entity, Document-HAS_TOPIC->Topic)
without requiring an NLP model. Two entity families are recognized:

- acronyms: 2-6 letter all-caps tokens (RAG, FAISS, API)
- terms: runs of capitalized words that are not sentence-initial artifacts

Topics are the most frequent meaningful lowercase words of a document.
Deliberately simple and replaceable by a proper NER model later.
"""

import re
from collections import Counter
from dataclasses import dataclass

_ACRONYM = re.compile(r"\b[A-Z][A-Z0-9]{1,5}\b")
_CAPITALIZED_RUN = re.compile(r"\b(?:[A-Z][a-z][\w-]*)(?:\s+(?:[A-Z][a-z][\w-]*|of|and|the|for)){0,4}\b")
_SENTENCE_START = re.compile(r"(?:^|[.!?]\s+|\n\s*)([A-Z][\w-]*)")
_WORD = re.compile(r"[a-z][a-z-]{3,}")

_STOPWORDS = frozenset(
    """the and for that with this from are was were been being have has had not
    but they them their there these those which what when where who whom whose
    will would could should shall may might must can its it's about into over
    under between among through during before after above below such than then
    once here very more most other some any each few both all only own same so
    too also just because while against further page section table figure
    chapter appendix introduction conclusion abstract summary overview
    document company policy""".split()
)

# Words that look capitalized mid-sentence but are generic connectors.
_GENERIC_TERMS = frozenset({"of", "and", "the", "for"})


@dataclass(frozen=True, slots=True)
class ExtractedEntity:
    name: str
    entity_type: str  # "acronym" | "term"


def extract_entities(text: str, *, max_entities: int = 20) -> list[ExtractedEntity]:
    """Extract named entities from a chunk of text, most frequent first."""
    sentence_starters = {m.group(1) for m in _SENTENCE_START.finditer(text)}

    counts: Counter[ExtractedEntity] = Counter()
    for match in _ACRONYM.finditer(text):
        token = match.group(0)
        if token.lower() not in _STOPWORDS and len(token) >= 2:
            counts[ExtractedEntity(token, "acronym")] += 1

    for match in _CAPITALIZED_RUN.finditer(text):
        phrase = match.group(0).strip()
        words = phrase.split()
        # Trim generic trailing connectors ("Ministry of" -> keep as-is only
        # when a capitalized word follows).
        while words and words[-1].lower() in _GENERIC_TERMS:
            words.pop()
        if not words:
            continue
        phrase = " ".join(words)
        if len(words) == 1:
            # Single capitalized words only count when they are not simply
            # starting a sentence and not stopwords.
            if phrase in sentence_starters or phrase.lower() in _STOPWORDS:
                continue
        counts[ExtractedEntity(phrase, "term")] += 1

    return [entity for entity, _ in counts.most_common(max_entities)]


def extract_topics(text: str, *, top_n: int = 5) -> list[str]:
    """Most frequent meaningful words — a document-level topic sketch."""
    counts = Counter(
        word
        for word in _WORD.findall(text.lower())
        if word not in _STOPWORDS
    )
    return [word for word, count in counts.most_common(top_n) if count >= 2]
