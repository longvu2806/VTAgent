"""Judge metrics through RAGAS 0.4 (``ragas.metrics.collections``), scored per question.

- Only answerable questions are judged; refusals of unanswerable ones are measured by
  ``refusal_accuracy`` in code.
- [S#] labels are stripped from the answer: they mean nothing to the judge.
- Every RAGAS prompt gets LANGUAGE_NOTE appended. RAGAS prompts are English with English
  examples; without the note the judge may write its statements and questions in
  English, which lowers answer_relevancy (cross-lingual embedding similarity) for no
  reason. ``BasePrompt.adapt()`` is not used: it re-translates the examples with the LLM
  on every run, so the prompts would not be fixed.
- Verdicts are cached in the run directory, keyed on the judge settings and the exact
  inputs: rescoring costs nothing and a corrected dataset re-judges only what changed.
"""

import asyncio
import hashlib
import json
import math
import os
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from rich.progress import Progress

from observability import console, log
from tests.eval.dataset import EvalItem
from tests.eval.metrics import is_refusal, strip_labels
from tests.eval.runs import RunRecord

os.environ.setdefault("RAGAS_DO_NOT_TRACK", "true")  # RAGAS sends usage analytics by default

PROMPT_VERSION = 3  # bump when the notes or the reference framing change, so cached verdicts are not reused
LANGUAGE_NOTE = (
    "\nThe inputs are Vietnamese legal text. Write every statement, claim and question you generate"
    " in Vietnamese, and keep numbers, units and legal references (Điều, khoản, điểm) exactly as"
    " written in the input."
)
# Answers cite sources ("Theo Điều 19 của Luật ...") that reference answers do not repeat; the
# judge attached them to every claim and rejected correct claims for the citation alone
# (question 39, a verbatim-correct answer, scored 0). Factual correctness only judges content;
# faithfulness keeps checking citations against the context.
ATTRIBUTION_NOTE = (
    "\nLeave out source attributions such as \"Theo Điều 19 của Luật Giao thông đường bộ\" or"
    " \"theo nguồn\": they are not facts to verify. Judge only the substantive content."
)
# Version of per-metric notes, part of the cache key of that metric only, so changing one
# metric's prompt does not re-judge (and re-bill) the others.
METRIC_PROMPT_VERSIONS = {"factual_correctness": 1}
NONCOMMITTAL_NOTE = (
    "\nAn answer whose only content is that the information was not found in the documents"
    ' (e.g. "Không tìm thấy thông tin này trong tài liệu đã nạp.") is noncommittal. An answer that'
    " gives a substantive answer first is not noncommittal, even if it also mentions missing information."
)
MAX_FAILURES_WITHOUT_SUCCESS = 5  # then the service is unreachable: skip the rest instead of failing each
# FactualCorrectness compares answer and reference without the question. Reference answers
# do not restate the question's situation, so an answer that does ("When a car stalls on the
# tracks, the driver must ...") had every claim judged unsupported. Framing the reference
# with the question fixes that (question 28: 0.0 → 1.0) and still scores wrong answers low.
REFERENCE_FRAME = "Tình huống trong câu hỏi: {question}\nĐáp án: {reference}"
EMBEDDING_ONLY = ("semantic_similarity",)  # needs no LLM, only the local embedding model
NEEDS_REFERENCE = ("context_precision", "context_recall", "factual_correctness", "semantic_similarity")
NEEDS_CONTEXTS = ("context_precision", "context_recall", "faithfulness")

DEFAULT_JUDGE = {
    "model": "deepseek/deepseek-v4-flash",
    "temperature": 0.0,
    "max_tokens": 16384,  # RAGAS's default 1024 truncates long faithfulness verdicts; 4096 and 8192 the longest answers
    "reasoning": False,  # OpenRouter only
    "providers": [],  # OpenRouter only
    "extra_body": {},  # other APIs: their own request fields (e.g. to switch thinking off)
    "max_concurrency": 8,
}


@dataclass(frozen=True)
class Sample:
    question: str
    answer: str  # without [S#] labels
    contexts: list[str]
    reference: str


Scorer = Callable[[str, Sample], Awaitable[float]]


