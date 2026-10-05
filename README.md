# VTAgent

Offline question answering over confidential Vietnamese documents, running on
one laptop with Ollama. This repo currently implements the **R0 baseline**
(naive RAG): fixed 400-token chunks, dense retrieval, top-5, answers with `[S#]`
citations. Design: `doc/VTAgent_SAD_v1_0.docx`.

## Setup (Windows)

1. Install [Ollama](https://ollama.com) and pull the models:

   ```bash
   ollama pull qwen3.5:9b
   ollama pull bge-m3
   ```

   Enable the iGPU and a large enough context (SAD 8.4), then restart Ollama:

   ```bash
   setx OLLAMA_IGPU_ENABLE 1
   setx OLLAMA_CONTEXT_LENGTH 8192
   ```

2. Create the environment:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Optional: copy `.env.example` to `.env` to override settings.

The first run downloads the bge-m3 tokenizer from Hugging Face. After that, set
`HF_HUB_OFFLINE=1` so processing makes no outbound connections (NFR-01).

## Usage

```bash
python main.py ingest contract.docx appendix.pdf
python main.py ask "Mức phạt chậm giao hàng là bao nhiêu?"
python -m pytest
```

Supported formats: PDF and DOCX with a text layer. Scanned PDFs are rejected.
Data (original files, Qdrant index, SQLite registry) is stored under `data/`.
