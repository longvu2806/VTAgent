"""Retrieval: question → ranked child chunks → the sources the LLM reads.

R0 searches dense vectors and shows the hits as they are; R1 swaps hits for their parent
articles; R3 adds sparse vectors (BM25 or bge-m3) fused with the dense ranking by RRF;
R4 reranks the candidates with a cross-encoder. Reused by the Retriever agent in the
multi-agent phase (SAD 5.x)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.models import RetrievedChunk
from observability import timed

if TYPE_CHECKING:
    from langchain_core.embeddings import Embeddings

    from core.sparse import SparseEncoder
    from core.stores import VectorStore

Rerank = Callable[[str, list[RetrievedChunk]], list[RetrievedChunk]]


@dataclass(frozen=True)
class Retrieval:
    hits: list[RetrievedChunk]  # search hits by rank (after reranking)
    sources: list[RetrievedChunk]  # what the LLM reads, in [S#] order


class Retriever:
    def __init__(self, embedder: Embeddings, store: VectorStore, top_k: int,
                 assemble: Callable[[list[RetrievedChunk]], list[RetrievedChunk]] | None = None,
                 sparse_encoder: SparseEncoder | None = None, rerank: Rerank | None = None,
                 candidates: int | None = None):
        self.embedder = embedder
        self.store = store
        self.top_k = top_k
        self.assemble = assemble  # None: the LLM reads the hits as they are (R0)
        self.sparse_encoder = sparse_encoder  # None: dense search only
        self.rerank = rerank  # None: keep the search order
        self.candidates = candidates or top_k  # hits each search contributes to fusion and reranking

    def retrieve(self, question: str, timings: dict[str, float]) -> Retrieval:
        """Stage durations are added to ``timings``."""
        with timed("embed_query", timings):
            vector = self.embedder.embed_query(question)
        sparse = None
        if self.sparse_encoder is not None:
            with timed("sparse_query", timings):
                sparse = self.sparse_encoder.query(question)
        limit = self.candidates if self.rerank is not None else self.top_k
        with timed("search", timings):
            hits = self.store.search(vector, limit, sparse=sparse, candidates=self.candidates)
        if self.rerank is not None:
            with timed("rerank", timings):
                hits = self.rerank(question, hits)  # keeps at most top_k
        sources = hits
        if hits and self.assemble is not None:
            with timed("assemble", timings):
                sources = self.assemble(hits)
        return Retrieval(hits, sources)
