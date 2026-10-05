"""Storage: dense chunk index in Qdrant, registry of indexed documents in SQLite."""

from __future__ import annotations

import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

from core.models import Chunk, DocumentRecord, RetrievedChunk

if TYPE_CHECKING:
    from qdrant_client import QdrantClient

DENSE = "dense"  # vector name, shared with later configs (SAD 7.3)


class VectorStore:
    """Dense-only chunk index in one Qdrant collection."""

    def __init__(self, client: QdrantClient, collection: str):
        self.client = client
        self.collection = collection

    def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        from qdrant_client import models

        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                self.collection,
                vectors_config={DENSE: models.VectorParams(size=len(vectors[0]), distance=models.Distance.COSINE)},
            )
        points = []
        for chunk, vector in zip(chunks, vectors, strict=True):
            payload = asdict(chunk)
            del payload["chunk_id"]  # stored as the point id
            points.append(models.PointStruct(id=chunk.chunk_id, vector={DENSE: vector}, payload=payload))
        self.client.upsert(self.collection, points)

    def search(self, vector: list[float], limit: int) -> list[RetrievedChunk]:
        if not self.client.collection_exists(self.collection):
            return []
        hits = self.client.query_points(
            self.collection, query=vector, using=DENSE, limit=limit, with_payload=True
        ).points
        return [RetrievedChunk(Chunk(chunk_id=str(h.id), **h.payload), h.score) for h in hits]


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

    def add(self, record: DocumentRecord) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO documents VALUES (?, ?, ?, ?, ?, ?)",
                (record.doc_id, self.collection, record.source, record.stored_path,
                 record.n_chunks, record.ingested_at),
            )
