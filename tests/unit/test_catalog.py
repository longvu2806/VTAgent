"""The SQLite catalog: migrations, documents and versions, conversations, BR10, jobs."""

import sqlite3

import pytest

from core.catalog import Catalog, CitationRecord
from core.models import Version


@pytest.fixture
def catalog(tmp_path):
    return Catalog(tmp_path / "vtagent.db", "default")


def _version(document_id="doc-1", version_id="v1", seq=1, name="hd.pdf"):
    return Version(version_id, document_id, seq, name, ".pdf", 100, f"data/files/{version_id}.pdf", 6,
                   "2026-11-20T00:00:00+00:00")


def _citation(document_id="doc-1", version_id="v1", label="S1"):
    return CitationRecord(label, "chunk-1", document_id, version_id, "Điều 8 › Khoản 2", 3, "unchecked")


def test_the_registry_of_earlier_versions_is_kept_aside(tmp_path):
    db = tmp_path / "vtagent.db"
    with sqlite3.connect(db) as old:
        old.execute("CREATE TABLE documents (doc_id TEXT, collection TEXT, source TEXT, stored_path TEXT,"
                    " n_chunks INTEGER, ingested_at TEXT)")
        old.execute("INSERT INTO documents VALUES ('abc', 'r1', 'law.pdf', 'p', 3, 't')")

    catalog = Catalog(db, "default")

    assert catalog.conn.execute("SELECT source FROM legacy_registry").fetchone()[0] == "law.pdf"
    assert catalog.documents("r1") == []
    assert catalog.conn.execute("PRAGMA user_version").fetchone()[0] == 1


def test_reopening_does_not_migrate_again(tmp_path):
    Catalog(tmp_path / "vtagent.db", "default").add_version(_version(), "r1", 3)

    assert [d.id for d in Catalog(tmp_path / "vtagent.db", "default").documents("r1")] == ["doc-1"]


def test_a_new_version_becomes_current_and_the_old_one_stays_in_history(catalog):
    catalog.add_version(_version(), "r1", 3)
    catalog.add_version(_version(version_id="v2", seq=2, name="hd-v2.pdf"), "r1", 4)

    [document] = catalog.documents("r1")
    assert document.current.id == "v2"
    assert [v.seq for v in document.versions] == [2, 1]
    assert catalog.is_current("v2") and not catalog.is_current("v1")


def test_documents_are_listed_per_collection(catalog):
    catalog.add_version(_version(), "r1", 3)

    assert catalog.indexed_chunks("v1", "r1") == 3
    assert catalog.indexed_chunks("v1", "r3") is None
    assert catalog.documents("r3") == []
    catalog.add_index("v1", "r3", 5)
    assert [d.id for d in catalog.documents("r3")] == ["doc-1"]


def test_another_tenant_sees_nothing(tmp_path):
    Catalog(tmp_path / "vtagent.db", "default").add_version(_version(), "r1", 3)
    other = Catalog(tmp_path / "vtagent.db", "other")

    assert (other.documents("r1"), other.version("v1"), other.document("doc-1")) == ([], None, None)


def test_deleting_a_document_deletes_the_answers_that_cite_it(catalog):
    catalog.add_version(_version(), "r1", 3)
    catalog.add_version(_version("doc-2", "w1", name="law.pdf"), "r1", 3)
    conversation = catalog.create_conversation("Phạt")
    citing = catalog.start_turn(conversation.id, "Mức phạt?", ["doc-1"], {})
    catalog.finish_turn(citing, "answered", "Phạt 0,05% [S1].", None, 900, [_citation()])
    other = catalog.start_turn(conversation.id, "Luật nói gì?", [], {})
    catalog.finish_turn(other, "answered", "Theo luật [S1].", None, 900, [_citation("doc-2", "w1")])

    assert catalog.set_deleting("doc-1")
    assert [d.id for d in catalog.documents("r1")] == ["doc-2"]  # hidden while its content is deleted
    catalog.delete_document("doc-1")

    assert [t.id for t in catalog.turns(conversation.id)] == [other]  # BR10
    assert catalog.version("v1") is None and catalog.deleting_documents() == []


def test_a_turn_keeps_its_citations_and_scope(catalog):
    catalog.add_version(_version(), "r1", 3)
    conversation = catalog.create_conversation("Phạt")
    turn_id = catalog.start_turn(conversation.id, "Mức phạt?", ["doc-1"], {"collection": "r1"})
    assert catalog.turn(turn_id).status == "processing"

    catalog.finish_turn(turn_id, "answered", "Phạt 0,05% [S1].", None, 1200, [_citation()])

    turn = catalog.turn(turn_id)
    assert (turn.status, turn.answer, turn.scope, turn.latency_ms) == ("answered", "Phạt 0,05% [S1].", ["doc-1"], 1200)
    [citation] = turn.citations
    assert (citation.section, citation.page, citation.document_title) == ("Điều 8 › Khoản 2", 3, "hd.pdf")


def test_renaming_or_pinning_keeps_the_order_but_an_answer_moves_a_conversation_up(catalog):
    first, second = catalog.create_conversation("Một"), catalog.create_conversation("Hai")
    catalog.conn.execute("UPDATE conversations SET updated_at = '2026-01-01' WHERE id = ?", (first.id,))
    catalog.conn.execute("UPDATE conversations SET updated_at = '2026-01-02' WHERE id = ?", (second.id,))

    catalog.update_conversation(first.id, title="Một (sửa)", pinned=True)
    assert [c.id for c in catalog.conversations()] == [second.id, first.id]
    assert (catalog.conversation(first.id).title, catalog.conversation(first.id).pinned) == ("Một (sửa)", True)

    catalog.fail_turn(catalog.start_turn(first.id, "Hỏi?", [], {}), 500)
    assert [c.id for c in catalog.conversations()] == [first.id, second.id]


def test_deleting_a_conversation_deletes_its_turns(catalog):
    conversation = catalog.create_conversation("Phạt")
    turn_id = catalog.start_turn(conversation.id, "Mức phạt?", [], {})

    assert catalog.delete_conversation(conversation.id)
    assert catalog.turn(turn_id) is None and catalog.conversation(conversation.id) is None


def test_jobs_record_their_progress_and_restart_picks_up_the_unfinished(catalog):
    queued = catalog.create_job("hd.pdf", upload_path="data/uploads/a.pdf")
    rejected = catalog.create_job("anh.png", error_code="unsupported_format", error="Chỉ nhận PDF, DOCX.")

    catalog.update_job(queued.id, status="running", stage="embedding", progress=0.5)
    assert [j.id for j in catalog.unfinished_jobs()] == [queued.id]
    catalog.update_job(queued.id, status="done", document_id="doc-1", version_id="v1")

    assert catalog.unfinished_jobs() == []
    assert (catalog.job(queued.id).status, catalog.job(rejected.id).status) == ("done", "failed")
    with pytest.raises(ValueError):
        catalog.update_job(queued.id, tenant_id="other")
