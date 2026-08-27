"""Tests for authority resolution (Phase 13): given two contradicting
claims from different documents, which one should be preferred?
"""

import uuid
from datetime import UTC, datetime

from app.modules.conflict.authority_resolver import DocumentAuthority, resolve_authority

_JAN = datetime(2024, 1, 1, tzinfo=UTC)
_JUN = datetime(2024, 6, 1, tzinfo=UTC)


def _authority(**overrides) -> DocumentAuthority:
    defaults = dict(
        document_id=uuid.uuid4(),
        chunk_id=uuid.uuid4(),
        document_title="Doc",
        department=None,
        priority=0,
        version_number=1,
        version_created_at=_JAN,
    )
    defaults.update(overrides)
    return DocumentAuthority(**defaults)


def test_higher_priority_wins() -> None:
    a = _authority(document_title="Legal Policy", priority=5)
    b = _authority(document_title="Draft Notes", priority=1)
    result = resolve_authority(a, b)
    assert result.resolved is True
    assert result.preferred_chunk_id == a.chunk_id
    assert "Legal Policy" in result.reason
    assert "priority" in result.reason.lower()


def test_higher_priority_wins_regardless_of_argument_order() -> None:
    a = _authority(priority=1)
    b = _authority(priority=5)
    result = resolve_authority(a, b)
    assert result.preferred_chunk_id == b.chunk_id


def test_tied_priority_falls_back_to_more_recent_date() -> None:
    a = _authority(document_title="Old Doc", priority=3, version_created_at=_JAN)
    b = _authority(document_title="New Doc", priority=3, version_created_at=_JUN)
    result = resolve_authority(a, b)
    assert result.resolved is True
    assert result.preferred_chunk_id == b.chunk_id
    assert "New Doc" in result.reason


def test_tied_priority_and_date_falls_back_to_version_number() -> None:
    a = _authority(document_title="v1 Doc", priority=0, version_created_at=_JAN, version_number=1)
    b = _authority(document_title="v3 Doc", priority=0, version_created_at=_JAN, version_number=3)
    result = resolve_authority(a, b)
    assert result.resolved is True
    assert result.preferred_chunk_id == b.chunk_id
    assert "v3 Doc" in result.reason


def test_full_tie_is_unresolved() -> None:
    a = _authority(document_title="Doc A")
    b = _authority(document_title="Doc B")
    result = resolve_authority(a, b)
    assert result.resolved is False
    assert result.preferred_chunk_id is None
    assert "unresolved" in result.reason.lower()


def test_department_alone_never_breaks_a_tie() -> None:
    """Department is informational only — there's no universal ranking of
    one department over another without organization-specific rules."""
    a = _authority(department="Legal")
    b = _authority(department="Facilities")
    result = resolve_authority(a, b)
    assert result.resolved is False
