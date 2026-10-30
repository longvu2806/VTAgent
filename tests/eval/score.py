"""Eval phase 2 — score a generated run and write report_<stamp>.md and scores_<stamp>.csv.

    python -m tests.eval.score data/eval_runs/<run> [--config tests/eval/score.toml]
                                                   [--only recall_at_k,mrr] [--skip ragas,latency]

Code metrics need no models. The RAGAS metrics need the judge API (key in .env) and the
local Ollama for embeddings; `--skip ragas` turns them all off. The dataset is re-read at
scoring time, so a corrected dataset is scored without regenerating the answers.
"""

import argparse
import csv
import json
import tomllib
from datetime import datetime, timezone
from pathlib import Path

from rich.table import Table

from config import settings
from observability import console, setup_logging
from tests.eval.dataset import Dataset, load_dataset
from tests.eval.metrics import (DEFAULT_PARAMS, JUDGE_METRICS, LATENCY, METRICS, Report, score_run,
                                select_metrics)
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

    judged, unavailable, judge_line = _judge(enabled, config, dataset, records, params, args.run_dir)
    report = score_run(dataset, records, enabled, params, judged, unavailable)
    _print_summary(report)
    scored_at = stamp()
    path = args.run_dir / f"report_{scored_at}.md"
    markdown = render_markdown(report, dataset, records, meta, args.run_dir, enabled, params, judge_line)
    path.write_text(markdown, encoding="utf-8")
    console.print(f"[green]report[/] → {path}")
    scores_path = args.run_dir / f"scores_{scored_at}.csv"
    write_scores(scores_path, report, dataset, records, params)
    console.print(f"[green]scores[/] → {scores_path}")


def _judge(enabled: list[str], config: dict, dataset: Dataset, records: dict[str, RunRecord], params: dict,
           run_dir: Path) -> tuple[dict, dict[str, str], str | None]:
    """Judge scores of the enabled RAGAS metrics, metrics that cannot run (with why), and a
    one-line description of the judge for the report."""
    wanted = [m for m in enabled if m in JUDGE_METRICS]
    if not wanted:
        return {}, {}, None
    from tests.eval.ragas_judge import DEFAULT_JUDGE, EMBEDDING_ONLY, build_scorer, cache_tag, is_openrouter, judge

    cfg = {**DEFAULT_JUDGE, **config.get("judge", {})}
    key = settings.judge_api_key.get_secret_value() if settings.judge_api_key else ""
    unavailable = {}
    if not key:
        reason = "no judge API key: set VTAGENT_JUDGE_API_KEY in .env"
        unavailable = {m: reason for m in wanted if m not in EMBEDDING_ONLY}
        wanted = [m for m in wanted if m in EMBEDDING_ONLY]
        if not wanted:
            return {}, unavailable, None

    scorer = build_scorer(cfg, wanted, settings.judge_base_url, key or None,
                          settings.ollama_base_url, settings.embedding_model)
    judged, failures = judge(dataset.items, records, wanted, scorer, run_dir / "judge_cache.jsonl",
                             cache_tag(cfg), {**DEFAULT_PARAMS, **params}, cfg["max_concurrency"])
    line = f"{settings.embedding_model} embeddings (local)"
    if key:
        if is_openrouter(settings.judge_base_url):
            options = f" · reasoning {'on' if cfg['reasoning'] else 'off'}"
            options += f" · providers {', '.join(cfg['providers'])}" if cfg["providers"] else ""
        else:
            options = f" · extra_body {json.dumps(cfg['extra_body'])}" if cfg["extra_body"] else ""
        line = f"{cfg['model']} via {settings.judge_base_url} · temperature {cfg['temperature']}{options} · {line}"
    if failures:
        console.print(f"[yellow]{failures} judge calls failed; rescore to retry them[/]")
        line += f" · {failures} failed calls (not scored)"
    return judged, unavailable, line


def render_markdown(report: Report, dataset: Dataset, records: dict[str, RunRecord], meta: dict,
                    run_dir: Path, enabled: list[str], params: dict, judge_line: str | None = None) -> str:
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
        f"| Models | {s['llm_model']} · {s['embedding_model']} · prompt {s.get('prompt', 'v1')} |",  # older runs: v1
        f"| Retrieval | collection `{s['collection']}` · {_chunking(s)} · {_search(s)} · top-{s['top_k']} |",
        *([f"| Judge | {judge_line} |"] if judge_line else []),
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
        if not by_value:  # the dataset has no such column
            continue
        lines += ["", f"## By {column}", "", f"| {column} | " + " | ".join(scored) + " |",
                  "|---|" + "---|" * len(scored)]
        for value, results in by_value.items():
            cells = [f"{_fmt(results[n]['value'])} ({results[n]['n']})" for n in scored]
            lines.append(f"| {value} | " + " | ".join(cells) + " |")

    lines += _failures(report, dataset, records, params["max_failures"])
    return "\n".join(lines) + "\n"


def _chunking(s: dict) -> str:
    if s.get("chunking") == "structured":
        return (f"structured chunks: child {s['child_min_tokens']}–{s['child_max_tokens']}, parent ≤ "
                f"{s['parent_max_tokens']}, context budget {s['context_budget_tokens']} tokens")
    return f"fixed chunks {s['chunk_size']}/{s['chunk_overlap']} tokens"


def _search(s: dict) -> str:
    sparse = s.get("sparse", "none")  # runs before R3 have no such setting
    search = "dense search" if sparse == "none" else f"dense + {sparse} search, RRF"
    if sparse == "bm25" and s.get("normalize_numbers"):
        search += ", numbers normalized"
    if s.get("rerank"):
        threshold = s.get("rerank_threshold")
        search += " · reranked" + ("" if threshold is None else f", threshold {threshold}")
    return search


def write_scores(path: Path, report: Report, dataset: Dataset, records: dict[str, RunRecord], params: dict) -> None:
    """One row per scored question, in dataset order, with one column per scored metric.
    An empty cell means the metric does not apply to that question."""
    group_by = [c for c in {**DEFAULT_PARAMS, **params}["group_by"] if any(c in i.extra for i in dataset.items)]
    metrics = [name for name, result in report.summary.items() if "skipped" not in result]
    rows = []
    for item in dataset.items:
        if item.id not in report.item_scores:
            continue
        scores = report.item_scores[item.id]
        rows.append({
            "id": item.id,
            "question": item.question,
            "answerable": "yes" if item.answerable else "no",
            **{c: item.extra.get(c, "") for c in group_by},
            "timed_out": "yes" if records[item.id].timed_out else "",
            "latency_s": round(records[item.id].latency_s, 2),
            **{m: "" if scores[m] is None else round(scores[m], 4) for m in metrics},
        })
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["id"])
        writer.writeheader()
        writer.writerows(rows)


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
