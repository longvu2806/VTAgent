"""Reranker: reorders the candidates by a cross-encoder score, keeps the best few."""

import pytest
from tokenizers import Tokenizer
from tokenizers.models import WordLevel
from tokenizers.pre_tokenizers import WhitespaceSplit

from core.models import Chunk, RetrievedChunk
from core.rerank import Reranker, onnx_cross_encoder

SCORES = {"a": 0.2, "b": 0.9, "c": 0.6, "d": 0.05}


def _hits(texts):
    return [RetrievedChunk(Chunk(t, "d", "law.pdf", 1, i, t), 1 / (i + 1)) for i, t in enumerate(texts)]


def _score(question, passages):
    return [SCORES[p] for p in passages]


def test_reranker_orders_by_its_score_and_keeps_the_best():
    kept = Reranker(_score, keep=2)("q", _hits(["a", "b", "c", "d"]))

    assert [(h.chunk.text, h.score) for h in kept] == [("b", 0.9), ("c", 0.6)]


def test_reranker_drops_chunks_below_the_threshold():
    kept = Reranker(_score, keep=5, threshold=0.5)("q", _hits(["a", "b", "c", "d"]))

    assert [h.chunk.text for h in kept] == ["b", "c"]


def test_reranker_keeps_nothing_when_every_chunk_is_below_the_threshold():
    assert Reranker(_score, keep=5, threshold=0.95)("q", _hits(["a", "b"])) == []


def test_reranker_does_not_score_an_empty_list():
    def fail(question, passages):
        raise AssertionError("scored")

    assert Reranker(fail, keep=5)("q", []) == []


class _Session:
    """onnxruntime.InferenceSession stand-in that runs on the providers it is given, or the CPU."""

    def __init__(self, path, providers, available=("CPUExecutionProvider",)):
        self.providers = [p for p in providers if p in available] or ["CPUExecutionProvider"]

    def get_providers(self):
        return self.providers

    def get_inputs(self):
        return []


@pytest.fixture
def tokenizer_file(tmp_path):
    tokenizer = Tokenizer(WordLevel({"[UNK]": 0, "<pad>": 1}, unk_token="[UNK]"))
    tokenizer.pre_tokenizer = WhitespaceSplit()
    path = tmp_path / "tokenizer.json"
    tokenizer.save(str(path))
    return str(path)


def test_a_gpu_reranker_without_cuda_fails_instead_of_running_on_the_cpu(monkeypatch, tokenizer_file):
    import onnxruntime

    monkeypatch.setattr(onnxruntime, "InferenceSession", _Session)

    with pytest.raises(RuntimeError, match="onnxruntime-gpu"):
        onnx_cross_encoder("model.onnx", tokenizer_file, max_length=512, batch_size=8, device="cuda")
    assert callable(onnx_cross_encoder("model.onnx", tokenizer_file, max_length=512, batch_size=8))
