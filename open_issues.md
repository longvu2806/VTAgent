# Regarding some problems need to be fixed

# 10/10/2026
-Design multi agent to double check, minimal halluciate
- clarify input/output token - window context per one chat ? 

# 16/10/2026 — Generation: refusals and questions that lack information

Handle before further chunking work (R2+).

## 1. Refuses although the answer is in the context

- R1 false refusals: #27, #51, #69, #71. R0 also had #2, #56, #68, #72. In all of them the
  article holding the answer was in the sources: a generation problem, not retrieval.
- Cause: the system prompt says "if the sources do not contain the answer, reply exactly
  NOT_FOUND" (`core/prompting.py`). The model reads it as all-or-nothing and refuses when no
  sentence answers verbatim, i.e. when the answer needs:
  - applying a rule to a situation: #68 "20-year-old driving a 5-ton truck?" (5 t > 3,500 kg
    → class C → 21+); #69 "class C licence, 7-seat car?" (C covers B1/B2 vehicles);
  - pointing out a false premise: #27 "from how many cc may motorbikes use expressways?"
    (no threshold; motorbikes are banned).
- Fix ideas (no agent needed):
  - rewrite the prompt: apply the rules to the situation; answer what is supported and say
    what the sources do not cover; name a false premise; refuse only if nothing is relevant;
  - 1–2 few-shot examples of applying an article to a case;
  - try thinking mode again (Ollama 0.40.4 prefill is ~3.5× faster; costs ~30–40 s/question).
- Constraint: unanswerable questions must stay refused (refusal_accuracy 20/20). Measure
  false_refusal_rate and refusal_accuracy together. Not part of the R0–R5 ablation: report it
  as a separate variant (e.g. R1-p2).

## 2. The context misses information the documents do have

- #10: top-5 holds two clauses of Điều 61 but not Điều 59 (class D). #3 (R0): Điều 31.1
  says "follow khoản 3 Điều 30", which one retrieval pass does not follow.
- Cheap fixes: expand references by regex ("khoản X Điều Y" → fetch that chunk, no LLM
  call); retrieve more children (e.g. top-10) and assemble at most 5 articles; reranker (R4).
- Full fix = agent / R5 (SAD): query decomposition by the Coordinator (B1), verify_claims +
  gap_queries for a second retrieval round (max 2 rounds).

## 3. The question depends on facts the user did not give

- Example: "Con trai tôi điều khiển xe 100cc có bị phạt không?" — depends on age and
  licence (Điều 59, 60: under 18 → violation; 18+ with A1 → allowed; 18+ without A1 →
  violation). Fine amounts are not in the loaded law (they are in a penalty decree): say so.
- Wanted: answer by cases using the thresholds in the sources, then ask back
  ("how old is he, does he have a licence?"); or ask back first in a multi-turn chat.
- The decision to ask back must come after retrieval: the thresholds (16, 18, 50 cm³) are
  in the documents; deciding before retrieval would rely on the model's own knowledge.
- Single turn, now: add a prompt rule "if the answer depends on facts the user did not give,
  split into cases by the thresholds in the sources, answer each, then ask for the missing
  facts". Add ~10 underspecified questions with case-split reference answers to the eval set.
- Multi-turn, with LangGraph: Reasoner returns an optional `follow_up_question`; short-term
  memory keeps 2–3 turns (SAD 5.7); the Coordinator rewrites "15 tuổi" + previous question
  into one query (B1). Not in the SAD (its intents have no "clarify"): record as an extension.

