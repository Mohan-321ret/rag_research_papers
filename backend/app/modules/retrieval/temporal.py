"""Resolves a query's temporal intent (Module 5) to a retrieval cutoff.

Old document versions are never deleted — they stay in PostgreSQL, FAISS,
and Neo4j precisely so a query like "what was the policy in 2023?" can be
answered from what was true then, not from whatever is current now. This
module turns ``(direction, target_date)`` into the datetime cutoff
retrieval filters chunks by: "the version active as of this moment."

Only "before"/"at"/"past" directions resolve to a cutoff. "after" doesn't
have a clean point-in-time reading (it names a range, not a moment) and
"current"/no intent both mean "use whatever is current" — the default
behavior with no cutoff at all.
"""

from datetime import UTC, datetime

_CUTOFF_DIRECTIONS = frozenset({"before", "at", "past"})


def resolve_as_of_cutoff(direction: str | None, target_date: str | None) -> datetime | None:
    """Return an exclusive upper bound: versions with ``created_at`` before
    this instant were active as of the query's target date.

    ``target_date`` is "YYYY" or "YYYY-MM" (see query_intelligence.temporal).
    "before 2024" -> versions created before 2024-01-01.
    "in 2023" / "as of 2023" -> versions created before 2024-01-01 (i.e.
    anything that existed by the end of 2023).
    """
    if direction not in _CUTOFF_DIRECTIONS or not target_date:
        return None

    parts = target_date.split("-")
    year = int(parts[0])
    month = int(parts[1]) if len(parts) > 1 else None

    if direction == "before":
        if month:
            return datetime(year, month, 1, tzinfo=UTC)
        return datetime(year, 1, 1, tzinfo=UTC)

    # "at" / "past": the cutoff is the start of the period *after* the
    # target one, i.e. everything created by the end of the target period.
    if month:
        year, month = (year, month + 1) if month < 12 else (year + 1, 1)
        return datetime(year, month, 1, tzinfo=UTC)
    return datetime(year + 1, 1, 1, tzinfo=UTC)
