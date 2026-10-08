"""Ingest + ask end to end, with fake models and in-memory Qdrant."""

from pathlib import Path

import docx
import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models import FakeListChatModel
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk
from qdrant_client import QdrantClient

from core.ingestion import Ingestor
from core.naive_rag import NaiveRAG
from core.prompting import NOT_FOUND
from core.stores import DocumentRegistry, VectorStore


class OllamaLikeChatModel(GenericFakeChatModel):
    """Streams like ChatOllama: the text first, then durations and token usage on a last chunk."""

    reply_metadata: dict
    reply_usage: dict

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        yield from super()._stream(messages, stop, run_manager, **kwargs)
        yield ChatGenerationChunk(message=AIMessageChunk(
            content="", response_metadata=self.reply_metadata, usage_metadata=self.reply_usage))


class CountingEmbedding(DeterministicFakeEmbedding):
    document_calls: int = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_calls += 1
        return super().embed_documents(texts)


@pytest.fixture
def client():
    return QdrantClient(":memory:")


@pytest.fixture
def embedder():
    return CountingEmbedding(size=16)


@pytest.fixture
def contract(tmp_path):
    path = tmp_path / "hd.docx"
    document = docx.Document()
    document.add_paragraph("Điều 5. Bên B chịu phạt 0,05% mỗi ngày chậm giao hàng.")
    document.save(path)
    return path


def _ingestor(tmp_path, tokenizer, embedder, client, collection="test"):
    return Ingestor(
        files_dir=tmp_path / "files",
        tokenizer=tokenizer,
        embedder=embedder,
        store=VectorStore(client, collection),
        registry=DocumentRegistry(tmp_path / "db.sqlite", collection),
        chunk_size=400,
        overlap=50,
    )


def test_ingest_then_ask_maps_citation_to_chunk(tmp_path, word_tokenizer, embedder, client, contract):
    record = _ingestor(tmp_path, word_tokenizer, embedder, client).ingest(contract)

    assert record.n_chunks == 1
    assert Path(record.stored_path).read_bytes() == contract.read_bytes()

    llm = FakeListChatModel(responses=["Phạt 0,05% mỗi ngày [S1]."])
    answer = NaiveRAG(embedder, VectorStore(client, "test"), llm, top_k=5).ask("Mức phạt chậm giao hàng?")

    assert answer.text == "Phạt 0,05% mỗi ngày [S1]."
    [citation] = answer.citations
    assert citation.chunk.doc_id == record.doc_id
    assert citation.chunk.source == "hd.docx"
    assert "0,05%" in citation.chunk.text


def test_reingesting_same_file_skips_embedding(tmp_path, word_tokenizer, embedder, client, contract):
    ingestor = _ingestor(tmp_path, word_tokenizer, embedder, client)
    first = ingestor.ingest(contract)
    second = ingestor.ingest(contract)

    assert second == first
    assert embedder.document_calls == 1


def test_same_file_is_indexed_again_for_another_collection(tmp_path, word_tokenizer, embedder, client, contract):
    _ingestor(tmp_path, word_tokenizer, embedder, client, "r0").ingest(contract)
    _ingestor(tmp_path, word_tokenizer, embedder, client, "r1").ingest(contract)

    assert embedder.document_calls == 2


def test_empty_index_answers_not_found_without_calling_llm(embedder, client):
    llm = FakeListChatModel(responses=[])  # raises if invoked
    answer = NaiveRAG(embedder, VectorStore(client, "empty"), llm, top_k=5).ask("Bất kỳ?")

    assert answer.text == NOT_FOUND
    assert answer.citations == []
    assert answer.sources == []
    assert set(answer.timings) == {"embed_query", "search"}


def test_ask_reports_stage_timings_and_ollama_stats(tmp_path, word_tokenizer, embedder, client, contract):
    _ingestor(tmp_path, word_tokenizer, embedder, client).ingest(contract)
    llm = OllamaLikeChatModel(
        messages=iter([AIMessage(content="Phạt 0,05% [S1].")]),
        reply_metadata={"load_duration": 1e9, "prompt_eval_duration": 2.5e9, "eval_duration": 4e9},
        reply_usage={"input_tokens": 1700, "output_tokens": 60, "total_tokens": 1760},
    )

    answer = NaiveRAG(embedder, VectorStore(client, "test"), llm, top_k=5).ask("Mức phạt?")

    assert {"embed_query", "search", "generate"} <= set(answer.timings)
    assert answer.timings["llm_load"] == 1.0
    assert answer.timings["llm_prefill"] == 2.5
    assert answer.timings["llm_decode"] == 4.0
    assert answer.tokens == {"input_tokens": 1700, "output_tokens": 60}
    assert not answer.timed_out


def test_llm_is_stopped_at_the_time_limit(tmp_path, word_tokenizer, embedder, client, contract):
    _ingestor(tmp_path, word_tokenizer, embedder, client).ingest(contract)
    looping = AIMessage(content="Không được [S1]. " + "Tuy nhiên, xét lại [S1]. " * 50)
    llm = GenericFakeChatModel(messages=iter([looping]))

    answer = NaiveRAG(embedder, VectorStore(client, "test"), llm, top_k=5, timeout_s=0).ask("Mức phạt?")

    assert answer.timed_out
    assert 0 < len(answer.text) < len(looping.content)
    assert answer.citations == [] or answer.citations[0].label == "S1"
