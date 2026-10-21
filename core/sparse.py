"""Sparse vectors for hybrid search (SAD 6.4): keyword weights that catch the numbers and codes
dense vectors blur ("160.000.000 đồng", "67/2025/QH15", "Điều 16").

Two encoders with the same interface, chosen by configuration:
- ``BM25Encoder`` (R3): BM25 term frequencies over a tokenizer that keeps numbers and codes
  whole and adds adjacent-syllable pairs for Vietnamese compounds; Qdrant applies the IDF.
- ``BgeM3SparseEncoder`` (R3′): bge-m3's learned lexical weights, through onnxruntime.
"""

from __future__ import annotations

import re
import unicodedata
import zlib
from collections import Counter
from typing import TYPE_CHECKING, Protocol

from core.models import SparseVector

if TYPE_CHECKING:
    from collections.abc import Callable


class SparseEncoder(Protocol):
    def documents(self, texts: list[str]) -> list[SparseVector]: ...

    def query(self, text: str) -> SparseVector: ...


# --- BM25 (R3) ---------------------------------------------------------------------------------

TOKEN = re.compile(r"\d+(?:[.,]\d+)*%?|\w+(?:[-/]\w+)*", re.UNICODE)  # SAD 6.4
_MARKDOWN = re.compile(r"[*_#]")  # emitted by the PDF parser; "_" would glue onto words


def tokenize(text: str, normalize: bool = False) -> list[str]:
    """Syllables plus adjacent-syllable pairs: "phạt vi phạm 8%" → phạt, vi, phạm, 8%,
    phạt_vi, vi_phạm, phạm_8%."""
    text = _MARKDOWN.sub(" ", unicodedata.normalize("NFC", text).lower())
    if normalize:
        text = normalize_numbers(text)
    syllables = TOKEN.findall(text)
    return syllables + [f"{a}_{b}" for a, b in zip(syllables, syllables[1:])]


_DATE_SLASH = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_DATE_WORDS = re.compile(r"\b(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})\b")
_SCALED = re.compile(r"\b(\d+(?:[.,]\d+)*)\s*(nghìn|ngàn|triệu|tỷ|tỉ)\b(?!\s+lệ)")  # not "tỷ lệ"
_THOUSANDS = re.compile(r"\b\d{1,3}(?:\.\d{3})+\b(?![.,]\d)")
_LEADING_ZERO = re.compile(r"\b0(\d)\b")
_SCALE = {"nghìn": 10**3, "ngàn": 10**3, "triệu": 10**6, "tỷ": 10**9, "tỉ": 10**9}


def normalize_numbers(text: str) -> str:
    """One spelling per number, so a question and a document match however each writes it:
    "160 triệu" and "160.000.000" → "160000000"; "1/3/2027" and "01 tháng 3 năm 2027" →
    "2027-3-1"; "05 ngày" → "5 ngày". Decimal commas ("0,25") and references ("Điều 7.3",
    "5.1.") are kept. Expects lower-case text."""
    text = _DATE_SLASH.sub(lambda m: f"{m[3]}-{int(m[2])}-{int(m[1])}", text)
    text = _DATE_WORDS.sub(lambda m: f"{m[3]}-{int(m[2])}-{int(m[1])}", text)
    while (scaled := _SCALED.sub(_scale, text)) != text:  # "30 nghìn tỷ" takes two passes
        text = scaled
    text = _THOUSANDS.sub(lambda m: m[0].replace(".", ""), text)
    return _LEADING_ZERO.sub(r"\1", text)


def _scale(m: re.Match) -> str:
    number = m[1]
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", number):
        number = number.replace(".", "")
    value = float(number.replace(",", ".")) * _SCALE[m[2]]
    return str(round(value))


def _term_id(token: str) -> int:
    """Stable 32-bit id (Python's hash() changes between runs)."""
    return zlib.crc32(token.encode("utf-8"))


class BM25Encoder:
    """Document side: BM25 term-frequency weights; query side: 1 per term. Qdrant multiplies
    in the IDF of each term (sparse vector with ``Modifier.IDF``)."""

    def __init__(self, k1: float, b: float, avg_len: float, normalize: bool = False):
        self.k1, self.b, self.avg_len, self.normalize = k1, b, avg_len, normalize

    def documents(self, texts: list[str]) -> list[SparseVector]:
        return [self._document(text) for text in texts]

    def _document(self, text: str) -> SparseVector:
        tokens = tokenize(text, self.normalize)
        norm = self.k1 * (1 - self.b + self.b * len(tokens) / self.avg_len)
        weights: dict[int, float] = {}
        for token, tf in Counter(tokens).items():
            term = _term_id(token)
            weights[term] = weights.get(term, 0.0) + tf * (self.k1 + 1) / (tf + norm)
        return SparseVector(list(weights), list(weights.values()))

    def query(self, text: str) -> SparseVector:
        terms = sorted({_term_id(t) for t in tokenize(text, self.normalize)})
        return SparseVector(terms, [1.0] * len(terms))


# --- bge-m3 lexical weights (R3′) -----------------------------------------------------------------

class BgeM3SparseEncoder:
    """bge-m3's sparse head through onnxruntime (bge-m3-lite). Term ids are tokenizer ids and
    the weights are learned, so the collection uses no IDF. Dense vectors still come from Ollama."""

    def __init__(self, encode: Callable[[list[str]], list[dict[str, float]]]):
        self.encode = encode  # texts → lexical weights {token id: weight}

    @classmethod
    def load(cls, precision: str) -> BgeM3SparseEncoder:
        from bge_m3_lite import BGEM3Embedder

        model = BGEM3Embedder(precision=precision)

        def encode(texts: list[str]) -> list[dict[str, float]]:
            return model.encode(texts, return_dense=False, return_sparse=True)["lexical_weights"]

        return cls(encode)

    def documents(self, texts: list[str]) -> list[SparseVector]:
        return [self._vector(weights) for weights in self.encode(texts)]

    def query(self, text: str) -> SparseVector:
        return self.documents([text])[0]

    @staticmethod
    def _vector(weights: dict[str, float]) -> SparseVector:
        items = sorted((int(term), float(w)) for term, w in weights.items() if w > 0)
        return SparseVector([t for t, _ in items], [w for _, w in items])
