from pathlib import Path

import pytest

from core.prompting import NOT_FOUND
from tests.eval.dataset import Dataset, EvalItem
from tests.eval.metrics import score_run, select_metrics
from tests.eval.runs import RunRecord

QUOTE = "Người đủ 24 tuổi trở lên được lái xe ô tô chở người từ 10 đến 30 chỗ ngồi"
ALL_COLUMNS = ("id", "question", "answerable", "key_points", "evidence")


def _ctx(chunk_id: str, text: str, page: int = 1) -> dict:
    return {"chunk_id": chunk_id, "text": text, "page": page, "source": "law.pdf", "rank": 0, "score": 0.5}


def _score(items, records, enabled, columns=ALL_COLUMNS, **params):
    dataset = Dataset(Path("set.csv"), frozenset(columns), list(items))
    return score_run(dataset, {r.id: r for r in records}, enabled, params)


def _value(report, name):
    return report.summary[name]["value"]


def test_retrieval_metrics_find_evidence_despite_markdown_and_line_breaks():
    item = EvalItem("1", "Q?", evidence=[QUOTE])
    contexts = [_ctx("a", "nhiễu"), _ctx("b", "**Điều 60.**\nNgười đủ 24 tuổi trở lên được lái xe ô tô\nchở người từ 10 đến 30 chỗ ngồi"),
                _ctx("c", "nhiễu")]
    record = RunRecord("1", "Q?", contexts=contexts)

    report = _score([item], [record], ["recall_at_k", "mrr", "ndcg_at_k"])
    assert _value(report, "recall_at_k") == 1.0
    assert _value(report, "mrr") == 0.5
    assert _value(report, "ndcg_at_k") == pytest.approx(0.631, abs=1e-3)

    assert _value(_score([item], [record], ["recall_at_k"], k=1), "recall_at_k") == 0.0


def test_quote_cut_by_a_chunk_boundary_counts_above_the_threshold():
    item = EvalItem("1", "Q?", evidence=[QUOTE])
    record = RunRecord("1", "Q?", contexts=[_ctx("a", QUOTE[:-8])])  # last word cut off

    assert _value(_score([item], [record], ["recall_at_k"], evidence_match=0.8), "recall_at_k") == 1.0
    assert _value(_score([item], [record], ["recall_at_k"], evidence_match=0.99), "recall_at_k") == 0.0


def test_refusal_metrics_split_answerable_and_unanswerable():
    items = [EvalItem("a", "Q?"), EvalItem("u1", "Q?", answerable=False), EvalItem("u2", "Q?", answerable=False)]
    records = [RunRecord("a", "Q?", answer=NOT_FOUND), RunRecord("u1", "Q?", answer=NOT_FOUND),
               RunRecord("u2", "Q?", answer="Mức phạt là 500.000 đồng.")]

    report = _score(items, records, ["refusal_accuracy", "false_refusal_rate"])

    assert report.summary["refusal_accuracy"] == {"value": 0.5, "n": 2}
    assert report.summary["false_refusal_rate"] == {"value": 1.0, "n": 1}


def test_answer_that_only_ends_with_the_refusal_phrase_is_not_a_refusal():
    hedged = f"Có, đó là vi phạm [S1].\n\n**Kết luận:** nếu là xe đạp: {NOT_FOUND}"
    report = _score([EvalItem("a", "Q?")], [RunRecord("a", "Q?", answer=hedged)], ["false_refusal_rate"])

    assert _value(report, "false_refusal_rate") == 0.0


def test_citation_metrics():
    item = EvalItem("1", "Q?", evidence=[QUOTE])
    record = RunRecord("1", "Q?", answer="X [S1]. Y [S3]. Z [S9].",
                       contexts=[_ctx("c1", QUOTE), _ctx("c2", "nhiễu"), _ctx("c3", "nhiễu")],
                       citations=[{"label": "S1", "chunk_id": "c1"}, {"label": "S3", "chunk_id": "c3"}])

    report = _score([item], [record], ["citation_validity", "citation_precision", "citation_recall", "citation_f1"])

    assert _value(report, "citation_validity") == pytest.approx(2 / 3)
    assert _value(report, "citation_precision") == 0.5
    assert _value(report, "citation_recall") == 1.0
    assert _value(report, "citation_f1") == pytest.approx(2 / 3)


