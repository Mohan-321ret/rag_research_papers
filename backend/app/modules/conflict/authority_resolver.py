"""Authority resolution — given two contradicting claims from different
documents, which one should be preferred?

    Claim A  <->  Contradiction  <->  Claim B
                       |
             priority -> date -> version -> unresolved

Both candidate chunks are always current-version content (conflict
detection only ever compares live corpus chunks — Phase 11 already
covers old-vs-new versions of the *same* document), so version currency
never applies here. Department is carried on each side for display, but
deliberately isn't ranked automatically: there's no universal ordering
of "HR" vs "Legal" vs "Facilities" without organization-specific rules,
so treating one as inherently more authoritative would be a fabricated
signal, not a real one.

Resolution stops at the first factor that isn't a tie. If priority,
date, and version all tie, the conflict is reported unresolved rather
than broken arbitrarily — that's a real outcome (Context Fusion keeps
both claims and flags the disagreement) not a bug.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class DocumentAuthority:
    """One side of a cross-document conflict, with everything the
    resolver needs to judge it."""

    document_id: uuid.UUID
    chunk_id: uuid.UUID
    document_title: str
    department: str | None
    priority: int
    version_number: int
    version_created_at: datetime


@dataclass(frozen=True, slots=True)
class ResolutionResult:
    preferred_chunk_id: uuid.UUID | None  # None when unresolved
    resolved: bool
    reason: str


def resolve_authority(a: DocumentAuthority, b: DocumentAuthority) -> ResolutionResult:
    if a.priority != b.priority:
        winner, loser = (a, b) if a.priority > b.priority else (b, a)
        return ResolutionResult(
            winner.chunk_id, True,
            f"{winner.document_title!r} has higher document priority "
            f"({winner.priority} > {loser.priority})",
        )

    if a.version_created_at != b.version_created_at:
        winner, loser = (
            (a, b) if a.version_created_at > b.version_created_at else (b, a)
        )
        return ResolutionResult(
            winner.chunk_id, True,
            f"{winner.document_title!r} is more recent "
            f"({winner.version_created_at.date()} > {loser.version_created_at.date()})",
        )

    if a.version_number != b.version_number:
        winner, loser = (a, b) if a.version_number > b.version_number else (b, a)
        return ResolutionResult(
            winner.chunk_id, True,
            f"{winner.document_title!r} is on a later version "
            f"(v{winner.version_number} > v{loser.version_number})",
        )

    return ResolutionResult(
        None, False,
        f"{a.document_title!r} and {b.document_title!r} tie on priority, date, "
        "and version — unresolved, both claims kept",
    )
