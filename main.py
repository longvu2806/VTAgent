"""VTAgent command line — index documents, ask questions through the agent graph (configs R0–R4, see
.env.example), or serve the API and web UI."""

import argparse
from pathlib import Path

from rich.markdown import Markdown
from rich.table import Table

from config import settings
from core.agent_factory import build_ingestor, build_query_graph
from core.parsing import UnsupportedDocumentError
from core.stores import CollectionMismatchError
from observability import console, log, setup_logging


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest", help="index PDF / DOCX files")
    ingest.add_argument("paths", nargs="+", type=Path)
    ask = commands.add_parser("ask", help="ask a question about the indexed documents")
    ask.add_argument("question")
    serve = commands.add_parser("serve", help="run the API and the web UI on http://127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    setup_logging()
    log.info("settings: %s", settings.model_dump_json())
    if args.command == "ingest":
        _ingest(args.paths)
    elif args.command == "ask":
        _ask(args.question)
    else:
        _serve(args.port)


def _ingest(paths: list[Path]) -> None:
    ingestor = build_ingestor()
    for path in paths:
        if not path.is_file():
            console.print(f"[red]not found:[/] {path}")
            continue
        try:
            record = ingestor.ingest(path)
        except UnsupportedDocumentError as e:
            console.print(f"[red]rejected:[/] {e}")
            continue
        state = "already indexed" if record.duplicate else "indexed"
        console.print(f"[green]{state}[/] {record.version.file_name} → document {record.document_id},"
                      f" version {record.version.seq} ({record.n_chunks} chunks)")


def _ask(question: str) -> None:
    answer = build_query_graph().ask(question)
    console.print(Markdown(answer.text))
    if answer.citations:
        table = Table("Label", "Source", "Section", "Page", "Text")
        for c in answer.citations:
            snippet = c.chunk.text[:120].replace("\n", " ")
            table.add_row(c.label, c.chunk.source, c.chunk.section or "–", str(c.chunk.page or "–"), snippet + "…")
        console.print(table)


def _serve(port: int) -> None:
    import uvicorn

    from api.app import create_app
    from api.services import build_services

    services = build_services(settings)
    try:
        services.store.check()  # refuse to start on an index built for another configuration (SDD 6.8)
    except CollectionMismatchError as e:
        console.print(f"[red]cannot serve:[/] {e}")
        raise SystemExit(1) from None
    web = Path(__file__).parent / "web" / "dist"
    if not (web / "index.html").is_file():
        log.warning("web/dist is not built (cd web && pnpm build): serving the API only")
    # Bound to the loopback interface only: the API has no authentication yet (SDD 9.1).
    uvicorn.run(create_app(services, web), host="127.0.0.1", port=port, log_config=None)


if __name__ == "__main__":
    main()
