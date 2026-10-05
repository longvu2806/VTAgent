import pytest

from core.chunking import split_fixed

WORDS = " ".join(f"w{i}" for i in range(10))


def test_windows_overlap_by_given_tokens(word_tokenizer):
    chunks = split_fixed(WORDS, word_tokenizer, chunk_size=4, overlap=1)
    assert chunks == ["w0 w1 w2 w3", "w3 w4 w5 w6", "w6 w7 w8 w9"]


def test_no_overlap(word_tokenizer):
    chunks = split_fixed(WORDS, word_tokenizer, chunk_size=5, overlap=0)
    assert chunks == ["w0 w1 w2 w3 w4", "w5 w6 w7 w8 w9"]


def test_chunks_are_verbatim_slices(word_tokenizer):
    text = "Điều 5.\n\n1.  Bên B   chịu phạt"
    assert split_fixed(text, word_tokenizer, chunk_size=400, overlap=50) == [text]


def test_blank_text_gives_no_chunks(word_tokenizer):
    assert split_fixed("  \n ", word_tokenizer, chunk_size=400, overlap=50) == []


def test_overlap_must_be_smaller_than_chunk(word_tokenizer):
    with pytest.raises(ValueError):
        split_fixed(WORDS, word_tokenizer, chunk_size=4, overlap=4)
