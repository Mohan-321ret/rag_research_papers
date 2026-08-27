"""Shared pytest fixtures.

Tests run against a throwaway SQLite database (the models use portable
column types), so neither PostgreSQL nor Neo4j needs to be running.
"""

import asyncio
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.database import get_db_session
from app.main import app
from app.models import Base


@pytest.fixture(scope="session")
def test_db_engine(tmp_path_factory: pytest.TempPathFactory) -> Iterator[object]:
    db_path: Path = tmp_path_factory.mktemp("db") / "test.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", poolclass=NullPool)

    async def _create_schema() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create_schema())
    yield engine
    asyncio.run(engine.dispose())


@pytest.fixture(autouse=True)
def override_db(test_db_engine: object) -> Iterator[None]:
    factory = async_sessionmaker(test_db_engine, expire_on_commit=False)  # type: ignore[arg-type]

    async def _get_test_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _get_test_session
    yield
    app.dependency_overrides.pop(get_db_session, None)


@pytest.fixture(autouse=True)
def temp_upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep uploads and vector indexes out of real data/ during tests."""
    from app.core.config import get_settings
    from app.modules.repository.vector_store import reset_vector_store
    from app.modules.retrieval.bm25_index import reset_bm25_index

    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr(get_settings(), "vector_index_dir", str(tmp_path / "vectors"))
    # Graph sync is exercised explicitly in graph tests, not on every upload.
    monkeypatch.setattr(get_settings(), "graph_auto_sync", False)
    # Deterministic answer generation without external credentials.
    monkeypatch.setattr(get_settings(), "llm_provider", "extractive")
    # Cross-encoder reranking is exercised explicitly in its own unit tests
    # (real model, real download); API tests use the passthrough reranker
    # for determinism and speed.
    monkeypatch.setattr(get_settings(), "reranker_enabled", False)
    # NLI evidence verification is exercised explicitly in its own unit
    # tests (real model); API tests skip it for determinism and speed.
    monkeypatch.setattr(get_settings(), "verification_enabled", False)
    # Knowledge evolution analysis (drift/conflict detection) is exercised
    # explicitly in its own tests; API tests skip it for speed.
    monkeypatch.setattr(get_settings(), "evolution_enabled", False)
    # Cross-document conflict detection (Phase 13) is exercised explicitly
    # in its own tests; API tests skip it for speed.
    monkeypatch.setattr(get_settings(), "conflict_detection_enabled", False)
    reset_vector_store()
    reset_bm25_index()
    yield
    reset_vector_store()
    reset_bm25_index()


class StubEmbedder:
    """Deterministic, dependency-free embedder for API tests.

    Produces stable normalized vectors derived from a hash of the text,
    so identical text always maps to the identical vector.

    Deliberately mirrors ``SentenceTransformerEmbedder``'s lazy-load
    contract — ``dimension`` raises until ``load()`` has run — because a
    stub that always knows its dimension hides real ordering bugs in
    callers (exactly how a "read dimension before loading" crash once got
    past the whole suite and only surfaced in a live run).
    """

    model_name = "stub-embedder"
    _DIMENSION = 16

    def __init__(self) -> None:
        self._loaded = False

    @property
    def dimension(self) -> int:
        if not self._loaded:
            raise RuntimeError("Embedding model not loaded yet; call embed_texts first")
        return self._DIMENSION

    async def load(self) -> None:
        self._loaded = True

    async def embed_texts(self, texts):
        import hashlib

        import numpy as np

        await self.load()
        vectors = []
        for text in texts:
            seed = int.from_bytes(hashlib.sha256(text.encode()).digest()[:4], "big")
            rng = np.random.default_rng(seed)
            vector = rng.standard_normal(self._DIMENSION)
            vectors.append((vector / np.linalg.norm(vector)).tolist())
        return vectors


@pytest.fixture(autouse=True)
def stub_embedder() -> Iterator[None]:
    """Replace the real sentence-transformers model in API tests.

    Unit and live tests exercise the real model; here determinism and
    speed matter more than embedding quality.
    """
    from app.api import deps
    from app.repositories.chunk_repository import ChunkRepository
    from app.repositories.conflict_repository import ConflictRepository
    from app.repositories.document_repository import DocumentRepository
    from app.repositories.evolution_repository import EvolutionRepository
    from app.repositories.knowledge_repository import KnowledgeRepository
    from app.services.conflict_service import ConflictService
    from app.services.evolution_service import EvolutionService
    from app.services.processing_service import ProcessingService

    from app.modules.context_fusion.reranker import PassthroughReranker
    from app.modules.repository.graph_store import GraphStore
    from app.modules.verification.nli_verifier import get_nli_verifier
    from app.repositories.interaction_repository import InteractionRepository
    from app.services.chat_service import ChatService
    from app.services.context_fusion_service import ContextFusionService
    from app.services.retrieval_service import RetrievalService
    from app.services.verification_service import VerificationService

    def evolution_override(
        settings: deps.SettingsDep, session: deps.DbSessionDep
    ) -> EvolutionService:
        return EvolutionService(
            settings,
            EvolutionRepository(session),
            ChunkRepository(session),
            StubEmbedder(),  # type: ignore[arg-type]
            get_nli_verifier(settings.verification_model_name, settings.evolution_enabled),
        )

    def conflict_override(
        settings: deps.SettingsDep, session: deps.DbSessionDep
    ) -> ConflictService:
        return ConflictService(
            settings,
            ConflictRepository(session),
            DocumentRepository(session),
            ChunkRepository(session),
            StubEmbedder(),  # type: ignore[arg-type]
            get_nli_verifier(
                settings.verification_model_name, settings.conflict_detection_enabled
            ),
        )

    def override(
        settings: deps.SettingsDep,
        session: deps.DbSessionDep,
        graph_service: deps.GraphServiceDep,
        evolution_service: deps.EvolutionServiceDep,
        conflict_service: deps.ConflictServiceDep,
    ) -> ProcessingService:
        return ProcessingService(
            settings,
            session,
            DocumentRepository(session),
            ChunkRepository(session),
            StubEmbedder(),  # type: ignore[arg-type]
            knowledge_repository=KnowledgeRepository(session),
            graph_service=graph_service,
            evolution_service=evolution_service,
            conflict_service=conflict_service,
        )

    def retrieval_override(
        settings: deps.SettingsDep,
        session: deps.DbSessionDep,
        neo4j_client: deps.Neo4jClientDep,
    ) -> RetrievalService:
        return RetrievalService(
            settings,
            ChunkRepository(session),
            StubEmbedder(),  # type: ignore[arg-type]
            GraphStore(neo4j_client),
        )

    def context_fusion_override(
        settings: deps.SettingsDep, session: deps.DbSessionDep
    ) -> ContextFusionService:
        return ContextFusionService(settings, PassthroughReranker(), ConflictRepository(session))

    def verification_override(
        settings: deps.SettingsDep, session: deps.DbSessionDep
    ) -> VerificationService:
        return VerificationService(
            settings,
            ChunkRepository(session),
            StubEmbedder(),  # type: ignore[arg-type]
            # Explicit args (not the no-arg call deps.py uses) so the
            # lru_cache key reflects *this test's* verification_enabled,
            # not whatever the first test in the process happened to set.
            get_nli_verifier(settings.verification_model_name, settings.verification_enabled),
        )

    def chat_override(
        settings: deps.SettingsDep,
        session: deps.DbSessionDep,
        query_intelligence: deps.QueryIntelligenceServiceDep,
        retrieval: deps.RetrievalServiceDep,
        context_fusion: deps.ContextFusionServiceDep,
        verification: deps.VerificationServiceDep,
    ) -> ChatService:
        return ChatService(
            settings,
            session,
            InteractionRepository(session),
            query_intelligence,
            retrieval,
            context_fusion,
            verification,
        )

    app.dependency_overrides[deps.get_processing_service] = override
    app.dependency_overrides[deps.get_evolution_service] = evolution_override
    app.dependency_overrides[deps.get_conflict_service] = conflict_override
    app.dependency_overrides[deps.get_retrieval_service] = retrieval_override
    app.dependency_overrides[deps.get_context_fusion_service] = context_fusion_override
    app.dependency_overrides[deps.get_verification_service] = verification_override
    app.dependency_overrides[deps.get_chat_service] = chat_override
    yield
    app.dependency_overrides.pop(deps.get_processing_service, None)
    app.dependency_overrides.pop(deps.get_evolution_service, None)
    app.dependency_overrides.pop(deps.get_conflict_service, None)
    app.dependency_overrides.pop(deps.get_retrieval_service, None)
    app.dependency_overrides.pop(deps.get_context_fusion_service, None)
    app.dependency_overrides.pop(deps.get_verification_service, None)
    app.dependency_overrides.pop(deps.get_chat_service, None)


@pytest.fixture
def client() -> Iterator[TestClient]:
    """HTTP client against the app, with lifespan startup/shutdown."""
    with TestClient(app) as test_client:
        yield test_client


def _build_minimal_pdf(text: str) -> bytes:
    """Assemble a small valid one-page PDF (correct xref) with optional text."""
    stream = f"BT /F1 18 Tf 72 720 Td ({text}) Tj ET".encode("latin-1") if text else b""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF"
    ).encode()
    return bytes(out)


@pytest.fixture
def minimal_pdf_factory():
    return _build_minimal_pdf


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    """Register a fresh user and return their Authorization header."""
    import uuid as _uuid

    email = f"user-{_uuid.uuid4().hex[:12]}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "secret-password-1", "full_name": "Test User"},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
