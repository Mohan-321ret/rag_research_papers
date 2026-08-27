"""Persistent local vector stores implementing the VectorIndex contract.

Two real implementations:

- ``FaissVectorStore`` — FAISS ``IndexIDMap2`` over an inner-product flat
  index (vectors are L2-normalized upstream, so IP == cosine).
- ``NumpyVectorStore`` — exact brute-force search; used automatically
  when faiss has no wheels for the running interpreter.

Both persist under ``VECTOR_INDEX_DIR`` together with ``meta.json``
(dimension, embedding model, next id) and hand out monotonically
increasing int64 ids; the id is stored on each chunk row
(``embedding_ref``), which keeps the Embedding -> Chunk -> Version ->
Document relationship in PostgreSQL.
"""

import asyncio
import importlib.util
import json
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from app.core.logging import get_logger
from app.modules.repository.interfaces import VectorSearchHit

logger = get_logger(__name__)

_META_FILE = "meta.json"


def faiss_available() -> bool:
    return importlib.util.find_spec("faiss") is not None


class _LocalVectorStoreBase:
    """Shared persistence, id allocation and locking."""

    def __init__(self, directory: Path, dimension: int, model_name: str) -> None:
        self._dir = directory
        self._dim = dimension
        self._model_name = model_name
        self._next_id = 1
        self._lock = asyncio.Lock()
        self._dir.mkdir(parents=True, exist_ok=True)
        self._load_meta()
        self._load_vectors()

    # -- meta ---------------------------------------------------------------

    def _load_meta(self) -> None:
        meta_path = self._dir / _META_FILE
        if not meta_path.exists():
            return
        meta = json.loads(meta_path.read_text())
        if meta.get("dimension") != self._dim:
            raise RuntimeError(
                f"Vector index at {self._dir} has dimension {meta.get('dimension')}, "
                f"but the embedding model produces {self._dim}. "
                "Delete the index directory to rebuild."
            )
        self._next_id = int(meta.get("next_id", 1))

    def _save_meta(self) -> None:
        (self._dir / _META_FILE).write_text(
            json.dumps(
                {
                    "dimension": self._dim,
                    "model": self._model_name,
                    "next_id": self._next_id,
                    "backend": type(self).__name__,
                }
            )
        )

    def _allocate_ids(self, count: int) -> list[int]:
        ids = list(range(self._next_id, self._next_id + count))
        self._next_id += count
        return ids

    # -- public API ---------------------------------------------------------

    @property
    def dimension(self) -> int:
        return self._dim

    async def add(self, vectors: Sequence[Sequence[float]]) -> list[int]:
        """Add vectors, returning their assigned int64 ids."""
        if not vectors:
            return []
        matrix = np.asarray(vectors, dtype=np.float32)
        async with self._lock:
            ids = self._allocate_ids(len(vectors))
            self._add_sync(matrix, np.asarray(ids, dtype=np.int64))
            self._persist()
        return ids

    async def remove(self, ids: Sequence[int]) -> None:
        if not ids:
            return
        async with self._lock:
            self._remove_sync(np.asarray(list(ids), dtype=np.int64))
            self._persist()

    async def search(self, vector: Sequence[float], k: int) -> list[VectorSearchHit]:
        query = np.asarray([vector], dtype=np.float32)
        async with self._lock:
            return self._search_sync(query, k)

    async def reconstruct(self, ids: Sequence[int]) -> dict[int, list[float]]:
        """Read stored vectors back by id (incremental re-indexing).

        Lets an unchanged chunk keep its existing embedding instead of
        paying for another transformer forward pass. Ids that are no
        longer in the index are simply absent from the result, so callers
        can fall back to embedding those.
        """
        if not ids:
            return {}
        async with self._lock:
            return self._reconstruct_sync([int(i) for i in ids])

    async def count(self) -> int:
        async with self._lock:
            return self._count_sync()

    def _persist(self) -> None:
        self._save_vectors()
        self._save_meta()

    # -- backend hooks ------------------------------------------------------

    def _load_vectors(self) -> None: ...

    def _save_vectors(self) -> None: ...

    def _add_sync(self, matrix: np.ndarray, ids: np.ndarray) -> None: ...

    def _remove_sync(self, ids: np.ndarray) -> None: ...

    def _search_sync(self, query: np.ndarray, k: int) -> list[VectorSearchHit]: ...

    def _reconstruct_sync(self, ids: list[int]) -> dict[int, list[float]]: ...

    def _count_sync(self) -> int: ...


