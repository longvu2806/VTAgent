"""Payloads of the HTTP API (SDD 10.1). Mirrors web/src/api/types.ts; change both together."""

from __future__ import annotations

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field

from core.catalog import Conversation, Job, Turn
from core.models import Document, Version

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None  # one page holds everything until cursors are needed


class VersionOut(BaseModel):
    id: str
    seq: int
    file_name: str
    file_ext: str
    pages: int | None
    status: Literal["processing", "ready", "failed"]
    ingested_at: str


class DocumentOut(BaseModel):
    id: str
    title: str | None
    doc_number: str | None
    genre: str
    validity_status: str
    current_version: VersionOut
    created_at: str


class RelationOut(BaseModel):
    relation_type: str
    target_number: str
    target_document_id: str | None
    target_title: str | None


class DocumentDetail(DocumentOut):
    versions: list[VersionOut]
    relations: list[RelationOut]  # empty until relations are extracted (FR-13)


class ProblemDetail(BaseModel):
    code: str
    detail: str


class JobOut(BaseModel):
    id: str
    file_name: str
    status: Literal["queued", "running", "done", "duplicate", "failed"]
    stage: str | None
    progress: float | None
    document_id: str | None
    error: ProblemDetail | None


class JobsOut(BaseModel):
    jobs: list[JobOut]


class PassageOut(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    section: str
    page: int | None
    text: str  # the cited chunk
    context: str  # its parent, to read the chunk in context (FR-20)


class ConversationIn(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class ConversationPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    pinned: bool | None = None


class ConversationOut(BaseModel):
    id: str
    title: str | None
    pinned: bool
    created_at: str
    updated_at: str


class CitationOut(BaseModel):
    label: str
    chunk_id: str
    document_id: str
    document_title: str
    version_id: str
    section: str
    page: int | None
    verdict: Literal["supported", "unsupported", "unchecked"]


class SentenceWarning(BaseModel):
    sentence_index: int
    reason: str


class TurnIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    document_ids: list[str] = []  # empty: every document (FR-14)


class TurnOut(BaseModel):
    id: str
    conversation_id: str
    question: str
    status: Literal["processing", "answered", "partial", "not_found", "failed"]
    answer: str | None
    missing: str | None
    citations: list[CitationOut]
    warnings: list[SentenceWarning]
    scope: list[str]
    latency_ms: int | None
    created_at: str


class ConversationDetail(ConversationOut):
    turns: list[TurnOut]


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    ollama: bool
    models: dict[str, bool]  # pulled or not
    qdrant: bool
    sqlite: bool


def version_out(v: Version) -> VersionOut:
    return VersionOut(id=v.id, seq=v.seq, file_name=v.file_name, file_ext=v.file_ext, pages=v.pages, status="ready",
                      ingested_at=v.ingested_at)


def document_out(d: Document) -> DocumentOut:
    return DocumentOut(id=d.id, title=d.title, doc_number=d.doc_number, genre=d.genre,
                       validity_status=d.validity_status, current_version=version_out(d.current),
                       created_at=d.created_at)


def document_detail(d: Document) -> DocumentDetail:
    return DocumentDetail(**document_out(d).model_dump(), versions=[version_out(v) for v in d.versions], relations=[])


def job_out(j: Job) -> JobOut:
    error = ProblemDetail(code=j.error_code, detail=j.error or "") if j.error_code else None
    return JobOut(id=j.id, file_name=j.file_name, status=j.status, stage=j.stage, progress=j.progress,
                  document_id=j.document_id, error=error)


def conversation_out(c: Conversation) -> ConversationOut:
    return ConversationOut(id=c.id, title=c.title, pinned=c.pinned, created_at=c.created_at, updated_at=c.updated_at)


def turn_out(t: Turn) -> TurnOut:
    return TurnOut(
        id=t.id, conversation_id=t.conversation_id, question=t.question, status=t.status, answer=t.answer,
        missing=t.missing, scope=t.scope, latency_ms=t.latency_ms, created_at=t.created_at,
        warnings=[SentenceWarning(**w) for w in t.warnings],
        citations=[CitationOut(label=c.label, chunk_id=c.chunk_id, document_id=c.document_id,
                               document_title=c.document_title, version_id=c.version_id, section=c.section,
                               page=c.page, verdict=c.verdict) for c in t.citations])
