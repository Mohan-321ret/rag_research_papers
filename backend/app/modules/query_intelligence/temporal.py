"""Temporal intent detection.

Recognizes when a query asks about a past, future, or explicitly current
state of knowledge — the signal that later routes retrieval to historical
document versions instead of only current ones.
"""

import re
from dataclasses import dataclass

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}
_MONTH_PATTERN = "|".join(_MONTHS)

_BEFORE = re.compile(rf"\b(before|prior to|until|up to)\s+(?:({_MONTH_PATTERN})\s+)?(\d{{4}})\b")
_AFTER = re.compile(rf"\b(after|since|from|starting)\s+(?:({_MONTH_PATTERN})\s+)?(\d{{4}})\b")
_AT = re.compile(rf"\b(in|as of|during|back in)\s+(?:({_MONTH_PATTERN})\s+)?(\d{{4}})\b")
_BARE_YEAR = re.compile(r"\b(19\d{2}|20\d{2})\b")
_PAST_MARKERS = re.compile(
    r"\b(was|were|used to|previously|formerly|originally|at the time|"
    r"old version|earlier version|historic(al)?ly?)\b"
)
_CURRENT_MARKERS = re.compile(r"\b(current(ly)?|latest|now|today|as of now|up to date)\b")


@dataclass(frozen=True, slots=True)
class TemporalIntent:
    is_temporal: bool
    direction: str | None  # "before" | "after" | "at" | "past" | "current"
    target_date: str | None  # "2024" or "2024-01"


def _format_date(month_name: str | None, year: str) -> str:
    if month_name:
        return f"{year}-{_MONTHS[month_name]:02d}"
    return year


def detect_temporal(normalized_query: str) -> TemporalIntent:
    """Detect temporal intent in a normalized (lowercase) query."""
    for pattern, direction in ((_BEFORE, "before"), (_AFTER, "after"), (_AT, "at")):
        match = pattern.search(normalized_query)
        if match:
            return TemporalIntent(
                is_temporal=True,
                direction=direction,
                target_date=_format_date(match.group(2), match.group(3)),
            )

    if _CURRENT_MARKERS.search(normalized_query):
        return TemporalIntent(is_temporal=True, direction="current", target_date=None)

    if _PAST_MARKERS.search(normalized_query):
        year = _BARE_YEAR.search(normalized_query)
        return TemporalIntent(
            is_temporal=True,
            direction="past",
            target_date=year.group(1) if year else None,
        )

    return TemporalIntent(is_temporal=False, direction=None, target_date=None)
