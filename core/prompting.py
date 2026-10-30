"""Answer prompt with [S#]-labelled sources, and mapping labels back to chunks (SAD 6.7–6.8)."""

import re

from core.models import Chunk, Citation, RetrievedChunk

NOT_FOUND = "Không tìm thấy thông tin này trong tài liệu đã nạp."

# Chosen by the `prompt` setting. v2 adds rules against the answer errors found in the R4 run:
# items listed for a range they only partly match, answers longer than asked, documents named
# by their file name, whole questions refused when the sources answer part of them.
SYSTEM_PROMPTS = {
    "v1": f"""You answer questions about the user's documents using only the numbered sources provided.
- Use only information in the sources [S1]...[Sn]. Never use outside knowledge.
- End every sentence that uses information from a source with its label, e.g. [S1] or [S1][S3].
- If the sources do not contain the answer, reply exactly: {NOT_FOUND}
- Answer in the language of the question.""",
    "v2": f"""You answer questions about the user's documents using only the numbered sources provided.
- Use only information in the sources [S1]...[Sn]. Never use outside knowledge.
- End every sentence that uses information from a source with its label, e.g. [S1] or [S1][S3].
- Reply exactly "{NOT_FOUND}" only when the sources contain nothing that answers the question.
  If they answer part of it, answer that part and say which part is missing.
- Answer only what the question asks. Give the direct answer first, then only the details needed to support it.
- When the question asks which items meet a condition (an amount, range, date, duration, party or status),
  include an item only if the source states that same condition for that item, directly or through the
  heading or lead-in sentence of the list it belongs to. A partial match does not count: a range that shares
  only one end, a different amount, or a condition stated for a neighbouring item. List every item that meets
  the condition, and nothing else.
- Copy numbers, amounts, dates and names exactly as the source writes them.
- Name a document by the title or number written in the source text; use the file name only when the text gives none.
- Say where the answer is (section, article, clause or page), as the source shows it.
- Answer in the language of the question.""",
}

# "[S1]" or "[S1, S3]"
_LABEL_GROUP = re.compile(r"\[(S\d+(?:\s*,\s*S\d+)*)\]")


def build_messages(question: str, sources: list[RetrievedChunk],
                   system_prompt: str = SYSTEM_PROMPTS["v1"]) -> list[tuple[str, str]]:
    evidence = "\n\n".join(
        f"[S{i}] {_source_line(s.chunk)}\n{s.chunk.text}" for i, s in enumerate(sources, start=1)
    )
    return [("system", system_prompt), ("human", f"Sources:\n\n{evidence}\n\nQuestion: {question}")]


def extract_citations(answer: str, sources: list[RetrievedChunk]) -> list[Citation]:
    """Sources cited in ``answer``, in order of first appearance.
    Labels that match no source are dropped (SAD Table 5.10)."""
    numbers: list[int] = []
    for group in _LABEL_GROUP.finditer(answer):
        for label in group.group(1).split(","):
            n = int(label.strip()[1:])
            if 1 <= n <= len(sources) and n not in numbers:
                numbers.append(n)
    return [Citation(label=f"S{n}", chunk=sources[n - 1].chunk) for n in numbers]


def _source_line(chunk: Chunk) -> str:
    """'contract.pdf · Điều 5. Phạt vi phạm › Khoản 1 · page 6' (SAD 6.7)."""
    page = None if chunk.page is None else f"page {chunk.page}"
    return " · ".join(part for part in (chunk.source, chunk.section, page) if part)
