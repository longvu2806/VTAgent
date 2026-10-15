"""Data passed between pipeline stages."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PageText:
    """Text of one page; ``page`` is 1-based, or None for formats without pages (DOCX)."""

    page: int | None
    text: str


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    source: str  # original file name, shown in citations
    page: int | None
    index: int  # position of the chunk within its document
    text: str


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: Chunk
    score: float


@dataclass(frozen=True)
class Citation:
    label: str  # "S1", "S2", ... as written in the answer
    chunk: Chunk


@dataclass(frozen=True)
class Answer:
    text: str
    citations: list[Citation]
    sources: list[RetrievedChunk]  # everything the LLM was shown, in label order
    timings: dict[str, float] = field(default_factory=dict)  # stage -> seconds
    tokens: dict[str, int] = field(default_factory=dict)  # input_tokens, output_tokens
    timed_out: bool = False  # the LLM was stopped at its time limit; text is incomplete


@dataclass(frozen=True)
class DocumentRecord:
    doc_id: str
    source: str
    stored_path: str
    n_chunks: int
    ingested_at: str  # ISO 8601, UTC
