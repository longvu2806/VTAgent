"""Builds pipeline components from settings — the only config-aware module in core/."""

from __future__ import annotations

import atexit
from functools import cache, partial
from typing import TYPE_CHECKING

from config import Settings
from config import settings as default_settings
from core.chunking import split_pages_fixed, split_structured
from core.context import assemble
from core.ingestion import Ingestor
from core.pipeline import RAGPipeline
from core.prompting import SYSTEM_PROMPTS
from core.rerank import Reranker, onnx_cross_encoder
from core.retrieval import Retriever
from core.sparse import BgeM3SparseEncoder, BM25Encoder
from core.stores import DocumentRegistry, VectorStore

if TYPE_CHECKING:
    from langchain_core.embeddings import Embeddings
    from qdrant_client import QdrantClient
    from tokenizers import Tokenizer

    from core.sparse import SparseEncoder

FALLBACK_CHUNK_TOKENS = 300  # documents without recognised structure (SAD 6.2)
CANDIDATES = 40  # hits from each of the dense and sparse searches, and reranked (SAD Table 9.1)
BM25_K1, BM25_B = 1.2, 0.75  # standard BM25 parameters
BM25_AVG_LEN = 279  # mean BM25 tokens per child chunk, measured on the 9-document test corpus
RERANK_MAX_TOKENS = 512  # question + child chunk (children are at most 400 tokens)
RERANK_BATCH = 8


def build_ingestor(s: Settings = default_settings) -> Ingestor:
    tokenizer = _tokenizer(s.tokenizer_name)
    if s.chunking == "fixed":
        chunker = partial(split_pages_fixed, tokenizer=tokenizer, chunk_size=s.chunk_size, overlap=s.chunk_overlap)
    else:
        chunker = partial(split_structured, tokenizer=tokenizer, child_min=s.child_min_tokens,
                          child_max=s.child_max_tokens, parent_max=s.parent_max_tokens,
                          fallback_max=FALLBACK_CHUNK_TOKENS)
    return Ingestor(
        files_dir=s.data_dir / "files",
        chunker=chunker,
        embedder=_embedder(s),
        store=_vector_store(s),
        registry=build_registry(s),
        sparse_encoder=sparse_encoder(s),
    )


def build_registry(s: Settings = default_settings) -> DocumentRegistry:
    """The documents indexed in the configured collection."""
    s.data_dir.mkdir(parents=True, exist_ok=True)
    return DocumentRegistry(s.data_dir / "vtagent.db", s.collection)


def build_pipeline(s: Settings = default_settings) -> RAGPipeline:
    from langchain.chat_models import init_chat_model

    llm = init_chat_model(
        s.llm_model,
        model_provider="ollama",
        base_url=s.ollama_base_url,
        temperature=s.llm_temperature,
        num_ctx=s.llm_num_ctx,
        reasoning=False,  # thinking mode off (SAD Table 9.1)
    )
    assembler = None
    if s.chunking == "structured":
        tokenizer = _tokenizer(s.tokenizer_name)  # bge-m3's, close enough to the LLM's for a budget

        def count(text: str) -> int:
            return len(tokenizer.encode(text, add_special_tokens=False).ids)

        assembler = partial(assemble, budget=s.context_budget_tokens, count_tokens=count)
    retriever = Retriever(_embedder(s), _vector_store(s), s.top_k, assemble=assembler,
                          sparse_encoder=sparse_encoder(s), rerank=_reranker(s) if s.rerank else None,
                          candidates=CANDIDATES)
    return RAGPipeline(retriever, llm, timeout_s=s.llm_timeout_s, system_prompt=SYSTEM_PROMPTS[s.prompt])


def sparse_encoder(s: Settings) -> SparseEncoder | None:
    """The configured sparse encoder for hybrid search, or None for dense search only."""
    if s.sparse == "bm25":
        return BM25Encoder(BM25_K1, BM25_B, BM25_AVG_LEN, normalize=s.normalize_numbers)
    if s.sparse == "bge-m3":
        return BgeM3SparseEncoder.load(s.bge_m3_precision)
    return None


def _reranker(s: Settings) -> Reranker:
    from huggingface_hub import hf_hub_download

    model = hf_hub_download(s.reranker_repo, s.reranker_file)  # downloaded once, then cached
    tokenizer = hf_hub_download(s.reranker_repo, "tokenizer.json")
    score = onnx_cross_encoder(model, tokenizer, max_length=RERANK_MAX_TOKENS, batch_size=RERANK_BATCH)
    return Reranker(score, keep=s.top_k, threshold=s.rerank_threshold)


def _tokenizer(name: str) -> Tokenizer:
    from tokenizers import Tokenizer

    return Tokenizer.from_pretrained(name)


def _embedder(s: Settings) -> Embeddings:
    from langchain_ollama import OllamaEmbeddings

    return OllamaEmbeddings(model=s.embedding_model, base_url=s.ollama_base_url)


def _vector_store(s: Settings) -> VectorStore:
    s.data_dir.mkdir(parents=True, exist_ok=True)
    sparse_idf = {"none": None, "bm25": True, "bge-m3": False}[s.sparse]  # bge-m3 weights are learned
    return VectorStore(_qdrant(s.qdrant_url, str(s.data_dir / "qdrant")), s.collection, sparse_idf=sparse_idf)


@cache
def _qdrant(url: str | None, path: str) -> QdrantClient:
    """One client per location: embedded Qdrant locks its folder to a single client."""
    from qdrant_client import QdrantClient

    client = QdrantClient(url=url) if url else QdrantClient(path=path)
    atexit.register(client.close)  # closing during interpreter teardown raises
    return client
