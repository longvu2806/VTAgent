# Eval metrics specification

How every metric in `tests/eval/metrics.py` is defined and computed. Read this before
interpreting a `report_<time>.md` or adding a metric.

- [1. Scoring pipeline](#1-scoring-pipeline)
- [2. Shared definitions](#2-shared-definitions)
- [3. Retrieval metrics](#3-retrieval-metrics)
- [4. Answer metrics](#4-answer-metrics)
- [5. Citation metrics](#5-citation-metrics)
- [6. Latency and tokens](#6-latency-and-tokens)
- [7. Ground truth required per metric](#7-ground-truth-required-per-metric)
- [8. Parameters](#8-parameters)
- [9. Known limitations](#9-known-limitations)
- [10. Planned metrics](#10-planned-metrics)
- [11. Adding a metric](#11-adding-a-metric)

## 1. Scoring pipeline

Scoring runs on a saved run (`records_<time>.jsonl`) and needs no models:

1. Load the dataset (schema in `dataset.py`) and the run's records.
2. Drop metrics that are switched off (`score.toml`, `--only`, `--skip`).
3. Drop metrics whose required dataset column is missing; the report lists them as
   `skipped` with the reason.
4. Score every **successful** record with every remaining metric. A metric returns a
   number in `[0, 1]`, or `None` when it does not apply to that question.
5. Aggregate: the value of a metric is the **mean of its non-`None` per-question
   scores** (macro average: each question weighs the same). `n` in the report is the
   number of questions the metric applied to.
6. Repeat step 5 for each value of every `group_by` column (e.g. `category`).

Record states:

| State | Scored? | Retried by `generate`? |
|---|---|---|
| Answered | Yes | No |
| Timed out (`timed_out`) | **Yes**, as far as the answer got | No: with temperature 0 it would loop again |
| Failed (`error`) | No; listed under errors | Yes |
| Not generated | No; counted as missing | — |

Timed-out answers are scored rather than excluded so that a failure never raises the
average by leaving the denominator.

## 2. Shared definitions

### Normalisation

Before any text comparison, both sides are normalised:

1. Unicode NFC, lower case.
2. Remove markdown characters `*`, `_`, `#` (emitted by the PDF parser).
3. Remove list bullets (`- ` at the start of a line).
4. Collapse all whitespace, including line breaks, to single spaces.

### Evidence quote

Each answerable question lists one or more **evidence quotes** in the dataset column
`evidence`: verbatim passages of the source document that together contain the answer.
Quotes are fixed by the dataset, independent of how a configuration chunks the document.

### Quote containment

A chunk **contains** a quote when, after normalisation:

- the quote is a substring of the chunk, **or**
- the longest contiguous block shared by chunk and quote covers at least
  `evidence_match` (default **0.8**) of the quote's length.

The second rule tolerates a chunk boundary that cuts off the end of a quote. It is
computed with `difflib.SequenceMatcher.find_longest_match`.

### Relevant chunk

A chunk is **relevant** to a question when it contains at least one of the question's
evidence quotes.

### Retrieved chunks

The chunks the pipeline showed the LLM, in rank order (`contexts` in the record; the
LLM sees them labelled `[S1]`, `[S2]`, …). R0 stores the top 5.

### Refusal

An answer is a **refusal** when, after normalisation, it **starts with** one of
`refusal_phrases` (default: the pipeline's fixed answer *"Không tìm thấy thông tin này
trong tài liệu đã nạp."*, trailing period ignored). An answer that answers first and only
ends with the phrase is not a refusal: it committed to an answer.

## 3. Retrieval metrics

Apply to: answerable questions with at least one evidence quote. Require column:
`evidence`.

### 3.1 `recall_at_k`: did the evidence reach the LLM?

The share of a question's evidence quotes found in its top-k retrieved chunks.

```
recall@k(q) = |{ e ∈ E(q) : ∃ chunk c in top-k(q) that contains e }| / |E(q)|
```

`E(q)` is the set of evidence quotes of question `q`; `k` defaults to 5.

- Counted per **quote**, not per chunk, so configurations with different chunk sizes
  are compared on the same units.
- A chunk containing several quotes counts for each of them; a quote found in several
  chunks counts once.
- It bounds answer quality from above: evidence that was not retrieved cannot be
  used, only refused or hallucinated.
- Stricter than *hit rate* (any quote found): a multi-hop question that retrieves 5 of
  its 6 quotes scores 0.833, not 1.

Example (question 10, 6 quotes):

| Rank | Page | Quotes contained |
|---|---|---|
| 1 | 33 | 3, 4, 5 |
| 2 | 31 | 1 |
| 3 | 32 | 2 |
| 4–5 | 36, 34 | – |

Quote 6 ("Người đủ 24 tuổi trở lên …") was not retrieved → recall@5 = 5/6 = 0.833.
The answer then missed the age condition.

Listed as a failure when the score is 0 (no evidence retrieved at all).

### 3.2 `mrr`: how high is the first relevant chunk?

Reciprocal rank of the first relevant chunk among all retrieved chunks.

```
rr(q)  = 1 / rank of the first relevant chunk     (0 if none is relevant)
MRR    = mean of rr(q)
```

Example (question 74): rank 1 is irrelevant, rank 2 is relevant → rr = 0.5.

Models attend most to what they read first; reranking (R4) should raise this value.

### 3.3 `ndcg_at_k`: is the whole ranking good?

Normalised discounted cumulative gain with binary relevance over the top-k chunks.

```
rel_i  = 1 if the chunk at rank i is relevant, else 0
DCG@k  = Σ_{i=1..k} rel_i / log2(i + 1)
nDCG@k = DCG@k / IDCG@k
```

Current implementation of the ideal DCG:

```
m       = min(k, max(|E(q)|, number of relevant chunks retrieved))
IDCG@k  = Σ_{i=1..m} 1 / log2(i + 1)
```

**Known issue:** this assumes the ideal ranking needs as many relevant chunks as there
are quotes. When one chunk contains several quotes, a perfect retrieval is penalised
(question 3: one chunk at rank 1 holds both quotes, yet nDCG = 0.613). Until fixed,
treat nDCG as a lower bound. The textbook fix is to take `m` as the number of relevant
chunks that exist in the whole index (capped at k). See [section 9](#9-known-limitations).

## 4. Answer metrics

### 4.1 `refusal_accuracy`: does the system refuse what it cannot answer?

Applies to: unanswerable questions (`answerable = no`). Requires column: `answerable`.

```
score(q) = 1 if the answer is a refusal, else 0
```

The value is the share of unanswerable questions correctly refused. A 0 means the
system answered a question the documents cannot answer: a hallucination, the most
damaging failure for this system. Listed as a failure when the score is 0.

### 4.2 `false_refusal_rate`: does it refuse what it could answer?

Applies to: answerable questions. Requires column: none (without `answerable`, every
question counts as answerable).

```
score(q) = 1 if the answer is a refusal, else 0
```

**Lower is better.** Read it together with `refusal_accuracy`: a system that always
refuses scores 1.0 on the first and 1.0 on this one. Listed as a failure when the
score is 1.

### 4.3 `key_point_coverage`: are the required points in the answer? (lexical proxy)

Applies to: answerable questions with key points. Requires column: `key_points`.

```
words(x)      = word tokens of normalise(x)              (regex \w+)
covered(p)    = |{ w ∈ words(p) : w ∈ words(answer) }| / |words(p)|  ≥  key_point_match
score(q)      = |{ p ∈ key_points(q) : covered(p) }| / |key_points(q)|
```

`key_point_match` defaults to 0.6. Words are compared as a set, anywhere in the answer.

This is a **lexical proxy**, optimistic by construction (see
[section 9](#9-known-limitations)). Example (question 10): the answer never mentions
licence class B2 and wrongly goes "from B1 to D", yet the key point "Nâng từ B2 lên D"
counts as covered because 4 of its 5 words appear elsewhere. Use it to track trends,
not as evidence in conclusions; an LLM-judged version is planned.

### 4.4 `number_match`: are the required numbers in the answer?

Applies to: answerable questions whose key points contain at least one number.
Requires column: `key_points`.

Number extraction from a text:

1. Normalise.
2. Remove article references (`điều 30`, `khoản 3`, `điểm 2.a`, `Điều 30.3.đ`), which
   are citations, not facts.
3. Take every number not preceded by a letter (so `B2`, `cm3`, `S1` are ignored).
4. Canonicalise: drop thousands separators (`3.500` → `3500`), use `.` as the decimal
   mark (`0,25` → `0.25`).

```
N_expected = numbers(all key points of q)
score(q)   = |N_expected ∩ numbers(answer)| / |N_expected|
```

Harder to fool than key point coverage: a missing age limit, distance or percentage
shows directly. Listed as a failure when below 1.

## 5. Citation metrics

The pipeline labels retrieved chunks `[S1]…[Sn]` and asks the model to end every
sentence with the labels it relied on.

- **Raw labels**: every `[S#]` in the answer text, including the form `[S1, S3]`.
- **Cited chunks**: the chunks the pipeline mapped the answer's valid labels to
  (`citations` in the record), each counted once.

### 5.1 `citation_validity`: do the labels point to real sources?

Applies to: answers containing at least one raw label. Requires column: none.

```
score(q) = |{ raw labels n with 1 ≤ n ≤ number of retrieved chunks }| / |raw labels|
```

Measured on raw labels because the pipeline silently drops invalid ones before mapping.
Listed as a failure when below 1.

### 5.2 `citation_precision`: are the cited chunks evidence?

Applies to: answerable questions with evidence and at least one cited chunk. Requires
column: `evidence`.

```
score(q) = |{ cited chunks that are relevant }| / |cited chunks|
```

Low precision means over-citing: question 3 cites all of S1–S5 while only S1 holds
evidence, so precision = 0.2.

### 5.3 `citation_recall`: is the evidence cited?

Applies to: answerable questions with evidence. Requires column: `evidence`.

```
score(q) = |{ e ∈ E(q) : some cited chunk contains e }| / |E(q)|
```

An answer that cites nothing scores 0 even when it is correct: the user cannot verify
it (question 28 retrieved the right chunk at rank 1 but cited nothing).

### 5.4 `citation_f1`

```
P = citation_precision(q), or 0 when nothing is cited
R = citation_recall(q)
score(q) = 2PR / (P + R),   0 when P + R = 0
```

Applies wherever `citation_recall` applies.

## 6. Latency and tokens

Toggled as `latency`. Computed over successful records (timed-out records included).

Per question, the pipeline reports stage timings in seconds:

| Stage | Meaning |
|---|---|
| `embed_query` | Embedding the question (bge-m3) |
| `search` | Vector search in Qdrant |
| `generate` | The whole LLM call, as measured by the pipeline |
| `llm_load` | Model loading inside Ollama (non-zero when the model was not resident) |
| `llm_prefill` | Ollama reading the prompt (prompt evaluation) |
| `llm_decode` | Ollama generating the answer (evaluation) |
| `total` | Wall clock for the whole question, measured by `generate.py` |

The `llm_*` stages come from Ollama's own counters and are reported only when the LLM
was called (a question with no retrieved chunk has none).

For every stage the report gives mean, p50, p95 and max. Percentiles use linear
interpolation between closest ranks:

```
pos = (n − 1) × q,   value = x[⌊pos⌋] + (x[⌈pos⌉] − x[⌊pos⌋]) × (pos − ⌊pos⌋)
```

where `x` is the sorted list of values. Mean input and output tokens per question are
reported alongside.

Methodology notes:

- The first question of a run usually includes model loading; `llm_load` shows how much.
- Ollama caches prompt prefixes: asking the same question twice makes the second prefill
  unrealistically fast. A run asks each question once; do not rerun questions to
  "warm up" a measurement.
- Check that `ollama ps` shows `100% GPU` before a run; a CPU fallback slows everything
  about 2.5× without any error.

## 7. Ground truth required per metric

| Metric | Reference-based? | Dataset columns used | Applies to |
|---|---|---|---|
| `recall_at_k` | yes | `evidence` | answerable |
| `mrr` | yes | `evidence` | answerable |
| `ndcg_at_k` | yes | `evidence` | answerable |
| `refusal_accuracy` | yes | `answerable` | unanswerable |
| `false_refusal_rate` | yes (optional) | `answerable` | answerable |
| `key_point_coverage` | yes | `key_points` | answerable |
| `number_match` | yes | `key_points` | answerable, with numbers |
| `citation_validity` | no | – | answers with labels |
| `citation_precision` | yes | `evidence` | answerable, with citations |
| `citation_recall` | yes | `evidence` | answerable |
| `citation_f1` | yes | `evidence` | answerable |
| latency, tokens | no | – | all successful records |

Columns not used by any metric yet: `expected_answer` (shown in the report's failure
list; input for a future LLM judge), `gold_refs` (for readers; future clause-level
citation metric), `gold_pages` (shown next to retrieved pages in the failure list),
`category` / `difficulty` (grouping).

`evidence` is the most valuable column: it drives six metrics. A dataset with only `id`
and `question` still runs, but measures only citation validity and latency.

## 8. Parameters

Set in `[params]` of `tests/eval/score.toml`; defaults in `metrics.DEFAULT_PARAMS`.

| Parameter | Default | Used by |
|---|---|---|
| `k` | 5 | `recall_at_k`, `ndcg_at_k` |
| `evidence_match` | 0.8 | every metric that tests quote containment |
| `key_point_match` | 0.6 | `key_point_coverage` |
| `refusal_phrases` | the pipeline's not-found answer | refusal metrics |
| `group_by` | `[]` | per-group tables |
| `max_failures` | 20 | failing questions listed per metric in the report |

Report the parameter values with any published number; changing `evidence_match` or
`key_point_match` changes the scores.

## 9. Known limitations

| Limitation | Effect | Mitigation |
|---|---|---|
| nDCG ideal assumes one chunk per quote | Penalises chunks that hold several quotes; values are a lower bound | Count relevant chunks in the whole index (planned fix) |
| `key_point_coverage` is a bag of words | Ignores order and negation; generic words and one-word points inflate it; paraphrases are penalised | Read with `number_match` and citation metrics; replace with an LLM judge |
| Evidence quotes are hand-picked | A missing quote makes recall look better than it is | Review quotes; the dataset builder checks each quote against the source |
| Larger chunks contain quotes more easily | Recall favours coarse chunking | Report mean `input_tokens` next to retrieval metrics |
| `recall_at_k` is capped by what the run stored | R0 stores 5 chunks, so recall@40 cannot be computed | Pipelines with reranking must store their candidates |
| Refusal detection is a prefix match | A refusal worded differently is counted as an answer | Add phrases to `refusal_phrases` |
| Small samples | One question moves a 10-question score by 10 points | Draw conclusions from the full set, with confidence intervals (planned) |

## 10. Planned metrics

From the proposed evaluation table (SAD chapter 10):

| Metric | Needs |
|---|---|
| recall@40 | Pipelines that expose their candidate list (R3/R4) |
| faithfulness per claim | LLM judge; reference-free (answer vs retrieved chunks) |
| LLM-judged key point coverage | LLM judge; `key_points` |
| calculate exact match, risk review precision/recall, document profile field accuracy, JSON validity | Multi-agent pipeline and the contract dataset with new columns |
| peak RAM | System-wide sampling (the model runs in the Ollama process, not in Python) |
| LLM calls per question | Multi-agent pipeline |
| run comparison with confidence intervals | A compare script over several runs (bootstrap or McNemar) |

## 11. Adding a metric

1. Write `fn(item: EvalItem, rec: RunRecord, p: dict) -> float | None` in `metrics.py`;
   return `None` when the metric does not apply to the question.
2. Register it in `METRICS` with a one-line description, the dataset columns it
   `needs`, and optionally a `failed` predicate to list failing questions in the report.
3. Add it to `[metrics]` in `score.toml`, add a unit test in
   `tests/unit/test_eval_metrics.py`, and document it here.
