"""Chunking. R0: fixed-size token windows (SAD Table 6.5). R1: parent–child chunks along
the document's structure — Điều / Khoản / Điểm (SAD 6.2)."""

from __future__ import annotations

import re
import unicodedata
from bisect import bisect_left, bisect_right
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from observability import log

if TYPE_CHECKING:
    from tokenizers import Tokenizer

    from core.models import PageText

SECTION_SEP = " › "  # "Điều 8. Các hành vi bị nghiêm cấm › Khoản 8"


@dataclass(frozen=True)
class Piece:
    """A chunk before it gets ids. Pieces with the same ``parent_key`` share one parent."""

    text: str
    page: int | None
    section: str = ""
    parent_key: str | None = None
    parent_text: str = ""


def split_fixed(text: str, tokenizer: Tokenizer, chunk_size: int, overlap: int) -> list[str]:
    """Split ``text`` into windows of ``chunk_size`` tokens, consecutive windows sharing
    ``overlap`` tokens. Chunks are slices of the original text, so citations quote the
    source verbatim."""
    if not 0 <= overlap < chunk_size:
        raise ValueError(f"need 0 <= overlap < chunk_size, got {overlap=} {chunk_size=}")

    offsets = tokenizer.encode(text, add_special_tokens=False).offsets
    step = chunk_size - overlap
    chunks = []
    for start in range(0, len(offsets), step):
        window = offsets[start : start + chunk_size]
        chunks.append(text[window[0][0] : window[-1][1]].strip())
        if start + chunk_size >= len(offsets):
            break
    return chunks


def split_pages_fixed(pages: list[PageText], tokenizer: Tokenizer, chunk_size: int, overlap: int) -> list[Piece]:
    """R0: fixed windows per page, so every chunk cites exactly one page."""
    return [Piece(text, page.page) for page in pages for text in split_fixed(page.text, tokenizer, chunk_size, overlap)]


# Structure patterns of SAD Table 6.2, matched on a line stripped of markdown and lower-cased.
# Widened for contracts: "ĐIỀU 5:", "Điều 5 – …", "**Điều 88** . **…**", clauses "5.1.", points "a.".
_ARTICLE = re.compile(r"(?:điều\s+\d+[a-z]?|phụ lục(?:\s+(?:số\s+)?[\divxlc]+)?)\s*(?:[.:–-](?!\d)|$)")
_HEADING = re.compile(r"(?:phần|chương|mục)\s+(?:[ivxlc]+|\d+)\b")  # starts a block, never a chunk
_CLAUSE = re.compile(r"(\d+(?:\.\d+)*)\.\s")
_POINT = re.compile(r"[a-zđ][.)]\s")
_PARAGRAPH = re.compile(r"\n\s*\n")
_SENTENCE = re.compile(r"(?<=[.;!?])\s+")
_PAGE_NUMBER = re.compile(r"\n[ \t]*\d{1,4}[ \t]*$")  # page-number line closing a page
_SPACE = re.compile(r"\s*")


def split_structured(pages: list[PageText], tokenizer: Tokenizer, child_min: int, child_max: int,
                     parent_max: int, fallback_max: int) -> list[Piece]:
    """R1 parent–child chunks (SAD 6.2).

    Pages are joined first, so an article may run across pages; each child cites the page it
    starts on. Each Điều (or Phụ lục) is a parent; each Khoản a child, the lead-in before
    Khoản 1 joining the first child. Children under ``child_min`` tokens merge with the next
    one; children over ``child_max`` are split at Điểm, then paragraph, then sentence
    boundaries (one sentence overlap). An article over ``parent_max`` tokens is cut into
    consecutive, non-overlapping groups of its children, each group a parent — SAD says a
    window around the child; fixed groups never repeat text, so parents dedupe cleanly.
    Text before the first article (parties, preamble) is one more block.

    Without any article the document is split at markdown headings, paragraphs and
    sentences into chunks of ``fallback_max`` tokens, without parents (SAD 6.2 fallback;
    one sentence overlap instead of 50 tokens)."""
    doc = _Doc(pages, tokenizer)
    blocks = doc.blocks()
    if not blocks:
        log.warning("no Điều found; falling back to paragraph chunks of %d tokens", fallback_max)
        spans = doc.fit((0, len(doc.text)), fallback_max, [doc.md_headings, doc.paragraphs, doc.sentences])
        return [Piece(doc.slice(s), doc.page_at(s[0])) for s in spans if doc.slice(s)]

    pieces = []
    bounds = [b[0] for b in blocks] + [len(doc.text)]
    if bounds[0] > 0:  # preamble
        pieces += doc.block_pieces((0, bounds[0]), "", child_min, child_max, parent_max)
    for (start, title), end in zip(blocks, bounds[1:]):
        pieces += doc.block_pieces((start, end), title, child_min, child_max, parent_max)
    return pieces


