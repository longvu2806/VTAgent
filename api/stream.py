"""The answer stream: graph events as AI SDK UI Message Stream v1 chunks (SDD 9.3).

The draft streams as reasoning, which the UI keeps in a collapsed panel; the answer the
validator let through is sent once, as text, followed by its citations and the turn status
(AD-05). A draft that is written again is reset first."""

from __future__ import annotations

import json

from api.schemas import TurnOut
from core.graph import Stage, Token

HEADERS = {"x-vercel-ai-ui-message-stream": "v1", "cache-control": "no-cache"}


def sse(chunk: dict) -> str:
    return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"


DONE = "data: [DONE]\n\n"


class AnswerStream:
    def __init__(self, turn_id: str, scope_size: int):
        self.turn_id = turn_id
        self.scope_size = scope_size  # documents the user chose; 0 = all
        self.draft: str | None = None  # id of the reasoning part being written

    def start(self) -> list[dict]:
        return [{"type": "start", "messageId": self.turn_id}]

    def stage(self, event: Stage) -> list[dict]:
        chunks = self._close_draft()
        if event.node == "retrieve" and event.round > 1:  # the validator asked for another draft
            chunks += [_stage("retry", event.round), {"type": "reset-step"}]
        detail = None
        if event.node == "retrieve":
            detail = f"{self.scope_size} tài liệu đã chọn" if self.scope_size else "toàn bộ tài liệu"
        chunks.append(_stage(event.node, event.round, detail))
        if event.node == "answer":
            self.draft = f"draft-{event.round}"
            chunks += [{"type": "start-step"}, {"type": "reasoning-start", "id": self.draft}]
        return chunks

    def token(self, event: Token) -> list[dict]:
        return [{"type": "reasoning-delta", "id": self.draft, "delta": event.text}] if self.draft else []

    def finish(self, turn: TurnOut) -> list[dict]:
        return [
            *self._close_draft(),
            {"type": "text-start", "id": "answer"},
            {"type": "text-delta", "id": "answer", "delta": turn.answer or ""},
            {"type": "text-end", "id": "answer"},
            {"type": "data-citations", "id": "citations", "data": [c.model_dump() for c in turn.citations]},
            {"type": "data-turn", "id": "turn", "data": {"id": turn.id, "status": turn.status,
                                                         "missing": turn.missing, "latency_ms": turn.latency_ms}},
            {"type": "finish"},
        ]

    def error(self, text: str) -> list[dict]:
        return [*self._close_draft(), {"type": "error", "errorText": text}]

    def _close_draft(self) -> list[dict]:
        if self.draft is None:
            return []
        chunks = [{"type": "reasoning-end", "id": self.draft}, {"type": "finish-step"}]
        self.draft = None
        return chunks


def _stage(node: str, round_: int, detail: str | None = None) -> dict:
    data = {"node": node, "round": round_} | ({"detail": detail} if detail else {})
    return {"type": "data-stage", "id": "stage", "data": data}
