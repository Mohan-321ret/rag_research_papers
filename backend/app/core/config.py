"""Application configuration loaded from environment variables / .env file."""

import json
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings.

    Values are read from environment variables first, then from the
    ``.env`` file in the working directory (``backend/``).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "DAA-RAG Backend"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production", "test"] = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # Logging
    log_level: str = "INFO"
    log_json: bool = False

    # PostgreSQL (async SQLAlchemy URL)
    database_url: str = (
        "postgresql+asyncpg://daarag:daarag@localhost:5432/rag_research_paper"
    )
    database_echo: bool = False
    database_pool_size: int = 5
    database_max_overflow: int = 10
    database_connect_timeout_seconds: float = 5.0

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "daarag-neo4j"

    # Auth: a single long-lived access token (simple flow, no refresh tokens)
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7
    refresh_token_expire_minutes: int = 60 * 24 * 7

    # Ingestion
    upload_dir: str = "data/uploads"
    max_upload_size_mb: int = 25
    ocr_enabled: bool = True

    # Processing (chunking + embeddings)
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    vector_index_dir: str = "data/vector_index"
    chunk_target_tokens: int = 300
    chunk_overlap_sentences: int = 1
    auto_process_on_upload: bool = True

    # Knowledge graph
    graph_auto_sync: bool = True

    # Incremental re-indexing (Phase 14): reuse the stored embedding of any
    # chunk whose content is byte-identical to one already indexed, so a
    # changed document only pays for the chunks that actually changed.
    # Turn off for the paper's full-rebuild ablation baseline.
    incremental_reindex_enabled: bool = True

    # Retrieval (baseline RAG)
    retrieval_min_score: float = 0.2

    # Enterprise LLM (Module 8): provider behind a narrow generate(prompt)
    # interface. "auto" prefers Anthropic when credentials are configured
    # (backward compatible with earlier phases), else Ollama — the
    # zero-credential local default this module starts with.
    llm_provider: Literal["auto", "ollama", "anthropic", "extractive"] = "auto"
    llm_max_tokens: int = 1024

    llm_model: str = "claude-opus-5"  # used when the Anthropic provider is active

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3:4b"  # any pulled Ollama model, e.g. llama3.2, gemma2
    ollama_timeout_seconds: float = 60.0

    # Context fusion (dedup -> rerank -> compression -> context builder)
    retrieval_candidate_k: int = 20  # candidate pool fetched before fusion
    context_top_k: int = 6  # final chunks sent to the LLM (spec range: 5-8)
    reranker_enabled: bool = True
    reranker_model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # Evidence verification (Module 9): claim extraction -> per-claim
    # evidence retrieval -> NLI fact verification -> confidence scoring ->
    # hallucination detection -> response refinement. Uses a dedicated NLI
    # cross-encoder (entailment/contradiction/neutral) rather than the
    # Module 7 relevance reranker, which cannot distinguish "same topic"
    # from "same fact" (e.g. "20 days" vs "25 days" of leave).
    verification_enabled: bool = True
    verification_model_name: str = "cross-encoder/nli-deberta-v3-xsmall"
    verification_support_threshold: float = 0.5
    verification_min_evidence_score: float = 0.2

    # Knowledge evolution (Module 3): Change Detector -> Diff Detector
    # (text) + Drift Detector (semantic, embedding centroids) -> Conflict
    # Detector (NLI over replaced sentence pairs, reusing the Module 9
    # model). Runs after each new version is processed.
    evolution_enabled: bool = True
    evolution_conflict_threshold: float = 0.5

    # Concept Drift Detection (Phase 12): chunk-level, embedding
    # nearest-neighbor comparison. A matched chunk pair with cosine
    # distance above this is flagged and classified (rewording/expansion/
    # narrowing/contradiction/topic_shift) via bidirectional NLI.
    concept_drift_threshold: float = 0.15

    # Knowledge Conflict Detection (Phase 13): cross-document contradiction
    # search. For each new chunk, a corpus-wide vector search (excluding
    # its own document) finds same-topic candidates above
    # conflict_similarity_threshold; NLI then flags a contradiction above
    # conflict_contradiction_threshold. Detected conflicts are resolved by
    # metadata (priority -> date -> version) at detection time, then
    # looked up (cheaply, no live NLI) by Context Fusion at query time.
    conflict_detection_enabled: bool = True
    conflict_similarity_threshold: float = 0.5
    conflict_contradiction_threshold: float = 0.5

    # CORS — origins of the existing frontend (Vite dev + preview servers)
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
    ]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept CORS_ORIGINS as a comma-separated string or a JSON list."""
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                return json.loads(stripped)
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Return the (cached) application settings."""
    return Settings()
