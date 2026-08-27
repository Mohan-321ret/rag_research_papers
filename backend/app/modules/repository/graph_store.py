"""Neo4j knowledge graph store.

Graph model (the third leg of the hybrid repository, next to PostgreSQL
and FAISS):

    (Document)-[:HAS_VERSION]->(Version)-[:CONTAINS]->(Chunk)
    (Chunk)-[:MENTIONS]->(Entity)
    (Version)-[:SUPERSEDES]->(Version)          # newer -> older
    (Document)-[:AUTHORED_BY]->(Author)
    (Document)-[:BELONGS_TO]->(Department)
    (Document)-[:HAS_TOPIC]->(Topic)

All writes are idempotent MERGEs, so re-syncing a document converges to
the same graph.
"""

from typing import Any

from neo4j.exceptions import Neo4jError, ServiceUnavailable

from app.core.exceptions import ServiceUnavailableError
from app.core.logging import get_logger
from app.core.neo4j import Neo4jClient

logger = get_logger(__name__)

_SCHEMA_STATEMENTS = [
    "CREATE CONSTRAINT document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
    "CREATE CONSTRAINT version_id IF NOT EXISTS FOR (v:Version) REQUIRE v.id IS UNIQUE",
    "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT entity_key IF NOT EXISTS FOR (e:Entity) REQUIRE e.key IS UNIQUE",
    "CREATE CONSTRAINT author_name IF NOT EXISTS FOR (a:Author) REQUIRE a.name IS UNIQUE",
    "CREATE CONSTRAINT department_name IF NOT EXISTS FOR (d:Department) REQUIRE d.name IS UNIQUE",
    "CREATE CONSTRAINT topic_name IF NOT EXISTS FOR (t:Topic) REQUIRE t.name IS UNIQUE",
]


def _wrap_unavailable(exc: Exception) -> ServiceUnavailableError:
    return ServiceUnavailableError(
        "Knowledge graph unavailable: cannot reach Neo4j "
        f"({type(exc).__name__})"
    )


