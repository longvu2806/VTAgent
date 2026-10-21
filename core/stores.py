"""Storage: chunk index in Qdrant, registry of indexed documents in SQLite."""

from __future__ import annotations

import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

from core.models import Chunk, DocumentRecord, RetrievedChunk, SparseVector

if TYPE_CHECKING:
    from qdrant_client import QdrantClient

DENSE = "dense"  # vector names, shared by every config (SAD 7.3)
SPARSE = "sparse"


class CollectionMismatchError(ValueError):
    """The collection was built for another retrieval configuration."""


class VectorStore:
    """Chunk index in one Qdrant collection: dense vectors, plus sparse vectors for hybrid
    search (R3) fused with the dense ranking by RRF (SAD 6.5).

    ``sparse_idf``: None = dense only; True = sparse with IDF applied by Qdrant (BM25);
    False = sparse with learned weights, no IDF (bge-m3)."""

    def __init__(self, client: QdrantClient, collection: str, sparse_idf: bool | None = None):
        self.client = client
        self.collection = collection
        self.sparse_idf = sparse_idf
        self._layout_checked = False

    def upsert(self, chunks: list[Chunk], vectors: list[list[float]], sparse: list[SparseVector] | None = None) -> None:
        from qdrant_client import models

        if not self.client.collection_exists(self.collection):
            sparse_config = None
            if self.sparse_idf is not None:
                modifier = models.Modifier.IDF if self.sparse_idf else None
                sparse_config = {SPARSE: models.SparseVectorParams(modifier=modifier)}
            self.client.create_collection(
                self.collection,
                vectors_config={DENSE: models.VectorParams(size=len(vectors[0]), distance=models.Distance.COSINE)},
                sparse_vectors_config=sparse_config,
            )
        self._check_layout()
        points = []
        for i, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
            payload = asdict(chunk)
            del payload["chunk_id"]  # stored as the point id
            named = {DENSE: vector}
            if sparse is not None:
                named[SPARSE] = models.SparseVector(indices=sparse[i].indices, values=sparse[i].values)
            points.append(models.PointStruct(id=chunk.chunk_id, vector=named, payload=payload))
        self.client.upsert(self.collection, points)

    def search(self, vector: list[float], limit: int, sparse: SparseVector | None = None,
               candidates: int | None = None) -> list[RetrievedChunk]:
        """Top ``limit`` chunks. With ``sparse``: the top ``candidates`` of the dense and of the
        sparse search, fused by reciprocal rank fusion."""
        from qdrant_client import models

        if not self.client.collection_exists(self.collection):
            return []
        self._check_layout()
        if sparse is None:
            hits = self.client.query_points(
                self.collection, query=vector, using=DENSE, limit=limit, with_payload=True
            ).points
        else:
            pool = candidates or limit
            hits = self.client.query_points(
                self.collection,
                prefetch=[
                    models.Prefetch(query=vector, using=DENSE, limit=pool),
                    models.Prefetch(query=models.SparseVector(indices=sparse.indices, values=sparse.values),
                                    using=SPARSE, limit=pool),
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=limit,
                with_payload=True,
            ).points
        return [RetrievedChunk(Chunk(chunk_id=str(h.id), **h.payload), h.score) for h in hits]

    def _check_layout(self) -> None:
        """Fail early, with a hint, when the collection was built for another configuration."""
        if self._layout_checked:
            return
        from qdrant_client import models

        params = self.client.get_collection(self.collection).config.params
        sparse = (params.sparse_vectors or {}).get(SPARSE)
        built = None if sparse is None else sparse.modifier == models.Modifier.IDF
        if built != self.sparse_idf:
            raise CollectionMismatchError(
                f"collection {self.collection!r} holds {_layout(built)}, but the configuration needs "
                f"{_layout(self.sparse_idf)}; set VTAGENT_COLLECTION to a collection built for this configuration")
        self._layout_checked = True


def _layout(sparse_idf: bool | None) -> str:
    if sparse_idf is None:
        return "dense vectors only"
    return "dense and sparse vectors " + ("with IDF (BM25)" if sparse_idf else "without IDF (bge-m3)")


class DocumentRegistry:
    """Documents already indexed into one collection, so re-ingesting skips them."""

    def __init__(self, db_path: Path, collection: str):
        self.collection = collection
        self.conn = sqlite3.connect(db_path)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS documents ("
            " doc_id TEXT NOT NULL, collection TEXT NOT NULL, source TEXT NOT NULL,"
            " stored_path TEXT NOT NULL, n_chunks INTEGER NOT NULL, ingested_at TEXT NOT NULL,"
            " PRIMARY KEY (doc_id, collection))"
        )

    def get(self, doc_id: str) -> DocumentRecord | None:
        row = self.conn.execute(
            "SELECT doc_id, source, stored_path, n_chunks, ingested_at FROM documents"
            " WHERE doc_id = ? AND collection = ?",
            (doc_id, self.collection),
        ).fetchone()
        return DocumentRecord(*row) if row else None

    def documents(self) -> list[DocumentRecord]:
        rows = self.conn.execute(
            "SELECT doc_id, source, stored_path, n_chunks, ingested_at FROM documents WHERE collection = ?",
            (self.collection,),
        ).fetchall()
        return [DocumentRecord(*row) for row in rows]

    def add(self, record: DocumentRecord) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO documents VALUES (?, ?, ?, ?, ?, ?)",
                (record.doc_id, self.collection, record.source, record.stored_path,
                 record.n_chunks, record.ingested_at),
            )
