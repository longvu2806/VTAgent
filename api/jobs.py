"""Ingest jobs: one per uploaded file, run one at a time by the worker (SDD 5.1, FR-07)."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from core.parsing import UnsupportedDocumentError
from core.stores import CollectionMismatchError
from observability import log

if TYPE_CHECKING:
    from fastapi import UploadFile

    from api.services import Services
    from core.catalog import Job

SIGNATURES = {".pdf": b"%PDF", ".docx": b"PK\x03\x04"}  # DOCX is a zip archive (BR01)
WRONG_COLLECTION = ("Chỉ mục đang dùng được dựng cho cấu hình khác. Đặt VTAGENT_COLLECTION trong .env sang"
                    " một collection mới (vtagent_chunks_...) rồi khởi động lại.")


def accept(services: Services, upload: UploadFile, document_id: str | None = None) -> Job:
    """Check one uploaded file (SDD 5.1, A1) and queue it, or record why it is refused, so the
    other files of the same upload are still ingested."""
    catalog = services.catalog
    name = Path(upload.filename or "tệp").name
    suffix = Path(name).suffix.lower()
    if suffix not in SIGNATURES or not upload.file.read(4).startswith(SIGNATURES[suffix]):
        return catalog.create_job(name, error_code="unsupported_format",
                                  error="Chỉ nhận tệp PDF hoặc DOCX.")
    if (upload.size or 0) > services.max_upload_bytes:
        return catalog.create_job(name, error_code="file_too_large",
                                  error=f"Tệp lớn hơn giới hạn {services.max_upload_bytes // 2**20} MB.")
    upload.file.seek(0)
    services.uploads_dir.mkdir(parents=True, exist_ok=True)
    path = services.uploads_dir / f"{uuid.uuid4()}{suffix}"  # never the user's file name (SDD 4.5)
    with path.open("wb") as out:
        shutil.copyfileobj(upload.file, out)
    job = catalog.create_job(name, upload_path=str(path), document_id=document_id)
    services.worker.submit(run, services, job.id)
    return job


def run(services: Services, job_id: str) -> None:
    catalog = services.catalog
    job = catalog.job(job_id)
    catalog.update_job(job_id, status="running", stage="validating", progress=0.0)
    try:
        result = services.ingestor.ingest(
            Path(job.upload_path), document_id=job.document_id, file_name=job.file_name,
            on_stage=lambda stage, progress: catalog.update_job(job_id, stage=stage, progress=progress))
    except UnsupportedDocumentError:
        catalog.update_job(job_id, status="failed", error_code="no_text_layer",
                           error="Tệp không có lớp văn bản, có thể là bản scan.")
    except CollectionMismatchError:
        log.exception("ingest job %s: wrong collection", job_id)
        catalog.update_job(job_id, status="failed", error_code="index_unavailable", error=WRONG_COLLECTION)
    except (ConnectionError, httpx.TransportError):
        log.exception("ingest job %s: model unavailable", job_id)
        catalog.update_job(job_id, status="failed", error_code="model_unavailable",
                           error="Không kết nối được Ollama để lập chỉ mục. Kiểm tra Ollama rồi tải lại tệp.")
    except Exception:  # a corrupt file, or a bug: the job fails, the other jobs go on (NFR-10)
        log.exception("ingest job %s failed", job_id)
        catalog.update_job(job_id, status="failed", error_code="unreadable_file",
                           error="Không đọc được tệp này.")
    else:
        catalog.update_job(job_id, status="duplicate" if result.duplicate else "done", progress=1.0,
                           document_id=result.document_id, version_id=result.version.id)
    finally:
        Path(job.upload_path).unlink(missing_ok=True)


def resume(services: Services) -> None:
    """Queue again the jobs a restart interrupted, while their upload is still there."""
    for job in services.catalog.unfinished_jobs():
        if job.upload_path and Path(job.upload_path).is_file():
            services.worker.submit(run, services, job.id)
        else:
            services.catalog.update_job(job.id, status="failed", error_code="interrupted",
                                        error="Tác vụ bị gián đoạn. Hãy tải tệp lên lại.")
