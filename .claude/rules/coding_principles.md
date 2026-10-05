# Coding principles

These apply to every change. They bias toward caution over speed; for trivial
edits, use judgment.

## 1. Think before coding

Don't assume. Don't hide confusion. Surface tradeoffs.

- State assumptions explicitly before implementing. If uncertain, ask.
- If a request has several reasonable interpretations, list them — don't pick one silently.
- If a simpler approach exists, say so. Push back when warranted.
- Read the relevant section of `doc/VTAgent_SAD_v1_0.docx` before designing anything.
  The SAD is the source of truth for architecture and parameters; if code must
  deviate from it, say so and why.

## 2. Simplicity first

Minimum code that solves the problem. Nothing speculative.

- No features beyond what was asked.
- No abstractions for single-use code; no configurability nobody asked for.
- No error handling for impossible scenarios — let unexpected errors surface.
- If 200 lines could be 50, rewrite it.

Test: would a senior engineer call this overcomplicated? If yes, simplify.

## 3. Surgical changes

Touch only what you must. Clean up only your own mess.

- Don't "improve" adjacent code, comments or formatting.
- Don't refactor what isn't broken.
- Match the existing style, even if you would do it differently.
- Noticed an unrelated bug or dead code? Mention it — don't fix it in the same change.
- Remove imports, variables and functions that *your* change made unused;
  leave pre-existing dead code alone.

Test: every changed line traces directly to the request.

## 4. Goal-driven execution

Define success criteria. Loop until verified.

Turn tasks into verifiable goals:

- "Add validation" → "write tests for invalid inputs, then make them pass"
- "Fix the bug" → "write a test that reproduces it, then make it pass"
- "Tune chunk size" → "run the eval on the dev set before and after, report the delta"

For multi-step tasks, state a short plan first:

```
1. [step] → verify: [check]
2. [step] → verify: [check]
```

Strong criteria let you loop independently; weak ones ("make it work") need
clarification first.

## 5. Test and review after big implementations

A big implementation is a new module, a new pipeline stage or ablation config
(R0–R5), or any change touching three or more files. After one:

1. Add unit tests for the new behavior.
2. Run the whole suite with `python -m pytest`. Everything green before reporting done.
3. Review your own diff against principles 2 and 3: drop dead code, speculative
   options and debug output.
4. When the ingest or query path changed, smoke-test end to end against the real
   Ollama models with `main.py`.
5. Report honestly: what was tested, what was not, and why.

Testing conventions:

- `tests/unit/` runs fully offline: no Ollama, no network, no model downloads.
  Use fakes — `FakeListChatModel`, `DeterministicFakeEmbedding` from
  `langchain_core`, `QdrantClient(":memory:")`, pytest's `tmp_path`.
- Anything that needs live models belongs in a smoke run, not the unit suite.
- Test behavior through public functions, not implementation details.
