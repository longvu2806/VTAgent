"""Context assembly (SAD 6.7): the retrieved child chunks → the sources shown to the LLM."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from core.chunking import SECTION_SEP
from core.models import RetrievedChunk


def assemble(hits: list[RetrievedChunk], budget: int, count_tokens: Callable[[str], int]) -> list[RetrievedChunk]:
    """Swap children for their parents while the sources fit ``budget`` tokens.

    Children are expanded best-ranked first, so when the budget runs out the lowest-ranked
    stay children. Children of one parent become a single source, which keeps the id, page
    and score of the best-ranked one so its [S#] label still points at a known chunk.
    Retrieved children are never dropped. Sources come back in document order: documents
    by their best hit, then position in the document."""
    sources = list(hits)
    cost = sum(count_tokens(h.chunk.text) for h in hits)
    for hit in hits:
        parent = hit.chunk.parent_id
        if parent is None or hit not in sources:  # no parent, or already merged into it
            continue
        siblings = [s for s in sources if s.chunk.parent_id == parent]
        new_cost = cost - sum(count_tokens(s.chunk.text) for s in siblings) + count_tokens(hit.chunk.parent_text)
        if new_cost > budget:
            continue
        section = hit.chunk.section.split(SECTION_SEP)[0]  # the article, not the Khoản
        merged = replace(hit, chunk=replace(hit.chunk, text=hit.chunk.parent_text, section=section))
        sources = [merged if s is hit else s for s in sources if s is hit or s.chunk.parent_id != parent]
        cost = new_cost

    first_hit: dict[str, int] = {}
    for rank, s in enumerate(sources):
        first_hit.setdefault(s.chunk.doc_id, rank)
    return sorted(sources, key=lambda s: (first_hit[s.chunk.doc_id], s.chunk.index))
