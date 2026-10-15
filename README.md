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

Run every command from the repository root with the virtual environment
activated (`.venv\Scripts\activate`). Make sure Ollama is running first.
Settings come from `.env` (see `.env.example`); the effective settings are
logged at the start of every run.

### 1. Ingest documents

```bash
python main.py ingest contract.docx appendix.pdf
```

Pass one or more files. Each file is parsed, split into 400-token chunks,
embedded with bge-m3 and indexed in Qdrant. One line is printed per file:

```
indexed contract.docx → 648899d2d11bab78 (12 chunks)
rejected: notes.txt: unsupported format '.txt' (PDF and DOCX only)
rejected: scan.pdf: no text layer found (scanned document?)
not found: missing.pdf
```

- **Formats:** PDF and DOCX with a text layer. Scanned PDFs and other formats
  are rejected with the reason; the remaining files are still ingested.
- **Re-ingesting is safe:** a file already indexed (same content) is skipped,
  so you can re-run the same command after adding new files.
- **Whole folder:** PowerShell does not expand `*` for Python, so pass the files
  explicitly:

  ```powershell
  python main.py ingest (Get-ChildItem docs\*.pdf, docs\*.docx).FullName
  ```

- **Where data goes:** `data/files/` keeps a copy of each original (for checking
  citations), `data/qdrant/` holds the index, `data/vtagent.db` lists the
  indexed documents.
- **Start over:** delete the `data/` folder and ingest again.
- **Changed chunking settings?** Also change `VTAGENT_COLLECTION` (e.g.
  `vtagent_docs_r0_300`). Documents are tracked per collection, so files already
  indexed with the old settings would otherwise be skipped.

### 2. Ask questions

```bash
python main.py ask "Mức phạt chậm giao hàng là bao nhiêu?"
```

Quote the question. The system retrieves the 5 most similar chunks, and
qwen3.5:9b answers from them only. Each sentence ends with a source label, and
a table maps every label to its file, page and text so you can check it:

```
Mức phạt là 0,05% giá trị phần nghĩa vụ bị vi phạm cho mỗi ngày chậm,
tối đa 8% [S1].

┌───────┬───────────────┬──────┬──────────────────────────────────┐
│ Label │ Source        │ Page │ Text                             │
├───────┼───────────────┼──────┼──────────────────────────────────┤
│ S1    │ contract.docx │ –    │ Điều 5. Phạt vi phạm. Trường hợp…│
└───────┴───────────────┴──────┴──────────────────────────────────┘
```

- Page shows `–` for DOCX files, which have no pages.
- If the documents do not contain the answer, the reply is exactly
  *"Không tìm thấy thông tin này trong tài liệu đã nạp."* and no table is shown.
- Expect about 10–30 s per question on the reference laptop; the first question
  after starting Ollama is slower because the model has to load.
- Each `ask` is independent: the R0 baseline has no conversation memory, so a
  follow-up must repeat its context ("phạt *chậm giao hàng* tối đa bao nhiêu?",
  not "tối đa bao nhiêu?").

### 3. Run the tests

```bash
python -m pytest
```

The unit tests run offline with fake models; Ollama is not needed.

### 4. Evaluate

Evaluation runs in two phases, so answers are generated once and scored as often as
needed.

```bash
# Phase 1: ask every question; needs Ollama and Qdrant (about 35 s per question)
python -m tests.eval.generate data/test/luat_gtdb_2008_eval100.csv --name r0
python -m tests.eval.generate data/test/luat_gtdb_2008_eval100.csv --name r0_dev --limit 10

# Phase 2: compute metrics and write a report
python -m tests.eval.score data/eval_runs/r0                    # all metrics, RAGAS included
python -m tests.eval.score data/eval_runs/r0 --skip ragas       # code metrics only: free, offline
python -m tests.eval.score data/eval_runs/r0 --skip latency,mrr
python -m tests.eval.score data/eval_runs/r0 --only faithfulness,factual_correctness
```

The metrics, how each is computed and which are primary are specified in
[tests/eval/METRICS.md](tests/eval/METRICS.md).

- **Dataset format:** a CSV with the columns documented in `tests/eval/dataset.py`.
  Only `id` and `question` are required; metrics that need a missing column are
  skipped and the report says why. Documents named in the `doc` column (next to the
  CSV) are ingested before the first question.
- **Phase 1 output** in `data/eval_runs/<name>/`: `results_<time>.csv` (open in Excel:
  answers, citations, retrieved pages, total latency and latency per stage, token
  counts) and `records_<time>.jsonl` (full chunk texts, read by phase 2). `<time>` is
  when the run was created (`YYYYMMDD-HHMMSS`); resuming keeps the same files.
- **Interrupted?** Rerun the same command: answered questions are skipped and failed
  ones retried. Changing settings in `.env` requires a new `--name`, so one run never
  mixes two configurations.
- **Time limit:** an answer still generating after `VTAGENT_LLM_TIMEOUT_S` (300 s) is
  stopped (the model sometimes loops). It is kept as far as it got, marked `timed_out`,
  scored like any answer and listed in the report; it is not retried.
- **Phase 2 output:** `report_<time>.md`, a new one per scoring, with the summary,
  latency per stage, scores per category and difficulty, and the failing questions.
  Next to it, `scores_<time>.csv` has one row per question and one column per metric
  (an empty cell: the metric does not apply to that question), for checking scores by hand.
  Turn metrics on and off in `tests/eval/score.toml` or with `--only` / `--skip`. The
  dataset is re-read, so a corrected dataset is scored without regenerating answers.
- **RAGAS metrics** (`context_precision`, `context_recall`, `faithfulness`,
  `answer_relevancy`, `factual_correctness`, `semantic_similarity`) use an LLM judge
  through any OpenAI-compatible API (DeepSeek directly, or OpenRouter) and bge-m3 on
  the local Ollama:
  1. In `.env`, set `VTAGENT_JUDGE_BASE_URL` (`https://api.deepseek.com` or
     `https://openrouter.ai/api/v1`) and `VTAGENT_JUDGE_API_KEY` (`.env` is git-ignored;
     never commit the key).
  2. Choose the judge model in `[judge]` of `tests/eval/score.toml` (`deepseek-v4-flash`
     on DeepSeek, `deepseek/deepseek-v4-flash` on OpenRouter).
  3. Start Ollama, then score. Without a key, the judge metrics are reported as skipped.

  One scoring of 80 answerable questions costs about $0.3–0.6. Verdicts are cached in
  the run directory (`judge_cache.jsonl`), so rescoring is free. The eval dataset is
  public law text; the judge is used only for evaluation, never in the running system.
