"""DAA-RAG domain modules.

Each subpackage owns one stage of the Drift-Aware Adaptive RAG pipeline
and currently exposes only its public interface (abstract contracts).
Concrete implementations arrive in later phases:

- ingestion:          document acquisition from enterprise sources
- processing:         chunking and embedding
- evolution:          knowledge/embedding drift detection and versioning
- repository:         vector (FAISS) and graph (Neo4j) knowledge stores
- query_intelligence: query analysis, rewriting and routing
- retrieval:          drift-aware retrieval strategies
- context_fusion:     merging retrieved evidence into a model context
- llm:                LLM client abstraction (LangChain-backed)
- verification:       grounding / faithfulness checks on answers
- learning:           feedback capture and adaptive improvement
"""
