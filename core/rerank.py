"""Reranking (R4, SAD 6.6): a cross-encoder reads the question together with each candidate
chunk and rescores it — more accurate than comparing vectors, so it reorders the candidates
of the search and keeps the best few. Scores below the threshold are dropped instead of
filling the context with noise; with none left, the pipeline refuses without calling the LLM."""

from __future__ import annotations

from collections.abc import Callable

from core.models import RetrievedChunk

Score = Callable[[str, list[str]], list[float]]  # (question, passages) → relevance in [0, 1]


class Reranker:
    def __init__(self, score: Score, keep: int, threshold: float | None = None):
        self.score = score
        self.keep = keep
        self.threshold = threshold  # None: always keep ``keep`` chunks

    def __call__(self, question: str, hits: list[RetrievedChunk]) -> list[RetrievedChunk]:
        """The ``keep`` best hits at or above the threshold, best first, carrying the reranker's score."""
        if not hits:
            return []
        scores = self.score(question, [h.chunk.text for h in hits])
        ranked = sorted(zip(hits, scores, strict=True), key=lambda pair: pair[1], reverse=True)
        kept = [RetrievedChunk(hit.chunk, score) for hit, score in ranked
                if self.threshold is None or score >= self.threshold]
        return kept[: self.keep]


def onnx_cross_encoder(model_path: str, tokenizer_path: str, max_length: int, batch_size: int) -> Score:
    """Scores with a cross-encoder exported to ONNX (e.g. bge-reranker-v2-m3 int8) on the CPU."""
    import numpy as np
    import onnxruntime
    from tokenizers import Tokenizer

    session = onnxruntime.InferenceSession(model_path, providers=["CPUExecutionProvider"])
    inputs = {i.name for i in session.get_inputs()}
    tokenizer = Tokenizer.from_file(tokenizer_path)
    tokenizer.enable_truncation(max_length=max_length)
    tokenizer.enable_padding(pad_id=tokenizer.token_to_id("<pad>"), pad_token="<pad>")

    def score(question: str, passages: list[str]) -> list[float]:
        scores: list[float] = []
        for start in range(0, len(passages), batch_size):
            encoded = tokenizer.encode_batch([(question, p) for p in passages[start:start + batch_size]])
            feeds = {
                "input_ids": np.array([e.ids for e in encoded], dtype=np.int64),
                "attention_mask": np.array([e.attention_mask for e in encoded], dtype=np.int64),
                "token_type_ids": np.array([e.type_ids for e in encoded], dtype=np.int64),
            }
            logits = session.run(None, {name: feeds[name] for name in inputs})[0]
            scores += (1 / (1 + np.exp(-logits.reshape(len(encoded), -1)[:, 0]))).tolist()
        return scores

    return score
