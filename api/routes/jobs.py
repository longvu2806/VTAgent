"""Ingest job status, read once or followed as server-sent events (FR-07, SDD 9.3)."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from api.errors import not_found
from api.schemas import JobOut, job_out
from api.services import Services, get_services

router = APIRouter(prefix="/jobs", tags=["jobs"])

POLL_S = 0.3  # the job row is re-read at this interval; cheaper than a pub/sub for one user


@router.get("/{job_id}")
def get_job(job_id: str, services: Services = Depends(get_services)) -> JobOut:
    job = services.catalog.job(job_id)
    if job is None:
        raise not_found("tác vụ này")
    return job_out(job)


@router.get("/{job_id}/events")
def job_events(job_id: str, services: Services = Depends(get_services)) -> StreamingResponse:
    if services.catalog.job(job_id) is None:
        raise not_found("tác vụ này")
    return StreamingResponse(_events(services, job_id), media_type="text/event-stream",
                             headers={"cache-control": "no-cache"})


async def _events(services: Services, job_id: str):
    last = None
    while True:
        job = services.catalog.job(job_id)
        if job.status in ("done", "duplicate"):
            document = services.catalog.document(job.document_id)
            yield _event("done", {"document_id": job.document_id, "version_id": job.version_id,
                                  "genre": document.genre if document else "unknown",
                                  "duplicate": job.status == "duplicate"})
            return
        if job.status == "failed":
            yield _event("failed", {"code": job.error_code, "message": job.error})
            return
        if job.stage and (job.stage, job.progress) != last:
            last = job.stage, job.progress
            yield _event("stage", {"stage": job.stage, "progress": job.progress})
        await asyncio.sleep(POLL_S)


def _event(name: str, data: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
