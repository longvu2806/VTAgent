# Code style & conventions

- Python 3.11+. Built-in generics: `list[str]`, `dict | None`.
- **English only** for code, comments, docstrings and repo docs. Vietnamese appears
  only in runtime strings the end user must see verbatim (e.g. the fixed
  "not found" answer).
- All terminal output via `rich.Console` — never `print()`. Use the shared
  `console` from `observability.py`.
- **Layering — dependencies point inward:** `core/` ← entry points (`main.py`,
  `tests/eval/*`). `core/` never imports an entry point. `config.py` and
  `observability.py` are cross-cutting.
- **`core/` building blocks are config-free:** they take a `*Config` dataclass or
  plain arguments. The only config-aware spot is `core/agent_factory.py`
  (see `configuration_rules.md`).
- **Lazy-import heavy or optional dependencies** inside the function that needs
  them (e.g. `pymupdf4llm`, `docx`, `langchain.chat_models`). Type-only imports go
  under `if TYPE_CHECKING:`.
- Run everything from the repository root with absolute imports
  (`from core...`, `from config import settings`) — no packaging.
- Dependencies are pinned with `==` in `requirements.txt`.
