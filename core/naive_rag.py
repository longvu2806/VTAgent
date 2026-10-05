"""R0 query path: embed question → dense top-k → prompt → LLM → answer with [S#] citations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.models import Answer
from core.prompting import NOT_FOUND, build_messages, extract_citations
from observability import timed

if TYPE_CHECKING:
    from langchain_core.embeddings import Embeddings
    from langchain_core.language_models import BaseChatModel

    from core.stores import VectorStore


class NaiveRAG:
    def __init__(self, embedder: Embeddings, store: VectorStore, llm: BaseChatModel, top_k: int):
        self.embedder = embedder
        self.store = store
        self.llm = llm
        self.top_k = top_k

    def ask(self, question: str) -> Answer:
        with timed("embed query"):
            vector = self.embedder.embed_query(question)
        with timed("dense search"):
            sources = self.store.search(vector, self.top_k)
        if not sources:
            return Answer(NOT_FOUND, citations=[], sources=[])

        with timed("generate"):
            text = self.llm.invoke(build_messages(question, sources)).text
        return Answer(text, extract_citations(text, sources), sources)
