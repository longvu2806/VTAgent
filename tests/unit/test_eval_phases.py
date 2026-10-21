"""Generate then score, with a fake pipeline instead of the models."""

import csv
import re
from pathlib import Path

import pytest

from core.models import Answer, Chunk, Citation, RetrievedChunk
from core.prompting import NOT_FOUND
from tests.eval.dataset import load_dataset
from tests.eval.generate import prepare_run_dir, run
from tests.eval.metrics import select_metrics, score_run
from tests.eval.runs import read_records
from tests.eval.score import render_markdown, write_scores

SETTINGS = {"llm_model": "fake", "embedding_model": "fake", "collection": "c", "chunk_size": 400,
            "chunk_overlap": 50, "top_k": 5}
CORPUS = ["law.pdf"]
RECORDS, RESULTS = "records.jsonl", "results.csv"


@pytest.fixture
def dataset(tmp_path):
    path = tmp_path / "set.csv"
    path.write_text(
        "id,question,answerable,expected_answer,evidence,category\n"
        "1,Phạt bao nhiêu?,yes,0.05%,phạt 0.05% mỗi ngày,numeric\n"
        "2,Có trọng tài không?,no,,,trap\n",
        encoding="utf-8",
    )
    return load_dataset(path)


def _answer(question: str) -> Answer:
    if question.startswith("Có"):
        return Answer(NOT_FOUND, [], [], timings={"generate": 1.0}, timed_out=True)
    chunk = Chunk("c1", "d", "law.pdf", 3, 0, "Bên A chịu phạt 0.05% mỗi ngày chậm.")
    return Answer("Phạt 0.05% mỗi ngày [S1].", [Citation("S1", chunk)], [RetrievedChunk(chunk, 0.9)],
                  timings={"embed_query": 0.1, "generate": 2.0}, tokens={"input_tokens": 900, "output_tokens": 20})


def test_generate_writes_records_and_results_csv(tmp_path, dataset):
    run(dataset.items, _answer, tmp_path / RECORDS, tmp_path / RESULTS)

    records = read_records(tmp_path / RECORDS)
    assert records["1"].contexts[0]["page"] == 3 and records["1"].citations == [{"label": "S1", "chunk_id": "c1"}]
    with (tmp_path / RESULTS).open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert [r["id"] for r in rows] == ["1", "2"]
    assert rows[0]["citations"] == "S1: law.pdf p.3"
    assert rows[0]["generate_s"] == "2.0" and rows[0]["input_tokens"] == "900"
    assert {"latency_s", "embed_query_s"} <= set(rows[0])
    assert (rows[0]["timed_out"], rows[1]["timed_out"]) == ("", "yes")


def test_timed_out_question_is_kept_and_not_retried(tmp_path, dataset):
    calls = []

    def counting(question):
        calls.append(question)
        return _answer(question)

    run(dataset.items, counting, tmp_path / RECORDS, tmp_path / RESULTS)
    run(dataset.items, counting, tmp_path / RECORDS, tmp_path / RESULTS)

    assert len(calls) == 2  # the timed-out answer is final, unlike an error
    assert read_records(tmp_path / RECORDS)["2"].timed_out


def test_generate_resumes_and_retries_failed_questions(tmp_path, dataset):
    calls = []

    def flaky(question):
        calls.append(question)
        if len(calls) == 2:
            raise ConnectionError("ollama down")
        return _answer(question)

    run(dataset.items, flaky, tmp_path / RECORDS, tmp_path / RESULTS)
    assert read_records(tmp_path / RECORDS)["2"].error == "ConnectionError: ollama down"

    run(dataset.items, flaky, tmp_path / RECORDS, tmp_path / RESULTS)  # only the failed question is asked again
    assert len(calls) == 3
    assert read_records(tmp_path / RECORDS)["2"].error is None


def test_generate_stops_when_every_question_fails(tmp_path, dataset):
    items = dataset.items * 3  # 6 questions
    calls = []

    def down(question):
        calls.append(question)
        raise ConnectionError("refused")

    run([type(i)(f"{n}", i.question) for n, i in enumerate(items)], down, tmp_path / RECORDS, tmp_path / RESULTS)
    assert len(calls) == 3


