"""Recursive-descent parser turning a boolean query string into a parse tree.

Grammar (precedence encoded outside-in, lowest first):

    query := or_expr
    or_expr  := and_expr (OR and_expr)*   # binds looser than AND
    and_expr := term (AND term)*          # binds tighter than OR
    term     := WORD | "PHRASE" | ( query )

AND binding tighter than OR is a deliberate choice: it matches SQL,
Lucene/Elasticsearch's classic syntax, and and/or precedence in
programming languages generally. "a AND b OR c" is therefore parsed as
"(a AND b) OR c".

Implicit juxtaposition ("cat dog", no AND/OR between them) is
deliberately NOT supported — rather than assume an implicit operator, a
QueryError is raised (see docs/known-limitations.md).
"""

import re

from shardsearch.query.ast import And, Or, Phrase, QueryNode, Term
from shardsearch.tokenizer import tokenize

_TOKEN_REGEX = re.compile(r'"[^"]*"|[()]|[^\s()]+')


class QueryError(Exception):
    pass


def _tokenize_query(query_text: str) -> list[tuple[str, str]]:
    """Splits the raw query string into (kind, value) pairs.

    kind is one of: PHRASE, LPAREN, RPAREN, AND, OR, WORD. AND/OR are
    recognized case-insensitively (the user may also type "and"/"or");
    WORD and PHRASE content is not normalized here, that's left to
    _term() in the parser.
    """
    tokens: list[tuple[str, str]] = []
    for part in _TOKEN_REGEX.findall(query_text):
        if part.startswith('"'):
            tokens.append(("PHRASE", part[1:-1]))
        elif part == "(":
            tokens.append(("LPAREN", part))
        elif part == ")":
            tokens.append(("RPAREN", part))
        elif part.upper() == "AND":
            tokens.append(("AND", part))
        elif part.upper() == "OR":
            tokens.append(("OR", part))
        else:
            tokens.append(("WORD", part))
    return tokens


class _QueryParser:
    def __init__(self, tokens: list[tuple[str, str]]) -> None:
        self._tokens = tokens
        self._pos = 0

    def _current(self) -> tuple[str, str] | None:
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return None

    def _advance(self) -> tuple[str, str]:
        token = self._current()
        if token is None:
            raise QueryError("Query ended earlier than expected")
        self._pos += 1
        return token

    def parse(self) -> QueryNode:
        if self._current() is None:
            raise QueryError("Empty query")
        node = self._or_expr()
        if self._current() is not None:
            raise QueryError(
                f"Unexpected token, likely two terms written next to each other "
                f"without AND/OR between them: {self._current()}"
            )
        return node

    def _or_expr(self) -> QueryNode:
        left = self._and_expr()
        while self._current() is not None and self._current()[0] == "OR":
            self._advance()
            right = self._and_expr()
            left = Or(left, right)
        return left

    def _and_expr(self) -> QueryNode:
        left = self._term()
        while self._current() is not None and self._current()[0] == "AND":
            self._advance()
            right = self._term()
            left = And(left, right)
        return left

    def _term(self) -> QueryNode:
        token = self._current()
        if token is None:
            raise QueryError("Query ended while expecting a term")
        kind, value = token

        if kind == "LPAREN":
            self._advance()
            node = self._or_expr()
            closing = self._current()
            if closing is None or closing[0] != "RPAREN":
                raise QueryError("Expected a closing parenthesis ')'")
            self._advance()
            return node

        if kind == "PHRASE":
            self._advance()
            return Phrase(tuple(tokenize(value)))

        if kind == "WORD":
            self._advance()
            words = tokenize(value)
            return Term(words[0] if words else "")

        raise QueryError(f"Unexpected token while expecting a term: {token}")


def parse(query_text: str) -> QueryNode:
    return _QueryParser(_tokenize_query(query_text)).parse()
