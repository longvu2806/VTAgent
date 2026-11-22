"""One question answered by the worker: run the graph, forward its events, store the turn."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TYPE_CHECKING

import httpx

from api.jobs import WRONG_COLLECTION
from api.schemas import turn_out
from api.stream import AnswerStream
from core.catalog import CitationRecord
from core.graph import Stage, Stopped, Token
from core.prompting import NOT_FOUND
from core.stores import CollectionMismatchError
from observability import log

if TYPE_CHECKING:
    import threading

    from api.services import Services
    from core.models import Answer

Send = Callable[[dict | None], None]  # a stream chunk, or None at the end

NO_OLLAMA = "Không kết nối được Ollama. Kiểm tra Ollama đang chạy rồi thử lại."
TIMED_OUT = "Mô hình không trả lời xong trong thời gian cho phép. Câu trả lời chưa hoàn tất."
FAILED = "Đã có lỗi khi xử lý câu hỏi. Chi tiết nằm trong log của máy chủ."


def answer_turn(services: Services, turn_id: str, question: str, document_ids: list[str],
                stop: threading.Event, send: Send) -> None:
    started = time.monotonic()
    stream = AnswerStream(turn_id, len(document_ids))
    catalog = services.catalog
    try:
        for chunk in stream.start():
            send(chunk)
        answer = None
        for event in services.graph.stream(question, document_ids, should_stop=stop.is_set):
            if isinstance(event, Stage):
                chunks = stream.stage(event)
            elif isinstance(event, Token):
                chunks = stream.token(event)
            else:
                answer, chunks = event, []
            for chunk in chunks:
                send(chunk)
        if answer.timed_out:  # never shown as if it were complete (SDD 6.8)
            raise TimeoutError
        catalog.finish_turn(turn_id, *_outcome(answer), _ms(started), _citations(answer))
        for chunk in stream.finish(turn_out(catalog.turn(turn_id))):
            send(chunk)
    except Stopped:
        log.info("turn %s stopped by the user", turn_id)
        catalog.fail_turn(turn_id, _ms(started))
    except Exception as e:
        log.exception("turn %s failed", turn_id)
        catalog.fail_turn(turn_id, _ms(started))
        if isinstance(e, (ConnectionError, httpx.TransportError)):
            text = NO_OLLAMA
        elif isinstance(e, CollectionMismatchError):
            text = WRONG_COLLECTION
        else:
            text = TIMED_OUT if isinstance(e, TimeoutError) else FAILED
        for chunk in stream.error(text):
            send(chunk)
    finally:
        send(None)


def _outcome(answer: Answer) -> tuple[str, str, None]:
    """Status, answer text, missing part. 'partial' needs the validator and is not detected yet."""
    status = "not_found" if not answer.sources or answer.text.strip() == NOT_FOUND else "answered"
    return status, answer.text, None


def _citations(answer: Answer) -> list[CitationRecord]:
    # Not checked against the sources until the validator exists (SDD 6.5).
    return [CitationRecord(c.label, c.chunk.chunk_id, c.chunk.document_id, c.chunk.version_id, c.chunk.section,
                           c.chunk.page, "unchecked") for c in answer.citations]


def _ms(started: float) -> int:
    return round((time.monotonic() - started) * 1000)
