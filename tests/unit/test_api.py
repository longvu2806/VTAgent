"""The HTTP API through FastAPI's TestClient, with fake models and in-memory Qdrant."""

import json
import time
from functools import partial
from pathlib import Path

import docx
import pytest
from fastapi.testclient import TestClient
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models import FakeListChatModel
from qdrant_client import QdrantClient

from api.app import create_app
from api.services import Services
from core.catalog import Catalog
from core.chunking import split_pages_fixed
from core.graph import QueryGraph
from core.ingestion import Ingestor
from core.pipeline import RAGPipeline
from core.retrieval import Retriever
from core.stores import VectorStore

WRITE = {"x-vtagent": "1"}
API = "/api/v1"


def _docx(path: Path, *lines: str) -> bytes:
    document = docx.Document()
    for line in lines:
        document.add_paragraph(line)
    document.save(path)
    return path.read_bytes()


@pytest.fixture
def llm():
    return FakeListChatModel(responses=["Bên B chịu phạt 0,05% mỗi ngày chậm giao hàng [S1]."])


@pytest.fixture
def services(tmp_path, word_tokenizer, llm):
    client = QdrantClient(":memory:")
    embedder = DeterministicFakeEmbedding(size=16)
    catalog = Catalog(tmp_path / "vtagent.db", "default")
    store = VectorStore(client, "test")
    chunker = partial(split_pages_fixed, tokenizer=word_tokenizer, chunk_size=400, overlap=50)
    return Services(
        config={"collection": "test"},
        catalog=catalog,
        store=store,
        stores=lambda collection: VectorStore(client, collection),
        ingestor=Ingestor(tmp_path / "files", chunker, embedder, VectorStore(client, "test"), catalog),
        graph=QueryGraph(RAGPipeline(Retriever(embedder, store, top_k=5), llm), max_rounds=2),
        uploads_dir=tmp_path / "uploads",
        max_upload_bytes=2**20,
        ollama_url="http://127.0.0.1:9",  # nothing listens there
        models=["qwen3.5:9b", "bge-m3"],
    )


@pytest.fixture
def client(services, tmp_path):
    web = tmp_path / "dist"
    web.mkdir()
    (web / "index.html").write_text("<!doctype html><title>VTAgent</title>", encoding="utf-8")
    with TestClient(create_app(services, web), base_url="http://127.0.0.1") as c:
        yield c


def _finished(client, job_id: str) -> dict:
    for _ in range(100):
        job = client.get(f"{API}/jobs/{job_id}").json()
        if job["status"] not in ("queued", "running"):
            return job
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish")


def _upload(client, tmp_path, name="hd.docx", lines=("Điều 5. Bên B chịu phạt 0,05% mỗi ngày chậm giao hàng.",)):
    return _post(client, name, _docx(tmp_path / name, *lines))


def _post(client, name: str, content: bytes) -> dict:
    [job] = client.post(f"{API}/documents", files=[("files", (name, content))], headers=WRITE).json()["jobs"]
    return _finished(client, job["id"])


def test_writes_need_the_marker_header(client):
    response = client.post(f"{API}/conversations", json={})

    assert response.status_code == 403
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "forbidden"


def test_requests_for_another_host_are_refused(services):
    with TestClient(create_app(services), base_url="http://vtagent.example") as other:
        assert other.get(f"{API}/documents").status_code == 400


def test_an_uploaded_file_becomes_a_document(client, tmp_path):
    job = _upload(client, tmp_path)

    assert (job["status"], job["error"]) == ("done", None)
    [document] = client.get(f"{API}/documents").json()["items"]
    assert (document["id"], document["current_version"]["file_name"]) == (job["document_id"], "hd.docx")
    assert client.get(f"{API}/documents/{document['id']}/file").content == (tmp_path / "hd.docx").read_bytes()
    with client.stream("GET", f"{API}/jobs/{job['id']}/events") as events:
        assert "event: done" in "".join(events.iter_text())


def test_the_same_file_again_is_a_duplicate(client, tmp_path):
    content = _docx(tmp_path / "hd.docx", "Điều 1. Phạm vi.")  # saving again would change its timestamps
    first = _post(client, "hd.docx", content)
    second = _post(client, "hop-dong.docx", content)

    assert (second["status"], second["document_id"]) == ("duplicate", first["document_id"])
    assert len(client.get(f"{API}/documents").json()["items"]) == 1