def judge(items: list[EvalItem], records: dict[str, RunRecord], metrics: list[str], scorer: Scorer,
          cache_path: Path, cache_tag: str, params: dict, concurrency: int) -> tuple[dict[str, dict], int]:
    """Per-question judge scores ``{id: {metric: score}}`` and the number of failed calls.
    Failed calls are not cached, so the next scoring retries them."""
    cache = _read_cache(cache_path)
    scores: dict[str, dict[str, float | None]] = {}
    jobs = []
    for item in items:
        rec = records.get(item.id)
        if rec is None or rec.error:
            continue
        sample = Sample(item.question, strip_labels(rec.answer), [c["text"] for c in rec.contexts],
                        item.expected_answer)
        for metric in metrics:
            if not _applies(metric, item, rec, params):
                continue
            key = _key(cache_tag, metric, sample)
            if key in cache:
                scores.setdefault(item.id, {})[metric] = cache[key]
            else:
                jobs.append((item.id, metric, sample, key))
    log.info("judge: %d scores cached, %d to request", sum(map(len, scores.values())), len(jobs))
    failures = asyncio.run(_run(jobs, scorer, scores, cache_path, concurrency)) if jobs else 0
    return scores, failures


def build_scorer(judge_cfg: dict, metrics: list[str], base_url: str, api_key: str | None,
                 ollama_url: str, embedding_model: str) -> Scorer:
    """RAGAS metric objects for ``metrics``; ``api_key`` may be None for embedding-only metrics."""
    from ragas.metrics import collections as rc

    embeddings = _embeddings(ollama_url, embedding_model)
    llm = None if api_key is None else _llm(judge_cfg, base_url, api_key)
    factories = {
        "context_precision": lambda: rc.ContextPrecisionWithReference(llm=llm),
        "context_recall": lambda: rc.ContextRecall(llm=llm),
        "faithfulness": lambda: rc.Faithfulness(llm=llm),
        "answer_relevancy": lambda: rc.AnswerRelevancy(llm=llm, embeddings=embeddings),
        "factual_correctness": lambda: rc.FactualCorrectness(llm=llm),
        "semantic_similarity": lambda: rc.SemanticSimilarity(embeddings=embeddings),
    }
    objects = {name: factories[name]() for name in metrics}
    for obj in objects.values():
        adapt_prompts(obj)

    async def score(name: str, s: Sample) -> float:
        m = objects[name]
        if name == "context_precision":
            result = await m.ascore(user_input=s.question, reference=s.reference, retrieved_contexts=s.contexts)
        elif name == "context_recall":
            result = await m.ascore(user_input=s.question, retrieved_contexts=s.contexts, reference=s.reference)
        elif name == "faithfulness":
            result = await m.ascore(user_input=s.question, response=s.answer, retrieved_contexts=s.contexts)
        elif name == "answer_relevancy":
            result = await m.ascore(user_input=s.question, response=s.answer)
        elif name == "factual_correctness":
            framed = REFERENCE_FRAME.format(question=s.question, reference=s.reference)
            result = await m.ascore(response=s.answer, reference=framed)
        else:
            result = await m.ascore(reference=s.reference, response=s.answer)
        return result.value

    return score


def adapt_prompts(metric_obj: object) -> None:
    """Append the Vietnamese notes to every prompt the metric object holds."""
    from ragas.prompt.metrics.base_prompt import BasePrompt

    for prompt in vars(metric_obj).values():
        if isinstance(prompt, BasePrompt):
            prompt.instruction += LANGUAGE_NOTE
            if type(prompt).__name__ == "AnswerRelevancePrompt":
                prompt.instruction += NONCOMMITTAL_NOTE
            if type(metric_obj).__name__ == "FactualCorrectness":
                prompt.instruction += ATTRIBUTION_NOTE


def cache_tag(judge_cfg: dict) -> str:
    """Everything that changes a verdict besides the inputs. Not max_tokens: it only cuts the
    output, and a cut verdict fails and is not cached, so a cached one never depended on it."""
    import ragas

    settings = {k: judge_cfg[k] for k in ("model", "temperature", "reasoning", "providers", "extra_body")}
    return json.dumps({**settings, "prompt_version": PROMPT_VERSION, "ragas": ragas.__version__}, sort_keys=True)


