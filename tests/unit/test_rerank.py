"""Reranker: reorders the candidates by a cross-encoder score, keeps the best few."""

from core.models import Chunk, RetrievedChunk
from core.rerank import Reranker

SCORES = {"a": 0.2, "b": 0.9, "c": 0.6, "d": 0.05}


def _hits(texts):
    return [RetrievedChunk(Chunk(t, "d", "law.pdf", 1, i, t), 1 / (i + 1)) for i, t in enumerate(texts)]


def _score(question, passages):
    return [SCORES[p] for p in passages]


def test_reranker_orders_by_its_score_and_keeps_the_best():
    kept = Reranker(_score, keep=2)("q", _hits(["a", "b", "c", "d"]))

    assert [(h.chunk.text, h.score) for h in kept] == [("b", 0.9), ("c", 0.6)]


def test_reranker_drops_chunks_below_the_threshold():
    kept = Reranker(_score, keep=5, threshold=0.5)("q", _hits(["a", "b", "c", "d"]))

    assert [h.chunk.text for h in kept] == ["b", "c"]


def test_reranker_keeps_nothing_when_every_chunk_is_below_the_threshold():
    assert Reranker(_score, keep=5, threshold=0.95)("q", _hits(["a", "b"])) == []


def test_reranker_does_not_score_an_empty_list():
    def fail(question, passages):
        raise AssertionError("scored")

    assert Reranker(fail, keep=5)("q", []) == []
