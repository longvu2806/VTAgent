# Configuration rules

- All settings live in `config.py` as a single pydantic-settings `Settings` class.
  Import the singleton: `from config import settings`.
- Override with environment variables prefixed `VTAGENT_` or a `.env` file at the
  repo root. `.env` is git-ignored; `.env.example` lists every setting and is
  updated in the same change that adds or removes one.
- Only `core/agent_factory.py` and entry points read `settings`. The factory turns
  settings into the plain arguments / `*Config` dataclasses that `core/` building
  blocks take. `core/` modules never import `config`.
- No magic numbers in `core/`: tunable values (chunk size, top-k, model names,
  thresholds) are `Settings` defaults passed down explicitly. Values fixed by the
  SAD may be hard-coded in the factory with a comment citing the SAD section.
- Every ablation config (R0–R5, SAD Table 6.5) must be reproducible from settings
  alone. One config = one Qdrant collection whose name carries the config id
  (e.g. `vtagent_docs_r0`), so indexes built with different chunking never mix.
- Entry points log the effective settings at the start of every run, so each
  result can be traced back to the exact configuration.
- Secrets (e.g. the API key of the offline eval judge) come only from environment
  variables — never from code or committed files.
- Exception: scoring settings (enabled metrics, thresholds) live in
  `tests/eval/score.toml`. They describe how a run is measured, not how the system
  behaves, so they stay out of `Settings`. Eval datasets follow the fixed schema
  documented in `tests/eval/dataset.py`.
