import pytest

from tests.eval.dataset import DatasetError, load_dataset


def _csv(tmp_path, text):
    path = tmp_path / "set.csv"
    path.write_text(text, encoding="utf-8")
    return path


def test_full_schema_row_is_parsed(tmp_path):
    path = _csv(tmp_path, (
        "id,question,doc,answerable,key_points,evidence,gold_pages,category\n"
        '7,Q?,law.pdf,no,a; b,"quote one || quote two",3; 4,multi_hop\n'
    ))

    dataset = load_dataset(path)

    [item] = dataset.items
    assert (item.id, item.question, item.answerable) == ("7", "Q?", False)
    assert item.key_points == ["a", "b"]
    assert item.evidence == ["quote one", "quote two"]
    assert item.gold_pages == [3, 4]
    assert item.extra == {"category": "multi_hop"}
    assert dataset.documents() == [tmp_path / "law.pdf"]
    assert "evidence" in dataset.columns and "expected_answer" not in dataset.columns


def test_required_columns_are_enough(tmp_path):
    dataset = load_dataset(_csv(tmp_path, "id,question\n1,Q?\n"))

    [item] = dataset.items
    assert item.answerable and item.evidence == [] and item.key_points == []
    assert dataset.documents() == []


def test_missing_required_column_is_rejected(tmp_path):
    with pytest.raises(DatasetError, match="question"):
        load_dataset(_csv(tmp_path, "id,prompt\n1,Q?\n"))


def test_bad_value_names_the_line(tmp_path):
    with pytest.raises(DatasetError, match="line 3: answerable must be yes or no"):
        load_dataset(_csv(tmp_path, "id,question,answerable\n1,Q?,yes\n2,Q?,maybe\n"))


def test_duplicate_ids_are_rejected(tmp_path):
    with pytest.raises(DatasetError, match="duplicate id '1'"):
        load_dataset(_csv(tmp_path, "id,question\n1,Q?\n1,Q2?\n"))
