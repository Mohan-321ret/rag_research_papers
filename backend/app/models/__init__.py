"""SQLAlchemy ORM models.

All model classes are imported here so Alembic autogenerate sees them
via ``Base.metadata``.
"""

from app.models.base import Base
from app.models.conflict import KnowledgeConflict
from app.models.document import Document, DocumentChunk, DocumentStatus, DocumentVersion
from app.models.evolution import ConceptDriftReport, VersionComparison
from app.models.interaction import (
    Answer,
    Citation,
    Feedback,
    FeedbackRating,
    Query,
    RetrievalLog,
)
from app.models.knowledge import KnowledgeEntity, KnowledgeRelationship
from app.models.system import AuditLog, SystemMetric
from app.models.user import User, UserRole

__all__ = [
    "Answer",
    "AuditLog",
    "Base",
    "Citation",
    "ConceptDriftReport",
    "Document",
    "DocumentChunk",
    "DocumentStatus",
    "DocumentVersion",
    "Feedback",
    "FeedbackRating",
    "KnowledgeConflict",
    "KnowledgeEntity",
    "KnowledgeRelationship",
    "Query",
    "RetrievalLog",
    "SystemMetric",
    "User",
    "UserRole",
    "VersionComparison",
]