class GraphStore:
    """Idempotent graph synchronization and queries against Neo4j."""

    def __init__(self, client: Neo4jClient) -> None:
        self._client = client
        self._schema_ready = False

    async def ensure_schema(self) -> None:
        if self._schema_ready:
            return
        try:
            async with self._client.driver.session() as session:
                for statement in _SCHEMA_STATEMENTS:
                    await session.run(statement)
            self._schema_ready = True
        except (ServiceUnavailable, OSError, Neo4jError) as exc:
            raise _wrap_unavailable(exc) from exc

    async def sync_document(self, payload: dict[str, Any]) -> dict[str, int]:
        """Merge a document with versions, chunks, entities and context nodes.

        ``payload`` shape::

            {
              "document": {"id", "title", "status", "source_type"},
              "author": str | None,
              "department": str | None,
              "topics": [str, ...],
              "versions": [{"id", "version_number", "content_hash",
                            "is_current", "created_at"}, ...],   # ascending
              "chunks": [{"id", "version_id", "chunk_index", "section",
                          "page_number",
                          "entities": [{"name", "entity_type"}, ...]}, ...],
            }
        """
        await self.ensure_schema()
        try:
            async with self._client.driver.session() as session:
                return await session.execute_write(self._sync_tx, payload)
        except (ServiceUnavailable, OSError) as exc:
            raise _wrap_unavailable(exc) from exc

    @staticmethod
    async def _sync_tx(tx: Any, payload: dict[str, Any]) -> dict[str, int]:
        doc = payload["document"]
        await tx.run(
            """
            MERGE (d:Document {id: $id})
            SET d.title = $title, d.status = $status, d.source_type = $source_type
            """,
            **doc,
        )
        if payload.get("author"):
            await tx.run(
                """
                MATCH (d:Document {id: $doc_id})
                MERGE (a:Author {name: $author})
                MERGE (d)-[:AUTHORED_BY]->(a)
                """,
                doc_id=doc["id"],
                author=payload["author"],
            )
        if payload.get("department"):
            await tx.run(
                """
                MATCH (d:Document {id: $doc_id})
                MERGE (dep:Department {name: $department})
                MERGE (d)-[:BELONGS_TO]->(dep)
                """,
                doc_id=doc["id"],
                department=payload["department"],
            )
        await tx.run(
            """
            MATCH (d:Document {id: $doc_id})
            UNWIND $topics AS topic
            MERGE (t:Topic {name: topic})
            MERGE (d)-[:HAS_TOPIC]->(t)
            """,
            doc_id=doc["id"],
            topics=payload.get("topics", []),
        )

        await tx.run(
            """
            MATCH (d:Document {id: $doc_id})
            UNWIND $versions AS version
            MERGE (v:Version {id: version.id})
            SET v.version_number = version.version_number,
                v.content_hash = version.content_hash,
                v.is_current = version.is_current,
                v.created_at = version.created_at
            MERGE (d)-[:HAS_VERSION]->(v)
            """,
            doc_id=doc["id"],
            versions=payload["versions"],
        )
        # SUPERSEDES chain: newer version -> the one it replaces.
        await tx.run(
            """
            UNWIND $pairs AS pair
            MATCH (newer:Version {id: pair.newer})
            MATCH (older:Version {id: pair.older})
            MERGE (newer)-[:SUPERSEDES]->(older)
            """,
            pairs=[
                {"newer": b["id"], "older": a["id"]}
                for a, b in zip(payload["versions"], payload["versions"][1:])
            ],
        )

        await tx.run(
            """
            UNWIND $chunks AS chunk
            MATCH (v:Version {id: chunk.version_id})
            MERGE (c:Chunk {id: chunk.id})
            SET c.chunk_index = chunk.chunk_index,
                c.section = chunk.section,
                c.page_number = chunk.page_number
            MERGE (v)-[:CONTAINS]->(c)
            """,
            chunks=payload["chunks"],
        )
        await tx.run(
            """
            UNWIND $mentions AS m
            MATCH (c:Chunk {id: m.chunk_id})
            MERGE (e:Entity {key: m.key})
            SET e.name = m.name, e.entity_type = m.entity_type
            MERGE (c)-[:MENTIONS]->(e)
            """,
            mentions=[
                {
                    "chunk_id": chunk["id"],
                    "key": f"{entity['entity_type']}:{entity['name']}",
                    "name": entity["name"],
                    "entity_type": entity["entity_type"],
                }
                for chunk in payload["chunks"]
                for entity in chunk.get("entities", [])
            ],
        )

        counts_result = await tx.run(
            """
            MATCH (d:Document {id: $doc_id})-[:HAS_VERSION]->(v:Version)
            OPTIONAL MATCH (v)-[:CONTAINS]->(c:Chunk)
            OPTIONAL MATCH (c)-[:MENTIONS]->(e:Entity)
            RETURN count(DISTINCT v) AS versions,
                   count(DISTINCT c) AS chunks,
                   count(DISTINCT e) AS entities
            """,
            doc_id=doc["id"],
        )
        record = await counts_result.single()
        return {
            "versions": record["versions"],
            "chunks": record["chunks"],
            "entities": record["entities"],
            "topics": len(payload.get("topics", [])),
        }

    async def delete_document(self, document_id: str) -> None:
        """Remove a document with its versions and chunks (entities/topics stay)."""
        try:
            async with self._client.driver.session() as session:
                await session.run(
                    """
                    MATCH (d:Document {id: $id})
                    OPTIONAL MATCH (d)-[:HAS_VERSION]->(v:Version)
                    OPTIONAL MATCH (v)-[:CONTAINS]->(c:Chunk)
                    DETACH DELETE d, v, c
                    """,
                    id=document_id,
                )
        except (ServiceUnavailable, OSError) as exc:
            raise _wrap_unavailable(exc) from exc

    async def chunks_mentioning(
        self, entity_terms: list[str], *, limit: int = 20
    ) -> list[tuple[str, float]]:
        """Chunk ids whose entities match the query terms (graph retrieval).

        Direct mentions score 1.0 per matched entity; a one-hop expansion
        over co-mentioned entities contributes 0.5 — the "multi-hop" part
        of graph retrieval. Only current versions' chunks are returned.
        """
        if not entity_terms:
            return []
        terms = [t.lower() for t in entity_terms]
        try:
            async with self._client.driver.session() as session:
                direct = await session.run(
                    """
                    UNWIND $terms AS term
                    MATCH (e:Entity) WHERE toLower(e.name) CONTAINS term
                    MATCH (c:Chunk)-[:MENTIONS]->(e)
                    MATCH (v:Version {is_current: true})-[:CONTAINS]->(c)
                    RETURN c.id AS chunk_id, count(DISTINCT e) AS matches
                    ORDER BY matches DESC LIMIT $limit
                    """,
                    terms=terms,
                    limit=limit,
                )
                scores: dict[str, float] = {
                    r["chunk_id"]: float(r["matches"]) async for r in direct
                }
                hop = await session.run(
                    """
                    UNWIND $terms AS term
                    MATCH (e:Entity) WHERE toLower(e.name) CONTAINS term
                    MATCH (e)<-[:MENTIONS]-(:Chunk)-[:MENTIONS]->(related:Entity)
                    WHERE related <> e
                    MATCH (c:Chunk)-[:MENTIONS]->(related)
                    MATCH (v:Version {is_current: true})-[:CONTAINS]->(c)
                    RETURN c.id AS chunk_id, count(DISTINCT related) AS matches
                    ORDER BY matches DESC LIMIT $limit
                    """,
                    terms=terms,
                    limit=limit,
                )
                async for record in hop:
                    chunk_id = record["chunk_id"]
                    scores[chunk_id] = scores.get(chunk_id, 0.0) + 0.5 * float(
                        record["matches"]
                    )
        except (ServiceUnavailable, OSError, Neo4jError) as exc:
            raise _wrap_unavailable(exc) from exc

        return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:limit]

    async def stats(self) -> dict[str, Any]:
        try:
            async with self._client.driver.session() as session:
                labels_result = await session.run(
                    "MATCH (n) UNWIND labels(n) AS label "
                    "RETURN label, count(*) AS count ORDER BY label"
                )
                nodes = {r["label"]: r["count"] async for r in labels_result}
                rels_result = await session.run(
                    "MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS count "
                    "ORDER BY type"
                )
                relationships = {r["type"]: r["count"] async for r in rels_result}
        except (ServiceUnavailable, OSError, Neo4jError) as exc:
            raise _wrap_unavailable(exc) from exc
        return {"nodes": nodes, "relationships": relationships}

    async def document_graph(self, document_id: str) -> dict[str, Any] | None:
        """Neighborhood summary of one document."""
        try:
            async with self._client.driver.session() as session:
                result = await session.run(
                    """
                    MATCH (d:Document {id: $id})
                    OPTIONAL MATCH (d)-[:HAS_VERSION]->(v:Version)
                    OPTIONAL MATCH (v)-[:CONTAINS]->(c:Chunk)
                    OPTIONAL MATCH (c)-[:MENTIONS]->(e:Entity)
                    OPTIONAL MATCH (d)-[:AUTHORED_BY]->(a:Author)
                    OPTIONAL MATCH (d)-[:BELONGS_TO]->(dep:Department)
                    OPTIONAL MATCH (d)-[:HAS_TOPIC]->(t:Topic)
                    RETURN d.title AS title,
                           collect(DISTINCT {id: v.id, number: v.version_number,
                                             is_current: v.is_current}) AS versions,
                           count(DISTINCT c) AS chunk_count,
                           collect(DISTINCT {name: e.name, type: e.entity_type})
                               AS entities,
                           collect(DISTINCT a.name) AS authors,
                           collect(DISTINCT dep.name) AS departments,
                           collect(DISTINCT t.name) AS topics
                    """,
                    id=document_id,
                )
                record = await result.single()
        except (ServiceUnavailable, OSError, Neo4jError) as exc:
            raise _wrap_unavailable(exc) from exc

        if record is None or record["title"] is None:
            return None
        versions = sorted(
            (v for v in record["versions"] if v["id"] is not None),
            key=lambda v: v["number"],
        )
        return {
            "document_id": document_id,
            "title": record["title"],
            "versions": versions,
            "chunk_count": record["chunk_count"],
            "entities": [e for e in record["entities"] if e["name"] is not None],
            "authors": record["authors"],
            "departments": record["departments"],
            "topics": record["topics"],
        }
