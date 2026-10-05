"""Answer prompt with [S#]-labelled sources, and mapping labels back to chunks (SAD 6.7–6.8)."""

import re

from core.models import Chunk, Citation, RetrievedChunk

NOT_FOUND = "Không tìm thấy thông tin này trong tài liệu đã nạp."

SYSTEM_PROMPT = f"""You answer questions about the user's documents using only the numbered sources provided.
- Use only information in the sources [S1]...[Sn]. Never use outside knowledge.
- End every sentence that uses information from a source with its label, e.g. [S1] or [S1][S3].
- If the sources do not contain the answer, reply exactly: {NOT_FOUND}
- Answer in the language of the question."""

# "[S1]" or "[S1, S3]"
_LABEL_GROUP = re.compile(r"\[(S\d+(?:\s*,\s*S\d+)*)\]")


def build_messages(question: str, sources: list[RetrievedChunk]) -> list[tuple[str, str]]:
    evidence = "\n\n".join(
        f"[S{i}] {_source_line(s.chunk)}\n{s.chunk.text}" for i, s in enumerate(sources, start=1)
    )
    return [("system", SYSTEM_PROMPT), ("human", f"Sources:\n\n{evidence}\n\nQuestion: {question}")]


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
    return chunk.source if chunk.page is None else f"{chunk.source} · page {chunk.page}"
