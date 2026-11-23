"""Document metadata read from a document's opening lines with fixed patterns, no model
(SDD 5.4, FR-13): the number ("Số: 389/2026/NĐ-CP") and the title ("NGHỊ ĐỊNH" + its name)
that Vietnamese legal documents and contracts print above their first "Căn cứ" or Điều."""

from __future__ import annotations

import re
import unicodedata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.models import PageText

# Document types whose name line follows the type line ("LUẬT" / "GIAO THÔNG ĐƯỜNG BỘ").
DOCUMENT_TYPES = ("luật", "bộ luật", "pháp lệnh", "nghị quyết", "nghị định", "quyết định", "thông tư",
                  "thông tư liên tịch", "chỉ thị", "hợp đồng")
_NUMBER = re.compile(r"\bsố\s*:\s*(\d[\w.\-]*/[\w./\-]*\w)", re.IGNORECASE)  # "Luật số: 24/2026/QH16"
_STOP = re.compile(r"(căn cứ|theo đề nghị|điều\s+\d|chương\s+[ivxlc\d]|phần\s+[ivxlc\d])", re.IGNORECASE)
OPENING_LINES = 40  # the title block of every test document ends well before this line
MAX_NAME_LINES = 6


def extract_metadata(pages: list[PageText]) -> tuple[str, str]:
    """(title, number) of the document; an empty string for what its opening does not show.
    The title is the type and the name in sentence case: "Luật sửa đổi, bổ sung … luật đầu tư"."""
    lines = _opening_lines(pages)
    number = next((m.group(1) for line in lines if (m := _NUMBER.search(line))), "")
    for i, line in enumerate(lines):
        if line.lower() in DOCUMENT_TYPES:
            name = []
            for next_line in lines[i + 1 : i + 1 + MAX_NAME_LINES]:
                if _STOP.match(next_line) or next_line.lower() in DOCUMENT_TYPES:
                    break
                name.append(next_line)
            title = _sentence_case(" ".join([line, *name]))
            if name and not name[0].isupper():  # "NGHỊ ĐỊNH" / "Quy định về …" → "Nghị định quy định về …"
                cut = len(_sentence_case(line)) + 1
                title = title[:cut] + title[cut : cut + 1].lower() + title[cut + 1 :]
            return title, number
    return "", number


def document_label(title: str, number: str) -> str:
    """How a source names its document: "Luật giao thông đường bộ (23/2008/QH12)"."""
    if title and number:
        return f"{title} ({number})"
    return title or number


def _opening_lines(pages: list[PageText]) -> list[str]:
    """The first non-empty lines, without markdown, each table cell a line of its own."""
    lines = []
    for page in pages:
        for raw in page.text.splitlines():
            for cell in raw.split("|"):
                text = unicodedata.normalize("NFC", " ".join(re.sub(r"[*_#]", " ", cell).split()))
                if text and not set(text) <= set("-: "):  # skip markdown table rules
                    lines.append(text)
            if len(lines) >= OPENING_LINES:
                return lines
    return lines


def _sentence_case(text: str) -> str:
    """Upper-case title lines lowered; the first letter capitalised."""
    words = [w.lower() if w.isupper() else w for w in text.split()]
    title = " ".join(words)
    return title[:1].upper() + title[1:]
