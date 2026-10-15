"""Eval phase 1 — run the pipeline over a dataset and save every answer with its timings.

    python -m tests.eval.generate data/test/luat_gtdb_2008_eval100.csv [--name r0] [--limit 5]

Each answer is appended to records_<stamp>.jsonl as soon as it is ready, so an
interrupted run resumes where it stopped and failed questions are retried.
results_<stamp>.csv is rewritten at the end (also after Ctrl+C) for reading in Excel.
<stamp> is the time the run was created, so resuming keeps writing to the same files.
"""

import argparse
import json
import time
from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from rich.progress import Progress

from config import JUDGE_SETTINGS, settings
from core.agent_factory import build_ingestor, build_naive_rag
from core.models import Answer, RetrievedChunk
from observability import console, log, setup_logging
from tests.eval.dataset import Dataset, EvalItem, load_dataset
from tests.eval.runs import RunRecord, append_record, read_records, stamp, write_results

MAX_CONSECUTIVE_ERRORS = 3  # a service is down; retrying the rest would only add error records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--name", help="run name (default: <collection>__<dataset>)")
    parser.add_argument("--limit", type=int, help="only the first N questions")
    args = parser.parse_args()

    setup_logging()
    log.info("settings: %s", settings.model_dump_json())
    dataset = load_dataset(args.dataset)
    run_dir = settings.data_dir / "eval_runs" / (args.name or f"{settings.collection}__{args.dataset.stem}")
    meta = prepare_run_dir(run_dir, args.dataset, settings.model_dump(mode="json", exclude=JUDGE_SETTINGS))
    records, results = run_dir / meta["records"], run_dir / meta["results"]
    log.info("records → %s", records)
    log.info("results → %s", results)
    _ingest(dataset)
    run(dataset.items[: args.limit], build_naive_rag().ask, records, results)
    console.print(f"[green]done[/]\n  records → {records}\n  results → {results}")


def prepare_run_dir(run_dir: Path, dataset_path: Path, settings_dump: dict) -> dict:
    """Create the run directory, or check that a resumed run keeps the same dataset and
    settings. Returns the run's meta, which names its output files."""
    meta_path = run_dir / "meta.json"
    meta = {"dataset": dataset_path.as_posix(), "settings": settings_dump}
    if meta_path.exists():
        old = json.loads(meta_path.read_text(encoding="utf-8"))
        changed = [k for k in meta["settings"] if old["settings"].get(k) != meta["settings"][k]]
        if old["dataset"] != meta["dataset"]:
            changed.insert(0, "dataset")
        if changed:
            raise SystemExit(f"{run_dir} was generated with a different {', '.join(changed)}; use another --name")
        return old
    run_dir.mkdir(parents=True, exist_ok=True)
    created = stamp()
    meta |= {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "records": f"records_{created}.jsonl",
        "results": f"results_{created}.csv",
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def run(items: list[EvalItem], ask: Callable[[str], Answer], records_path: Path, results_path: Path) -> None:
    done = {id_ for id_, r in read_records(records_path).items() if r.error is None}
    todo = [item for item in items if item.id not in done]
    log.info("%d questions: %d already answered, %d to go", len(items), len(items) - len(todo), len(todo))

    errors_in_a_row = 0
    try:
        with Progress(console=console) as progress:
            task = progress.add_task("generating", total=len(todo))
            for item in todo:
                record = _answer(item, ask)
                append_record(records_path, record)
                progress.advance(task)
                errors_in_a_row = errors_in_a_row + 1 if record.error else 0
                if errors_in_a_row == MAX_CONSECUTIVE_ERRORS:
                    log.error("%d questions failed in a row, stopping; fix the cause and rerun", errors_in_a_row)
                    break
    finally:
        write_results(results_path, items, read_records(records_path))


def _answer(item: EvalItem, ask: Callable[[str], Answer]) -> RunRecord:
    start = time.perf_counter()
    try:
        answer = ask(item.question)
    except Exception as e:  # keep a long run alive; failed questions are retried on the next run
        log.warning("question %s failed: %s", item.id, e)
        return RunRecord(item.id, item.question, latency_s=time.perf_counter() - start, error=f"{type(e).__name__}: {e}")
    return RunRecord(
        id=item.id,
        question=item.question,
        answer=answer.text,
        contexts=_ranked(answer.sources),
        retrieved=_ranked(answer.retrieved) if answer.retrieved != answer.sources else [],  # R0: = contexts
        citations=[{"label": c.label, "chunk_id": c.chunk.chunk_id} for c in answer.citations],
        timings=answer.timings,
        tokens=answer.tokens,
        latency_s=time.perf_counter() - start,
        timed_out=answer.timed_out,
    )


def _ranked(chunks: list[RetrievedChunk]) -> list[dict]:
    """Chunks as stored in a record; parent_text is left out (a source already shows it)."""
    return [{"rank": rank, **{k: v for k, v in asdict(s.chunk).items() if k != "parent_text"}, "score": s.score}
            for rank, s in enumerate(chunks, 1)]


def _ingest(dataset: Dataset) -> None:
    documents = dataset.documents()
    if not documents:
        log.warning("dataset has no 'doc' column; assuming its documents are already indexed")
        return
    missing = [str(d) for d in documents if not d.is_file()]
    if missing:
        raise SystemExit(f"documents named in the dataset were not found: {missing}")
    ingestor = build_ingestor()
    for document in documents:
        ingestor.ingest(document)


if __name__ == "__main__":
    main()
