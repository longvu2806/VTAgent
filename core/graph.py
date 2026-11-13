"""Query orchestration graph (SAD 5.7): coordinator_route → agent → validator → finalize.

The skeleton of the multi-agent system. For now the coordinator sends every question to the
RAG agent and the validator accepts every draft, so the answers are those of RAGPipeline.ask;
the real coordinator and validator replace these two stubs."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Literal, TypedDict

from core.models import Answer

if TYPE_CHECKING:
    from core.pipeline import RAGPipeline

Gate = Literal["accept", "retry", "give_up"]


class VTState(TypedDict):
    question: str
    route: str | None  # agent chosen by coordinator_route
    draft: Answer | None  # the chosen agent's latest answer
    round: int  # drafts written so far
    gate: Gate | None  # the validator's decision on the draft
    final: Answer | None


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

    def ask(self, question: str) -> Answer:
        return self.graph.invoke({"question": question, "round": 0})["final"]

    def _route(self, state: VTState) -> dict:
        return {"route": "rag"}  # stub coordinator: every question is a lookup

    def _rag(self, state: VTState) -> dict:
        return {"draft": self.rag.ask(state["question"]), "round": state["round"] + 1}

    def _validator(self, state: VTState) -> dict:
        gate = self.validate(state["draft"])
        if gate == "retry" and state["round"] >= self.max_rounds:
            gate = "give_up"
        return {"gate": gate}

    def _finalize(self, state: VTState) -> dict:
        return {"final": state["draft"]}
