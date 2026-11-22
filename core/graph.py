"""Query orchestration graph (SAD 5.7): coordinator_route → agent → validator → finalize.

The skeleton of the multi-agent system. For now the coordinator sends every question to the
RAG agent and the validator accepts every draft, so the answers are those of RAGPipeline.ask;
the real coordinator and validator replace these two stubs. ``stream`` reports each stage and
the draft's tokens as they happen, for the API's answer stream (SDD 9.3)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, TypedDict

from core.models import Answer

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

    from core.pipeline import RAGPipeline

Gate = Literal["accept", "retry", "give_up"]


class VTState(TypedDict):
    question: str
    document_ids: list[str]  # the user's scope; empty = every document (FR-14)
    route: str | None  # agent chosen by coordinator_route
    draft: Answer | None  # the chosen agent's latest answer
    round: int  # drafts written so far
    gate: Gate | None  # the validator's decision on the draft
    final: Answer | None


@dataclass(frozen=True)
class Stage:
    node: Literal["route", "retrieve", "answer", "finalize"]
    round: int


@dataclass(frozen=True)
class Token:
    text: str  # a piece of the draft being written
    round: int


class Stopped(Exception):
    """The caller asked to stop (the user pressed Stop); the LLM stream is closed."""


def accept_all(draft: Answer) -> Gate:
    """Stub validator: every draft is accepted."""
    return "accept"


class QueryGraph:
    def __init__(self, rag: RAGPipeline, max_rounds: int, validate: Callable[[Answer], Gate] = accept_all):
        from langgraph.graph import END, START, StateGraph

        self.rag = rag
        self.max_rounds = max_rounds  # a retry past this many drafts becomes give_up
        self.validate = validate
        graph = StateGraph(VTState)
        graph.add_node("coordinator_route", self._route)
        graph.add_node("rag", self._rag)
        graph.add_node("validator", self._validator)
        graph.add_node("finalize", self._finalize)
        graph.add_edge(START, "coordinator_route")
        graph.add_conditional_edges("coordinator_route", lambda s: s["route"], {"rag": "rag"})
        graph.add_edge("rag", "validator")
        graph.add_conditional_edges("validator", lambda s: s["gate"],
                                    {"accept": "finalize", "give_up": "finalize", "retry": "rag"})
        graph.add_edge("finalize", END)
        self.graph = graph.compile()

    def ask(self, question: str, document_ids: list[str] | None = None) -> Answer:
        return self.graph.invoke(self._input(question, document_ids))["final"]

    def stream(self, question: str, document_ids: list[str] | None = None,
               should_stop: Callable[[], bool] = lambda: False) -> Iterator[Stage | Token | Answer]:
        """Each stage and draft token as the graph runs, then the final answer. Raises Stopped
        once ``should_stop`` turns true while the draft is being written."""
        config = {"configurable": {"should_stop": should_stop}}
        final = None
        for mode, chunk in self.graph.stream(self._input(question, document_ids), config,
                                             stream_mode=["custom", "values"]):
            if mode == "custom":
                yield chunk
            else:
                final = chunk.get("final") or final
        yield final

    @staticmethod
    def _input(question: str, document_ids: list[str] | None) -> dict:
        return {"question": question, "document_ids": document_ids or [], "round": 0}

    def _route(self, state: VTState) -> dict:
        _emit(Stage("route", state["round"] + 1))
        return {"route": "rag"}  # stub coordinator: every question is a lookup

    def _rag(self, state: VTState, config: RunnableConfig) -> dict:
        round_ = state["round"] + 1
        should_stop = config.get("configurable", {}).get("should_stop", lambda: False)

        def on_token(text: str) -> None:
            if should_stop():
                raise Stopped
            _emit(Token(text, round_))

        timings: dict[str, float] = {}
        _emit(Stage("retrieve", round_))
        retrieval = self.rag.retriever.retrieve(state["question"], timings, state["document_ids"])
        _emit(Stage("answer", round_))
        return {"draft": self.rag.answer(state["question"], retrieval, timings, on_token), "round": round_}

    def _validator(self, state: VTState) -> dict:
        gate = self.validate(state["draft"])
        if gate == "retry" and state["round"] >= self.max_rounds:
            gate = "give_up"
        return {"gate": gate}

    def _finalize(self, state: VTState) -> dict:
        _emit(Stage("finalize", state["round"]))
        return {"final": state["draft"]}


def _emit(event: Stage | Token) -> None:
    """Report to ``stream``'s caller; does nothing when the graph runs through ``ask``."""
    from langgraph.config import get_stream_writer

    get_stream_writer()(event)
