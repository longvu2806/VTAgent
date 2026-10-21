"""Single-pass RAG: retrieve once → prompt with [S#]-labelled sources → LLM → answer with
citations. Runs every ablation config (R0 naive … R4); stays as the baseline next to the
multi-agent system."""

from __future__ import annotations

import time
from contextlib import closing
from typing import TYPE_CHECKING

from core.models import Answer
from core.prompting import NOT_FOUND, build_messages, extract_citations
from observability import log, timed

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel
    from langchain_core.messages import AIMessageChunk

    from core.retrieval import Retriever

# Ollama reports these durations (nanoseconds) for every call.
_OLLAMA_DURATIONS = {"load_duration": "llm_load", "prompt_eval_duration": "llm_prefill", "eval_duration": "llm_decode"}


class RAGPipeline:
    def __init__(self, retriever: Retriever, llm: BaseChatModel, timeout_s: float | None = None):
        self.retriever = retriever
        self.llm = llm
        self.timeout_s = timeout_s  # None: no limit on the LLM step

    def ask(self, question: str) -> Answer:
        timings: dict[str, float] = {}
        retrieval = self.retriever.retrieve(question, timings)
        sources = retrieval.sources
        if not sources:
            return Answer(NOT_FOUND, citations=[], sources=[], timings=timings, retrieved=retrieval.hits)

        with timed("generate", timings):
            reply, timed_out = self._generate(build_messages(question, sources))
        if timed_out:
            log.warning("LLM stopped after %.0fs time limit; the answer is incomplete", self.timeout_s)
        for key, stage in _OLLAMA_DURATIONS.items():
            if key in reply.response_metadata:
                timings[stage] = reply.response_metadata[key] / 1e9
        usage = reply.usage_metadata or {}
        tokens = {k: usage[k] for k in ("input_tokens", "output_tokens") if k in usage}
        return Answer(reply.text, extract_citations(reply.text, sources), sources, timings, tokens, timed_out,
                      retrieval.hits)

    def _generate(self, messages: list[tuple[str, str]]) -> tuple[AIMessageChunk, bool]:
        """Stream the reply and stop once ``timeout_s`` has passed (checked as tokens arrive).
        Closing the stream closes the connection, which makes Ollama stop generating."""
        deadline = None if self.timeout_s is None else time.monotonic() + self.timeout_s
        reply = None
        with closing(iter(self.llm.stream(messages))) as stream:
            for chunk in stream:
                reply = chunk if reply is None else reply + chunk
                if deadline is not None and time.monotonic() >= deadline:
                    return reply, True
        return reply, False
