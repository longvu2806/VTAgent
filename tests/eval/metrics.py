"""Eval metrics. A metric scores one question (None = not applicable) and the scores are
averaged. To add one, write its scoring function and register it in METRICS.

Code metrics are computed here. Judge metrics (``fn=None``) are scored by an LLM judge
through RAGAS in ``ragas_judge.py`` and handed to ``score_run`` as precomputed scores.
Latency is not a per-question metric; it is summarised separately and toggled as "latency".
Specification: METRICS.md.
"""

import math
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from difflib import SequenceMatcher

from core.prompting import NOT_FOUND
from tests.eval.dataset import Dataset, EvalItem
from tests.eval.runs import RunRecord

DEFAULT_PARAMS = {
    "k": 5,  # cut-off for recall_at_k and ndcg_at_k
    "evidence_match": 0.8,  # share of an evidence quote a chunk must contain (chunk cuts may split quotes)
    "refusal_phrases": [NOT_FOUND],
    "group_by": [],  # extra dataset columns to break scores down by
    "max_failures": 20,  # failing questions listed per metric in the report
}
LATENCY = "latency"
JUDGE_METRICS = ("context_precision", "context_recall", "faithfulness", "answer_relevancy",
                 "factual_correctness", "semantic_similarity")
GROUPS = {"ragas": JUDGE_METRICS}  # names that stand for several metrics in --only / --skip


@dataclass(frozen=True)
class Metric:
    name: str
    description: str
    fn: Callable[[EvalItem, RunRecord, dict], float | None] | None  # None: scored by the LLM judge
    needs: tuple[str, ...] = ()  # dataset columns the metric requires
    failed: Callable[[float], bool] | None = None  # scores the report lists as failures


@dataclass
class Report:
    summary: dict[str, dict]  # metric -> {"value", "n"} or {"skipped": reason}
    item_scores: dict[str, dict[str, float | None]]  # question id -> metric -> score
    groups: dict[str, dict[str, dict[str, dict]]]  # column -> value -> metric -> {"value", "n"}
    latency: dict[str, dict[str, float]] | None  # stage -> mean / p50 / p95 / max
    tokens: dict[str, float] | None  # mean tokens per question
    missing: list[str]  # dataset ids without a record
    errors: list[RunRecord]
    timed_out: list[str]  # ids whose answer was cut at the LLM time limit (still scored)


# --- text matching -----------------------------------------------------------------

def _norm(text: str) -> str:
    text = unicodedata.normalize("NFC", text).lower()
    text = re.sub(r"[*_#]", "", text)  # markdown emitted by the PDF parser
    text = re.sub(r"(?m)^\s*-\s+", "", text)  # list bullets
    return re.sub(r"\s+", " ", text).strip()


def _contains(text: str, quote: str, share: float) -> bool:
    """Whether ``text`` holds at least ``share`` of ``quote`` as one contiguous piece."""
    text, quote = _norm(text), _norm(quote)
    if quote in text:
        return True
    match = SequenceMatcher(None, text, quote, autojunk=False).find_longest_match(0, len(text), 0, len(quote))
    return match.size >= share * len(quote)


def _relevant(text: str, item: EvalItem, p: dict) -> bool:
    return any(_contains(text, quote, p["evidence_match"]) for quote in item.evidence)


def _quotes_found(texts: list[str], item: EvalItem, p: dict) -> float:
    found = sum(any(_contains(t, quote, p["evidence_match"]) for t in texts) for quote in item.evidence)
    return found / len(item.evidence)


def is_refusal(answer: str, p: dict) -> bool:
    """The answer leads with a refusal phrase; one that only ends with it answered first."""
    answer = _norm(answer)
    return any(answer.startswith(_norm(phrase).rstrip(".")) for phrase in p["refusal_phrases"])


def strip_labels(answer: str) -> str:
    """The answer without its [S#] citation labels."""
    text = re.sub(r"[ \t]+", " ", _LABEL_GROUP.sub("", answer))
    return re.sub(r" ([.,;:!?])", r"\1", text).strip()


_LABEL_GROUP = re.compile(r"\[(S\d+(?:\s*,\s*S\d+)*)\]")
_LEGAL_REF = re.compile(r"\b(điều|khoản|điểm)\s+\d+[\w.]*")  # "Điều 30.3.đ", "khoản 3"
_NUMBER = re.compile(r"(?<!\w)\d+(?:[.,]\d+)*")


def _labels(answer: str) -> list[int]:
    return [int(label.strip()[1:]) for group in _LABEL_GROUP.finditer(answer) for label in group.group(1).split(",")]


def _numbers(text: str) -> set[str]:
    """Numbers stated in the text, ignoring article references; "3.500" → "3500", "0,25" → "0.25"."""
    text = _LEGAL_REF.sub(" ", _norm(text))
    return {re.sub(r"\.(?=\d{3}\b)", "", n).replace(",", ".") for n in _NUMBER.findall(text)}


