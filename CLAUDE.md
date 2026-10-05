# VTAgent

Offline question answering over confidential Vietnamese documents (mainly
contracts): multi-agent + Advanced RAG, running entirely on one laptop.
Undergraduate thesis project.

## Source of truth

- `doc/VTAgent_SAD_v1_0.docx` — architecture, fixed parameters, ablation plan.
  Read the relevant section before designing anything.
- `doc/design/*.drawio` — diagrams; `baseline.drawio` is the R0 pipeline.

## Rules

`.claude/rules/` is loaded automatically and always applies:
`coding_principles.md`, `code_style.md`, `configuration_rules.md`.

## Hardware constraint (drives every design decision)

Ryzen 7 8845HS, Radeon 780M iGPU (Vulkan, `OLLAMA_IGPU_ENABLE=1`), 32 GB RAM with
~26 GB usable, no discrete GPU. Inference is memory-bandwidth bound.
Priority is accuracy over latency; ceiling is p95 < 3 min per query.

## Stack

Ollama native (`qwen3.5:9b` answers, `qwen3.5:4b` routing/verification, `bge-m3`
embeddings), Qdrant, SQLite. Later: LangGraph (multi-agent), Streamlit (UI).
Qdrant runs embedded under `data/qdrant` until Docker is installed; set
`VTAGENT_QDRANT_URL` to switch to a server.

## Ablation configs (SAD Table 6.5)

| Id | Change vs previous |
|----|--------------------|
| R0 | Baseline: fixed 400-token chunks, dense only, top-5 |
| R1 | Structure-aware parent–child chunking (Điều / Khoản / Điểm) |
| R2 | Contextual headers |
| R3 | BM25 sparse vectors + RRF fusion (R3′: bge-m3 sparse) |
| R4 | Cross-encoder reranking 40 → 5 |
| R5 | Claim verification + second retrieval round |

## Commands

```bash
python -m pytest                               # offline unit tests
python main.py ingest doc1.pdf doc2.docx       # index documents
python main.py ask "Mức phạt chậm giao hàng?"  # ask a question
```
