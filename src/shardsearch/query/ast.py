"""Nodes of the query parse tree.

No common base class is defined — the four node types are independent
`dataclass`es, distinguished with `isinstance` in evaluator.py. There is
no shared behavior across the four that would justify an abstraction.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Term:
    word: str


@dataclass(frozen=True)
class Phrase:
    words: tuple[str, ...]


@dataclass(frozen=True)
class And:
    left: "QueryNode"
    right: "QueryNode"


@dataclass(frozen=True)
class Or:
    left: "QueryNode"
    right: "QueryNode"


QueryNode = Term | Phrase | And | Or
