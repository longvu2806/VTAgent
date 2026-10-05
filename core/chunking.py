"""R0 chunking: fixed-size token windows with overlap (SAD Table 6.5)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tokenizers import Tokenizer


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
