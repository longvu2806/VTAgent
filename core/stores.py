"""Chunk index in Qdrant. The catalog of documents is in SQLite (core/catalog.py)."""

from __future__ import annotations

from dataclasses import asdict, fields
from typing import TYPE_CHECKING

from core.models import Chunk, RetrievedChunk, SparseVector

if TYPE_CHECKING:
    from qdrant_client import QdrantClient

DENSE = "dense"  # vector names, shared by every config (SAD 7.3)
SPARSE = "sparse"
_CHUNK_FIELDS = {f.name for f in fields(Chunk)} - {"chunk_id"}


class CollectionMismatchError(ValueError):
    """The collection was built for another retrieval configuration."""


class VectorStore:
    """Chunk index in one Qdrant collection: dense vectors, plus sparse vectors for hybrid
    search (R3) fused with the dense ranking by RRF (SAD 6.5).

    ``sparse_idf``: None = dense only; True = sparse with IDF applied by Qdrant (BM25);
    False = sparse with learned weights, no IDF (bge-m3).

    Every point carries ``tenant_id`` and ``is_current`` (SDD 4.4): searches only see the
    tenant's current versions, as Qdrant cannot look them up in SQLite."""

    def __init__(self, client: QdrantClient, collection: str, sparse_idf: bool | None = None,
                 tenant_id: str = "default"):
        self.client = client
        self.collection = collection
        self.sparse_idf = sparse_idf
        self.tenant_id = tenant_id
        self._layout_checked = False

    def upsert(self, chunks: list[Chunk], vectors: list[list[float]], sparse: list[SparseVector] | None = None,
               is_current: bool = True) -> None:
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
            for field, schema in [("tenant_id", models.KeywordIndexParams(type="keyword", is_tenant=True)),
                                  ("document_id", models.PayloadSchemaType.KEYWORD),
                                  ("version_id", models.PayloadSchemaType.KEYWORD),
                                  ("is_current", models.PayloadSchemaType.BOOL)]:
                self.client.create_payload_index(self.collection, field, field_schema=schema)
        self._check_layout()
        points = []
        for i, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
            payload = asdict(chunk)
            del payload["chunk_id"]  # stored as the point id
            payload.update(tenant_id=self.tenant_id, is_current=is_current)
            named = {DENSE: vector}
            if sparse is not None:
                named[SPARSE] = models.SparseVector(indices=sparse[i].indices, values=sparse[i].values)
            points.append(models.PointStruct(id=chunk.chunk_id, vector=named, payload=payload))
        self.client.upsert(self.collection, points)

    def search(self, vector: list[float], limit: int, sparse: SparseVector | None = None,
               candidates: int | None = None, document_ids: list[str] | None = None) -> list[RetrievedChunk]:
        """Top ``limit`` chunks of the tenant's current versions, within ``document_ids`` when
        given (FR-14). With ``sparse``: the top ``candidates`` of the dense and of the sparse
        search, fused by reciprocal rank fusion."""
        from qdrant_client import models

        if not self.client.collection_exists(self.collection):
            return []
        self._check_layout()
        must = [self._is_tenant(), models.FieldCondition(key="is_current", match=models.MatchValue(value=True))]
        if document_ids:
            must.append(models.FieldCondition(key="document_id", match=models.MatchAny(any=document_ids)))
        where = models.Filter(must=must)
        if sparse is None:
            hits = self.client.query_points(
                self.collection, query=vector, using=DENSE, limit=limit, query_filter=where, with_payload=True
            ).points
        else:
            pool = candidates or limit
            hits = self.client.query_points(
                self.collection,
                prefetch=[
                    models.Prefetch(query=vector, using=DENSE, limit=pool, filter=where),
                    models.Prefetch(query=models.SparseVector(indices=sparse.indices, values=sparse.values),
                                    using=SPARSE, limit=pool, filter=where),
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=limit,
                with_payload=True,
            ).points
        return [RetrievedChunk(_chunk(h.id, h.payload), h.score) for h in hits]

    def get(self, chunk_id: str) -> Chunk | None:
        """One chunk of the tenant, current or not (a cited passage, FR-20)."""
        if not self.client.collection_exists(self.collection):
            return None
        found = self.client.retrieve(self.collection, ids=[chunk_id], with_payload=True)
        if not found or found[0].payload.get("tenant_id") != self.tenant_id:
            return None
        return _chunk(found[0].id, found[0].payload)

    def set_current(self, document_id: str, version_id: str) -> None:
        """Make ``version_id`` the only searchable version of its document (FR-06), by a payload
        update rather than re-embedding (SDD 4.4)."""
        from qdrant_client import models

        document = models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id))
        version = models.FieldCondition(key="version_id", match=models.MatchValue(value=version_id))
        self.client.set_payload(self.collection, {"is_current": False},
                                points=models.Filter(must=[self._is_tenant(), document], must_not=[version]))
        self.client.set_payload(self.collection, {"is_current": True},
                                points=models.Filter(must=[self._is_tenant(), version]))

    def delete_document(self, document_id: str) -> None:
        """Delete every chunk of every version of a document (BR10)."""
        from qdrant_client import models

        if not self.client.collection_exists(self.collection):
            return
        document = models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id))
        self.client.delete(self.collection, points_selector=models.FilterSelector(
            filter=models.Filter(must=[self._is_tenant(), document])))

    def _is_tenant(self):
        from qdrant_client import models

        return models.FieldCondition(key="tenant_id", match=models.MatchValue(value=self.tenant_id))

    def check(self) -> None:
        """Raise CollectionMismatchError now if the collection was built for another configuration,
        rather than at the first upload or question (SDD 6.8). A missing collection is fine."""
        if self.client.collection_exists(self.collection):
            self._check_layout()

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
        points, _ = self.client.scroll(self.collection, limit=1, with_payload=["tenant_id"])
        if points and "tenant_id" not in points[0].payload:
            raise CollectionMismatchError(
                f"collection {self.collection!r} was built before documents had versions and tenants; "
                "set VTAGENT_COLLECTION to a new collection and ingest the documents again")
        self._layout_checked = True


def _chunk(point_id: object, payload: dict) -> Chunk:
    return Chunk(chunk_id=str(point_id), **{k: v for k, v in payload.items() if k in _CHUNK_FIELDS})


def _layout(sparse_idf: bool | None) -> str:
    if sparse_idf is None:
        return "dense vectors only"
    return "dense and sparse vectors " + ("with IDF (BM25)" if sparse_idf else "without IDF (bge-m3)")
