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


def test_ollama_switches_thinking_by_the_setting():
    assert agent_factory._llm(_settings(llm_thinking=True)).reasoning is True
    assert agent_factory._llm(_settings()).reasoning is False


def test_an_openai_compatible_server_gets_qwens_thinking_switch():
    llm = agent_factory._llm(_settings(model_server="openai", llm_model="Qwen/Qwen3.5-9B", llm_thinking=True,
                                       llm_base_url="http://127.0.0.1:8001/v1"))

    assert (llm.model_name, llm.openai_api_base) == ("Qwen/Qwen3.5-9B", "http://127.0.0.1:8001/v1")
    assert llm.extra_body == {"chat_template_kwargs": {"enable_thinking": True}}
    assert llm.stream_usage


def test_an_openai_compatible_server_embeds_plain_text():
    embedder = agent_factory._embedder(_settings(model_server="openai", embedding_model="BAAI/bge-m3",
                                                 embedding_base_url="http://127.0.0.1:8002/v1"))

    assert (embedder.model, embedder.openai_api_base) == ("BAAI/bge-m3", "http://127.0.0.1:8002/v1")
    assert not embedder.check_embedding_ctx_length  # no tiktoken ids for a non-OpenAI model
