"""Entity recognition over user queries.

Queries are usually lowercase, so capitalization-based NER (used for
documents) is not enough. Three complementary strategies:

1. Knowledge-base matching — entity names extracted during document
   processing (Phase 4) are matched against the query, so the analyzer
   recognizes the vocabulary of the corpus itself.
2. Capitalized/acronym extraction — reuses the document entity extractor
   for queries that do carry casing (product names, acronyms).
3. Noun-phrase heuristic — contiguous runs of content words (stopwords
   removed) become candidate entities ("leave policy", "remote work").
"""

import re

from app.modules.processing.entities import extract_entities as extract_cased_entities
from app.modules.query_intelligence.parser import STOPWORDS, ParsedQuery

_MAX_PHRASE_WORDS = 3


def _noun_phrases(parsed: ParsedQuery) -> list[str]:
    """Contiguous content-word runs in query order (longest first per run)."""
    phrases: list[str] = []
    run: list[str] = []
    for token in parsed.tokens:
        if token in STOPWORDS or len(token) <= 1 or token.isdigit():
            if run:
                phrases.append(" ".join(run[:_MAX_PHRASE_WORDS]))
                run = []
        else:
            run.append(token)
    if run:
        phrases.append(" ".join(run[:_MAX_PHRASE_WORDS]))
    return phrases


def extract_query_entities(
    parsed: ParsedQuery, known_entities: list[str]
) -> list[str]:
    """Entities mentioned in the query, most specific first, deduplicated."""
    found: list[str] = []

    # 1. Knowledge-base entities present in the query (longest names first
    #    so "annual leave policy" wins over "leave").
    padded = f" {parsed.normalized} "
    for name in sorted(known_entities, key=len, reverse=True):
        lowered = name.lower().strip()
        if len(lowered) > 2 and f" {lowered} " in padded:
            found.append(lowered)

    # 2. Cased entities (acronyms, proper nouns) from the original text.
    for entity in extract_cased_entities(parsed.original, max_entities=5):
        found.append(entity.name.lower())

    # 3. Noun-phrase fallback.
    found.extend(_noun_phrases(parsed))

    deduped: list[str] = []
    for candidate in found:
        candidate = re.sub(r"\s+", " ", candidate).strip()
        if not candidate:
            continue
        # Skip candidates fully contained in an already-accepted phrase.
        if any(candidate in accepted for accepted in deduped):
            continue
        deduped.append(candidate)
    return deduped[:8]
