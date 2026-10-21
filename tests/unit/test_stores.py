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
