import pytest

from core.chunking import context_header, split_fixed, split_structured
from core.models import PageText

WORDS = " ".join(f"w{i}" for i in range(10))


def _structured(texts, tokenizer, pages=None, child_min=1, child_max=400, parent_max=1200, fallback_max=300):
    pages = pages or [None] * len(texts)
    return split_structured([PageText(p, t) for p, t in zip(pages, texts)], tokenizer, child_min=child_min,
                            child_max=child_max, parent_max=parent_max, fallback_max=fallback_max)


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


# --- structured (R1) ---

LAW_PAGE_5 = """CHƯƠNG I
QUY ĐỊNH CHUNG

**Điều 1. Phạm vi điều chỉnh**

Luật này quy định về quy tắc giao thông.

## **Điều 8. Các hành vi bị nghiêm cấm**

5
"""
LAW_PAGE_6 = """1. Phá hoại đường, cầu.

2. Điều khiển xe ô tô mà trong máu có nồng độ cồn. Điều khiển xe mô tô vượt quá 50 miligam.

6
"""


def test_law_articles_are_parents_and_clauses_children_across_pages(word_tokenizer):
    pieces = _structured([LAW_PAGE_5, LAW_PAGE_6], word_tokenizer, pages=[5, 6])

    assert [(p.section, p.page) for p in pieces] == [
        ("Điều 1. Phạm vi điều chỉnh", 5),  # the Chương heading opens the article's block
        ("Điều 8. Các hành vi bị nghiêm cấm › Khoản 1", 5),  # lead-in joins Khoản 1
        ("Điều 8. Các hành vi bị nghiêm cấm › Khoản 2", 6),
    ]
    chapter, clause1, clause2 = pieces
    assert chapter.text.startswith("CHƯƠNG I") and chapter.parent_text == chapter.text
    assert clause2.text == ("2. Điều khiển xe ô tô mà trong máu có nồng độ cồn. "
                            "Điều khiển xe mô tô vượt quá 50 miligam.")  # verbatim; page number "6" dropped
    assert clause1.parent_key == clause2.parent_key != chapter.parent_key
    assert clause1.parent_text.startswith("## **Điều 8.") and clause1.parent_text.endswith("50 miligam.")
    assert "\n5\n" not in clause1.parent_text  # page number dropped where the pages join


def test_contract_layouts_are_recognised(word_tokenizer):
    contract = """HỢP ĐỒNG MUA BÁN
Số 15/2026

ĐIỀU 1: ĐỊNH NGHĨA
Hàng hóa là máy bơm.

Điều 2 – Giá trị hợp đồng
2.1. Giá là 100 triệu đồng.
2.2. Thanh toán trong 30 ngày.

**Điều 3** . **Hiệu lực**
Hợp đồng có hiệu lực từ ngày ký.
Phụ lục 01 là bộ phận không tách rời của hợp đồng.
Điều 2.1 nêu giá.

PHỤ LỤC 01
Danh mục hàng hóa."""

    pieces = _structured([contract], word_tokenizer)

    assert [p.section for p in pieces] == [
        "",  # preamble
        "ĐIỀU 1: ĐỊNH NGHĨA",
        "Điều 2 – Giá trị hợp đồng › Khoản 2.1",
        "Điều 2 – Giá trị hợp đồng › Khoản 2.2",
        "Điều 3. Hiệu lực",  # body lines naming "Phụ lục 01" or "Điều 2.1" start no new block
        "PHỤ LỤC 01",
    ]
    assert pieces[0].text == "HỢP ĐỒNG MUA BÁN\nSố 15/2026" and pieces[0].page is None


def test_small_children_merge_with_the_next(word_tokenizer):
    article = "Điều 5. Phạt\n1. x x\n2. y\n3. z z z z z z"

    pieces = _structured([article], word_tokenizer, child_min=5)

    assert [p.text for p in pieces] == ["Điều 5. Phạt\n1. x x", "2. y\n3. z z z z z z"]
    assert [p.section for p in pieces] == ["Điều 5. Phạt › Khoản 1", "Điều 5. Phạt › Khoản 2, 3"]


def test_long_clause_is_split_at_points(word_tokenizer):
    article = "Điều 6. Cấm\n1. Không được:\na) w w w w\nb) w w w w\nc) w w w w"

    pieces = _structured([article], word_tokenizer, child_max=10)

    assert [p.text for p in pieces] == ["Điều 6. Cấm\n1. Không được:", "a) w w w w\nb) w w w w", "c) w w w w"]
    assert {p.section for p in pieces} == {"Điều 6. Cấm › Khoản 1"}
    assert {p.parent_text for p in pieces} == {article}


