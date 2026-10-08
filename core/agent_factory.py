"""Builds pipeline components from settings — the only config-aware module in core/."""

from __future__ import annotations

import atexit
from functools import cache
from typing import TYPE_CHECKING

from config import Settings
from config import settings as default_settings
from core.ingestion import Ingestor
from core.naive_rag import NaiveRAG
from core.stores import DocumentRegistry, VectorStore

if TYPE_CHECKING:
    from langchain_core.embeddings import Embeddings
    from qdrant_client import QdrantClient


def build_ingestor(s: Settings = default_settings) -> Ingestor:
    from tokenizers import Tokenizer

    s.data_dir.mkdir(parents=True, exist_ok=True)
    return Ingestor(
        files_dir=s.data_dir / "files",
        tokenizer=Tokenizer.from_pretrained(s.tokenizer_name),
        embedder=_embedder(s),
        store=_vector_store(s),
        registry=DocumentRegistry(s.data_dir / "vtagent.db", s.collection),
        chunk_size=s.chunk_size,
        overlap=s.chunk_overlap,
    )


def build_naive_rag(s: Settings = default_settings) -> NaiveRAG:
    from langchain.chat_models import init_chat_model

    llm = init_chat_model(
        s.llm_model,
        model_provider="ollama",
        base_url=s.ollama_base_url,
        temperature=s.llm_temperature,
        num_ctx=s.llm_num_ctx,
        reasoning=False,  # thinking mode off (SAD Table 9.1)
    )
    return NaiveRAG(_embedder(s), _vector_store(s), llm, s.top_k, timeout_s=s.llm_timeout_s)


def _embedder(s: Settings) -> Embeddings:
    from langchain_ollama import OllamaEmbeddings

    return OllamaEmbeddings(model=s.embedding_model, base_url=s.ollama_base_url)


def _vector_store(s: Settings) -> VectorStore:
    s.data_dir.mkdir(parents=True, exist_ok=True)
    return VectorStore(_qdrant(s.qdrant_url, str(s.data_dir / "qdrant")), s.collection)


@cache
def _qdrant(url: str | None, path: str) -> QdrantClient:
    """One client per location: embedded Qdrant locks its folder to a single client."""
    from qdrant_client import QdrantClient

    client = QdrantClient(url=url) if url else QdrantClient(path=path)
    atexit.register(client.close)  # closing during interpreter teardown raises
    return client
