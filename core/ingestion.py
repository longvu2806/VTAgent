"""Ingestion: parse → chunks → embed → Qdrant; originals kept in a file store."""

from __future__ import annotations

import hashlib
import shutil
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from core.models import Chunk, DocumentRecord, PageText
from core.parsing import parse
from core.structure import extract_metadata
from observability import log, timed

if TYPE_CHECKING:
    from langchain_core.embeddings import Embeddings

    from core.chunking import Piece
    from core.sparse import SparseEncoder
    from core.stores import DocumentRegistry, VectorStore


class Ingestor:
    def __init__(
        self,
        files_dir: Path,
        chunker: Callable[[list[PageText]], list[Piece]],
        embedder: Embeddings,
        store: VectorStore,
        registry: DocumentRegistry,
        sparse_encoder: SparseEncoder | None = None,
        context_header: Callable[[str, str, str], str] | None = None,
    ):
        self.files_dir = files_dir
        self.chunker = chunker  # split_pages_fixed (R0) or split_structured (R1), configured
        self.embedder = embedder
        self.store = store
        self.registry = registry
        self.sparse_encoder = sparse_encoder  # hybrid search (R3): BM25 or bge-m3 term weights
        self.context_header = context_header  # R2: (title, number, section) -> header; None: no header
        files_dir.mkdir(parents=True, exist_ok=True)

    def ingest(self, path: Path) -> DocumentRecord:
        """Index one file. A file already indexed into this collection is skipped."""
        version_id = hashlib.sha256(path.read_bytes()).hexdigest()[:32]
        if (record := self.registry.get(version_id)) is not None:
            log.info("%s already indexed as %s, skipping", path.name, version_id)
            return record

        with timed(f"parse {path.name}"):
            pages = parse(path)
        chunks = self._chunk(version_id, path.name, pages)
        texts = [f"{c.header}\n{c.text}" if c.header else c.text for c in chunks]  # R2: the header is searched too
        with timed(f"embed {len(chunks)} chunks"):
            vectors = self.embedder.embed_documents(texts)
        sparse = None
        if self.sparse_encoder is not None:
            with timed(f"sparse vectors for {len(chunks)} chunks"):
                sparse = self.sparse_encoder.documents(texts)
        self.store.upsert(chunks, vectors, sparse)

        stored = self.files_dir / f"{version_id}{path.suffix.lower()}"
        shutil.copyfile(path, stored)
        record = DocumentRecord(
            version_id=version_id,
            source=path.name,
            stored_path=str(stored),
            n_chunks=len(chunks),
            ingested_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        self.registry.add(record)
        return record

    def _chunk(self, version_id: str, source: str, pages: list[PageText]) -> list[Chunk]:
        title, number = extract_metadata(pages) if self.context_header is not None else ("", "")
        chunks = []
        for index, piece in enumerate(self.chunker(pages)):
            chunk_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"vtagent:{version_id}:{index}"))
            parent_id = None if piece.parent_key is None else str(
                uuid.uuid5(uuid.NAMESPACE_URL, f"vtagent:{version_id}:parent:{piece.parent_key}"))
            header = "" if self.context_header is None else self.context_header(title, number, piece.section)
            chunks.append(Chunk(chunk_id, version_id, source, piece.page, index, piece.text,
                                piece.section, parent_id, piece.parent_text, document_id=version_id,
                                title=title, doc_number=number, header=header))
        return chunks
