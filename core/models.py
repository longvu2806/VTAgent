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
    version_id: str  # the indexed file: the first 32 hex digits of its SHA-256 (SDD 4.6)
    source: str  # original file name, shown in citations
    page: int | None
    index: int  # position of the chunk within its document
    text: str
    section: str = ""  # place in the document's structure, e.g. "Điều 8. … › Khoản 8" (R1+)
    parent_id: str | None = None  # children of one parent share it (R1+)
    parent_text: str = ""  # the parent's text, stored with each child (SAD 7.x)
    document_id: str = ""  # the document the version belongs to; stable across versions


@dataclass(frozen=True)
class SparseVector:
    """Term weights for keyword matching (hybrid search, SAD 6.4)."""

    indices: list[int]  # term ids: hashed tokens (BM25) or tokenizer ids (bge-m3)
    values: list[float]


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
    retrieved: list[RetrievedChunk] = field(default_factory=list)  # search hits by rank, before assembly


@dataclass(frozen=True)
class Version:
    """One file of a document (SDD 4.3, document_versions)."""

    id: str
    document_id: str
    seq: int  # 1 for the first file, then +1 per new version
    file_name: str
    file_ext: str  # ".pdf", ".docx"
    file_size: int
    stored_path: str
    pages: int | None
    ingested_at: str  # ISO 8601, UTC


@dataclass(frozen=True)
class Document:
    id: str
    title: str | None  # filled in by metadata extraction (FR-12), not yet implemented
    doc_number: str | None
    genre: str
    validity_status: str
    status: str  # ready | deleting
    created_at: str
    current: Version
    versions: list[Version]  # newest first


@dataclass(frozen=True)
class IngestResult:
    document_id: str
    version: Version
    n_chunks: int
    duplicate: bool  # the file was already indexed in this collection; nothing was done
