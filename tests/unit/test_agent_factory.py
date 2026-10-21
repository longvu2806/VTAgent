"""The sparse encoder is chosen by configuration."""

from config import Settings
from core import agent_factory
from core.sparse import BgeM3SparseEncoder, BM25Encoder


def _settings(**values):
    return Settings(_env_file=None, **values)


def test_no_sparse_encoder_for_dense_search():
    assert agent_factory.sparse_encoder(_settings(sparse="none")) is None


def test_bm25_encoder_follows_the_number_normalization_setting():
    encoder = agent_factory.sparse_encoder(_settings(sparse="bm25", normalize_numbers=True))

    assert isinstance(encoder, BM25Encoder) and encoder.normalize


def test_bge_m3_encoder_is_loaded_at_the_configured_precision(monkeypatch):
    loaded = []
    monkeypatch.setattr(BgeM3SparseEncoder, "load", classmethod(lambda cls, precision: loaded.append(precision)))

    agent_factory.sparse_encoder(_settings(sparse="bge-m3", bge_m3_precision="fp32"))

    assert loaded == ["fp32"]