@pytest.mark.parametrize(("name", "content", "code"), [
    ("notes.txt", b"plain text", "unsupported_format"),
    ("fake.pdf", b"PK\x03\x04 not a pdf", "unsupported_format"),
    ("big.pdf", b"%PDF" + b"0" * 2**20, "file_too_large"),
], ids=["text", "wrong-signature", "too-large"])
def test_a_refused_file_fails_its_job_only(client, tmp_path, name, content, code):
    good = _docx(tmp_path / "hd.docx", "Điều 1. Phạm vi.")
    jobs = client.post(f"{API}/documents", files=[("files", (name, content)), ("files", ("hd.docx", good))],
                       headers=WRITE).json()["jobs"]

    assert (jobs[0]["status"], jobs[0]["error"]["code"]) == ("failed", code)
    assert _finished(client, jobs[1]["id"])["status"] == "done"
    with client.stream("GET", f"{API}/jobs/{jobs[0]['id']}/events") as events:
        assert "event: failed" in "".join(events.iter_text())


def test_a_file_without_text_fails_with_the_reason(client, tmp_path):
    job = _upload(client, tmp_path, "empty.docx", lines=())

    assert (job["status"], job["error"]["code"]) == ("failed", "no_text_layer")


def test_a_new_version_becomes_current(client, tmp_path):
    document_id = _upload(client, tmp_path)["document_id"]
    content = _docx(tmp_path / "hd-v2.docx", "Điều 5. Bên B chịu phạt 0,1% mỗi ngày chậm giao hàng.")

    job = client.post(f"{API}/documents/{document_id}/versions", files={"file": ("hd-v2.docx", content)},
                      headers=WRITE).json()

    assert _finished(client, job["id"])["status"] == "done"
    detail = client.get(f"{API}/documents/{document_id}").json()
    assert (detail["current_version"]["seq"], [v["seq"] for v in detail["versions"]]) == (2, [2, 1])


def test_deleting_a_document_removes_it_and_its_file(client, services, tmp_path):
    document_id = _upload(client, tmp_path)["document_id"]
    stored = Path(services.catalog.document(document_id).current.stored_path)

    assert client.delete(f"{API}/documents/{document_id}", headers=WRITE).status_code == 204

    response = client.get(f"{API}/documents/{document_id}")
    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert not stored.exists() and client.get(f"{API}/documents").json()["items"] == []


def test_a_passage_comes_with_its_document(client, services, tmp_path):
    _upload(client, tmp_path)
    [hit] = services.store.search(DeterministicFakeEmbedding(size=16).embed_query("phạt"), 1)

    passage = client.get(f"{API}/passages/{hit.chunk.chunk_id}").json()

    assert (passage["document_title"], passage["text"]) == ("hd.docx", hit.chunk.text)
    assert passage["context"] == hit.chunk.text  # fixed chunks have no parent
    assert client.get(f"{API}/passages/00000000-0000-0000-0000-000000000000").status_code == 404


def test_health_reports_what_is_down(client):
    health = client.get(f"{API}/system/health").json()

    assert (health["status"], health["ollama"], health["qdrant"], health["sqlite"]) == ("degraded", False, True, True)


def test_the_web_ui_is_served_for_its_own_routes_only(client, tmp_path):
    (tmp_path / "dist" / "worker.mjs").write_text("export {}", encoding="utf-8")

    assert "VTAgent" in client.get("/c/some-conversation").text
    assert client.get("/worker.mjs").headers["content-type"].startswith("text/javascript")
    assert "swagger" not in client.get("/docs").text.lower()  # its page would load a CDN (NFR-01)
    response = client.get(f"{API}/nothing-here")
    assert (response.status_code, response.json()["code"]) == (404, "not_found")


class OllamaDownChatModel(FakeListChatModel):
    def _stream(self, *args, **kwargs):
        raise ConnectionError("Failed to connect to Ollama")


def _ask(client, conversation_id: str, question: str = "Mức phạt chậm giao hàng?", scope=()) -> list:
    """The parts of the answer stream, then '[DONE]'."""
    response = client.post(f"{API}/conversations/{conversation_id}/turns", headers=WRITE,
                           json={"question": question, "document_ids": list(scope)})
    assert response.headers["x-vercel-ai-ui-message-stream"] == "v1"
    data = [line[6:] for line in response.text.split("\n") if line.startswith("data: ")]
    return [json.loads(d) for d in data[:-1]] + [data[-1]]


def _conversation(client, title="Phạt") -> str:
    return client.post(f"{API}/conversations", json={"title": title}, headers=WRITE).json()["id"]


