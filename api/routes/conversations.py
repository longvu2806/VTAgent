"""Conversations and their turns (UC05, UC12, UC14): the answer of a new question streams back
as the response of the POST (SDD 9.3)."""

from __future__ import annotations

import asyncio
import threading
from typing import Literal

from fastapi import APIRouter, Depends, Response
from fastapi.responses import StreamingResponse

from api import exports, stream
from api.errors import not_found
from api.schemas import (ConversationDetail, ConversationIn, ConversationOut, ConversationPatch, Page, TurnIn,
                         TurnOut, conversation_out, turn_out)
from api.services import Services, get_services
from api.turns import answer_turn

router = APIRouter(tags=["conversations"])


@router.get("/conversations")
def list_conversations(services: Services = Depends(get_services)) -> Page[ConversationOut]:
    return Page(items=[conversation_out(c) for c in services.catalog.conversations()])


@router.post("/conversations", status_code=201)
def create_conversation(body: ConversationIn, services: Services = Depends(get_services)) -> ConversationOut:
    return conversation_out(services.catalog.create_conversation(body.title))


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, services: Services = Depends(get_services)) -> ConversationDetail:
    conversation = services.catalog.conversation(conversation_id)
    if conversation is None:
        raise not_found("hội thoại này")
    return ConversationDetail(**conversation_out(conversation).model_dump(),
                              turns=[turn_out(t) for t in services.catalog.turns(conversation_id)])


@router.patch("/conversations/{conversation_id}")
def update_conversation(conversation_id: str, body: ConversationPatch,
                        services: Services = Depends(get_services)) -> ConversationOut:
    conversation = services.catalog.update_conversation(conversation_id, body.title, body.pinned)
    if conversation is None:
        raise not_found("hội thoại này")
    return conversation_out(conversation)


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str, services: Services = Depends(get_services)) -> Response:
    if not services.catalog.delete_conversation(conversation_id):
        raise not_found("hội thoại này")
    return Response(status_code=204)


@router.post("/conversations/{conversation_id}/turns")
async def ask(conversation_id: str, body: TurnIn, services: Services = Depends(get_services)) -> StreamingResponse:
    """Answer a question; the reply is an AI SDK UI Message Stream. Closing it (Stop) stops the LLM."""
    if services.catalog.conversation(conversation_id) is None:
        raise not_found("hội thoại này")
    turn_id = services.catalog.start_turn(conversation_id, body.question, body.document_ids, services.config)
    loop = asyncio.get_running_loop()
    chunks: asyncio.Queue[dict | None] = asyncio.Queue()
    stop = threading.Event()
    services.worker.submit(answer_turn, services, turn_id, body.question, body.document_ids, stop,
                           lambda chunk: loop.call_soon_threadsafe(chunks.put_nowait, chunk))

    async def events():
        try:
            while (chunk := await chunks.get()) is not None:
                yield stream.sse(chunk)
            yield stream.DONE
        finally:
            stop.set()  # the client went away: the worker stops at the next token

    return StreamingResponse(events(), media_type="text/event-stream", headers=stream.HEADERS)


@router.get("/turns/{turn_id}")
def get_turn(turn_id: str, services: Services = Depends(get_services)) -> TurnOut:
    turn = services.catalog.turn(turn_id)
    if turn is None:
        raise not_found("lượt hỏi đáp này")
    return turn_out(turn)


@router.get("/turns/{turn_id}/export")
def export_turn(turn_id: str, format: Literal["md", "json"] = "md",
                services: Services = Depends(get_services)) -> Response:
    turn = get_turn(turn_id, services)
    passages = {c.chunk_id: chunk.text for c in turn.citations if (chunk := services.store.get(c.chunk_id))}
    body = exports.turn_markdown(turn, passages) if format == "md" else exports.turn_json(turn, passages)
    media = "text/markdown; charset=utf-8" if format == "md" else "application/json"
    return Response(body, media_type=media,
                    headers={"content-disposition": f'attachment; filename="cau-tra-loi-{turn_id[:8]}.{format}"'})
