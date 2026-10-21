"""Sparse encoders for hybrid search: BM25 tokenizer, number normalization, term weights."""

import pytest

from core.sparse import BgeM3SparseEncoder, BM25Encoder, normalize_numbers, tokenize


def _bm25(normalize=False):
    return BM25Encoder(k1=1.2, b=0.75, avg_len=10, normalize=normalize)


def test_tokenize_adds_adjacent_syllable_pairs():  # the SAD 6.4 example
    assert tokenize("Phạt vi phạm 8%") == ["phạt", "vi", "phạm", "8%", "phạt_vi", "vi_phạm", "phạm_8%"]


def test_tokenize_keeps_numbers_whole_and_drops_markdown():
    tokens = tokenize("**Điều 5.** Phạt 160.000.000 đồng; 0,05%")

    assert {"điều", "5", "160.000.000", "0,05%", "phạt_160.000.000"} <= set(tokens)
    assert not any("*" in t for t in tokens)


@pytest.mark.parametrize(("text", "expected"), [
    ("phạt 160 triệu đồng", "phạt 160000000 đồng"),
    ("160.000.000 đồng", "160000000 đồng"),
    ("1,5 tỷ", "1500000000"),
    ("30 nghìn tỷ đồng", "30000000000000 đồng"),
    ("từ 1/3/2027", "từ 2027-3-1"),
    ("01 tháng 3 năm 2027", "2027-3-1"),
    ("05 ngày", "5 ngày"),
])
def test_normalize_numbers_gives_one_spelling(text, expected):
    assert normalize_numbers(text) == expected


@pytest.mark.parametrize("text", ["điều 7.3", "khoản 5.1.", "0,25%", "tỷ lệ 25%"])
def test_normalize_numbers_keeps_references_and_decimals(text):
    assert normalize_numbers(text) == text


def test_term_ids_are_stable_across_runs():
    assert _bm25().query("phạt").indices == [1440544248]  # crc32, unlike the per-run salted hash()


def test_query_weighs_each_distinct_term_once():
    vector = _bm25().query("phạt phạt tiền")

    assert vector.indices == sorted(set(vector.indices))
    assert len(vector.indices) == 4  # phạt, tiền, phạt_phạt, phạt_tiền
    assert vector.values == [1.0] * 4


def _weight(encoder, text, term):
    [vector] = encoder.documents([text])
    [term_id] = encoder.query(term).indices
    return vector.values[vector.indices.index(term_id)]


def test_bm25_term_frequency_saturates():
    encoder = _bm25()
    once, twice, often = (_weight(encoder, " ".join(["phạt"] * n + ["x"] * (10 - n)), "phạt") for n in (1, 2, 9))

    assert once < twice < often < 1.2 + 1  # bounded by k1 + 1


def test_bm25_longer_chunks_weigh_a_term_less():
    encoder = _bm25()

    assert _weight(encoder, "phạt " + "x " * 20, "phạt") < _weight(encoder, "phạt x", "phạt")


def test_normalized_question_matches_another_spelling_of_the_number():
    plain, normalized = _bm25(), _bm25(normalize=True)
    document = "Phạt tiền từ 160.000.000 đồng"

    assert not set(plain.query("160 triệu").indices) & set(plain.documents([document])[0].indices)
    assert set(normalized.query("160 triệu").indices) <= set(normalized.documents([document])[0].indices)


def test_bge_m3_keeps_positive_weights_sorted_by_token_id():
    encoder = BgeM3SparseEncoder(lambda texts: [{"5": 0.3, "12": 0.0, "3": 0.2}] * len(texts))

    vector = encoder.query("câu hỏi")

    assert (vector.indices, vector.values) == ([3, 5], [0.2, 0.3])
    assert encoder.documents(["a", "b"]) == [vector, vector]