def test_number_match_normalises_thousands_and_ignores_article_references():
    item = EvalItem("1", "Q?", key_points=["Đủ 21 tuổi", "Từ 3.500 kg trở lên", "Theo khoản 3 Điều 60"])

    full = _score([item], [RunRecord("1", "Q?", answer="Phải đủ 21 tuổi, xe từ 3500 kg.")], ["number_match"])
    partial = _score([item], [RunRecord("1", "Q?", answer="Phải đủ 18 tuổi, xe từ 3500 kg.")], ["number_match"])

    assert _value(full, "number_match") == 1.0
    assert _value(partial, "number_match") == 0.5


def test_key_point_coverage_counts_points_whose_words_appear():
    item = EvalItem("1", "Q?", key_points=["Xe xuống dốc nhường xe lên dốc", "Xe gần chỗ tránh hơn phải vào vị trí tránh"])
    record = RunRecord("1", "Q?", answer="Xe xuống dốc phải nhường đường cho xe đang lên dốc.")

    assert _value(_score([item], [record], ["key_point_coverage"]), "key_point_coverage") == 0.5


def test_metric_is_skipped_when_the_dataset_lacks_its_column():
    report = _score([EvalItem("1", "Q?")], [RunRecord("1", "Q?", answer="x")],
                    ["recall_at_k", "refusal_accuracy", "false_refusal_rate"], columns=("id", "question"))

    assert report.summary["recall_at_k"] == {"skipped": "dataset has no evidence column"}
    assert report.summary["refusal_accuracy"] == {"skipped": "dataset has no answerable column"}
    assert report.summary["false_refusal_rate"] == {"value": 0.0, "n": 1}


def test_failed_and_missing_questions_are_reported_not_scored():
    items = [EvalItem("ok", "Q?"), EvalItem("bad", "Q?"), EvalItem("todo", "Q?")]
    records = [RunRecord("ok", "Q?", answer="x"), RunRecord("bad", "Q?", error="ConnectError: refused")]

    report = _score(items, records, ["false_refusal_rate"])

    assert report.summary["false_refusal_rate"]["n"] == 1
    assert [r.id for r in report.errors] == ["bad"]
    assert report.missing == ["todo"]


def test_latency_summary_per_stage_and_tokens():
    records = [RunRecord(str(i), "Q?", timings={"generate": float(i)}, tokens={"input_tokens": 100 * i},
                         latency_s=float(i) + 1) for i in range(1, 5)]
    items = [EvalItem(r.id, "Q?") for r in records]

    report = _score(items, records, ["latency"])

    assert report.latency["generate"]["p50"] == 2.5
    assert report.latency["total"]["max"] == 5.0
    assert report.tokens == {"input_tokens": 250.0}
    assert _score(items, records, ["mrr"]).latency is None


def test_scores_are_broken_down_by_group_column():
    items = [EvalItem("1", "Q?", extra={"difficulty": "hard"}), EvalItem("2", "Q?", extra={"difficulty": "medium"})]
    records = [RunRecord("1", "Q?", answer=NOT_FOUND), RunRecord("2", "Q?", answer="x")]

    report = _score(items, records, ["false_refusal_rate"], group_by=["difficulty"])

    assert report.groups["difficulty"]["hard"]["false_refusal_rate"]["value"] == 1.0
    assert report.groups["difficulty"]["medium"]["false_refusal_rate"]["value"] == 0.0


def test_select_metrics():
    assert "mrr" not in select_metrics({"mrr": False}, [], [])
    assert "latency" in select_metrics({}, [], [])  # unlisted metrics are on
    assert select_metrics({"mrr": False}, ["mrr", "latency"], ["latency"]) == ["mrr"]
    with pytest.raises(ValueError, match="unknown metric"):
        select_metrics({"recal": True}, [], [])