class _Doc:
    """The joined text of a document, its lines and token offsets."""

    def __init__(self, pages: list[PageText], tokenizer: Tokenizer):
        texts, self.page_starts, self.page_numbers = [], [], []
        offset = 0
        for page in pages:
            text = _PAGE_NUMBER.sub("", page.text.rstrip())
            self.page_starts.append(offset)
            self.page_numbers.append(page.page)
            texts.append(text)
            offset += len(text) + 2
        self.text = "\n\n".join(texts)
        self.lines = [(m.start(), _clean(m.group())) for m in re.finditer(r"(?m)^.*$", self.text)]
        self.token_starts = [o[0] for o in tokenizer.encode(self.text, add_special_tokens=False).offsets]

    # --- basics ---

    def count(self, start: int, end: int) -> int:
        return bisect_left(self.token_starts, end) - bisect_left(self.token_starts, start)

    def slice(self, span: tuple[int, int]) -> str:
        return self.text[span[0] : span[1]].strip()

    def page_at(self, start: int) -> int | None:
        visible = _SPACE.match(self.text, start).end()
        return self.page_numbers[bisect_right(self.page_starts, visible) - 1]

    # --- structure ---

    def blocks(self) -> list[tuple[int, str]]:
        """(start, title) per article. A Chương / Mục heading opens the next article's block."""
        blocks, heading_at = [], None
        for start, clean in self.lines:
            if _HEADING.match(clean):
                heading_at = start if heading_at is None else heading_at
            elif _ARTICLE.match(clean):
                line_end = self.text.find("\n", start)
                line = self.text[start : None if line_end == -1 else line_end]
                blocks.append((start if heading_at is None else heading_at, _title(line)))
                heading_at = None
        return blocks

    def block_pieces(self, span: tuple[int, int], title: str, child_min: int, child_max: int,
                     parent_max: int) -> list[Piece]:
        start, end = span
        clauses = [(s, _CLAUSE.match(c).group(1)) for s, c in self.lines if start < s < end and _CLAUSE.match(c)]
        cuts = [s for s, _ in clauses[1:]]  # the lead-in joins Khoản 1
        segments = _merge_small(list(zip([start, *cuts], [*cuts, end])), self.count, child_min)
        children = [c for seg in segments for c in self.fit(seg, child_max, [self.points, self.paragraphs, self.sentences])
                    if self.slice(c)]

        if self.count(start, end) <= parent_max:
            groups = [(children, (start, end))]
        else:
            groups = [(g, (g[0][0], g[-1][1])) for g in _group(children, self.count, parent_max)]

        pieces = []
        for group, (g_start, g_end) in groups:
            parent = self.slice((g_start, g_end))
            if g_start != start:  # a later group of a long article: repeat the article title
                parent = f"{title}\n\n{parent}"
            for child in group:
                number = _clause_of(child, clauses) if title else None  # a preamble has no Khoản
                section = title if number is None else f"{title}{SECTION_SEP}Khoản {number}"
                pieces.append(Piece(self.slice(child), self.page_at(child[0]), section, str(g_start), parent))
        return pieces

    # --- splitting ---

    def fit(self, span: tuple[int, int], limit: int, finders: list[Callable]) -> list[tuple[int, int]]:
        """``span`` cut into spans of at most ``limit`` tokens, at the first kind of boundary
        ``finders`` find inside it; token windows as the last resort."""
        start, end = span
        if self.count(start, end) <= limit:
            return [span]
        for i, find in enumerate(finders):
            cuts = find(start, end)
            if cuts:
                units = list(zip([start, *cuts], [*cuts, end]))
                return self._pack(units, limit, finders[i + 1 :], overlap=find == self.sentences)
        return self._windows(start, end, limit)

    def _pack(self, units: list[tuple[int, int]], limit: int, finer: list[Callable], overlap: bool) -> list[tuple[int, int]]:
        """Consecutive units packed greedily; with ``overlap`` a new span repeats the last unit."""
        spans, current, last = [], None, None
        for unit in units:
            if self.count(*unit) > limit:
                spans += [current] if current else []
                spans += self.fit(unit, limit, finer)
                current = last = None
            elif current is None:
                current, last = unit, unit
            elif self.count(current[0], unit[1]) <= limit:
                current, last = (current[0], unit[1]), unit
            else:
                spans.append(current)
                repeat = overlap and self.count(last[0], unit[1]) <= limit
                current, last = (last[0] if repeat else unit[0], unit[1]), unit
        return spans + ([current] if current else [])

    def _windows(self, start: int, end: int, limit: int) -> list[tuple[int, int]]:
        first, last = bisect_left(self.token_starts, start), bisect_left(self.token_starts, end)
        cuts = [self.token_starts[i] for i in range(first + limit, last, limit)]
        return list(zip([start, *cuts], [*cuts, end]))

    def points(self, start: int, end: int) -> list[int]:
        return [s for s, c in self.lines if start < s < end and _POINT.match(c)]

    def md_headings(self, start: int, end: int) -> list[int]:
        return [s for s, _ in self.lines if start < s < end and self.text.startswith("#", s)]

    def paragraphs(self, start: int, end: int) -> list[int]:
        return [m.end() for m in _PARAGRAPH.finditer(self.text, start, end) if m.end() < end]

    def sentences(self, start: int, end: int) -> list[int]:
        return [m.end() for m in _SENTENCE.finditer(self.text, start, end) if m.end() < end]


