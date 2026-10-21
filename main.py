"""VTAgent command line — single-pass RAG (configs R0–R4, see .env.example): index documents, ask questions."""

import argparse
from pathlib import Path

from rich.markdown import Markdown
from rich.table import Table

from config import settings
from core.agent_factory import build_ingestor, build_pipeline
from core.parsing import UnsupportedDocumentError
from observability import console, log, setup_logging


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest", help="index PDF / DOCX files")
    ingest.add_argument("paths", nargs="+", type=Path)
    ask = commands.add_parser("ask", help="ask a question about the indexed documents")
    ask.add_argument("question")
    args = parser.parse_args()

    setup_logging()
    log.info("settings: %s", settings.model_dump_json())
    if args.command == "ingest":
        _ingest(args.paths)
    else:
        _ask(args.question)


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
        console.print(f"[green]indexed[/] {record.source} → {record.doc_id} ({record.n_chunks} chunks)")


def _ask(question: str) -> None:
    answer = build_pipeline().ask(question)
    console.print(Markdown(answer.text))
    if answer.citations:
        table = Table("Label", "Source", "Section", "Page", "Text")
        for c in answer.citations:
            snippet = c.chunk.text[:120].replace("\n", " ")
            table.add_row(c.label, c.chunk.source, c.chunk.section or "–", str(c.chunk.page or "–"), snippet + "…")
        console.print(table)


if __name__ == "__main__":
    main()
