"""The VTAgent HTTP API (SDD 9) and the built web UI, served by one local process (AD-04)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import FileResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from api import errors, jobs
from api.routes import conversations, documents, jobs as job_routes, passages, system
from api.services import Services

API_PREFIX = "/api/v1"
LOCAL_HOSTS = ["127.0.0.1", "localhost"]  # a page on another site cannot reach the API through DNS rebinding
WRITES = {"POST", "PUT", "PATCH", "DELETE"}
# Windows' registry maps .mjs to text/plain, and browsers refuse to run a module served so
# (the PDF viewer's worker). Other files keep the type guessed from their suffix.
STATIC_TYPES = {".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css"}


def create_app(services: Services, web_dir: Path | None = None) -> FastAPI:
    """``web_dir``: the built UI (web/dist), served at / when present."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Finish what a previous run left half done (SDD 4.7).
        for document_id in services.catalog.deleting_documents():
            documents.remove_document(services, document_id)
        jobs.resume(services)
        services.catalog.fail_unfinished_turns()
        yield
        services.worker.shutdown(wait=False, cancel_futures=True)

    # No /docs or /redoc: they load Swagger and ReDoc from a CDN, and VTAgent stays offline
    # (NFR-01). The schema is still at /openapi.json.
    app = FastAPI(title="VTAgent", version="1.0", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.services = services
    errors.install(app)

    @app.middleware("http")
    async def require_marker(request: Request, call_next):
        # A cross-site form cannot set this header, so it cannot change anything (SDD 11.6).
        if (request.method in WRITES and request.url.path.startswith(API_PREFIX)
                and request.headers.get("x-vtagent") != "1"):
            return errors.problem(403, "forbidden", "Thiếu header X-VTAgent: 1.")
        return await call_next(request)

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=LOCAL_HOSTS)

    api = APIRouter(prefix=API_PREFIX)
    for module in (conversations, documents, job_routes, passages, system):
        api.include_router(module.router)
    app.include_router(api)

    if web_dir is not None and (web_dir / "index.html").is_file():
        root = web_dir.resolve()

        @app.get("/{path:path}", include_in_schema=False)
        def web(path: str) -> FileResponse:
            if path.startswith("api/"):
                raise errors.not_found("điểm cuối này")
            file = (root / path).resolve()
            if path and file.is_file() and file.is_relative_to(root):
                return FileResponse(file, media_type=STATIC_TYPES.get(file.suffix))
            return FileResponse(root / "index.html")  # a client-side route such as /c/{id}

    return app
