"""R0 ingestion: parse → fixed-size chunks → embed → Qdrant; originals kept in a file store."""

from __future__ import annotations

import hashlib
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from core.chunking import split_fixed
from core.models import Chunk, DocumentRecord, PageText
from core.parsing import parse
from observability import log, timed

if TYPE_CHECKING:
    from langchain_core.embeddings import Embeddings
    from tokenizers import Tokenizer

    from core.stores import DocumentRegistry, VectorStore


class Ingestor:
    def __init__(
        self,
        files_dir: Path,
        tokenizer: Tokenizer,
        embedder: Embeddings,
        store: VectorStore,
        registry: DocumentRegistry,
        chunk_size: int,
        overlap: int,
    ):
        self.files_dir = files_dir
        self.tokenizer = tokenizer
        self.embedder = embedder
        self.store = store
        self.registry = registry
        self.chunk_size = chunk_size
        self.overlap = overlap
        files_dir.mkdir(parents=True, exist_ok=True)

    def ingest(self, path: Path) -> DocumentRecord:
        """Index one file. A file already indexed into this collection is skipped."""
        doc_id = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        if (record := self.registry.get(doc_id)) is not None:
            log.info("%s already indexed as %s, skipping", path.name, doc_id)
            return record

        with timed(f"parse {path.name}"):
            pages = parse(path)
        chunks = self._chunk(doc_id, path.name, pages)
        with timed(f"embed {len(chunks)} chunks"):
            vectors = self.embedder.embed_documents([c.text for c in chunks])
        self.store.upsert(chunks, vectors)

        stored = self.files_dir / f"{doc_id}{path.suffix.lower()}"
        shutil.copyfile(path, stored)
        record = DocumentRecord(
            doc_id=doc_id,
            source=path.name,
            stored_path=str(stored),
            n_chunks=len(chunks),
            ingested_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        self.registry.add(record)
        return record

    def _chunk(self, doc_id: str, source: str, pages: list[PageText]) -> list[Chunk]:
        """Chunks never span pages, so every chunk cites exactly one page."""
        chunks = []
        for page in pages:
            for text in split_fixed(page.text, self.tokenizer, self.chunk_size, self.overlap):
                index = len(chunks)
                chunk_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"vtagent:{doc_id}:{index}"))
                chunks.append(Chunk(chunk_id, doc_id, source, page.page, index, text))
        return chunks