def test_output_files_are_stamped_with_the_run_creation_time(tmp_path):
    meta = prepare_run_dir(tmp_path, Path("set.csv"), SETTINGS, CORPUS)

    assert re.fullmatch(r"records_\d{8}-\d{6}\.jsonl", meta["records"])
    assert meta["results"] == meta["records"].replace("records_", "results_").replace(".jsonl", ".csv")
    assert prepare_run_dir(tmp_path, Path("set.csv"), SETTINGS, CORPUS)["records"] == meta["records"]  # resume: same files


def test_resuming_with_other_settings_or_corpus_is_refused(tmp_path):
    prepare_run_dir(tmp_path, Path("set.csv"), SETTINGS, CORPUS)
    prepare_run_dir(tmp_path, Path("set.csv"), SETTINGS, CORPUS)  # same settings: fine

    with pytest.raises(SystemExit, match="top_k"):
        prepare_run_dir(tmp_path, Path("set.csv"), {**SETTINGS, "top_k": 3}, CORPUS)
    with pytest.raises(SystemExit, match="corpus"):  # documents added to the collection since
        prepare_run_dir(tmp_path, Path("set.csv"), SETTINGS, [*CORPUS, "decree.docx"])


def test_score_report_end_to_end(tmp_path, dataset):
    prepare_run_dir(tmp_path, dataset.path, SETTINGS, CORPUS)
    run(dataset.items, _answer, tmp_path / RECORDS, tmp_path / RESULTS)
    records = read_records(tmp_path / RECORDS)
    enabled = select_metrics({"mrr": False}, [], ["ragas"])

    report = score_run(dataset, records, enabled, {"group_by": ["category", "target"]})  # no target column
    markdown = render_markdown(report, dataset, records, {"settings": SETTINGS}, tmp_path, enabled, {"k": 5})

    assert report.summary["recall_at_k"]["value"] == 1.0
    assert report.summary["refusal_accuracy"]["value"] == 1.0
    assert "| number_match | skipped | – | dataset has no key_points column |" in markdown
    assert "Disabled: `mrr`, `context_precision`" in markdown
    assert "## Latency (seconds)" in markdown and "| generate |" in markdown
    assert "## By category" in markdown and "## By target" not in markdown
    assert report.timed_out == ["2"] and "### timed out: 1 questions" in markdown
    assert "fixed chunks 400/50 tokens · dense search · top-5 |" in markdown


def test_report_names_the_hybrid_search_and_reranking(tmp_path, dataset):
    settings = {**SETTINGS, "sparse": "bm25", "normalize_numbers": True, "rerank": True, "rerank_threshold": 0.3}
    report = score_run(dataset, {}, [], {})

    markdown = render_markdown(report, dataset, {}, {"settings": settings}, tmp_path, [], {})

    assert "dense + bm25 search, RRF, numbers normalized · reranked, threshold 0.3 · top-5 |" in markdown


def test_per_question_scores_csv(tmp_path, dataset):
    run(dataset.items, _answer, tmp_path / RECORDS, tmp_path / RESULTS)
    records = read_records(tmp_path / RECORDS)
    enabled = select_metrics({}, ["recall_at_k", "number_match", "refusal_accuracy"], [])
    report = score_run(dataset, records, enabled, {"group_by": ["category", "difficulty"]})

    write_scores(tmp_path / "scores.csv", report, dataset, records, {"group_by": ["category", "difficulty"]})

    with (tmp_path / "scores.csv").open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert list(rows[0]) == ["id", "question", "answerable", "category", "timed_out", "latency_s",
                             "recall_at_k", "refusal_accuracy"]  # skipped metric and absent column left out
    assert (rows[0]["recall_at_k"], rows[0]["refusal_accuracy"]) == ("1.0", "")  # empty: does not apply
    assert (rows[1]["recall_at_k"], rows[1]["refusal_accuracy"], rows[1]["timed_out"]) == ("", "1.0", "yes")