def _ranked(rec: RunRecord) -> list[str]:
    """Texts of the search hits by rank: the retrieved children from R1 on, the contexts in R0."""
    return [c["text"] for c in rec.retrieved or rec.contexts]


def _cited_texts(rec: RunRecord) -> list[str]:
    by_id = {c["chunk_id"]: c["text"] for c in rec.contexts}
    return [by_id[c["chunk_id"]] for c in rec.citations if c["chunk_id"] in by_id]


# --- metrics -----------------------------------------------------------------------

def recall_at_k(item: EvalItem, rec: RunRecord, p: dict) -> float | None:
    if not item.answerable or not item.evidence:
        return None
    return _quotes_found(_ranked(rec)[: p["k"]], item, p)


def mrr(item: EvalItem, rec: RunRecord, p: dict) -> float | None:
    if not item.answerable or not item.evidence:
        return None
    for rank, text in enumerate(_ranked(rec), start=1):
        if _relevant(text, item, p):
            return 1 / rank
    return 0.0


def ndcg_at_k(item: EvalItem, rec: RunRecord, p: dict) -> float | None:
    if not item.answerable or not item.evidence:
        return None
    relevant = [_relevant(text, item, p) for text in _ranked(rec)[: p["k"]]]
    dcg = sum(1 / math.log2(i + 2) for i, r in enumerate(relevant) if r)
    # Ideal ranking of the retrieved chunks: all relevant ones first. Missing evidence is
    # recall_at_k's job, so one chunk holding several quotes is not penalised.
    idcg = sum(1 / math.log2(i + 2) for i in range(sum(relevant)))
    return dcg / idcg if idcg else 0.0


def refusal_accuracy(item: EvalItem, rec: RunRecord, p: dict) -> float | None:
    return None if item.answerable else float(is_refusal(rec.answer, p))


def false_refusal_rate(item: EvalItem, rec: RunRecord, p: dict) -> float | None:
    return float(is_refusal(rec.answer, p)) if item.answerable else None


def number_match(item: EvalItem, rec: RunRecord, p: dict) -> float | None:
    expected = _numbers(" ; ".join(item.key_points))
    if not item.answerable or not expected:
        return None
    return len(expected & _numbers(rec.answer)) / len(expected)


def citation_validity(item: EvalItem, rec: RunRecord, p: dict) -> float | None:
    labels = _labels(rec.answer)
    if not labels:
        return None
    return sum(1 <= n <= len(rec.contexts) for n in labels) / len(labels)


def citation_precision(item: EvalItem, rec: RunRecord, p: dict) -> float | None:
    cited = _cited_texts(rec)
    if not item.answerable or not item.evidence or not cited:
        return None
    return sum(_relevant(t, item, p) for t in cited) / len(cited)


def citation_recall(item: EvalItem, rec: RunRecord, p: dict) -> float | None:
    if not item.answerable or not item.evidence:
        return None
    return _quotes_found(_cited_texts(rec), item, p)


def citation_f1(item: EvalItem, rec: RunRecord, p: dict) -> float | None:
    recall = citation_recall(item, rec, p)
    if recall is None:
        return None
    precision = citation_precision(item, rec, p) or 0.0  # nothing cited counts as precision 0
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


def timeout_rate(item: EvalItem, rec: RunRecord, p: dict) -> float | None:
    return float(rec.timed_out)


METRICS = {m.name: m for m in [
    # Retrieval
    Metric("recall_at_k", "Share of evidence quotes found in the top-k retrieved chunks",
           recall_at_k, ("evidence",), failed=lambda v: v == 0),
    Metric("mrr", "1 / rank of the first retrieved chunk that contains evidence", mrr, ("evidence",)),
    Metric("ndcg_at_k", "Rank-weighted order of the relevant chunks among the top-k", ndcg_at_k, ("evidence",)),
    Metric("context_precision", "Judge: useful chunks are ranked above useless ones", None, ("expected_answer",)),
    Metric("context_recall", "Judge: claims of the reference answer supported by the chunks",
           None, ("expected_answer",)),
    # Answer correctness
    Metric("factual_correctness", "Judge: claim-level F1 of the answer against the reference answer",
           None, ("expected_answer",), failed=lambda v: v == 0),
    Metric("semantic_similarity", "Embedding cosine similarity of answer and reference answer",
           None, ("expected_answer",)),
    Metric("number_match", "Share of numbers in the key points that appear in the answer",
           number_match, ("key_points",), failed=lambda v: v < 1),
    # Grounding and citation
    Metric("faithfulness", "Judge: claims of the answer supported by the retrieved chunks",
           None, failed=lambda v: v < 0.5),
    Metric("citation_f1", "Harmonic mean of citation precision and recall", citation_f1, ("evidence",)),
    Metric("citation_precision", "Share of cited chunks that contain evidence", citation_precision, ("evidence",)),
    Metric("citation_recall", "Share of evidence quotes covered by the cited chunks", citation_recall, ("evidence",)),
    Metric("citation_validity", "Share of [S#] labels that point to a retrieved chunk",
           citation_validity, failed=lambda v: v < 1),
    # Relevance
    Metric("answer_relevancy", "Judge: the answer addresses the question (0 if evasive)", None),
    # Abstention
    Metric("refusal_accuracy", "Unanswerable questions the system refused",
           refusal_accuracy, ("answerable",), failed=lambda v: v == 0),
    Metric("false_refusal_rate", "Answerable questions the system refused (lower is better)",
           false_refusal_rate, failed=lambda v: v == 1),
    # System
    Metric("timeout_rate", "Answers cut at the LLM time limit", timeout_rate),
]}


