"""Phase 5 tests: does a query string parse into the right tree.

Precedence rule: AND binds tighter than OR — "a AND b OR c" must always
be "(a AND b) OR c", NOT "a AND (b OR c)". This is consistent with
SQL/general programming language convention and the least surprising
choice for users.
"""

import pytest

from shardsearch.query import And, Or, Phrase, QueryError, Term, parse


def test_single_term() -> None:
    assert parse("kedi") == Term("kedi")


def test_and_expression() -> None:
    assert parse("kedi AND köpek") == And(Term("kedi"), Term("köpek"))


def test_or_expression() -> None:
    assert parse("kedi OR köpek") == Or(Term("kedi"), Term("köpek"))


def test_and_or_also_work_lowercase() -> None:
    assert parse("kedi and köpek") == And(Term("kedi"), Term("köpek"))
    assert parse("kedi or köpek") == Or(Term("kedi"), Term("köpek"))


def test_and_is_evaluated_before_or() -> None:
    # "a AND b OR c" -> "(a AND b) OR c" — AND binds tighter.
    expected = Or(And(Term("a"), Term("b")), Term("c"))
    assert parse("a AND b OR c") == expected


def test_precedence_holds_from_the_other_side_too() -> None:
    # "a OR b AND c" -> "a OR (b AND c)" — the symmetric result of the same rule.
    expected = Or(Term("a"), And(Term("b"), Term("c")))
    assert parse("a OR b AND c") == expected


def test_parentheses_can_override_precedence() -> None:
    expected = And(Term("a"), Or(Term("b"), Term("c")))
    assert parse("a AND (b OR c)") == expected


def test_nested_parentheses() -> None:
    expected = Or(And(Term("a"), Term("b")), And(Term("c"), Term("d")))
    assert parse("(a AND b) OR (c AND d)") == expected


def test_phrase_parsing() -> None:
    assert parse('"kedi köpek"') == Phrase(("kedi", "köpek"))


def test_phrase_content_is_normalized_turkish() -> None:
    # Phrase content also goes through tokenize(): the Turkish İ/ı and punctuation rules apply
    assert parse('"İstanbul, Ankara"') == Phrase(("istanbul", "ankara"))


def test_phrase_and_term_together() -> None:
    expected = And(Phrase(("kedi", "köpek")), Term("balık"))
    assert parse('"kedi köpek" AND balık') == expected


def test_term_content_is_normalized_turkish() -> None:
    assert parse("İSTANBUL") == Term("istanbul")


def test_complex_query() -> None:
    # "a AND b OR "c d" AND (e OR f)"
    # -> (a AND b) OR ("c d" AND (e OR f))
    expected = Or(
        And(Term("a"), Term("b")),
        And(Phrase(("c", "d")), Or(Term("e"), Term("f"))),
    )
    assert parse('a AND b OR "c d" AND (e OR f)') == expected


@pytest.mark.parametrize(
    "query",
    [
        "kedi köpek",  # implicit juxtaposition with no operator — deliberately unsupported
        "kedi AND",  # missing second term
        "AND kedi",  # missing first term
        "(kedi AND köpek",  # unclosed parenthesis
        "kedi AND köpek)",  # extra closing parenthesis
        "",  # empty query
        "   ",  # whitespace only
    ],
)
def test_invalid_queries_raise_an_error(query: str) -> None:
    with pytest.raises(QueryError):
        parse(query)
