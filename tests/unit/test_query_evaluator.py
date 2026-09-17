"""Phase 5 tests: does the parse tree produce the right doc_id set against
an inverted index — including a negative test confirming phrase matching
really requires ADJACENCY (not just "the words appear in the same
document").
"""

from shardsearch.index import InvertedIndex
from shardsearch.query import collect_terms, evaluate, parse


def _test_index() -> InvertedIndex:
    index = InvertedIndex()
    index.add_document("d01", "kedi köpek ile oynuyor")  # "kedi köpek" adjacent
    index.add_document("d02", "köpek ve kedi parkta yürüyor")  # both present, NOT adjacent
    index.add_document("d03", "balık havuzda yüzüyor")  # neither cat nor dog
    index.add_document("d04", "kedi uyuyor, köpek de uyuyor")  # both present, not adjacent
    index.add_document("d05", "kuş ve kedi köpek üçü de bahçede")  # "kedi köpek" adjacent
    return index


def test_term_returns_matching_documents() -> None:
    index = _test_index()
    assert evaluate(parse("kedi"), index) == {"d01", "d02", "d04", "d05"}


def test_and_takes_the_intersection() -> None:
    index = _test_index()
    # "kedi" and "balık" never co-occur in any document
    assert evaluate(parse("kedi AND balık"), index) == set()
    # "kedi" and "köpek" co-occur in d01, d02, d04, d05
    assert evaluate(parse("kedi AND köpek"), index) == {"d01", "d02", "d04", "d05"}


def test_or_takes_the_union() -> None:
    index = _test_index()
    assert evaluate(parse("balık OR kuş"), index) == {"d03", "d05"}


def test_phrase_only_matches_where_the_words_are_adjacent() -> None:
    index = _test_index()
    # "kedi" and "köpek" co-occur in d01,d02,d04,d05, but are ADJACENT only
    # in d01 and d05. In d02/d04 other words sit between them — phrase
    # matching should filter those out.
    assert evaluate(parse('"kedi köpek"'), index) == {"d01", "d05"}


def test_phrase_returns_empty_if_never_adjacent_anywhere() -> None:
    index = _test_index()
    assert evaluate(parse('"köpek kedi"'), index) == set()


def test_phrase_returns_empty_if_it_contains_an_unknown_word() -> None:
    index = _test_index()
    assert evaluate(parse('"kedi nonexistentword"'), index) == set()


def test_complex_query_with_parentheses() -> None:
    index = _test_index()
    # "kedi köpek" (adjacent) OR balık -> d01, d05, d03
    expected = {"d01", "d05", "d03"}
    assert evaluate(parse('"kedi köpek" OR balık'), index) == expected


def test_and_is_applied_before_or() -> None:
    index = _test_index()
    # "kedi AND köpek OR balık" -> (kedi AND köpek) OR balık
    # kedi AND köpek (intersection, adjacency not required) = {d01,d02,d04,d05}, OR balık {d03}
    expected = {"d01", "d02", "d03", "d04", "d05"}
    assert evaluate(parse("kedi AND köpek OR balık"), index) == expected


def test_collect_terms_single_term() -> None:
    assert collect_terms(parse("kedi")) == ["kedi"]


def test_collect_terms_returns_phrase_words_separately() -> None:
    assert collect_terms(parse('"kedi köpek"')) == ["kedi", "köpek"]


def test_collect_terms_ignores_and_or_distinction() -> None:
    # The AND/OR structure is ignored here — for BM25 scoring, both are
    # treated the same way as "a word that appears in the query".
    assert collect_terms(parse("kedi AND köpek")) == ["kedi", "köpek"]
    assert collect_terms(parse("kedi OR köpek")) == ["kedi", "köpek"]


def test_collect_terms_on_a_complex_tree() -> None:
    expected = ["a", "b", "c", "d", "e", "f"]
    assert collect_terms(parse('a AND b OR "c d" AND (e OR f)')) == expected
