"""Ingestion: parse → chunks → embed → Qdrant; the original kept in a file store and the
document's version recorded in the catalog (SDD 5.1)."""

from __future__ import annotations

import hashlib
import shutil
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from core.catalog import now
from core.models import Chunk, IngestResult, PageText, Version
from core.parsing import parse
from observability import log, timed

if TYPE_CHECKING:
    from langchain_core.embeddings import Embeddings

    from core.catalog import Catalog
    from core.chunking import Piece
    from core.sparse import SparseEncoder
    from core.stores import VectorStore

Progress = Callable[[str, float], None]  # stage, fraction done (FR-07)


class Ingestor:
    def __init__(
        self,
        files_dir: Path,
        chunker: Callable[[list[PageText]], list[Piece]],
        embedder: Embeddings,
        store: VectorStore,
        catalog: Catalog,
        sparse_encoder: SparseEncoder | None = None,
    ):
        self.files_dir = files_dir
        self.chunker = chunker  # split_pages_fixed (R0) or split_structured (R1), configured
        self.embedder = embedder
        self.store = store
        self.catalog = catalog
        self.sparse_encoder = sparse_encoder  # hybrid search (R3): BM25 or bge-m3 term weights
        files_dir.mkdir(parents=True, exist_ok=True)

    def ingest(self, path: Path, document_id: str | None = None, file_name: str | None = None,
               on_stage: Progress | None = None) -> IngestResult:
        """Index one file as a new document, or as the new current version of ``document_id``
        (FR-06). A file already indexed in this collection is not indexed again (BR03); one
        indexed for another configuration keeps its document and ids."""
        report = on_stage or (lambda stage, progress: None)
        name = file_name or path.name  # an upload is stored under its job id
        data = path.read_bytes()
        version_id = hashlib.sha256(data).hexdigest()[:32]
        known = self.catalog.version(version_id)
        if known is not None and (n := self.catalog.indexed_chunks(version_id, self.store.collection)) is not None:
            log.info("%s already indexed as %s, skipping", name, version_id)
            return IngestResult(known.document_id, known, n, duplicate=True)
        if known is not None:
            document_id = known.document_id
        elif document_id is not None and self.catalog.document(document_id) is None:
            raise ValueError(f"no document {document_id} to add a version to")
        document_id = document_id or str(uuid.uuid4())

        report("parsing", 0.1)
        with timed(f"parse {name}"):
            pages = parse(path)
        report("chunking", 0.3)
        chunks = self._chunk(document_id, version_id, name, pages)
        texts = [c.text for c in chunks]
        report("embedding", 0.5)
        with timed(f"embed {len(chunks)} chunks"):
            vectors = self.embedder.embed_documents(texts)
        sparse = None
        if self.sparse_encoder is not None:
            with timed(f"sparse vectors for {len(chunks)} chunks"):
                sparse = self.sparse_encoder.documents(texts)
        report("indexing", 0.9)
        # Content first, catalog last: a failure in between leaves only orphan points (SDD 4.7).
        is_current = known is None or self.catalog.is_current(version_id)
        self.store.upsert(chunks, vectors, sparse, is_current=is_current)
        stored = self.files_dir / f"{version_id}{path.suffix.lower()}"
        if not stored.exists():
            shutil.copyfile(path, stored)

        if known is not None:
            self.catalog.add_index(version_id, self.store.collection, len(chunks))
            return IngestResult(document_id, known, len(chunks), duplicate=False)
        version = Version(version_id, document_id, self.catalog.next_seq(document_id), name, path.suffix.lower(),
                          len(data), str(stored), max((p.page for p in pages if p.page), default=None), now())
        self.catalog.add_version(version, self.store.collection, len(chunks))
        if version.seq > 1:
            self.store.set_current(document_id, version_id)
        return IngestResult(document_id, version, len(chunks), duplicate=False)

    def _chunk(self, document_id: str, version_id: str, source: str, pages: list[PageText]) -> list[Chunk]:
        chunks = []
        for index, piece in enumerate(self.chunker(pages)):
            chunk_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"vtagent:{version_id}:{index}"))
            parent_id = None if piece.parent_key is None else str(
                uuid.uuid5(uuid.NAMESPACE_URL, f"vtagent:{version_id}:parent:{piece.parent_key}"))
            chunks.append(Chunk(chunk_id, version_id, source, piece.page, index, piece.text,
                                piece.section, parent_id, piece.parent_text, document_id))
        return chunks
