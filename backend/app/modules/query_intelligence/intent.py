"""Rule-based intent detection."""

import re

from app.modules.query_intelligence.interfaces import QueryIntent
from app.modules.query_intelligence.parser import ParsedQuery

_COMPARATIVE = re.compile(
    r"\b(compare|comparison|versus|vs|difference between|differ|better|worse|"
    r"advantages|disadvantages|pros and cons)\b"
)
_PROCEDURAL = re.compile(
    r"\b(how (do|does|can|could|should|to)|steps? (to|for)|process (of|for)|"
    r"procedure|instructions|guide (to|for)|set up|configure|apply for|submit)\b"
)
_ANALYTICAL = re.compile(
    r"\b(why|analy[sz]e|analysis|impact|effect|implication|trend|cause|"
    r"explain|reason|insight|evaluate)\b"
)
_SUMMARIZATION = re.compile(
    r"\b(summari[sz]e|summary|overview|briefly describe|key points|tl;?dr|"
    r"main takeaways)\b"
)


def detect_intent(parsed: ParsedQuery) -> QueryIntent:
    """Classify the query's intent (checked most-specific first)."""
    text = parsed.normalized
    if _SUMMARIZATION.search(text):
        return QueryIntent.SUMMARIZATION
    if _COMPARATIVE.search(text):
        return QueryIntent.COMPARATIVE
    if _PROCEDURAL.search(text):
        return QueryIntent.PROCEDURAL
    if _ANALYTICAL.search(text):
        return QueryIntent.ANALYTICAL
    return QueryIntent.FACTUAL_LOOKUP
