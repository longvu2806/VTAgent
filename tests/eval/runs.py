"""Run directory shared by the two eval phases.

    data/eval_runs/<name>/
        meta.json                  dataset, settings and output file names of the run
        records_<created>.jsonl    one RunRecord per question; input of the score phase
        results_<created>.csv      the same records flattened for reading in Excel
        report_<scored>.md         one per scoring, so rescoring keeps earlier reports

<created> and <scored> are local times as YYYYMMDD-HHMMSS.
"""

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from tests.eval.dataset import EvalItem


def stamp() -> str:
    """Local time for output file names; sorts chronologically."""
    return datetime.now().strftime("%Y%m%d-%H%M%S")


@dataclass
class RunRecord:
    id: str
    question: str
    answer: str = ""
    contexts: list[dict] = field(default_factory=list)  # chunks shown to the LLM, in [S#] order
    citations: list[dict] = field(default_factory=list)  # {"label", "chunk_id"}, as cited
    timings: dict[str, float] = field(default_factory=dict)  # pipeline stage -> seconds
    tokens: dict[str, int] = field(default_factory=dict)
    latency_s: float = 0.0  # wall clock for the whole question
    timed_out: bool = False  # answer cut at the LLM time limit; scored as it stands, not retried
    error: str | None = None


def read_records(path: Path) -> dict[str, RunRecord]:
    """Latest record per question id (a retried question appends a newer record)."""
    if not path.exists():
        return {}
    records = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = RunRecord(**json.loads(line))
            records[record.id] = record
    return records


def append_record(path: Path, record: RunRecord) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


def write_results(path: Path, items: list[EvalItem], records: dict[str, RunRecord]) -> None:
    """One row per answered question, in dataset order, with every timing as its own column."""
    answered = [(item, records[item.id]) for item in items if item.id in records]
    stages = list(dict.fromkeys(stage for _, r in answered for stage in r.timings))
    rows = []
    for item, r in answered:
        by_id = {c["chunk_id"]: c for c in r.contexts}
        rows.append({
            "id": item.id,
            "question": item.question,
            "answerable": "yes" if item.answerable else "no",
            "expected_answer": item.expected_answer,
            "answer": r.answer,
            "citations": "; ".join(f"{c['label']}: {_place(by_id[c['chunk_id']])}" for c in r.citations),
            "retrieved": "; ".join(f"{c['rank']}. {_place(c)} ({c['score']:.3f})" for c in r.contexts),
            "latency_s": round(r.latency_s, 2),
            **{f"{stage}_s": round(r.timings[stage], 2) if stage in r.timings else "" for stage in stages},
            "input_tokens": r.tokens.get("input_tokens", ""),
            "output_tokens": r.tokens.get("output_tokens", ""),
            "timed_out": "yes" if r.timed_out else "",
            "error": r.error or "",
        })
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = list(rows[0]) if rows else ["id"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _place(context: dict) -> str:
    page = context.get("page")
    return context["source"] if page is None else f"{context['source']} p.{page}"
