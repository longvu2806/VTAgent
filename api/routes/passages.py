"""A cited passage with its parent, to read the answer's source in context (UC09, FR-20)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.errors import not_found
from api.schemas import PassageOut
from api.services import Services, get_services

router = APIRouter(tags=["passages"])


@router.get("/passages/{chunk_id}")
def get_passage(chunk_id: str, services: Services = Depends(get_services)) -> PassageOut:
    chunk = services.store.get(chunk_id)
    document = chunk and services.catalog.document(chunk.document_id)
    if not document:  # unknown, deleted, or indexed only in another collection
        raise not_found("đoạn này trong chỉ mục đang dùng")
    return PassageOut(chunk_id=chunk.chunk_id, document_id=chunk.document_id,
                      document_title=document.title or chunk.source, section=chunk.section, page=chunk.page,
                      text=chunk.text, context=chunk.parent_text or chunk.text)
