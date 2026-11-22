"""The agent graph skeleton: routing, the validator's retry loop and its round limit, and the
events it streams."""

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models import FakeListChatModel
from qdrant_client import QdrantClient

from core.graph import QueryGraph, Stage, Stopped, Token
from core.models import Answer, Chunk
from core.pipeline import RAGPipeline
from core.retrieval import Retrieval, Retriever
from core.stores import VectorStore


class CountingRAG:
    """Stands in for the RAG agent: a new draft on every call."""

    def __init__(self):
        self.questions = []
        self.scopes = []
        self.retriever = self

    def retrieve(self, question, timings, document_ids=None) -> Retrieval:
        self.questions.append(question)
        self.scopes.append(document_ids)
        return Retrieval(hits=[], sources=[])

    def answer(self, question, retrieval, timings=None, on_token=None) -> Answer:
        return Answer(f"draft {len(self.questions)}", citations=[], sources=[])


def test_a_question_goes_to_rag_once_and_its_draft_is_the_answer():
    rag = CountingRAG()

    answer = QueryGraph(rag, max_rounds=2).ask("Mức phạt?")

    assert (rag.questions, answer.text) == (["Mức phạt?"], "draft 1")


def test_a_retry_asks_again_and_the_accepted_draft_is_the_answer():
    rag = CountingRAG()
    decisions = iter(["retry", "accept"])

    answer = QueryGraph(rag, max_rounds=2, validate=lambda draft: next(decisions)).ask("Mức phạt?")

    assert (len(rag.questions), answer.text) == (2, "draft 2")


def test_retries_stop_at_the_round_limit():
    rag = CountingRAG()

    answer = QueryGraph(rag, max_rounds=2, validate=lambda draft: "retry").ask("Mức phạt?")

    assert (len(rag.questions), answer.text) == (2, "draft 2")  # gave up with the last draft


def test_the_graph_answers_like_the_pipeline():
    embedder = DeterministicFakeEmbedding(size=16)
    store = VectorStore(QdrantClient(":memory:"), "c")
    text = "Điều 5. Bên B chịu phạt 0,05% mỗi ngày chậm giao hàng."
    store.upsert([Chunk("00000000-0000-0000-0000-000000000001", "d", "hd.docx", None, 0, text)],
                 embedder.embed_documents([text]))
    reply = "Phạt 0,05% mỗi ngày [S1]."
    rag = RAGPipeline(Retriever(embedder, store, top_k=5), FakeListChatModel(responses=[reply, reply]))

    direct, through_graph = rag.ask("Mức phạt?"), QueryGraph(rag, max_rounds=2).ask("Mức phạt?")

    assert (through_graph.text, through_graph.citations, through_graph.sources) == \
        (direct.text, direct.citations, direct.sources)


def _pipeline(reply: str) -> RAGPipeline:
    embedder = DeterministicFakeEmbedding(size=16)
    store = VectorStore(QdrantClient(":memory:"), "c")
    text = "Điều 5. Bên B chịu phạt 0,05% mỗi ngày chậm giao hàng."
    store.upsert([Chunk("00000000-0000-0000-0000-000000000001", "v", "hd.docx", None, 0, text, document_id="d")],
                 embedder.embed_documents([text]))
    return RAGPipeline(Retriever(embedder, store, top_k=5), FakeListChatModel(responses=[reply]))


def test_the_stream_reports_each_stage_and_the_draft_then_the_answer():
    reply = "Phạt 0,05% [S1]."
    events = list(QueryGraph(_pipeline(reply), max_rounds=2).stream("Mức phạt?"))

    stages = [e.node for e in events if isinstance(e, Stage)]
    assert stages == ["route", "retrieve", "answer", "finalize"]
    assert "".join(e.text for e in events if isinstance(e, Token)) == reply
    assert isinstance(events[-1], Answer) and events[-1].text == reply


def test_stopping_closes_the_draft_midway():
    tokens = []
    checks = iter([False, False, False])  # the user presses Stop before the fourth token
    graph = QueryGraph(_pipeline("Phạt 0,05% mỗi ngày chậm giao hàng [S1]."), max_rounds=2)

    with pytest.raises(Stopped):
        for event in graph.stream("Mức phạt?", should_stop=lambda: next(checks, True)):
            if isinstance(event, Token):
                tokens.append(event.text)

    assert len(tokens) == 3


def test_the_scope_reaches_retrieval():
    rag = CountingRAG()

    QueryGraph(rag, max_rounds=2).ask("Mức phạt?", ["doc-1"])

    assert rag.scopes == [["doc-1"]]
