"""Context assembly: children → parents within the token budget (SAD 6.7)."""

from core.context import assemble
from core.models import Chunk, RetrievedChunk


def _words(text: str) -> int:
    return len(text.split())


def _hit(chunk_id, index, text, parent=None, parent_text="", section="", doc="d"):
    return RetrievedChunk(Chunk(chunk_id, doc, "law.pdf", 6, index, text, section, parent, parent_text), 0.9)


ARTICLE_8 = "Điều 8. Các hành vi bị nghiêm cấm 1. Phá hoại 8. Lái xe có cồn"


def test_children_of_one_parent_become_one_source_in_document_order():
    k8 = _hit("k8", 5, "8. Lái xe có cồn", "p8", ARTICLE_8, "Điều 8. Các hành vi bị nghiêm cấm › Khoản 8")
    other = _hit("x", 2, "Điều 3. Giải thích từ ngữ")  # no parent: stays as it is
    k1 = _hit("k1", 4, "1. Phá hoại", "p8", ARTICLE_8, "Điều 8. Các hành vi bị nghiêm cấm › Khoản 1")

    sources = assemble([k8, other, k1], budget=100, count_tokens=_words)

    assert [s.chunk.chunk_id for s in sources] == ["x", "k8"]  # by position; k1 merged into k8's parent
    article = sources[1].chunk
    assert article.text == ARTICLE_8
    assert article.section == "Điều 8. Các hành vi bị nghiêm cấm"
    assert (article.page, sources[1].score) == (6, 0.9)  # of the best-ranked child


def test_parents_that_do_not_fit_leave_their_child_and_smaller_ones_still_expand():
    big = _hit("a", 1, "a a", "pa", "A " * 20)
    small = _hit("b", 2, "b b", "pb", "B B B B")
    low = _hit("c", 3, "c c", "pc", "C C C C")

    sources = assemble([big, small, low], budget=9, count_tokens=_words)

    # 6 words of children; "a" would need 24 → child; "b" → 8; "c" would need 10 → child
    assert [s.chunk.text for s in sources] == ["a a", "B B B B", "c c"]


def test_documents_come_in_order_of_their_best_hit():
    hits = [_hit("b2", 9, "x", doc="b"), _hit("a1", 1, "y", doc="a"), _hit("b1", 3, "z", doc="b")]

    sources = assemble(hits, budget=100, count_tokens=_words)

    assert [s.chunk.chunk_id for s in sources] == ["b1", "b2", "a1"]
