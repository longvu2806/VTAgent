"""Documents (UC01–UC04): upload, list, detail, new version, original file, delete."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Response, UploadFile
from fastapi.responses import FileResponse

from api.errors import not_found
from api.jobs import accept
from api.schemas import DocumentDetail, DocumentOut, JobOut, JobsOut, Page, document_detail, document_out, job_out
from api.services import Services, get_services

router = APIRouter(prefix="/documents", tags=["documents"])

MEDIA_TYPES = {".pdf": "application/pdf",
               ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


@router.get("")
def list_documents(services: Services = Depends(get_services)) -> Page[DocumentOut]:
    return Page(items=[document_out(d) for d in services.catalog.documents(services.store.collection)])


@router.post("", status_code=202)
def upload(files: Annotated[list[UploadFile], File()], services: Services = Depends(get_services)) -> JobsOut:
    """One ingest job per file (UC01, FR-01); follow each at /jobs/{id}/events."""
    return JobsOut(jobs=[job_out(accept(services, f)) for f in files])


@router.post("/{document_id}/versions", status_code=202)
def upload_version(document_id: str, file: Annotated[UploadFile, File()],
                   services: Services = Depends(get_services)) -> JobOut:
    """A new version of a document; the previous one stays in its history (UC04, FR-06)."""
    if services.catalog.document(document_id) is None:
        raise not_found("tài liệu này")
    return job_out(accept(services, file, document_id))


@router.get("/{document_id}")
def get_document(document_id: str, services: Services = Depends(get_services)) -> DocumentDetail:
    document = services.catalog.document(document_id)
    if document is None:
        raise not_found("tài liệu này")
    return document_detail(document)


@router.get("/{document_id}/file")
def get_file(document_id: str, version: str | None = None, services: Services = Depends(get_services)) -> FileResponse:
    document = services.catalog.document(document_id)
    found = document and next((v for v in document.versions if v.id == (version or document.current.id)), None)
    if not found or not Path(found.stored_path).is_file():
        raise not_found("tệp gốc của tài liệu này")
    return FileResponse(found.stored_path, media_type=MEDIA_TYPES.get(found.file_ext), filename=found.file_name,
                        content_disposition_type="inline")


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: str, services: Services = Depends(get_services)) -> Response:
    if services.catalog.document(document_id) is None:
        raise not_found("tài liệu này")
    remove_document(services, document_id)
    return Response(status_code=204)


def remove_document(services: Services, document_id: str) -> None:
    """Delete a document in the order of SDD 7.10: hide it, delete its content from every
    collection and the file store, then its catalog entries with the answers citing it (BR10).
    A failure midway leaves it hidden as 'deleting'; the next start finishes the job."""
    catalog = services.catalog
    catalog.set_deleting(document_id)
    for collection in catalog.collections_of(document_id):
        services.stores(collection).delete_document(document_id)
    for path in catalog.stored_paths(document_id):
        Path(path).unlink(missing_ok=True)
    catalog.delete_document(document_id)
