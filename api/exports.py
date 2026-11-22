"""An answer as a file to keep or send on (UC14, FR-31, SDD 10.4)."""

from __future__ import annotations

import json

from api.schemas import TurnOut

DISCLAIMER = "_VTAgent chỉ trả lời từ tài liệu đã nạp và không thay thế tư vấn chuyên môn._"


def turn_markdown(turn: TurnOut, passages: dict[str, str]) -> str:
    """``passages``: the text of each cited chunk still in the index, by chunk id."""
    lines = [f"# {turn.question}", "", turn.answer or "", ""]
    if turn.missing:
        lines += [f"**Chưa tìm thấy:** {turn.missing}", ""]
    if turn.warnings:
        lines += ["## Câu chưa đủ căn cứ", "", *(f"- Câu {w.sentence_index + 1}: {w.reason}" for w in turn.warnings), ""]
    if turn.citations:
        lines += ["## Nguồn", ""]
        for c in turn.citations:
            page = f", trang {c.page}" if c.page is not None else ""
            lines.append(f"- **[{c.label}]** {c.document_title}, {c.section}{page}")
            if c.chunk_id in passages:
                lines.append(f"  > {' '.join(passages[c.chunk_id].split())}")
        lines.append("")
    lines.append(DISCLAIMER)
    return "\n".join(lines)


def turn_json(turn: TurnOut, passages: dict[str, str]) -> str:
    sources = [c.model_dump() | {"passage": passages.get(c.chunk_id)} for c in turn.citations]
    return json.dumps(turn.model_dump() | {"sources": sources}, ensure_ascii=False, indent=2)
