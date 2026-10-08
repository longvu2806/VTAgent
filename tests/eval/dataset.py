"""Eval dataset: a CSV in one fixed schema. Only ``id`` and ``question`` are required;
metrics that need a missing column are skipped.

| column          | format                                    | used by                          |
|-----------------|-------------------------------------------|----------------------------------|
| id              | unique                                    | everything                       |
| question        | text                                      | generate                         |
| doc             | file names next to the CSV, ";"-separated | generate (ingested before asking)|
| answerable      | yes / no (empty = yes)                    | refusal metrics                  |
| expected_answer | text                                      | report                           |
| key_points      | ";"-separated                             | key point coverage, number match |
| evidence        | verbatim quotes, "||"-separated           | retrieval and citation metrics   |
| gold_refs       | ";"-separated                             | report                           |
| gold_pages      | integers, ";"-separated                   | report                           |

Any other column (category, difficulty, ...) is kept in ``EvalItem.extra`` for grouping.
"""

import csv
from dataclasses import dataclass, field
from pathlib import Path

REQUIRED = ("id", "question")
LIST_SEPARATORS = {"doc": ";", "key_points": ";", "evidence": "||", "gold_refs": ";", "gold_pages": ";"}
SCHEMA = (*REQUIRED, "answerable", "expected_answer", *LIST_SEPARATORS)


class DatasetError(ValueError):
    """The dataset file does not follow the eval schema."""


@dataclass(frozen=True)
class EvalItem:
    id: str
    question: str
    docs: list[str] = field(default_factory=list)
    answerable: bool = True
    expected_answer: str = ""
    key_points: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    gold_refs: list[str] = field(default_factory=list)
    gold_pages: list[int] = field(default_factory=list)
    extra: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Dataset:
    path: Path
    columns: frozenset[str]  # schema columns present in the file
    items: list[EvalItem]

    def documents(self) -> list[Path]:
        """Source documents named in the ``doc`` column, resolved next to the CSV."""
        names = dict.fromkeys(doc for item in self.items for doc in item.docs)
        return [self.path.parent / name for name in names]


def load_dataset(path: Path) -> Dataset:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        rows = list(reader)
    missing = [c for c in REQUIRED if c not in header]
    if missing:
        raise DatasetError(f"{path.name}: missing required column(s) {missing}")

    items, seen = [], set()
    for line, row in enumerate(rows, start=2):
        try:
            item = _item(row, header)
            if item.id in seen:
                raise DatasetError(f"duplicate id {item.id!r}")
        except DatasetError as e:
            raise DatasetError(f"{path.name} line {line}: {e}") from None
        seen.add(item.id)
        items.append(item)
    return Dataset(path, frozenset(c for c in header if c in SCHEMA), items)


def _item(row: dict[str, str], header: list[str]) -> EvalItem:
    def get(column: str) -> str:
        return (row.get(column) or "").strip()

    if not get("id") or not get("question"):
        raise DatasetError("empty id or question")
    answerable = get("answerable").lower() or "yes"
    if answerable not in ("yes", "no"):
        raise DatasetError(f"answerable must be yes or no, got {answerable!r}")
    lists = {c: [p.strip() for p in get(c).split(sep) if p.strip()] for c, sep in LIST_SEPARATORS.items()}
    if not all(p.isdigit() for p in lists["gold_pages"]):
        raise DatasetError(f"gold_pages must be integers, got {get('gold_pages')!r}")

    return EvalItem(
        id=get("id"),
        question=get("question"),
        docs=lists["doc"],
        answerable=answerable == "yes",
        expected_answer=get("expected_answer"),
        key_points=lists["key_points"],
        evidence=lists["evidence"],
        gold_refs=lists["gold_refs"],
        gold_pages=[int(p) for p in lists["gold_pages"]],
        extra={c: get(c) for c in header if c not in SCHEMA},
    )