def test_long_text_without_points_is_split_at_sentences_with_one_sentence_overlap(word_tokenizer):
    article = "Điều 7. Tiêu đề\nA a a. B b b. C c c."

    pieces = _structured([article], word_tokenizer, child_max=8)

    assert [p.text for p in pieces] == ["Điều 7. Tiêu đề\nA a a.", "Tiêu đề\nA a a. B b b.", "B b b. C c c."]


def test_long_article_is_split_into_several_parents(word_tokenizer):
    article = "Điều 9. X\n1. a a a\n2. b b b\n3. c c c"

    first, second, third = _structured([article], word_tokenizer, parent_max=8)

    assert first.parent_text == first.text == "Điều 9. X\n1. a a a"
    assert second.parent_key == third.parent_key != first.parent_key
    assert second.parent_text == "Điều 9. X\n\n2. b b b\n3. c c c"  # later groups repeat the article title


def test_document_without_articles_falls_back_to_paragraph_chunks(word_tokenizer):
    minutes = "Biên bản họp\n\nĐoạn một a b c.\n\nĐoạn hai d e."

    pieces = _structured([minutes], word_tokenizer, fallback_max=4)

    assert [p.text for p in pieces] == ["Biên bản họp", "Đoạn một a b", "c.", "Đoạn hai d e."]
    assert all(p.parent_key is None and p.section == "" for p in pieces)


AMENDING_LAW = """Điều 2. Điều khoản thi hành
1. Luật này có hiệu lực từ ngày 01 tháng 3 năm 2027.
2. Sửa đổi khoản 1 và khoản 2 Điều 88 của Luật Xây dựng như sau:
“1. Cá nhân đảm nhận chức danh phải có chứng chỉ.
2. Tổ chức tham gia hoạt động xây dựng phải có năng lực.
Điều 89. Điều kiện của tổ chức.”.
3. Bãi bỏ điểm a khoản 1 Điều 90 của Luật Xây dựng."""


def test_text_an_amending_law_quotes_opens_no_article_or_clause(word_tokenizer):
    pieces = _structured([AMENDING_LAW], word_tokenizer)

    assert [p.section for p in pieces] == [f"Điều 2. Điều khoản thi hành › Khoản {n}" for n in (1, 2, 3)]
    assert pieces[1].text.endswith("Điều 89. Điều kiện của tổ chức.”.")  # the quote stays inside Khoản 2


def test_a_quote_that_never_closes_quotes_its_own_line_only(word_tokenizer):
    law = "Điều 2. X\n1. a\n2. Sửa đổi như sau:\n“1. b\n3. c"

    assert [p.section for p in _structured([law], word_tokenizer)] == ["Điều 2. X › Khoản 1", "Điều 2. X › Khoản 2",
                                                                       "Điều 2. X › Khoản 3"]


# --- contextual headers (R2) ---

def _words(text):
    return len(text.split())


def test_the_header_names_the_document_and_the_section():
    header = context_header("Luật đầu tư", "24/2026/QH16", "Điều 2. Điều khoản thi hành › Khoản 1", _words, 40)

    assert header == "[Luật đầu tư (24/2026/QH16) › Điều 2. Điều khoản thi hành › Khoản 1]"


def test_a_long_header_trims_title_and_article_name_in_turn_but_keeps_the_numbers():
    title = "Luật sửa đổi, bổ sung một số điều của luật thuế thu nhập cá nhân và luật thuế giá trị gia tăng"
    section = "Điều 1. Sửa đổi, bổ sung khoản 1 Điều 7 của Luật Thuế thu nhập cá nhân › Khoản 1"

    short = context_header(title, "09/2026/QH16", section, _words, 14)
    shorter = context_header(title, "09/2026/QH16", section, _words, 6)

    assert short == "[Luật sửa đổi,… (09/2026/QH16) › Điều 1. Sửa đổi, bổ sung… › Khoản 1]"
    assert shorter == "[Luật… (09/2026/QH16) › Điều 1… › Khoản 1]"


def test_without_document_metadata_the_header_is_the_section_or_nothing():
    assert context_header("", "", "Điều 5. Phạt vi phạm", _words, 40) == "[Điều 5. Phạt vi phạm]"
    assert context_header("", "", "", _words, 40) == ""
