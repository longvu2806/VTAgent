"""Eval phase 2 — score a generated run and write report_<stamp>.md. Needs no models.

    python -m tests.eval.score data/eval_runs/<run> [--config tests/eval/score.toml]
                                                   [--only recall_at_k,mrr] [--skip latency]

The dataset is re-read at scoring time, so a corrected dataset is scored without
regenerating the answers.
"""

import argparse
import json
import tomllib
from datetime import datetime, timezone
from pathlib import Path

from rich.table import Table

from observability import console, setup_logging
from tests.eval.dataset import Dataset, load_dataset
from tests.eval.metrics import DEFAULT_PARAMS, LATENCY, METRICS, Report, score_run, select_metrics
from tests.eval.runs import RunRecord, read_records, stamp

DEFAULT_CONFIG = Path(__file__).with_name("score.toml")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--dataset", type=Path, help="score against this dataset instead of the one in meta.json")
    parser.add_argument("--only", default="", help="comma-separated metrics to score, ignoring the config")
    parser.add_argument("--skip", default="", help="comma-separated metrics not to score")
    args = parser.parse_args()

    setup_logging()
    config = tomllib.loads(args.config.read_text(encoding="utf-8"))
    params = config.get("params", {})
    enabled = select_metrics(config.get("metrics", {}), _names(args.only), _names(args.skip))
    meta = json.loads((args.run_dir / "meta.json").read_text(encoding="utf-8"))
    dataset = load_dataset(args.dataset or Path(meta["dataset"]))
    records_path = args.run_dir / meta["records"]
    console.print(f"records → {records_path}")
    records = read_records(records_path)

    report = score_run(dataset, records, enabled, params)
    _print_summary(report)
    path = args.run_dir / f"report_{stamp()}.md"
    path.write_text(render_markdown(report, dataset, records, meta, args.run_dir, enabled, params), encoding="utf-8")
    console.print(f"[green]report[/] → {path}")


def render_markdown(report: Report, dataset: Dataset, records: dict[str, RunRecord], meta: dict,
                    run_dir: Path, enabled: list[str], params: dict) -> str:
    params = {**DEFAULT_PARAMS, **params}
    s = meta["settings"]
    n_unanswerable = sum(not i.answerable for i in dataset.items)
    answered = len(dataset.items) - len(report.missing) - len(report.errors)
    lines = [
        f"# Eval report: {run_dir.name}",
        "",
        "| | |",
        "|---|---|",
        f"| Run | `{run_dir.as_posix()}` |",
        f"| Dataset | `{dataset.path.as_posix()}`: {len(dataset.items)} questions, {n_unanswerable} unanswerable |",
        f"| Answered | {answered}, of which {len(report.timed_out)} cut at the LLM time limit"
        f" ({len(report.errors)} errors, {len(report.missing)} not generated) |",
        f"| Generated | {meta.get('created_at', '?')} |",
        f"| Scored | {datetime.now(timezone.utc).isoformat(timespec='seconds')} |",
        f"| Models | {s['llm_model']} · {s['embedding_model']} |",
        f"| Retrieval | collection `{s['collection']}` · chunk {s['chunk_size']}/{s['chunk_overlap']} tokens · top-{s['top_k']} |",
        "",
        "Full settings are in `meta.json`.",
        "",
        "## Summary",
        "",
        "| Metric | Value | Questions | Measures |",
        "|---|---|---|---|",
    ]
    for name, result in report.summary.items():
        description = METRICS[name].description.replace("top-k", f"top-{params['k']}")
        if "skipped" in result:
            lines.append(f"| {name} | skipped | – | {result['skipped']} |")
        else:
            lines.append(f"| {name} | {_fmt(result['value'])} | {result['n']} | {description} |")
    disabled = [name for name in [*METRICS, LATENCY] if name not in enabled]
    if disabled:
        lines += ["", f"Disabled: {', '.join(f'`{n}`' for n in disabled)}"]

    if report.latency:
        lines += ["", "## Latency (seconds)", "", "| Stage | Mean | p50 | p95 | Max |", "|---|---|---|---|---|"]
        lines += [f"| {stage} | {st['mean']:.2f} | {st['p50']:.2f} | {st['p95']:.2f} | {st['max']:.2f} |"
                  for stage, st in report.latency.items()]
        if report.tokens:
            lines += ["", "Mean tokens per question: " + ", ".join(f"{k} {v:.0f}" for k, v in report.tokens.items())]

    scored = [name for name, result in report.summary.items() if "skipped" not in result]
    for column, by_value in report.groups.items():
        lines += ["", f"## By {column}", "", f"| {column} | " + " | ".join(scored) + " |",
                  "|---|" + "---|" * len(scored)]
        for value, results in by_value.items():
            cells = [f"{_fmt(results[n]['value'])} ({results[n]['n']})" for n in scored]
            lines.append(f"| {value} | " + " | ".join(cells) + " |")

    lines += _failures(report, dataset, records, params["max_failures"])
    return "\n".join(lines) + "\n"


