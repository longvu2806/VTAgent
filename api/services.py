"""What the routes work with, built once from the settings."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import Request

from config import JUDGE_SETTINGS, Settings
from core.agent_factory import build_catalog, build_ingestor, build_query_graph, vector_store

if TYPE_CHECKING:
    from core.catalog import Catalog
    from core.graph import QueryGraph
    from core.ingestion import Ingestor
    from core.stores import VectorStore


def _worker() -> ThreadPoolExecutor:
    # One worker runs ingest jobs and questions one at a time: memory does not hold the
    # embedding pass and the answer models at once (SDD 5.6).
    return ThreadPoolExecutor(max_workers=1, thread_name_prefix="vtagent-worker")


@dataclass
class Services:
    config: dict  # effective settings, stored with every answer (NFR-12)
    catalog: Catalog
    store: VectorStore  # the configured collection
    stores: Callable[[str], VectorStore]  # any collection: a deleted document leaves all of them
    ingestor: Ingestor
    graph: QueryGraph
    uploads_dir: Path
    max_upload_bytes: int
    ollama_url: str
    models: list[str]  # must be pulled in Ollama
    worker: ThreadPoolExecutor = field(default_factory=_worker)


def build_services(s: Settings) -> Services:
    catalog = build_catalog(s)
    return Services(
        config=s.model_dump(mode="json", exclude=JUDGE_SETTINGS),
        catalog=catalog,
        store=vector_store(s),
        stores=partial(vector_store, s),
        ingestor=build_ingestor(s, catalog),
        graph=build_query_graph(s),
        uploads_dir=s.data_dir / "uploads",
        max_upload_bytes=s.max_upload_mb * 2**20,
        ollama_url=s.ollama_base_url,
        models=[s.llm_model, s.embedding_model],
    )


def get_services(request: Request) -> Services:
    return request.app.state.services
