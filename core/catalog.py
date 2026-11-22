"""Catalog: documents, versions, conversations, turns and ingest jobs in SQLite (SDD 4.3).

The relational half of the stores; chunks live in Qdrant (core/stores.py). Standard SQL only,
so a later move to PostgreSQL touches this module alone (SDD 4.8). Every row belongs to one
tenant. One connection is shared by the API threads and the worker, serialized by a lock."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from core.models import Document, Version

MIGRATIONS = Path(__file__).parent / "migrations"
FINISHED = {"done", "duplicate", "failed"}  # job statuses that end a job


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Conversation:
    id: str
    title: str | None
    pinned: bool
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class CitationRecord:
    label: str
    chunk_id: str
    document_id: str
    version_id: str
    section: str
    page: int | None
    verdict: str  # supported | unsupported | unchecked
    document_title: str = ""  # filled in when read: the document's title, else its file name


@dataclass(frozen=True)
class Turn:
    id: str
    conversation_id: str
    question: str
    status: str
    answer: str | None
    missing: str | None
    warnings: list[dict]
    scope: list[str]
    latency_ms: int | None
    created_at: str
    citations: list[CitationRecord]


@dataclass(frozen=True)
class Job:
    id: str
    file_name: str
    status: str
    stage: str | None
    progress: float | None
    error_code: str | None
    error: str | None
    upload_path: str | None
    document_id: str | None
    version_id: str | None
    created_at: str


_VERSION = "v.id, v.document_id, v.seq, v.file_name, v.file_ext, v.file_size, v.stored_path, v.pages, v.ingested_at"
_JOB_COLUMNS = {"status", "stage", "progress", "error_code", "error", "document_id", "version_id"}


class Catalog:
    def __init__(self, db_path: Path, tenant_id: str):
        self.tenant_id = tenant_id
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode = WAL")  # the UI reads while an answer is written
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA secure_delete = ON")  # deleted content is overwritten (NFR-02)
        self._migrate()
        with self._tx():
            self.conn.execute("INSERT OR IGNORE INTO tenants VALUES (?, ?, ?)", (tenant_id, tenant_id, now()))

    @contextmanager
    def _tx(self) -> Iterator[None]:
        with self._lock, self.conn:
            yield

    def _rows(self, sql: str, params: tuple | list = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self.conn.execute(sql, params).fetchall()

    def _row(self, sql: str, params: tuple | list = ()) -> sqlite3.Row | None:
        rows = self._rows(sql, params)
        return rows[0] if rows else None

    def _migrate(self) -> None:
        """Apply the numbered migrations newer than the database (PRAGMA user_version)."""
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        if version == 0 and self.conn.execute(
                "SELECT 1 FROM pragma_table_info('documents') WHERE name = 'doc_id'").fetchone():
            # The registry of earlier versions: kept, but its collections must be re-ingested.
            self.conn.execute("ALTER TABLE documents RENAME TO legacy_registry")
        for path in sorted(MIGRATIONS.glob("*.sql")):
            number = int(path.name.split("_")[0])
            if number > version:
                script = path.read_text(encoding="utf-8")
                self.conn.executescript(f"BEGIN;\n{script}\nPRAGMA user_version = {number};\nCOMMIT;")

    # Documents and versions

    def version(self, version_id: str) -> Version | None:
        row = self._row(f"SELECT {_VERSION} FROM document_versions v JOIN documents d ON d.id = v.document_id"
                        " WHERE v.id = ? AND d.tenant_id = ?", (version_id, self.tenant_id))
        return Version(*row) if row else None

    def indexed_chunks(self, version_id: str, collection: str) -> int | None:
        """How many chunks of the version ``collection`` holds; None if it is not indexed there."""
        row = self._row("SELECT n_chunks FROM indexed_versions WHERE version_id = ? AND collection = ?",
                        (version_id, collection))
        return row[0] if row else None

    def is_current(self, version_id: str) -> bool:
        return self._row("SELECT 1 FROM documents WHERE current_version_id = ?", (version_id,)) is not None

    def next_seq(self, document_id: str) -> int:
        row = self._row("SELECT MAX(seq) FROM document_versions WHERE document_id = ?", (document_id,))
        return (row[0] or 0) + 1

    def add_version(self, version: Version, collection: str, n_chunks: int) -> None:
        """Record an indexed file as the current version of its document, creating the document
        on its first version."""
        at = now()
        with self._tx():
            self.conn.execute("INSERT OR IGNORE INTO documents (id, tenant_id, created_at, updated_at)"
                              " VALUES (?, ?, ?, ?)", (version.document_id, self.tenant_id, at, at))
            self.conn.execute(
                "INSERT INTO document_versions (id, document_id, seq, file_name, file_ext, file_size, stored_path,"
                " pages, ingested_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (version.id, version.document_id, version.seq, version.file_name, version.file_ext,
                 version.file_size, version.stored_path, version.pages, version.ingested_at))
            self.conn.execute("UPDATE documents SET current_version_id = ?, updated_at = ? WHERE id = ?",
                              (version.id, at, version.document_id))
            self._index(version.id, collection, n_chunks)

    def add_index(self, version_id: str, collection: str, n_chunks: int) -> None:
        """Record that a known version is now indexed in another collection too."""
        with self._tx():
            self._index(version_id, collection, n_chunks)

    def _index(self, version_id: str, collection: str, n_chunks: int) -> None:
        self.conn.execute("INSERT OR REPLACE INTO indexed_versions VALUES (?, ?, ?, ?)",
                          (version_id, collection, n_chunks, now()))

    def documents(self, collection: str) -> list[Document]:
        """Documents whose current version is indexed in ``collection``, newest first."""
        return self._documents(
            "JOIN indexed_versions i ON i.version_id = d.current_version_id AND i.collection = ?"
            " WHERE d.tenant_id = ? AND d.status = 'ready' ORDER BY d.created_at DESC",
            (collection, self.tenant_id))

    def document(self, document_id: str) -> Document | None:
        found = self._documents("WHERE d.id = ? AND d.tenant_id = ? AND d.status = 'ready'",
                                (document_id, self.tenant_id))
        return found[0] if found else None

    def _documents(self, where: str, params: tuple) -> list[Document]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT d.id, d.title, d.doc_number, d.genre_id, d.validity_status, d.status, d.created_at,"
                f" d.current_version_id FROM documents d {where}", params).fetchall()
            ids = [r["id"] for r in rows]
            versions: dict[str, list[Version]] = {i: [] for i in ids}
            if ids:
                marks = ",".join("?" * len(ids))
                for v in self.conn.execute(f"SELECT {_VERSION} FROM document_versions v WHERE v.document_id"
                                           f" IN ({marks}) ORDER BY v.seq DESC", ids):
                    versions[v["document_id"]].append(Version(*v))
        return [Document(r["id"], r["title"], r["doc_number"], r["genre_id"], r["validity_status"], r["status"],
                         r["created_at"], next(v for v in versions[r["id"]] if v.id == r["current_version_id"]),
                         versions[r["id"]]) for r in rows]

    def set_deleting(self, document_id: str) -> bool:
        """Hide a document from lists and search before its content is deleted (SDD 7.10)."""
        with self._tx():
            return self.conn.execute("UPDATE documents SET status = 'deleting' WHERE id = ? AND tenant_id = ?",
                                     (document_id, self.tenant_id)).rowcount > 0

    def deleting_documents(self) -> list[str]:
        return [r[0] for r in self._rows("SELECT id FROM documents WHERE status = 'deleting' AND tenant_id = ?",
                                         (self.tenant_id,))]

    def stored_paths(self, document_id: str) -> list[str]:
        return [r[0] for r in self._rows("SELECT stored_path FROM document_versions WHERE document_id = ?",
                                         (document_id,))]

    def collections_of(self, document_id: str) -> list[str]:
        return [r[0] for r in self._rows(
            "SELECT DISTINCT i.collection FROM indexed_versions i JOIN document_versions v ON v.id = i.version_id"
            " WHERE v.document_id = ?", (document_id,))]

    def delete_document(self, document_id: str) -> None:
        """Delete the catalog entries of a document whose content is already deleted, with the
        answers that cite it (BR10). Versions and their scope rows go by cascade."""
        with self._tx():
            self.conn.execute("DELETE FROM turns WHERE id IN (SELECT turn_id FROM citations WHERE document_id = ?)",
                              (document_id,))
            self.conn.execute("DELETE FROM documents WHERE id = ? AND tenant_id = ?", (document_id, self.tenant_id))

    # Conversations and turns

    def create_conversation(self, title: str | None) -> Conversation:
        conversation = Conversation(str(uuid.uuid4()), title, False, now(), now())
        with self._tx():
            self.conn.execute("INSERT INTO conversations VALUES (?, ?, ?, 0, ?, ?)",
                              (conversation.id, self.tenant_id, title, conversation.created_at,
                               conversation.updated_at))
        return conversation

    def conversations(self) -> list[Conversation]:
        """Most recently answered first."""
        return [self._conversation(r) for r in self._rows(
            "SELECT * FROM conversations WHERE tenant_id = ? ORDER BY updated_at DESC", (self.tenant_id,))]

    def conversation(self, conversation_id: str) -> Conversation | None:
        row = self._row("SELECT * FROM conversations WHERE id = ? AND tenant_id = ?",
                        (conversation_id, self.tenant_id))
        return self._conversation(row) if row else None

    @staticmethod
    def _conversation(row: sqlite3.Row) -> Conversation:
        return Conversation(row["id"], row["title"], bool(row["pinned"]), row["created_at"], row["updated_at"])

    def update_conversation(self, conversation_id: str, title: str | None = None,
                            pinned: bool | None = None) -> Conversation | None:
        """Rename or pin; neither moves the conversation in the recent list."""
        with self._tx():
            if title is not None:
                self.conn.execute("UPDATE conversations SET title = ? WHERE id = ? AND tenant_id = ?",
                                  (title, conversation_id, self.tenant_id))
            if pinned is not None:
                self.conn.execute("UPDATE conversations SET pinned = ? WHERE id = ? AND tenant_id = ?",
                                  (int(pinned), conversation_id, self.tenant_id))
        return self.conversation(conversation_id)

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation with its turns and citations (FR-29)."""
        with self._tx():
            return self.conn.execute("DELETE FROM conversations WHERE id = ? AND tenant_id = ?",
                                     (conversation_id, self.tenant_id)).rowcount > 0

    def start_turn(self, conversation_id: str, question: str, scope: list[str], config: dict) -> str:
        turn_id = str(uuid.uuid4())
        with self._tx():
            seq = self.conn.execute("SELECT COUNT(*) FROM turns WHERE conversation_id = ?",
                                    (conversation_id,)).fetchone()[0] + 1
            self.conn.execute(
                "INSERT INTO turns (id, conversation_id, seq, question, status, config, created_at)"
                " VALUES (?, ?, ?, ?, 'processing', ?, ?)",
                (turn_id, conversation_id, seq, question, json.dumps(config, ensure_ascii=False), now()))
            self.conn.executemany("INSERT INTO turn_scope VALUES (?, ?)", [(turn_id, d) for d in scope])
        return turn_id

    def finish_turn(self, turn_id: str, status: str, answer: str, missing: str | None, latency_ms: int,
                    citations: list[CitationRecord]) -> None:
        """Store the answer and its citations in one transaction (SDD 6.5, finalize)."""
        with self._tx():
            self.conn.execute("UPDATE turns SET status = ?, answer = ?, missing = ?, latency_ms = ? WHERE id = ?",
                              (status, answer, missing, latency_ms, turn_id))
            self.conn.executemany(
                "INSERT INTO citations (turn_id, label, chunk_id, document_id, version_id, section, page, verdict)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [(turn_id, c.label, c.chunk_id, c.document_id, c.version_id, c.section, c.page, c.verdict)
                 for c in citations])
            self._touch(turn_id)

    def fail_turn(self, turn_id: str, latency_ms: int) -> None:
        with self._tx():
            self.conn.execute("UPDATE turns SET status = 'failed', latency_ms = ? WHERE id = ?", (latency_ms, turn_id))
            self._touch(turn_id)

    def fail_unfinished_turns(self) -> None:
        """Turns a restart interrupted while they were being answered."""
        with self._tx():
            self.conn.execute("UPDATE turns SET status = 'failed' WHERE status = 'processing' AND conversation_id IN"
                              " (SELECT id FROM conversations WHERE tenant_id = ?)", (self.tenant_id,))

    def _touch(self, turn_id: str) -> None:
        """The conversation moves to the top of the recent list."""
        self.conn.execute("UPDATE conversations SET updated_at = ? WHERE id ="
                          " (SELECT conversation_id FROM turns WHERE id = ?)", (now(), turn_id))

    def turn(self, turn_id: str) -> Turn | None:
        found = self._turns("t.id = ?", (turn_id,))
        return found[0] if found else None

    def turns(self, conversation_id: str) -> list[Turn]:
        return self._turns("t.conversation_id = ?", (conversation_id,))

    def _turns(self, where: str, params: tuple) -> list[Turn]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT t.* FROM turns t JOIN conversations c ON c.id = t.conversation_id"
                f" WHERE {where} AND c.tenant_id = ? ORDER BY t.seq", (*params, self.tenant_id)).fetchall()
            ids = [r["id"] for r in rows]
            marks = ",".join("?" * len(ids))
            citations: dict[str, list[CitationRecord]] = {i: [] for i in ids}
            scope: dict[str, list[str]] = {i: [] for i in ids}
            if ids:
                for c in self.conn.execute(
                        "SELECT c.*, COALESCE(d.title, v.file_name, '') AS document_title FROM citations c"
                        " LEFT JOIN documents d ON d.id = c.document_id"
                        " LEFT JOIN document_versions v ON v.id = c.version_id"
                        f" WHERE c.turn_id IN ({marks}) ORDER BY c.turn_id, CAST(SUBSTR(c.label, 2) AS INTEGER)",
                        ids):
                    citations[c["turn_id"]].append(CitationRecord(
                        c["label"], c["chunk_id"], c["document_id"], c["version_id"], c["section"], c["page"],
                        c["verdict"], c["document_title"]))
                for s in self.conn.execute(f"SELECT * FROM turn_scope WHERE turn_id IN ({marks})", ids):
                    scope[s["turn_id"]].append(s["document_id"])
        return [Turn(r["id"], r["conversation_id"], r["question"], r["status"], r["answer"], r["missing"],
                     json.loads(r["warnings"]), scope[r["id"]], r["latency_ms"], r["created_at"], citations[r["id"]])
                for r in rows]

    # Ingest jobs

    def create_job(self, file_name: str, upload_path: str | None = None, document_id: str | None = None,
                   error_code: str | None = None, error: str | None = None) -> Job:
        """A queued job, or with ``error_code`` one that failed before it started."""
        job_id = str(uuid.uuid4())
        status = "failed" if error_code else "queued"
        with self._tx():
            self.conn.execute(
                "INSERT INTO ingest_jobs (id, tenant_id, file_name, status, error_code, error, upload_path,"
                " document_id, created_at, finished_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (job_id, self.tenant_id, file_name, status, error_code, error, upload_path, document_id, now(),
                 now() if error_code else None))
        return self.job(job_id)

    def job(self, job_id: str) -> Job | None:
        row = self._row("SELECT * FROM ingest_jobs WHERE id = ? AND tenant_id = ?", (job_id, self.tenant_id))
        return self._job(row) if row else None

    @staticmethod
    def _job(row: sqlite3.Row) -> Job:
        return Job(row["id"], row["file_name"], row["status"], row["stage"], row["progress"], row["error_code"],
                   row["error"], row["upload_path"], row["document_id"], row["version_id"], row["created_at"])

    def update_job(self, job_id: str, **changes: object) -> None:
        unknown = set(changes) - _JOB_COLUMNS
        if unknown:
            raise ValueError(f"not job columns: {unknown}")
        if changes.get("status") in FINISHED:
            changes["finished_at"] = now()
        assignments = ", ".join(f"{column} = ?" for column in changes)
        with self._tx():
            self.conn.execute(f"UPDATE ingest_jobs SET {assignments} WHERE id = ?", (*changes.values(), job_id))

    def unfinished_jobs(self) -> list[Job]:
        """Jobs a restart interrupted, oldest first."""
        return [self._job(r) for r in self._rows(
            "SELECT * FROM ingest_jobs WHERE status IN ('queued', 'running') AND tenant_id = ? ORDER BY created_at",
            (self.tenant_id,))]
