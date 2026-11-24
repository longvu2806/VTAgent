"""Turn PDF / DOCX files into page texts. Text-layer documents only (SAD 3.5)."""

import re
import unicodedata
from pathlib import Path

from core.models import PageText

# pymupdf4llm wraps highlighted / underlined spans in HTML tags, and an accent drawn outside
# the highlight comes out detached: "<mark>co</mark> ́ <mark>chuyên" for "có chuyên".
_HTML_STYLE_TAG = re.compile(r"</?(?:mark|u)>")
_DETACHED_ACCENT = re.compile(r"\s+([̀-ͯ])")


class UnsupportedDocumentError(ValueError):
    """The file cannot be ingested: unsupported format, or no extractable text."""


def parse(path: Path) -> list[PageText]:
    """Non-empty pages of ``path``, as markdown."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        pages = _parse_pdf(path)
    elif suffix == ".docx":
        pages = _parse_docx(path)
    else:
        raise UnsupportedDocumentError(f"{path.name}: unsupported format {suffix!r} (PDF and DOCX only)")

    pages = [p for p in pages if p.text.strip()]
    if not pages:
        raise UnsupportedDocumentError(f"{path.name}: no text layer found (scanned document?)")
    return pages


def _parse_pdf(path: Path) -> list[PageText]:
    import pymupdf4llm

    pages = pymupdf4llm.to_markdown(str(path), page_chunks=True)
    return [PageText(page=p["metadata"]["page_number"], text=_clean_pdf_text(p["text"])) for p in pages]


def _clean_pdf_text(text: str) -> str:
    text = _DETACHED_ACCENT.sub(r"\1", _HTML_STYLE_TAG.sub("", text))
    return unicodedata.normalize("NFC", text)


def _parse_docx(path: Path) -> list[PageText]:
    import docx
    from docx.table import Table

    blocks = []
    for item in docx.Document(str(path)).iter_inner_content():
        if isinstance(item, Table):
            blocks.append(_table_to_markdown(item))
        elif item.text.strip():
            blocks.append(item.text)
    return [PageText(page=None, text="\n\n".join(blocks))]


def _table_to_markdown(table) -> str:
    rows = [[cell.text.strip().replace("\n", " ") for cell in row.cells] for row in table.rows]
    lines = ["| " + " | ".join(row) + " |" for row in rows]
    lines.insert(1, "|" + " --- |" * len(rows[0]))
    return "\n".join(lines)
