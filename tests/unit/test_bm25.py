"""Phase 3 tests: each piece of the BM25 formula is verified independently.

Expected values are computed by hand here (re-deriving the formula
directly with math.log) rather than by calling the functions in
src/scoring/bm25.py — no self-referential (tautological) verification.
"""

import math

import pytest

from shardsearch.index import InvertedIndex
from shardsearch.scoring.bm25 import (
    bm25_score,
    bm25_term_score,
    inverse_document_frequency,
    length_normalization,
    rank,
    term_frequency,
)


def _test_index() -> InvertedIndex:
    # a: 4 tokens, b: 3 tokens, c: 5 tokens -> total 12, average 4.0
    index = InvertedIndex()
    index.add_document("a", "kedi kedi köpek hayvan")
    index.add_document("b", "köpek kuş hayvan")
    index.add_document("c", "kedi kuş balık balık hayvan")
    return index


@pytest.mark.parametrize(
    ("token", "doc_id", "expected"),
    [
        ("kedi", "a", 2),
        ("kedi", "b", 0),
        ("kedi", "c", 1),
        ("balık", "c", 2),
        ("hayvan", "a", 1),
        ("nonexistentword", "a", 0),
    ],
)
def test_term_frequency(token: str, doc_id: str, expected: int) -> None:
    assert term_frequency(_test_index(), token, doc_id) == expected


@pytest.mark.parametrize(
    ("token", "expected_n"),
    [
        ("kedi", 2),  # a, c
        ("köpek", 2),  # a, b
        ("kuş", 2),  # b, c
        ("balık", 1),  # only c
        ("hayvan", 3),  # a, b, c
        ("nonexistentword", 0),  # not in any document
    ],
)
def test_inverse_document_frequency(token: str, expected_n: int) -> None:
    N = 3
    expected = math.log(1 + (N - expected_n + 0.5) / (expected_n + 0.5))
    assert inverse_document_frequency(_test_index(), token) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("length", "average", "b", "expected"),
    [
        (4, 4.0, 0.75, 1.0),
        (3, 4.0, 0.75, 0.8125),
        (5, 4.0, 0.75, 1.1875),
        (0, 0.0, 0.75, 0.25),  # should return 1-b instead of ZeroDivisionError when average is zero
    ],
)
def test_length_normalization(length: int, average: float, b: float, expected: float) -> None:
    assert length_normalization(length, average, b) == pytest.approx(expected)


def test_bm25_term_score() -> None:
    # idf * (tf * (k1+1)) / (tf + k1*norm) = 0.5 * (2*2.5) / (2 + 1.5*1.0)
    assert bm25_term_score(tf=2, idf=0.5, norm=1.0, k1=1.5) == pytest.approx(2.5 / 3.5)


def test_bm25_score_sums_across_multiple_terms() -> None:
    index = _test_index()
    N = 3
    idf_kedi = math.log(1 + (N - 2 + 0.5) / (2 + 0.5))
    idf_hayvan = math.log(1 + (N - 3 + 0.5) / (3 + 0.5))
    norm_a = 1 - 0.75 + 0.75 * (4 / 4.0)  # a's length (4) equals the average (4.0) -> 1.0

    expected = idf_kedi * (2 * 2.5) / (2 + 1.5 * norm_a) + idf_hayvan * (1 * 2.5) / (
        1 + 1.5 * norm_a
    )

    assert bm25_score(index, ["kedi", "hayvan"], "a") == pytest.approx(expected)


def test_bm25_score_is_zero_with_no_shared_token() -> None:
    index = _test_index()
    assert bm25_score(index, ["nonexistentword"], "a") == 0.0


def test_rank_returns_only_relevant_documents_in_the_right_order() -> None:
    index = _test_index()

    score_a = bm25_score(index, ["kedi"], "a")
    score_c = bm25_score(index, ["kedi"], "c")
    expected_order = sorted(
        [("a", score_a), ("c", score_c)], key=lambda pair: pair[1], reverse=True
    )

    result = rank(index, "kedi")

    # "b" never contains "kedi", it should never appear in the result
    assert [doc_id for doc_id, _ in result] == [doc_id for doc_id, _ in expected_order]
    assert [score for _, score in result] == pytest.approx([score for _, score in expected_order])


def test_rank_returns_empty_list_with_no_matches() -> None:
    index = _test_index()
    assert rank(index, "nonexistentword") == []
