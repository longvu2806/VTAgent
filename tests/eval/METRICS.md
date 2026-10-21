# Eval metrics specification

How every metric of the eval is defined and computed. Read this before interpreting a
`report_<time>.md` or adding a metric. Code metrics live in `metrics.py`; judge metrics
are computed through RAGAS in `ragas_judge.py`.

- [1. The metric set](#1-the-metric-set)
- [2. Scoring pipeline](#2-scoring-pipeline)
- [3. Shared definitions](#3-shared-definitions)
- [4. Retrieval](#4-retrieval)
- [5. Answer correctness](#5-answer-correctness)
- [6. Grounding and citation](#6-grounding-and-citation)
- [7. Relevance](#7-relevance)
- [8. Abstention](#8-abstention)
- [9. System](#9-system)
- [10. The LLM judge](#10-the-llm-judge)
- [11. Ground truth required per metric](#11-ground-truth-required-per-metric)
- [12. Parameters and switches](#12-parameters-and-switches)
- [13. Known limitations](#13-known-limitations)
- [14. Planned metrics](#14-planned-metrics)
- [15. Adding a metric](#15-adding-a-metric)

## 1. The metric set

16 metrics in 6 tiers. **Primary** metrics go into the ablation table (R0–R5);
**secondary** ones diagnose and cross-check.

| # | Tier | Metric | Report name | Method | Role |
|---|---|---|---|---|---|
| 1 | Retrieval | Recall@k | `recall_at_k` | Code | ⭐ Primary |
| 2 | | MRR | `mrr` | Code | ⭐ Primary |
| 3 | | nDCG@k | `ndcg_at_k` | Code | Secondary |
| 4 | | Context Precision | `context_precision` | RAGAS | Secondary: cross-check of 1–3 |
| 5 | | Context Recall | `context_recall` | RAGAS | Secondary: cross-check of 1 |
| 6 | Answer Correctness | **Factual Correctness** | `factual_correctness` | RAGAS | ⭐ Primary |
| 7 | | Semantic Similarity | `semantic_similarity` | RAGAS (embeddings only) | Secondary |
| 8 | | Number Match | `number_match` | Code | Secondary |
| 9 | Grounding & Citation | **Faithfulness** | `faithfulness` | RAGAS | ⭐ Primary |
| 10 | | Citation F1 (with Citation Precision, Citation Recall) | `citation_f1`, `citation_precision`, `citation_recall` | Code | ⭐ Primary |
| 11 | | Citation Validity | `citation_validity` | Code | Secondary |
| 12 | Relevance | Answer Relevancy | `answer_relevancy` | RAGAS | Secondary |
| 13 | Abstention | Refusal Accuracy | `refusal_accuracy` | Code | ⭐ Primary |
| 14 | | False Refusal Rate | `false_refusal_rate` | Code | ⭐ Primary |
| 15 | System | Latency p50 / p95 per stage | `latency` | Code | ⭐ Primary (measured on the laptop) |
| 16 | | Timeout Rate | `timeout_rate` | Code | Secondary |

Rules behind the split:

- Where a gold label exists, measure in code: deterministic, free, sensitive to small
  differences between configurations.
- Where the meaning of an answer must be understood, use an LLM judge, and validate it
  against human labels (section 10).
- Report every primary metric with a 95 % confidence interval and break results down by
  question category: R0 already retrieves 93 % of the evidence, so differences between
  configurations show mainly per category.

Removed from earlier versions: *key point coverage* (lexical word overlap; it scored a
wrong answer 0.857), replaced by Factual Correctness.

## 2. Scoring pipeline

Scoring runs on a saved run (`records_<time>.jsonl`); answers are never regenerated.

1. Load the dataset (schema in `dataset.py`) and the run's records.
2. Drop metrics switched off in `score.toml` or with `--only` / `--skip`.
3. Drop metrics whose required dataset column is missing, and judge metrics that cannot
   run (no API key); the report lists them as `skipped` with the reason.
4. Judge metrics: send each applicable question to the judge (cached, section 10).
5. Score every **successful** record with every remaining metric. A metric returns a
   number in `[0, 1]`, or `None` when it does not apply to that question.
6. Aggregate: a metric's value is the **mean of its non-`None` per-question scores**
   (macro average). `n` in the report is the number of questions it applied to.
7. Repeat step 6 for each value of every `group_by` column (e.g. `category`).

Record states:

| State | Scored? | Retried by `generate`? |
|---|---|---|
| Answered | Yes | No |
| Timed out (`timed_out`) | **Yes**, as far as the answer got | No: with temperature 0 it would loop again |
| Failed (`error`) | No; listed under errors | Yes |
| Not generated | No; counted as missing | — |

Timed-out answers are scored rather than excluded, so a failure never raises the average
by leaving the denominator.

## 3. Shared definitions

### Normalisation

Before any text comparison in code, both sides are normalised: Unicode NFC, lower case,
markdown characters `*`, `_`, `#` removed, list bullets (`- ` at a line start) removed,
all whitespace collapsed to single spaces.

### Evidence quote

Each answerable question lists one or more **evidence quotes** in the dataset column
`evidence`: verbatim passages of the source document that together contain the answer.
They are fixed by the dataset, independent of how a configuration chunks the document.

### Quote containment

A chunk **contains** a quote when, after normalisation, the quote is a substring of the
chunk, **or** the longest contiguous block shared by chunk and quote covers at least
`evidence_match` (default **0.8**) of the quote's length. The second rule tolerates a
chunk boundary that cuts off the end of a quote (`difflib.SequenceMatcher`).

### Relevant chunk

A chunk is **relevant** to a question when it contains at least one of its quotes.

### Retrieved chunks

The chunks the search returned, in rank order. R0 shows them to the LLM as they are, so
they are also its **contexts** (`contexts` in the record, labelled `[S1]`, `[S2]`, … in the
prompt). R0 stores the top 5.

From R1 on, the search returns child chunks (one Khoản each) and context assembly swaps
them for their parent articles before the LLM reads them, in document order (SAD 6.7).
The record then keeps both:

- `retrieved`: the child chunks by rank. The code retrieval metrics (§4.1–4.3) use these,
  so they measure the search itself and stay comparable with R0: a whole article would
  contain the evidence more often and inflate recall, and document order has no ranks.
- `contexts`: the assembled sources the LLM read. Citation metrics and every judge metric
  (context precision and recall included) use these.

With hybrid search (R3), `score` is the RRF fusion score. With reranking (R4), `retrieved`
holds the top-k child chunks after reranking, and `score` is the reranker's relevance
in [0, 1]. The retrieval metrics therefore measure the chunks the LLM actually reads.

### Refusal

An answer is a **refusal** when, after normalisation, it **starts with** one of
`refusal_phrases` (default: the pipeline's fixed answer *"Không tìm thấy thông tin này
trong tài liệu đã nạp."*). An answer that answers first and only ends with the phrase
committed to an answer and is not a refusal.

## 4. Retrieval

Code metrics apply to answerable questions with at least one evidence quote and need the
column `evidence`.

### 4.1 `recall_at_k`: did the evidence reach the LLM?

```
recall@k(q) = |{ e ∈ E(q) : some chunk in top-k(q) contains e }| / |E(q)|
```

`E(q)` is the set of evidence quotes of question `q`; `k` defaults to 5.

- Counted per **quote**, not per chunk, so configurations with different chunk sizes
  are compared on the same units.
- A chunk containing several quotes counts for each; a quote in several chunks counts once.
- An upper bound on answer quality: evidence not retrieved can only be refused or
  hallucinated.
- Stricter than *hit rate*: a multi-hop question that retrieves 5 of its 6 quotes
  scores 0.833, not 1.

Example (question 10, 6 quotes): ranks 1–3 hold quotes {3, 4, 5}, {1}, {2}; quote 6
("Người đủ 24 tuổi trở lên …") is missing → 0.833. The answer then missed the age
condition. Listed as a failure when the score is 0.

### 4.2 `mrr`: how high is the first relevant chunk?

```
rr(q) = 1 / rank of the first relevant chunk   (0 if none is relevant)
MRR   = mean of rr(q)
```

Example (question 74): rank 1 irrelevant, rank 2 relevant → 0.5. Models attend most to
what they read first; reranking (R4) should raise this value.

### 4.3 `ndcg_at_k`: are the relevant chunks ranked first?

Binary relevance over the top-k chunks:

```
rel_i  = 1 if the chunk at rank i is relevant, else 0
DCG@k  = Σ_{i=1..k} rel_i / log2(i + 1)
IDCG@k = DCG of the same chunks reordered with the relevant ones first
nDCG@k = DCG@k / IDCG@k            (0 when no chunk is relevant)
```

The ideal is computed over the **retrieved** chunks, so nDCG measures ordering only and
missing evidence is left to `recall_at_k`. An earlier version assumed one ideal chunk
per quote and penalised a single chunk holding several quotes (question 3: perfect
retrieval scored 0.613); it was replaced.

### 4.4 `context_precision` (RAGAS): are useful chunks ranked first?

RAGAS `ContextPrecisionWithReference`. For each retrieved chunk the judge decides
whether it was useful for arriving at the **reference answer** (verdict 0/1, one call
per chunk). The score is the average precision of these verdicts:

```
AP = Σ_i (precision@i × v_i) / Σ_i v_i
```

A semantic counterpart of MRR/nDCG that needs no evidence quotes, only `expected_answer`.

### 4.5 `context_recall` (RAGAS): does the context support the reference answer?

RAGAS `ContextRecall`. The judge splits the reference answer into statements and marks
each as attributable to the retrieved chunks or not (one call):

```
context_recall = attributable reference statements / reference statements
```

A semantic counterpart of `recall_at_k`. Disagreements between the two are informative:
code says *miss* while the judge says *supported* suggests the dataset lacks an
alternative evidence quote; the opposite suggests a judge error or a chunk that holds the
quote without enough context.

## 5. Answer correctness

### 5.1 `factual_correctness` (RAGAS): is the answer correct?

RAGAS `FactualCorrectness`, mode `f1`, atomicity and coverage `low` (defaults). The
judge decomposes both answer and reference into claims, then checks each claim of one
against the other text:

```
TP = answer claims supported by the reference
FP = answer claims not supported by the reference
FN = reference claims not supported by the answer
precision = TP / (TP + FP),  recall = TP / (TP + FN),  F1 = 2PR / (P + R)
```

Applies to answerable questions with an `expected_answer`. A refusal of an answerable
question scores 0. Listed as a failure when the score is 0.

### 5.2 `semantic_similarity` (RAGAS, embeddings only): how close in meaning?

Cosine similarity between the embeddings of the answer and the reference answer, using
the local bge-m3 (no API cost). **Weak for legal text**: embeddings barely separate
*"được"* from *"không được"* or *"21 tuổi"* from *"18 tuổi"*. Report for reference
only; never draw conclusions from it.

### 5.3 `number_match`: are the required numbers in the answer?

Applies to answerable questions whose key points contain a number; needs `key_points`.

1. Normalise; remove article references (`điều 30`, `khoản 3`, `Điều 30.3.đ`).
2. Take every number not preceded by a letter (`B2`, `cm3`, `S1` are ignored).
3. Canonicalise: drop thousands separators (`3.500` → `3500`), use `.` as decimal mark
   (`0,25` → `0.25`).

```
number_match(q) = |numbers(key points) ∩ numbers(answer)| / |numbers(key points)|
```

A hard check that a judge cannot talk around: a missing age, distance or percentage
shows directly. Listed as a failure when below 1.

## 6. Grounding and citation

### 6.1 `faithfulness` (RAGAS): is every claim backed by the retrieved chunks?

RAGAS `Faithfulness`. The judge splits the answer into standalone statements (one call),
then decides for each whether it can be directly inferred from the retrieved chunks
(one call):

```
faithfulness = supported statements / statements
```

Reference-free: it measures hallucination against the context, not correctness. Not
scored for refusals (they claim nothing). Listed as a failure when below 0.5.

### 6.2 Citation metrics (code)

The pipeline labels retrieved chunks `[S1]…[Sn]` and asks the model to end each sentence
with the labels it relied on. **Raw labels** are every `[S#]` in the answer (including
`[S1, S3]`); **cited chunks** are the chunks the pipeline mapped valid labels to.

| Metric | Applies to | Formula |
|---|---|---|
| `citation_validity` | answers with ≥1 raw label | valid raw labels / raw labels (valid: 1 ≤ n ≤ chunks retrieved) |
| `citation_precision` | answerable, evidence, ≥1 cited chunk | relevant cited chunks / cited chunks |
| `citation_recall` | answerable, evidence | quotes contained in some cited chunk / quotes |
| `citation_f1` | answerable, evidence | 2PR / (P + R), with P = 0 when nothing is cited |

Validity is measured on raw labels because the pipeline silently drops invalid ones.
Low precision means over-citing (question 3 cites S1–S5 while only S1 holds evidence:
0.2); an answer that cites nothing gets recall 0 even when correct, because the user
cannot verify it.

## 7. Relevance

### 7.1 `answer_relevancy` (RAGAS): does the answer address the question?

RAGAS `AnswerRelevancy`, strictness 3. The judge generates 3 questions that the answer
would answer and flags whether the answer is noncommittal (3 calls); the generated
questions are embedded with bge-m3 and compared with the original question:

```
answer_relevancy = mean cosine(question, generated question) × (0 if every flag is noncommittal)
```

Catches evasive answers (question 78 talks around the question with the wrong article).
Even a perfect answer rarely reaches 1, so compare configurations rather than reading
the value as a rate.

## 8. Abstention

### 8.1 `refusal_accuracy`

Applies to unanswerable questions; needs `answerable`.
`score(q) = 1 if the answer is a refusal, else 0`. A 0 is a hallucination, the most
damaging failure for this system. Listed as a failure when 0.

### 8.2 `false_refusal_rate`

Applies to answerable questions (without the `answerable` column every question counts
as answerable). `score(q) = 1 if the answer is a refusal, else 0`. **Lower is better.**
Always report with `refusal_accuracy`: a system that always refuses scores 1.0 on both.
Listed as a failure when 1.

## 9. System

### 9.1 `latency`: time per stage

Stage timings per question, in seconds, over successful records:

| Stage | Meaning |
|---|---|
| `embed_query` | Embedding the question (bge-m3) |
| `search` | Vector search in Qdrant |
| `generate` | The whole LLM call, as measured by the pipeline |
| `llm_load` | Model loading inside Ollama (non-zero when the model was not resident) |
| `llm_prefill` | Ollama reading the prompt |
| `llm_decode` | Ollama generating the answer |
| `total` | Wall clock for the whole question, measured by `generate.py` |

The report gives mean, p50, p95 and max per stage (percentiles by linear interpolation
between closest ranks) and mean input / output tokens.

Methodology: the first question of a run includes model loading (see `llm_load`); Ollama
caches prompt prefixes, so never rerun a question to "warm up" a measurement; check
`ollama ps` shows `100% GPU` before a run; plug the laptop in and close other
applications (prefill throughput varied 2.6× between sessions).

### 9.2 `timeout_rate`

Share of successful records cut at the LLM time limit (`VTAGENT_LLM_TIMEOUT_S`).

## 10. The LLM judge

### Setup

| Item | Value |
|---|---|
| Library | RAGAS 0.4.3, `ragas.metrics.collections` (per-question `ascore`) |
| Judge | DeepSeek V4 Flash (`score.toml` → `[judge]`), through the DeepSeek API directly or OpenRouter |
| Why this judge | A different model family from the system's qwen3.5, so no self-preference bias |
| Connection | `VTAGENT_JUDGE_BASE_URL`, `VTAGENT_JUDGE_API_KEY` in `.env` (key is a secret) |
| Sampling | temperature 0, max 4096 output tokens, thinking off: DeepSeek thinks by default (197 thinking tokens for a 7-token verdict), so `extra_body = { thinking = { type = "disabled" } }`; OpenRouter: `reasoning = false` |
| Embeddings | local bge-m3 on Ollama (`answer_relevancy`, `semantic_similarity`) |
| Telemetry | RAGAS usage analytics disabled (`RAGAS_DO_NOT_TRACK=true`) |

### Which questions are judged

Only answerable questions; refusals of unanswerable ones are measured in code. Also:
`context_precision`, `context_recall`, `factual_correctness` and `semantic_similarity`
need an `expected_answer`; the context metrics and `faithfulness` need retrieved chunks;
`faithfulness` skips refusals and answers cut at the time limit (a cut repetition loop
has no complete claims, and its verdict overflows `max_tokens`). A judge result of NaN
(nothing to judge) counts as not applicable.

### Prompt review and adaptations

RAGAS prompts are English instructions with English few-shot examples, followed by a
JSON schema and the input as JSON (Vietnamese characters are kept as UTF-8). Findings
and what was changed:

| Finding | Risk | Adaptation |
|---|---|---|
| The judge may write extracted statements and generated questions in English | `answer_relevancy` compares a Vietnamese question with English ones, lowering scores for no reason; claims lose precision in translation | Every prompt gets a note: write statements, claims and questions in Vietnamese; keep numbers, units and legal references (Điều, khoản, điểm) as written |
| Noncommittal examples are English ("I don't know") | The fixed Vietnamese refusal might not be flagged as noncommittal | The `answer_relevancy` prompt names the refusal sentence as noncommittal, but only for an answer whose *only* content it is (a first wording also flagged answers that answered first; question 3 scored 0 instead of 0.97) |
| `FactualCorrectness` compares answer and reference without the question | Reference answers do not restate the question's situation, so an answer that does had every claim judged unsupported (question 28: 0 in 3 of 3 runs, although correct). RAGAS's `recall` mode does not help: its numerator also counts answer claims | The reference is framed with the question (`REFERENCE_FRAME`): question 28 → 1.0, wrong answers still score low |
| Answers carry `[S#]` labels | The judge may extract meaningless claims such as "according to S1" | Labels are stripped before judging |
| Answers cite sources ("Theo Điều 19 của Luật ...") that reference answers do not repeat | The judge attached the citation to every claim and rejected correct claims for it alone (question 39, verbatim-correct, scored 0; 7 of 80 questions affected) | `factual_correctness` prompts leave source attributions out and judge content only (`ATTRIBUTION_NOTE`); `faithfulness` still checks citations against the context, so a wrong article number counts there |
| A refusal yields a statement that cannot be supported | `faithfulness` would score 0 for an answer that claims nothing | `faithfulness` skips refusals |
| RAGAS's default limit of 1024 output tokens | Long faithfulness verdicts get truncated into invalid JSON | `max_tokens = 4096` |

`BasePrompt.adapt()` (LLM translation of the examples) is not used: it re-translates on
every run, so the prompts would not be fixed. The notes are versioned by
`PROMPT_VERSION` (all metrics) and `METRIC_PROMPT_VERSIONS` (one metric, so changing it
does not re-judge the others) in `ragas_judge.py`.

### Cache and reproducibility

Verdicts are cached in `judge_cache.jsonl` in the run directory, keyed on the judge
settings, the prompt version, the RAGAS version and the exact inputs. Rescoring costs
nothing; correcting a question in the dataset re-judges only that question. Failed calls
are not cached and are retried at the next scoring; after 5 failures with no success
the judge is considered unreachable and the remaining calls are skipped.

OpenRouter may route one model to several providers; set `providers` in `score.toml` to
pin one so reruns are judged by the same backend. Providers also update the model behind
a name (DeepSeek's `deepseek-v4-flash` may now serve V4.1): keep one model id for every
configuration R0–R5 and report it with the scoring date.

### Judge noise (measured)

Temperature 0 does not make the judge deterministic. Judging the same 8 answers three
times (DeepSeek `deepseek-flash`, 2026-10-09) gave means that moved by up to 0.07
(faithfulness 0.69 / 0.73 / 0.76) and single questions that moved by up to 0.52. The
cache freezes one draw, so a report is reproducible, but a difference between two
configurations is only meaningful if it exceeds this noise: judge R0 two or three times
to estimate it, and report judge metrics with confidence intervals.

### Validation (required before reporting judge metrics)

A judge is only as credible as its agreement with people. Before publishing
`factual_correctness` or `faithfulness`, label about 30 questions by hand (correct /
partly correct / wrong; supported / not supported), compare with the judge and report
Cohen's kappa. Accept the judge at κ ≥ 0.6; otherwise try a stronger model.

### Cost

About 15 judge calls per question (context precision 5, factual correctness 4, answer
relevancy 3, faithfulness 2, context recall 1; semantic similarity uses only the local
embeddings), roughly 20 k input and 3.4 k output tokens. For 80 answerable questions:
about 1.2 k calls, 1.6 M input and 0.27 M output tokens, **≈ $0.2–0.45 per scoring** (DeepSeek API directly: about $0.02 per 10 questions, measured)
with reasoning off, and **≈ $0.8–2.2** with reasoning on (300–1,000 thinking tokens per
call, billed as output), using DeepSeek V4 Flash on OpenRouter at $0.007 / $1.28 per
million input / output tokens (prices change; check the model page). Cached rescoring
is free.

## 11. Ground truth required per metric

| Metric | Reference-based? | Dataset columns | Applies to |
|---|---|---|---|
| `recall_at_k`, `mrr`, `ndcg_at_k` | yes | `evidence` | answerable |
| `context_precision`, `context_recall` | yes | `expected_answer` | answerable with chunks |
| `factual_correctness`, `semantic_similarity` | yes | `expected_answer` | answerable |
| `number_match` | yes | `key_points` | answerable, with numbers |
| `faithfulness` | no | – | answerable, not refused, with chunks |
| `citation_precision`, `citation_recall`, `citation_f1` | yes | `evidence` | answerable |
| `citation_validity` | no | – | answers with labels |
| `answer_relevancy` | no | – | answerable |
| `refusal_accuracy` | yes | `answerable` | unanswerable |
| `false_refusal_rate` | yes (optional) | `answerable` | answerable |
| `latency`, `timeout_rate` | no | – | all successful records |

Columns not used by any metric: `gold_refs` (for readers; a future clause-level citation
metric), `gold_pages` (shown in the failure list), `category` / `difficulty` (grouping).

## 12. Parameters and switches

`tests/eval/score.toml`:

| Section | Key | Default | Used by |
|---|---|---|---|
| `[params]` | `k` | 5 | `recall_at_k`, `ndcg_at_k` |
| | `evidence_match` | 0.8 | every quote-containment test |
| | `refusal_phrases` | the pipeline's not-found answer | abstention metrics, judge selection |
| | `group_by` | `["category", "difficulty"]` | per-group tables |
| | `max_failures` | 20 | failing questions listed per metric |
| `[judge]` | `model` | `deepseek/deepseek-v4-flash` | judge metrics |
| | `temperature`, `max_tokens`, `reasoning`, `providers`, `max_concurrency` | 0, 4096, false, [], 8 | judge metrics |
| `[metrics]` | one boolean per metric | true | switches; unlisted metrics are on |

Command line: `--only a,b` scores just those, `--skip a,b` drops them; both accept the
group name `ragas` for all six judge metrics (`--skip ragas` scores code metrics only,
free and offline). Report the parameter values with any published number.

## 13. Known limitations

| Limitation | Effect | Mitigation |
|---|---|---|
| The judge is an LLM | Verdicts are noisy and may be biased | Temperature 0, cache, different model family, kappa validation |
| Evidence quotes are hand-picked | A missing quote makes recall look better | Cross-check with `context_recall`; the dataset builder checks quotes against the source |
| Larger chunks contain quotes more easily | Recall favours coarse chunking | Report mean `input_tokens` next to retrieval metrics |
| `recall_at_k` is capped by what the run stored | R0 stores 5 chunks, so recall@40 cannot be computed | Pipelines with reranking must store their candidates |
| Refusal detection is a prefix match | A refusal worded differently counts as an answer | Add phrases to `refusal_phrases` |
| `semantic_similarity` ignores negation and numbers | Contradictory answers can score high | Reference only |
| Single-document corpus | Retrieval is easier than with several documents | State it; the contract dataset adds documents |
| Small samples | One question moves a 10-question score by 10 points | Conclude from the full set with confidence intervals (planned) |

## 14. Planned metrics

| Metric | Needs |
|---|---|
| Recall@40 | Pipelines that expose their candidate list (R3/R4) |
| Confidence intervals and run comparison | A compare script over several runs (bootstrap) |
| Calculation Accuracy, Risk Detection Precision / Recall, Profile Field Accuracy, JSON Validity Rate, LLM Calls per Query | Multi-agent pipeline (R5) and the contract dataset with new columns |

## 15. Adding a metric

- **Code metric:** write `fn(item: EvalItem, rec: RunRecord, p: dict) -> float | None` in
  `metrics.py` (`None` when it does not apply) and register it in `METRICS` with a
  description, the dataset columns it `needs`, and optionally a `failed` predicate.
- **Judge metric:** register it in `METRICS` with `fn=None`, add its name to
  `JUDGE_METRICS`, and build and call the RAGAS object in `ragas_judge.build_scorer`.
- Then add it to `[metrics]` in `score.toml`, add a unit test, and document it here.
