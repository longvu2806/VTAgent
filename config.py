"""Application settings, overridable via VTAGENT_* environment variables or .env."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE = Path(__file__).parent / ".env"  # found regardless of the working directory


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VTAGENT_", env_file=ENV_FILE, extra="ignore")

    # Storage
    data_dir: Path = Path("data")
    qdrant_url: str | None = None  # unset: embedded Qdrant under data_dir/qdrant
    collection: str = "vtagent_docs_r0"

    # Models served by Ollama
    ollama_base_url: str = "http://localhost:11434"
    llm_model: str = "qwen3.5:9b"
    llm_num_ctx: int = 8192  # Ollama's default context silently truncates prompts
    llm_temperature: float = 0.0
    embedding_model: str = "bge-m3"
    tokenizer_name: str = "BAAI/bge-m3"  # must match embedding_model

    # R0 baseline: fixed-size chunking, dense-only retrieval (SAD Table 6.5)
    chunk_size: int = 400  # tokens
    chunk_overlap: int = 50  # tokens
    top_k: int = 5


settings = Settings()
