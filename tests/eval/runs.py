"""Run directory shared by the two eval phases.

    data/eval_runs/<name>/
        meta.json                  dataset, settings and output file names of the run
        records_<created>.jsonl    one RunRecord per question; input of the score phase
        results_<created>.csv      the same records flattened for reading in Excel, chunk texts included;
                                   rewrite it with `python -m tests.eval.runs <run_dir>`
        report_<scored>.md         one per scoring, so rescoring keeps earlier reports
        scores_<scored>.csv        per-question score of every metric, written with the report

<created> and <scored> are local times as YYYYMMDD-HHMMSS.
"""

import argparse
import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from observability import console
from tests.eval.dataset import EvalItem, load_dataset


def stamp() -> str:
    """Local time for output file names; sorts chronologically."""
    return datetime.now().strftime("%Y%m%d-%H%M%S")


@dataclass
class RunRecord:
    id: str
    question: str
    answer: str = ""
    contexts: list[dict] = field(default_factory=list)  # chunks shown to the LLM, in [S#] order
    retrieved: list[dict] = field(default_factory=list)  # search hits by rank, before context assembly (R1+)
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
    """One row per answered question, in dataset order, with every timing as its own column.
    S1…Sn hold the sources as the LLM read them (after context assembly), hit_1…hit_k the
    retrieved chunks by rank; each cell is the chunk's place, then its text."""
    answered = [(item, records[item.id]) for item in items if item.id in records]
    stages = list(dict.fromkeys(stage for _, r in answered for stage in r.timings))
    n_sources = max((len(r.contexts) for _, r in answered), default=0)
    n_hits = max((len(r.retrieved or r.contexts) for _, r in answered), default=0)
    rows = []
    for item, r in answered:
        by_id = {c["chunk_id"]: c for c in r.contexts}
        hits = r.retrieved or r.contexts  # R0: no context assembly, the sources are the hits
        rows.append({
            "id": item.id,
            "question": item.question,
            "answerable": "yes" if item.answerable else "no",
            "expected_answer": item.expected_answer,
            "answer": r.answer,
            "citations": "; ".join(f"{c['label']}: {_place(by_id[c['chunk_id']])}" for c in r.citations),
            "retrieved": "; ".join(f"{c['rank']}. {_place(c)} ({c['score']:.3f})" for c in hits),
            **{f"S{n}": _cell(c) for n, c in _padded(r.contexts, n_sources)},
            **{f"hit_{n}": _cell(c, ranked=True) for n, c in _padded(hits, n_hits)},
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


def _padded(chunks: list[dict], width: int) -> list[tuple[int, dict | None]]:
    """(1-based position, chunk) for ``width`` columns; None past the record's last chunk."""
    return [(n, chunks[n - 1] if n <= len(chunks) else None) for n in range(1, width + 1)]


def _cell(chunk: dict | None, ranked: bool = False) -> str:
    """'law.pdf p.3 · Điều 5 › Khoản 1', then the chunk text; a hit also shows its rank and score."""
    if chunk is None:
        return ""
    head = " · ".join(part for part in (_place(chunk), chunk.get("section")) if part)
    if ranked:
        head = f"{chunk['rank']}. {head} ({chunk['score']:.3f})"
    return f"{head}\n{chunk['text']}"


def main() -> None:
    """Rewrite a run's results CSV from its records, e.g. after columns were added; no models needed."""
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    meta = json.loads((args.run_dir / "meta.json").read_text(encoding="utf-8"))
    path = args.run_dir / meta["results"]
    write_results(path, load_dataset(Path(meta["dataset"])).items, read_records(args.run_dir / meta["records"]))
    console.print(f"[green]results →[/] {path}")


if __name__ == "__main__":
    main()
