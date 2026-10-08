"""Eval metrics. A metric scores one question (None = not applicable) and the scores are
averaged. To add one, write its scoring function and register it in METRICS.

Latency is not a per-question metric; it is summarised separately and toggled as "latency".
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
    "key_point_match": 0.6,  # share of a key point's words the answer must contain
    "refusal_phrases": [NOT_FOUND],
    "group_by": [],  # extra dataset columns to break scores down by
    "max_failures": 20,  # failing questions listed per metric in the report
}
LATENCY = "latency"


@dataclass(frozen=True)
class Metric:
    name: str
    description: str
    fn: Callable[[EvalItem, RunRecord, dict], float | None]
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


def _is_refusal(answer: str, p: dict) -> bool:
    """The answer leads with a refusal phrase; one that only ends with it answered first."""
    answer = _norm(answer)
    return any(answer.startswith(_norm(phrase).rstrip(".")) for phrase in p["refusal_phrases"])


_LABEL_GROUP = re.compile(r"\[(S\d+(?:\s*,\s*S\d+)*)\]")
_LEGAL_REF = re.compile(r"\b(điều|khoản|điểm)\s+\d+[\w.]*")  # "Điều 30.3.đ", "khoản 3"
_NUMBER = re.compile(r"(?<!\w)\d+(?:[.,]\d+)*")


def _labels(answer: str) -> list[int]:
    return [int(label.strip()[1:]) for group in _LABEL_GROUP.finditer(answer) for label in group.group(1).split(",")]


def _numbers(text: str) -> set[str]:
    """Numbers stated in the text, ignoring article references; "3.500" → "3500", "0,25" → "0.25"."""
    text = _LEGAL_REF.sub(" ", _norm(text))
    return {re.sub(r"\.(?=\d{3}\b)", "", n).replace(",", ".") for n in _NUMBER.findall(text)}


def _words(text: str) -> list[str]:
    return re.findall(r"\w+", _norm(text))


def _cited_texts(rec: RunRecord) -> list[str]:
    by_id = {c["chunk_id"]: c["text"] for c in rec.contexts}
    return [by_id[c["chunk_id"]] for c in rec.citations if c["chunk_id"] in by_id]


# --- metrics -----------------------------------------------------------------------

def recall_at_k(item: EvalItem, rec: RunRecord, p: dict) -> float | None:
    if not item.answerable or not item.evidence:
        return None
    return _quotes_found([c["text"] for c in rec.contexts[: p["k"]]], item, p)


def mrr(item: EvalItem, rec: RunRecord, p: dict) -> float | None:
    if not item.answerable or not item.evidence:
        return None
    for rank, context in enumerate(rec.contexts, start=1):
        if _relevant(context["text"], item, p):
            return 1 / rank
    return 0.0


def ndcg_at_k(item: EvalItem, rec: RunRecord, p: dict) -> float | None:
    if not item.answerable or not item.evidence:
        return None
    relevant = [_relevant(c["text"], item, p) for c in rec.contexts[: p["k"]]]
    dcg = sum(1 / math.log2(i + 2) for i, r in enumerate(relevant) if r)
    ideal_hits = min(p["k"], max(len(item.evidence), sum(relevant)))
    return dcg / sum(1 / math.log2(i + 2) for i in range(ideal_hits))


def refusal_accuracy(item: EvalItem, rec: RunRecord, p: dict) -> float | None:
    return None if item.answerable else float(_is_refusal(rec.answer, p))


def false_refusal_rate(item: EvalItem, rec: RunRecord, p: dict) -> float | None:
    return float(_is_refusal(rec.answer, p)) if item.answerable else None


def key_point_coverage(item: EvalItem, rec: RunRecord, p: dict) -> float | None:
    if not item.answerable or not item.key_points:
        return None
    answer = set(_words(rec.answer))

    def covered(point: str) -> bool:
        words = _words(point)
        return bool(words) and sum(w in answer for w in words) / len(words) >= p["key_point_match"]

    return sum(map(covered, item.key_points)) / len(item.key_points)


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


METRICS = {m.name: m for m in [
    Metric("recall_at_k", "Share of evidence quotes found in the top-k retrieved chunks",
           recall_at_k, ("evidence",), failed=lambda v: v == 0),
    Metric("mrr", "1 / rank of the first retrieved chunk that contains evidence", mrr, ("evidence",)),
    Metric("ndcg_at_k", "Rank-weighted share of top-k chunks that contain evidence", ndcg_at_k, ("evidence",)),
    Metric("refusal_accuracy", "Unanswerable questions the system refused",
           refusal_accuracy, ("answerable",), failed=lambda v: v == 0),
    Metric("false_refusal_rate", "Answerable questions the system refused (lower is better)",
           false_refusal_rate, failed=lambda v: v == 1),
    Metric("key_point_coverage", "Share of key points whose words appear in the answer (lexical)",
           key_point_coverage, ("key_points",)),
    Metric("number_match", "Share of numbers in the key points that appear in the answer",
           number_match, ("key_points",), failed=lambda v: v < 1),
    Metric("citation_validity", "Share of [S#] labels that point to a retrieved chunk",
           citation_validity, failed=lambda v: v < 1),
    Metric("citation_precision", "Share of cited chunks that contain evidence", citation_precision, ("evidence",)),
    Metric("citation_recall", "Share of evidence quotes covered by the cited chunks", citation_recall, ("evidence",)),
    Metric("citation_f1", "Harmonic mean of citation precision and recall", citation_f1, ("evidence",)),
]}


# --- scoring -----------------------------------------------------------------------

def select_metrics(toggles: dict[str, bool], only: list[str], skip: list[str]) -> list[str]:
    """Metrics to score: ``only`` if given, else all not switched off; minus ``skip``."""
    known = [*METRICS, LATENCY]
    unknown = sorted((set(toggles) | set(only) | set(skip)) - set(known))
    if unknown:
        raise ValueError(f"unknown metric(s) {unknown}; known: {known}")
    chosen = only or [name for name in known if toggles.get(name, True)]
    return [name for name in chosen if name not in skip]


def score_run(dataset: Dataset, records: dict[str, RunRecord], enabled: list[str], params: dict) -> Report:
    p = {**DEFAULT_PARAMS, **params}
    active, skipped = [], {}
    for name in enabled:
        if name == LATENCY:
            continue
        metric = METRICS[name]
        absent = [c for c in metric.needs if c not in dataset.columns]
        if absent:
            skipped[name] = {"skipped": f"dataset has no {', '.join(absent)} column"}
        else:
            active.append(metric)

    answered = [(i, records[i.id]) for i in dataset.items if i.id in records and records[i.id].error is None]
    item_scores = {item.id: {m.name: m.fn(item, rec, p) for m in active} for item, rec in answered}

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