def _clean(line: str) -> str:
    """The line as structure patterns see it: no markdown, lower case."""
    return unicodedata.normalize("NFC", re.sub(r"[*_#]", "", line)).strip().lower()


def _title(line: str) -> str:
    """'**Điều 88** . **Hiệu lực thi hành**' → 'Điều 88. Hiệu lực thi hành'."""
    return re.sub(r"\s+([.:])", r"\1", " ".join(re.sub(r"[*_#]", "", line).split()))


def _clause_of(child: tuple[int, int], clauses: list[tuple[int, str]]) -> str | None:
    """Numbers of the Khoản the child covers: the one it starts in and those starting inside
    it, e.g. "7, 8" for a short Khoản 7 merged with Khoản 8."""
    before = [n for s, n in clauses if s <= child[0]]
    numbers = before[-1:] + [n for s, n in clauses if child[0] < s < child[1]]
    return ", ".join(numbers) or None


def _merge_small(spans: list[tuple[int, int]], count: Callable, minimum: int) -> list[tuple[int, int]]:
    """Spans under ``minimum`` tokens joined to the next span (the last one to the previous)."""
    merged: list[tuple[int, int]] = []
    for span in spans:
        if merged and count(*merged[-1]) < minimum:
            merged[-1] = (merged[-1][0], span[1])
        else:
            merged.append(span)
    if len(merged) > 1 and count(*merged[-1]) < minimum:
        last = merged.pop()
        merged[-1] = (merged[-1][0], last[1])
    return merged


def _group(children: list[tuple[int, int]], count: Callable, limit: int) -> list[list[tuple[int, int]]]:
    """Consecutive children grouped while a group spans at most ``limit`` tokens."""
    groups: list[list[tuple[int, int]]] = []
    for child in children:
        if groups and count(groups[-1][0][0], child[1]) <= limit:
            groups[-1].append(child)
        else:
            groups.append([child])
    return groups