# --- scoring -----------------------------------------------------------------------

def select_metrics(toggles: dict[str, bool], only: list[str], skip: list[str]) -> list[str]:
    """Metrics to score: ``only`` if given, else all not switched off; minus ``skip``.
    ``only`` and ``skip`` also accept group names (``ragas``)."""
    known = [*METRICS, LATENCY]
    unknown = sorted((set(toggles) | set(only) | set(skip)) - set(known) - set(GROUPS))
    if unknown:
        raise ValueError(f"unknown metric(s) {unknown}; known: {known} and groups {list(GROUPS)}")

    def expand(names: list[str]) -> list[str]:
        return [m for n in names for m in GROUPS.get(n, (n,))]

    only, skip = expand(only), expand(skip)
    chosen = [n for n in known if n in only] if only else [n for n in known if toggles.get(n, True)]
    return [name for name in chosen if name not in skip]


def score_run(dataset: Dataset, records: dict[str, RunRecord], enabled: list[str], params: dict,
              judged: dict[str, dict[str, float | None]] | None = None,
              unavailable: dict[str, str] | None = None) -> Report:
    """Score a run. ``judged`` holds the judge metrics' per-question scores; metrics named in
    ``unavailable`` are reported as skipped with the given reason."""
    p = {**DEFAULT_PARAMS, **params}
    judged, unavailable = judged or {}, unavailable or {}
    active, skipped = [], {}
    for name in enabled:
        if name == LATENCY:
            continue
        metric = METRICS[name]
        absent = [c for c in metric.needs if c not in dataset.columns]
        if absent:
            skipped[name] = {"skipped": f"dataset has no {', '.join(absent)} column"}
        elif name in unavailable:
            skipped[name] = {"skipped": unavailable[name]}
        else:
            active.append(metric)

    def score(metric: Metric, item: EvalItem, rec: RunRecord) -> float | None:
        if metric.fn is None:
            return judged.get(item.id, {}).get(metric.name)
        return metric.fn(item, rec, p)

    answered = [(i, records[i.id]) for i in dataset.items if i.id in records and records[i.id].error is None]
    item_scores = {item.id: {m.name: score(m, item, rec) for m in active} for item, rec in answered}

    def aggregate(ids: list[str]) -> dict[str, dict]:
        out = {}
        for m in active:
            values = [item_scores[i][m.name] for i in ids if item_scores[i][m.name] is not None]
            out[m.name] = {"value": sum(values) / len(values) if values else None, "n": len(values)}
        return out

    overall = aggregate(list(item_scores))
    groups = {}
    for column in p["group_by"]:
        ids_by_value: dict[str, list[str]] = {}
        for item, _ in answered:
            if column in item.extra:
                ids_by_value.setdefault(item.extra[column], []).append(item.id)
        groups[column] = {value: aggregate(ids) for value, ids in sorted(ids_by_value.items())}

    successes = [rec for _, rec in answered]
    return Report(
        summary={name: overall.get(name) or skipped.get(name) for name in enabled if name != LATENCY},
        item_scores=item_scores,
        groups=groups,
        latency=_latency(successes) if LATENCY in enabled else None,
        tokens=_tokens(successes) if LATENCY in enabled else None,
        missing=[i.id for i in dataset.items if i.id not in records],
        errors=[records[i.id] for i in dataset.items if i.id in records and records[i.id].error],
        timed_out=[rec.id for rec in successes if rec.timed_out],
    )


def _latency(records: list[RunRecord]) -> dict[str, dict[str, float]]:
    stages = list(dict.fromkeys(s for r in records for s in r.timings))
    series = {stage: [r.timings[stage] for r in records if stage in r.timings] for stage in stages}
    series["total"] = [r.latency_s for r in records]
    return {
        stage: {"mean": sum(v) / len(v), "p50": _percentile(v, 0.5), "p95": _percentile(v, 0.95), "max": max(v)}
        for stage, v in series.items() if v
    }


def _tokens(records: list[RunRecord]) -> dict[str, float]:
    keys = list(dict.fromkeys(k for r in records for k in r.tokens))
    return {k: sum(r.tokens[k] for r in records if k in r.tokens) / sum(k in r.tokens for r in records) for k in keys}


def _percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    low, high = math.floor(pos), math.ceil(pos)
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)
