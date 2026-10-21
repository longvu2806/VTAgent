"""Application settings, overridable via VTAGENT_* environment variables or .env."""

from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE = Path(__file__).parent / ".env"  # found regardless of the working directory


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VTAGENT_", env_file=ENV_FILE, extra="ignore")

    # Storage
    data_dir: Path = Path("data")
    qdrant_url: str | None = None  # unset: embedded Qdrant under data_dir/qdrant
    collection: str = "vtagent_docs_r0"

    # Models served by Ollama.
    # Use 127.0.0.1, not localhost: on Windows, localhost tries IPv6 first and adds ~2 s
    # to every request to a server that listens on IPv4 only (Ollama, Qdrant in Docker).
    ollama_base_url: str = "http://127.0.0.1:11434"
    llm_model: str = "qwen3.5:9b"
    llm_num_ctx: int = 8192  # Ollama's default context silently truncates prompts
    llm_temperature: float = 0.0
    llm_timeout_s: float = 300  # stops an answer stuck in a repetition loop
    embedding_model: str = "bge-m3"
    tokenizer_name: str = "BAAI/bge-m3"  # must match embedding_model

    # Chunking (SAD Table 6.5): "fixed" = R0, windows of chunk_size tokens per page;
    # "structured" = R1, parent–child chunks along Điều / Khoản / Điểm (SAD 6.2)
    chunking: Literal["fixed", "structured"] = "fixed"
    chunk_size: int = 400  # tokens (fixed)
    chunk_overlap: int = 50  # tokens (fixed)
    child_min_tokens: int = 80  # structured: smaller children merge with the next (SAD Table 6.3)
    child_max_tokens: int = 400  # structured: larger children are split
    parent_max_tokens: int = 1200  # structured: longer articles are split into several parents
    context_budget_tokens: int = 2500  # structured: evidence in the answer prompt (SAD Table 6.4)

    # Retrieval (SAD 6.4–6.6). A sparse type needs its own collection (VTAGENT_COLLECTION).
    top_k: int = 5
    sparse: Literal["none", "bm25", "bge-m3"] = "none"  # hybrid search: R3 = bm25, R3′ = bge-m3
    normalize_numbers: bool = False  # bm25 only: "160 triệu" and "160.000.000" become one token
    bge_m3_precision: Literal["int8", "fp32"] = "int8"  # bge-m3 sparse model; int8 fits the RAM budget
    rerank: bool = False  # R4: cross-encoder reranks the candidates down to top_k
    reranker_repo: str = "onnx-community/bge-reranker-v2-m3-ONNX"
    reranker_file: str = "onnx/model_int8.onnx"  # ONNX int8 on the CPU (SAD 6.6)
    rerank_threshold: float | None = None  # None: keep top_k; set after calibrating on the eval sets

    # LLM judge of the eval's RAGAS metrics (any OpenAI-compatible API). Used only by
    # tests/eval/score.py; the judge model is chosen in tests/eval/score.toml.
    judge_base_url: str = "https://openrouter.ai/api/v1"
    judge_api_key: SecretStr | None = None  # secret: set it in .env, which is git-ignored


JUDGE_SETTINGS = {"judge_base_url", "judge_api_key"}  # do not affect generated answers

settings = Settings()
