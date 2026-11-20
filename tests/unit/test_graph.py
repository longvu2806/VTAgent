"""The agent graph skeleton: routing, the validator's retry loop and its round limit."""

from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models import FakeListChatModel
from qdrant_client import QdrantClient

from core.graph import QueryGraph
from core.models import Answer, Chunk
from core.pipeline import RAGPipeline
from core.retrieval import Retriever
from core.stores import VectorStore


class CountingRAG:
    """Stands in for the RAG agent: a new draft on every call."""

    def __init__(self):
        self.questions = []

    def ask(self, question: str) -> Answer:
        self.questions.append(question)
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
