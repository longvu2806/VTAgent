"""RAGAS judge plumbing, offline: a fake scorer stands in for the judge API."""

import pytest

from core.prompting import NOT_FOUND
from tests.eval.dataset import EvalItem
from tests.eval.metrics import DEFAULT_PARAMS
from tests.eval.ragas_judge import DEFAULT_JUDGE, _embeddings, _llm, adapt_prompts, judge
from tests.eval.runs import RunRecord

CONTEXTS = [{"chunk_id": "c1", "text": "Người đủ 24 tuổi trở lên được lái xe khách 10 đến 30 chỗ."}]


class FakeScorer:
    def __init__(self, value=0.8, fail_on=()):
        self.calls, self.value, self.fail_on = [], value, fail_on

    async def __call__(self, metric, sample):
        self.calls.append((metric, sample))
        if metric in self.fail_on:
            raise ValueError("malformed JSON")
        return self.value


def _judge(tmp_path, items, records, metrics, scorer):
    return judge(items, {r.id: r for r in records}, metrics, scorer, tmp_path / "cache.jsonl", "tag",
                 DEFAULT_PARAMS, concurrency=2)


def test_only_applicable_questions_are_judged_and_labels_are_stripped(tmp_path):
    items = [EvalItem("ok", "Q?", expected_answer="Không, phải đủ 24 tuổi."),
             EvalItem("refused", "Q?", expected_answer="Có."),
             EvalItem("no_ref", "Q?"),
             EvalItem("trap", "Q?", answerable=False)]
    records = [RunRecord("ok", "Q?", answer="Không, phải đủ 24 tuổi [S1].", contexts=CONTEXTS),
               RunRecord("refused", "Q?", answer=NOT_FOUND, contexts=CONTEXTS),
               RunRecord("no_ref", "Q?", answer="Có [S1, S2].", contexts=CONTEXTS),
               RunRecord("trap", "Q?", answer=NOT_FOUND, contexts=CONTEXTS)]
    scorer = FakeScorer()

    scores, failures = _judge(tmp_path, items, records, ["faithfulness", "factual_correctness"], scorer)

    assert failures == 0
    assert scores == {"ok": {"faithfulness": 0.8, "factual_correctness": 0.8},
                      "refused": {"factual_correctness": 0.8},  # a refusal claims nothing to verify
                      "no_ref": {"faithfulness": 0.8}}  # no reference answer to compare with
    answers = {s.answer for _, s in scorer.calls}
    assert answers == {"Không, phải đủ 24 tuổi.", NOT_FOUND, "Có."}


def test_faithfulness_skips_answers_cut_at_the_time_limit(tmp_path):
    items = [EvalItem("1", "Q?", expected_answer="A")]
    records = [RunRecord("1", "Q?", answer="Không được. Tuy nhiên... " * 50, contexts=CONTEXTS, timed_out=True)]

    scores, _ = _judge(tmp_path, items, records, ["faithfulness", "factual_correctness"], FakeScorer())

    assert scores == {"1": {"factual_correctness": 0.8}}


def test_verdicts_are_cached_and_failures_retried(tmp_path):
    items = [EvalItem("1", "Q?", expected_answer="A")]
    records = [RunRecord("1", "Q?", answer="x", contexts=CONTEXTS)]

    first = FakeScorer(fail_on=("context_recall",))
    scores, failures = _judge(tmp_path, items, records, ["faithfulness", "context_recall"], first)
    assert failures == 1 and scores == {"1": {"faithfulness": 0.8}}

    second = FakeScorer()
    scores, failures = _judge(tmp_path, items, records, ["faithfulness", "context_recall"], second)
    assert [m for m, _ in second.calls] == ["context_recall"]  # faithfulness came from the cache
    assert scores == {"1": {"faithfulness": 0.8, "context_recall": 0.8}}


def test_judging_stops_when_the_service_is_unreachable(tmp_path):
    items = [EvalItem(str(i), "Q?", expected_answer="A") for i in range(20)]
    records = [RunRecord(str(i), "Q?", answer="x", contexts=CONTEXTS) for i in range(20)]
    scorer = FakeScorer(fail_on=("faithfulness",))

    scores, not_scored = _judge(tmp_path, items, records, ["faithfulness"], scorer)

    assert len(scorer.calls) == 5 and not_scored == 20 and scores == {}


def test_changed_inputs_are_judged_again(tmp_path):
    items = [EvalItem("1", "Q?", expected_answer="A")]
    _judge(tmp_path, items, [RunRecord("1", "Q?", answer="x", contexts=CONTEXTS)], ["faithfulness"], FakeScorer())

    scorer = FakeScorer()
    _judge(tmp_path, items, [RunRecord("1", "Q?", answer="y", contexts=CONTEXTS)], ["faithfulness"], scorer)

    assert len(scorer.calls) == 1


def test_nan_verdict_counts_as_not_applicable(tmp_path):
    items = [EvalItem("1", "Q?", expected_answer="A")]
    records = [RunRecord("1", "Q?", answer="x", contexts=CONTEXTS)]

    scores, _ = _judge(tmp_path, items, records, ["faithfulness"], FakeScorer(value=float("nan")))

    assert scores == {"1": {"faithfulness": None}}


@pytest.mark.filterwarnings("ignore")
def test_every_ragas_prompt_gets_the_vietnamese_notes():
    from ragas.metrics import collections as rc

    llm = _llm(DEFAULT_JUDGE, "http://127.0.0.1:9/v1", "test-key")  # never called
    embeddings = _embeddings("http://127.0.0.1:9", "bge-m3")
    metrics = [rc.Faithfulness(llm=llm), rc.AnswerRelevancy(llm=llm, embeddings=embeddings),
               rc.ContextPrecisionWithReference(llm=llm), rc.ContextRecall(llm=llm),
               rc.FactualCorrectness(llm=llm)]

    for metric in metrics:
        adapt_prompts(metric)

    prompts = [p for m in metrics for p in vars(m).values() if hasattr(p, "instruction")]
    assert len(prompts) == 7
    assert all("in Vietnamese" in p.instruction for p in prompts)
    assert "Không tìm thấy" in metrics[1].prompt.instruction  # refusals count as noncommittal
    factual = metrics[4]
    assert "source attributions" in factual.prompt.instruction and "source attributions" in factual.nli_prompt.instruction
    assert "source attributions" not in metrics[0].nli_statement_prompt.instruction  # faithfulness stays strict


def test_openrouter_options_go_only_to_openrouter():
    cfg = {**DEFAULT_JUDGE, "providers": ["deepseek"], "extra_body": {"thinking": {"type": "disabled"}}}

    openrouter = _llm(cfg, "https://openrouter.ai/api/v1", "test-key").model_args["extra_body"]
    deepseek = _llm(cfg, "https://api.deepseek.com", "test-key").model_args["extra_body"]

    assert openrouter == {"thinking": {"type": "disabled"}, "reasoning": {"enabled": False},
                          "provider": {"order": ["deepseek"], "allow_fallbacks": False}}
    assert deepseek == {"thinking": {"type": "disabled"}}