def _applies(metric: str, item: EvalItem, rec: RunRecord, params: dict) -> bool:
    if not item.answerable:
        return False
    if metric in NEEDS_REFERENCE and not item.expected_answer:
        return False
    if metric in NEEDS_CONTEXTS and not rec.contexts:
        return False
    if metric == "faithfulness" and rec.timed_out:
        return False  # a cut repetition loop: no complete claims, and its verdict overflows max_tokens
    return not (metric == "faithfulness" and is_refusal(rec.answer, params))  # a refusal claims nothing


def _key(tag: str, metric: str, sample: Sample) -> str:
    version = {"metric_prompt_version": METRIC_PROMPT_VERSIONS[metric]} if metric in METRIC_PROMPT_VERSIONS else {}
    payload = json.dumps({"tag": tag, "metric": metric, **version, **asdict(sample)}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _read_cache(path: Path) -> dict[str, float | None]:
    if not path.exists():
        return {}
    entries = (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    return {e["key"]: e["score"] for e in entries}


async def _run(jobs: list[tuple], scorer: Scorer, scores: dict, cache_path: Path, concurrency: int) -> int:
    """Run the judge calls; returns how many were not scored."""
    semaphore = asyncio.Semaphore(concurrency)
    done = {"ok": 0, "failed": 0, "skipped": 0}

    def unreachable() -> bool:
        return not done["ok"] and done["failed"] >= MAX_FAILURES_WITHOUT_SUCCESS

    with Progress(console=console) as progress:
        task = progress.add_task("judging", total=len(jobs))

        async def one(item_id: str, metric: str, sample: Sample, key: str) -> None:
            try:
                async with semaphore:
                    if unreachable():
                        done["skipped"] += 1
                        return
                    value = await scorer(metric, sample)
            except Exception as e:  # one bad verdict (e.g. malformed JSON) must not stop the others
                done["failed"] += 1
                log.warning("judge failed on question %s, %s: %s", item_id, metric, e)
                return
            finally:
                progress.advance(task)
            done["ok"] += 1
            value = None if value is None or math.isnan(value) else float(value)  # NaN: nothing to judge
            scores.setdefault(item_id, {})[metric] = value
            with cache_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"key": key, "id": item_id, "metric": metric, "score": value}) + "\n")

        await asyncio.gather(*(one(*job) for job in jobs))
    if done["skipped"]:
        log.error("judge stopped: the first %d calls all failed, so the judge API or Ollama looks"
                  " unreachable; %d calls skipped", done["failed"], done["skipped"])
    return done["failed"] + done["skipped"]


def _llm(judge_cfg: dict, base_url: str, api_key: str):
    from openai import AsyncOpenAI
    from ragas.llms import llm_factory

    extra_body = dict(judge_cfg["extra_body"])  # provider-specific request fields, sent as given
    if is_openrouter(base_url):  # `reasoning` and `providers` are OpenRouter options
        if not judge_cfg["reasoning"]:
            extra_body["reasoning"] = {"enabled": False}
        if judge_cfg["providers"]:  # pin the backend so reruns are judged the same way
            extra_body["provider"] = {"order": judge_cfg["providers"], "allow_fallbacks": False}
    client = AsyncOpenAI(base_url=base_url, api_key=api_key)
    return llm_factory(judge_cfg["model"], client=client, temperature=judge_cfg["temperature"],
                       max_tokens=judge_cfg["max_tokens"], extra_body=extra_body)


def is_openrouter(base_url: str) -> bool:
    return "openrouter.ai" in base_url


def _embeddings(base_url: str, model: str):
    """The local embedding model (bge-m3 on Ollama) in RAGAS's embedding interface."""
    from langchain_ollama import OllamaEmbeddings
    from ragas.embeddings.base import BaseRagasEmbedding

    class OllamaEmbedding(BaseRagasEmbedding):
        def __init__(self):
            super().__init__()
            self.client = OllamaEmbeddings(model=model, base_url=base_url)

        def embed_text(self, text: str, **kwargs) -> list[float]:
            return self.client.embed_query(text)

        async def aembed_text(self, text: str, **kwargs) -> list[float]:
            return await self.client.aembed_query(text)

    return OllamaEmbedding()