def test_an_answer_streams_its_stages_and_draft_then_the_answer_once(client, tmp_path):
    document_id = _upload(client, tmp_path)["document_id"]
    conversation_id = _conversation(client)

    parts = _ask(client, conversation_id)

    types = [p if p == "[DONE]" else p["type"] for p in parts]
    first_delta = types.index("reasoning-delta")
    assert types[:first_delta] == ["start", "data-stage", "data-stage", "data-stage", "start-step", "reasoning-start"]
    assert types[types.index("reasoning-end"):] == [
        "reasoning-end", "finish-step", "data-stage", "text-start", "text-delta", "text-end", "data-citations",
        "data-turn", "finish", "[DONE]"]
    stages = [p["data"] for p in parts if isinstance(p, dict) and p["type"] == "data-stage"]
    assert [s["node"] for s in stages] == ["route", "retrieve", "answer", "finalize"]
    assert stages[1]["detail"] == "toàn bộ tài liệu"
    draft = "".join(p["delta"] for p in parts if isinstance(p, dict) and p["type"] == "reasoning-delta")
    answer = next(p["delta"] for p in parts if isinstance(p, dict) and p["type"] == "text-delta")
    assert draft == answer == "Bên B chịu phạt 0,05% mỗi ngày chậm giao hàng [S1]."

    [turn] = client.get(f"{API}/conversations/{conversation_id}").json()["turns"]
    assert (turn["status"], turn["answer"]) == ("answered", answer)
    [citation] = turn["citations"]
    assert (citation["document_id"], citation["document_title"], citation["verdict"]) == \
        (document_id, "hd.docx", "unchecked")
    assert parts[-3]["data"] == {"id": turn["id"], "status": "answered", "missing": None,
                                 "latency_ms": turn["latency_ms"]}


def test_without_documents_the_answer_is_not_found(client):
    parts = _ask(client, _conversation(client))

    turn = next(p["data"] for p in parts if isinstance(p, dict) and p["type"] == "data-turn")
    assert turn["status"] == "not_found"
    assert next(p for p in parts if isinstance(p, dict) and p["type"] == "data-citations")["data"] == []


def test_when_ollama_is_down_the_stream_ends_with_an_error(client, services, tmp_path):
    _upload(client, tmp_path)
    services.graph.rag.llm = OllamaDownChatModel(responses=[])
    conversation_id = _conversation(client)

    parts = _ask(client, conversation_id)

    assert parts[-2] == {"type": "error", "errorText": "Không kết nối được Ollama. Kiểm tra Ollama đang chạy rồi thử lại."}
    [turn] = client.get(f"{API}/conversations/{conversation_id}").json()["turns"]
    assert (turn["status"], turn["answer"]) == ("failed", None)


def test_deleting_a_document_deletes_the_answers_citing_it(client, tmp_path):
    document_id = _upload(client, tmp_path)["document_id"]
    conversation_id = _conversation(client)
    _ask(client, conversation_id)

    client.delete(f"{API}/documents/{document_id}", headers=WRITE)

    assert client.get(f"{API}/conversations/{conversation_id}").json()["turns"] == []  # BR10


def test_an_answer_exports_with_its_sources(client, tmp_path):
    _upload(client, tmp_path)
    turn_id = next(p["data"]["id"] for p in _ask(client, _conversation(client))
                   if isinstance(p, dict) and p["type"] == "data-turn")

    exported = client.get(f"{API}/turns/{turn_id}/export", params={"format": "md"})

    assert 'filename="cau-tra-loi-' in exported.headers["content-disposition"]
    assert exported.text.startswith("# Mức phạt chậm giao hàng?")
    assert "**[S1]** hd.docx" in exported.text and "> Điều 5. Bên B chịu phạt" in exported.text
    assert json.loads(client.get(f"{API}/turns/{turn_id}/export", params={"format": "json"}).text)["sources"]


def test_conversations_are_renamed_pinned_and_deleted(client):
    conversation_id = _conversation(client, "Cũ")

    patched = client.patch(f"{API}/conversations/{conversation_id}", json={"title": "Mới", "pinned": True},
                           headers=WRITE).json()

    assert (patched["title"], patched["pinned"]) == ("Mới", True)
    assert [c["id"] for c in client.get(f"{API}/conversations").json()["items"]] == [conversation_id]
    assert client.delete(f"{API}/conversations/{conversation_id}", headers=WRITE).status_code == 204
    assert client.get(f"{API}/conversations/{conversation_id}").status_code == 404
    assert client.patch(f"{API}/conversations/{conversation_id}", json={"pinned": False},
                        headers=WRITE).status_code == 404


def test_an_index_built_for_another_configuration_is_named_as_the_cause(client, services, tmp_path):
    from qdrant_client import models

    qdrant = services.store.client
    qdrant.create_collection("old", vectors_config={"dense": models.VectorParams(size=16, distance=models.Distance.COSINE)})
    qdrant.upsert("old", [models.PointStruct(id=1, vector={"dense": [0.1] * 16}, payload={"doc_id": "x"})])
    services.ingestor.store = services.graph.rag.retriever.store = VectorStore(qdrant, "old")

    job = _upload(client, tmp_path)
    parts = _ask(client, _conversation(client))

    assert (job["status"], job["error"]["code"]) == ("failed", "index_unavailable")
    assert "VTAGENT_COLLECTION" in job["error"]["detail"] and "VTAGENT_COLLECTION" in parts[-2]["errorText"]
