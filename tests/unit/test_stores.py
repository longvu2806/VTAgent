"""Hybrid search in Qdrant: dense + sparse vectors fused by RRF, and collection layout checks."""

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding
from qdrant_client import QdrantClient

from core.models import Chunk
from core.sparse import BM25Encoder
from core.stores import CollectionMismatchError, VectorStore

TEXTS = [f"Điều {i}. Quy định chung về nội dung thứ {i}." for i in range(1, 20)] + [
    "Phạt tiền từ 160.000.000 đồng đến 200.000.000 đồng."]
BM25 = BM25Encoder(k1=1.2, b=0.75, avg_len=10)
EMBEDDER = DeterministicFakeEmbedding(size=16)  # random vectors: dense search cannot find the number


@pytest.fixture
def client():
    return QdrantClient(":memory:")


def _store(client, sparse_idf, collection="c", sparse=True):
    store = VectorStore(client, collection, sparse_idf=sparse_idf)
    chunks = [Chunk(f"00000000-0000-0000-0000-{i:012d}", "d", "law.pdf", 1, i, t) for i, t in enumerate(TEXTS)]
    store.upsert(chunks, EMBEDDER.embed_documents(TEXTS), BM25.documents(TEXTS) if sparse else None)
    return store


def test_hybrid_search_finds_the_exact_number(client):
    question = "số tiền 160.000.000"
    vector = EMBEDDER.embed_query(question)
    dense = [h.chunk.text for h in _store(client, None, "dense", sparse=False).search(vector, len(TEXTS))]
    assert "160.000.000" not in " ".join(dense[:10])  # random vectors rank it low

    [hit] = _store(client, sparse_idf=True).search(vector, 1, sparse=BM25.query(question), candidates=40)

    assert "160.000.000" in hit.chunk.text


def test_without_a_sparse_query_the_search_is_dense_only(client):
    hybrid, dense = _store(client, sparse_idf=True, collection="hybrid"), _store(client, None, "dense", sparse=False)
    vector = EMBEDDER.embed_query("phạt tiền")

    assert [h.chunk.chunk_id for h in hybrid.search(vector, 5)] == [h.chunk.chunk_id for h in dense.search(vector, 5)]


@pytest.mark.parametrize(("built", "configured"), [(None, True), (True, None), (True, False), (False, True)])
def test_a_collection_built_for_another_configuration_is_refused(client, built, configured):
    _store(client, built, sparse=built is not None)

    with pytest.raises(CollectionMismatchError, match="VTAGENT_COLLECTION"):
        VectorStore(client, "c", sparse_idf=configured).search(EMBEDDER.embed_query("q"), 5)


def _chunk(i, text, document, version):
    return Chunk(f"00000000-0000-0000-0001-{i:012d}", version, "hd.pdf", 1, i, text, document_id=document)


def _versions(client):
    """Tenant t1: document A in versions a1 (old) and a2, document B; tenant t2: document C."""
    mine, other = VectorStore(client, "v", tenant_id="t1"), VectorStore(client, "v", tenant_id="t2")
    texts = ["Điều 1 của A bản mới", "Điều 1 của B", "Điều 1 của A bản cũ", "Điều 1 của C"]
    vectors = EMBEDDER.embed_documents(texts)
    mine.upsert([_chunk(0, texts[0], "A", "a2"), _chunk(1, texts[1], "B", "b1")], vectors[:2])
    mine.upsert([_chunk(2, texts[2], "A", "a1")], vectors[2:3], is_current=False)
    other.upsert([_chunk(3, texts[3], "C", "c1")], vectors[3:])
    return mine, other


def _found(store, **options):
    return sorted(h.chunk.version_id for h in store.search(EMBEDDER.embed_query("Điều 1"), 10, **options))


def test_search_sees_only_the_current_versions_of_its_tenant(client):
    mine, _ = _versions(client)

    assert _found(mine) == ["a2", "b1"]
    assert _found(mine, document_ids=["B"]) == ["b1"]


def test_a_new_current_version_hides_the_previous_one(client):
    mine, _ = _versions(client)
    mine.set_current("A", "a1")

    assert _found(mine) == ["a1", "b1"]


def test_deleting_a_document_deletes_all_its_versions(client):
    mine, other = _versions(client)
    mine.delete_document("A")
    mine.set_current("B", "b1")

    assert _found(mine) == ["b1"] and _found(other) == ["c1"]
    assert mine.get(_chunk(2, "", "A", "a1").chunk_id) is None


def test_a_passage_is_read_by_id_within_the_tenant(client):
    mine, other = _versions(client)
    old = _chunk(2, "", "A", "a1").chunk_id

    assert mine.get(old).text == "Điều 1 của A bản cũ"  # cited answers may point at an old version
    assert other.get(old) is None


def test_a_collection_from_before_versions_is_refused(client):
    from qdrant_client import models

    client.create_collection("old", vectors_config={"dense": models.VectorParams(size=16, distance=models.Distance.COSINE)})
    client.upsert("old", [models.PointStruct(id=1, vector={"dense": EMBEDDER.embed_query("x")}, payload={"doc_id": "x"})])

    with pytest.raises(CollectionMismatchError, match="ingest the documents again"):
        VectorStore(client, "old").search(EMBEDDER.embed_query("x"), 5)
