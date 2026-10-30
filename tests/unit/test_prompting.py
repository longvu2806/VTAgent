from core.models import Chunk, RetrievedChunk
from core.prompting import NOT_FOUND, SYSTEM_PROMPTS, build_messages, extract_citations


def _source(i: int, page: int | None = None) -> RetrievedChunk:
    return RetrievedChunk(Chunk(f"id{i}", "doc", "hd.pdf", page, i, f"text {i}"), score=1.0)


SOURCES = [_source(1, page=3), _source(2), _source(3)]


def test_sources_are_labelled_in_order_with_page():
    (_, system), (_, human) = build_messages("Q?", SOURCES)
    assert NOT_FOUND in system
    assert human.index("[S1] hd.pdf · page 3\ntext 1") < human.index("[S2] hd.pdf\ntext 2") < human.index("[S3]")
    assert human.endswith("Question: Q?")


def test_the_given_system_prompt_is_used_and_v1_is_the_default():
    assert build_messages("Q?", SOURCES)[0] == ("system", SYSTEM_PROMPTS["v1"])
    assert build_messages("Q?", SOURCES, SYSTEM_PROMPTS["v2"])[0] == ("system", SYSTEM_PROMPTS["v2"])
    assert all(NOT_FOUND in prompt for prompt in SYSTEM_PROMPTS.values())  # the refusal must stay verbatim


def test_citations_follow_first_appearance():
    cited = extract_citations("A [S2]. B [S1][S2]. C [S3].", SOURCES)
    assert [c.label for c in cited] == ["S2", "S1", "S3"]
    assert cited[0].chunk is SOURCES[1].chunk


def test_unknown_labels_are_dropped():
    cited = extract_citations("X [S4] [S0] [S1].", SOURCES)
    assert [c.label for c in cited] == ["S1"]


def test_comma_separated_labels():
    cited = extract_citations("X [S1, S3].", SOURCES)
    assert [c.label for c in cited] == ["S1", "S3"]


def test_refusal_has_no_citations():
    assert extract_citations(NOT_FOUND, SOURCES) == []