def _failures(report: Report, dataset: Dataset, records: dict[str, RunRecord], limit: int) -> list[str]:
    lines = ["", "## Failures"]
    items = {i.id: i for i in dataset.items}
    for name in report.summary:
        failed = METRICS[name].failed
        if failed is None or "skipped" in report.summary[name]:
            continue
        ids = [i for i, scores in report.item_scores.items() if scores[name] is not None and failed(scores[name])]
        if not ids:
            continue
        lines += ["", f"### {name}: {len(ids)} questions", ""]
        for item_id in ids[:limit]:
            item, rec = items[item_id], records[item_id]
            pages = ", ".join(str(c["page"]) for c in rec.contexts if c.get("page") is not None) or "–"
            gold = ", ".join(map(str, item.gold_pages)) or "–"
            lines += [
                f"- **#{item_id}** {item.question}",
                f"  - Expected: {_clip(item.expected_answer, 250)}",
                f"  - Answer: {_clip(rec.answer, 350)}",
                f"  - Pages retrieved: {pages} · gold: {gold} · score {_fmt(report.item_scores[item_id][name])}",
            ]
        if len(ids) > limit:
            lines.append(f"- … {len(ids) - limit} more")
    if report.timed_out:
        lines += ["", f"### timed out: {len(report.timed_out)} questions", ""]
        lines += [f"- **#{i}** {items[i].question} ({records[i].tokens.get('output_tokens', '?')} tokens generated)"
                  for i in report.timed_out]
    if report.errors:
        lines += ["", f"### errors: {len(report.errors)} questions", ""]
        lines += [f"- **#{rec.id}** `{rec.error}`" for rec in report.errors]
    if len(lines) == 2:
        lines += ["", "None."]
    return lines


def _print_summary(report: Report) -> None:
    table = Table("Metric", "Value", "Questions")
    for name, result in report.summary.items():
        if "skipped" in result:
            table.add_row(name, f"[yellow]skipped[/] ({result['skipped']})", "–")
        else:
            table.add_row(name, _fmt(result["value"]), str(result["n"]))
    if report.latency:
        total = report.latency["total"]
        table.add_row("latency total (s)", f"p50 {total['p50']:.1f} · p95 {total['p95']:.1f}", "")
    console.print(table)
    if report.errors or report.missing or report.timed_out:
        console.print(f"[yellow]{len(report.timed_out)} timed out, {len(report.errors)} errors, "
                      f"{len(report.missing)} questions not generated[/]")


def _fmt(value: float | None) -> str:
    return "–" if value is None else f"{value:.3f}"


def _clip(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + "…"


def _names(csv_list: str) -> list[str]:
    return [n.strip() for n in csv_list.split(",") if n.strip()]


if __name__ == "__main__":
    main()
