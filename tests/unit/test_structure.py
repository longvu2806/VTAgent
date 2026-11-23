"""Title and number read from a document's opening lines (SDD 5.4); layouts as the parsers emit them."""

from core.models import PageText
from core.structure import document_label, extract_metadata

DOCX_LAW = """| QUỐC HỘI | CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM Độc lập - Tự do - Hạnh phúc |
| --- | --- |
| Luật số: 24/2026/QH16 |  |

LUẬT

SỬA ĐỔI, BỔ SUNG MỘT SỐ ĐIỀU CỦA LUẬT ĐẦU TƯ

Căn cứ Hiến pháp nước Cộng hòa xã hội chủ nghĩa Việt Nam;

Điều 1. Sửa đổi, bổ sung một số điều của Luật Đầu tư"""

DECREE = """| CHÍNH PHỦ _______  Số: 389/2026/NĐ-CP | CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM |
| --- | --- |

NGHỊ ĐỊNH

Quy định về xử phạt vi phạm hành chính trong lĩnh vực kinh doanh xổ số

Căn cứ Luật Tổ chức Chính phủ số 63/2025/QH15;"""

PDF_LAW = """**QUỐC HỘI CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM** Luật số: 23/2008/QH12 **Độc lập - Tự do - Hạnh phúc**

# **LUẬT**

# **GIAO THÔNG ĐƯỜNG BỘ**

_Căn cứ Hiến pháp nước Cộng hòa xã hội chủ nghĩa Việt Nam năm 1992;_

CHƯƠNG I"""


def _read(text):
    return extract_metadata([PageText(1, text)])


def test_a_law_in_a_docx_table_header():
    assert _read(DOCX_LAW) == ("Luật sửa đổi, bổ sung một số điều của luật đầu tư", "24/2026/QH16")


def test_a_decree_whose_name_line_is_not_upper_case():
    assert _read(DECREE) == ("Nghị định quy định về xử phạt vi phạm hành chính trong lĩnh vực kinh doanh xổ số",
                             "389/2026/NĐ-CP")


def test_a_pdf_law_with_markdown_emphasis():
    assert _read(PDF_LAW) == ("Luật giao thông đường bộ", "23/2008/QH12")


def test_a_document_without_the_legal_layout_gets_empty_fields():
    assert _read("Báo cáo tình hình tháng 5\n\nDoanh thu tăng 10%.") == ("", "")


def test_the_label_names_the_document_by_title_and_number():
    assert document_label("Luật chuyển đổi số", "148/2025/QH15") == "Luật chuyển đổi số (148/2025/QH15)"
    assert document_label("", "148/2025/QH15") == "148/2025/QH15"
    assert document_label("", "") == ""
