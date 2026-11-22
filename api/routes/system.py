"""Whether the services VTAgent needs are up (NFR-10)."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends

from api.schemas import Health
from api.services import Services, get_services

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health")
def health(services: Services = Depends(get_services)) -> Health:
    try:
        tags = httpx.get(f"{services.ollama_url}/api/tags", timeout=2).json()["models"]
        pulled = {m["name"] for m in tags}
        ollama = True
    except (httpx.HTTPError, KeyError, ValueError):
        pulled, ollama = set(), False
    models = {m: m in pulled or f"{m}:latest" in pulled for m in services.models}
    try:
        services.store.client.get_collections()
        qdrant = True
    except Exception:  # any client or connection error means the index is unavailable
        qdrant = False
    try:
        services.catalog.conversations()
        sqlite = True
    except Exception:
        sqlite = False
    ok = ollama and qdrant and sqlite and all(models.values())
    return Health(status="ok" if ok else "degraded", ollama=ollama, models=models, qdrant=qdrant, sqlite=sqlite)