class FaissVectorStore(_LocalVectorStoreBase):
    """FAISS-backed store (inner product over normalized vectors)."""

    def _index_path(self) -> Path:
        return self._dir / "index.faiss"

    def _load_vectors(self) -> None:
        import faiss

        if self._index_path().exists():
            self._index = faiss.read_index(str(self._index_path()))
        else:
            self._index = faiss.IndexIDMap2(faiss.IndexFlatIP(self._dim))

    def _save_vectors(self) -> None:
        import faiss

        faiss.write_index(self._index, str(self._index_path()))

    def _add_sync(self, matrix: np.ndarray, ids: np.ndarray) -> None:
        self._index.add_with_ids(matrix, ids)

    def _remove_sync(self, ids: np.ndarray) -> None:
        self._index.remove_ids(ids)

    def _search_sync(self, query: np.ndarray, k: int) -> list[VectorSearchHit]:
        if self._index.ntotal == 0:
            return []
        scores, ids = self._index.search(query, min(k, self._index.ntotal))
        return [
            VectorSearchHit(chunk_id=str(int(i)), score=float(s))
            for i, s in zip(ids[0], scores[0])
            if i != -1
        ]

    def _reconstruct_sync(self, ids: list[int]) -> dict[int, list[float]]:
        found: dict[int, list[float]] = {}
        for vector_id in ids:
            try:
                found[vector_id] = self._index.reconstruct(vector_id).tolist()
            except RuntimeError:
                # Not in the index (removed, or never added) — caller re-embeds.
                continue
        return found

    def _count_sync(self) -> int:
        return int(self._index.ntotal)


class NumpyVectorStore(_LocalVectorStoreBase):
    """Exact brute-force store for interpreters without faiss wheels."""

    def _npz_path(self) -> Path:
        return self._dir / "vectors.npz"

    def _load_vectors(self) -> None:
        if self._npz_path().exists():
            data = np.load(self._npz_path())
            self._matrix = data["vectors"].astype(np.float32)
            self._ids = data["ids"].astype(np.int64)
        else:
            self._matrix = np.empty((0, self._dim), dtype=np.float32)
            self._ids = np.empty((0,), dtype=np.int64)

    def _save_vectors(self) -> None:
        np.savez(self._npz_path(), vectors=self._matrix, ids=self._ids)

    def _add_sync(self, matrix: np.ndarray, ids: np.ndarray) -> None:
        self._matrix = np.vstack([self._matrix, matrix])
        self._ids = np.concatenate([self._ids, ids])

    def _remove_sync(self, ids: np.ndarray) -> None:
        mask = ~np.isin(self._ids, ids)
        self._matrix = self._matrix[mask]
        self._ids = self._ids[mask]

    def _search_sync(self, query: np.ndarray, k: int) -> list[VectorSearchHit]:
        if len(self._ids) == 0:
            return []
        scores = self._matrix @ query[0]
        top = np.argsort(-scores)[:k]
        return [
            VectorSearchHit(chunk_id=str(int(self._ids[i])), score=float(scores[i]))
            for i in top
        ]

    def _reconstruct_sync(self, ids: list[int]) -> dict[int, list[float]]:
        wanted = set(ids)
        return {
            int(stored_id): self._matrix[position].tolist()
            for position, stored_id in enumerate(self._ids)
            if int(stored_id) in wanted
        }

    def _count_sync(self) -> int:
        return len(self._ids)


_store_instance: _LocalVectorStoreBase | None = None
_store_creation_lock = asyncio.Lock()


async def get_vector_store(
    directory: str | Path, dimension: int, model_name: str
) -> _LocalVectorStoreBase:
    """Return the shared vector store, creating it on first use."""
    global _store_instance
    async with _store_creation_lock:
        if _store_instance is None:
            backend = FaissVectorStore if faiss_available() else NumpyVectorStore
            if backend is NumpyVectorStore:
                logger.warning(
                    "faiss_unavailable_using_numpy_store",
                    hint="install faiss-cpu (or use the Docker image) for FAISS",
                )
            _store_instance = backend(Path(directory), dimension, model_name)
        return _store_instance


async def get_existing_vector_store(
    directory: str | Path,
) -> _LocalVectorStoreBase | None:
    """Return the store only if one already exists on disk (or in memory).

    Lets maintenance paths (e.g. deleting a document's vectors) work
    without forcing the embedding model to load just to learn the
    dimension — it is read from the persisted meta.json instead.
    """
    global _store_instance
    async with _store_creation_lock:
        if _store_instance is not None:
            return _store_instance
        meta_path = Path(directory) / _META_FILE
        if not meta_path.exists():
            return None
        meta = json.loads(meta_path.read_text())
        backend = FaissVectorStore if faiss_available() else NumpyVectorStore
        _store_instance = backend(
            Path(directory), int(meta["dimension"]), str(meta.get("model", ""))
        )
        return _store_instance


def reset_vector_store() -> None:
    """Testing hook: drop the cached store instance."""
    global _store_instance
    _store_instance = None
