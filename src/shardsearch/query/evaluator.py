"""Runs a parse tree against an inverted index to produce the set of
matching doc_ids.

The `index` parameter is intentionally duck-typed: both InvertedIndex and
SqliteInvertedIndex expose a `get_postings()` method, so either works
here with no type check needed.
"""

from typing import Protocol

from shardsearch.query.ast import And, Or, Phrase, QueryNode, Term


class _PostingsSource(Protocol):
    def get_postings(self, token: str) -> list: ...


def evaluate(node: QueryNode, index: _PostingsSource) -> set[str]:
    if isinstance(node, Term):
        return {p.doc_id for p in index.get_postings(node.word)}

    if isinstance(node, Phrase):
        return _match_phrase(node, index)

    if isinstance(node, And):
        return evaluate(node.left, index) & evaluate(node.right, index)

    if isinstance(node, Or):
        return evaluate(node.left, index) | evaluate(node.right, index)

    raise TypeError(f"Unknown query node: {node!r}")


def _match_phrase(phrase: Phrase, index: _PostingsSource) -> set[str]:
    words = phrase.words
    if not words:
        return set()

    postings_lists = [index.get_postings(word) for word in words]
    if any(not postings for postings in postings_lists):
        return set()  # if any word never occurs, the phrase can't match either

    # The set of doc_ids each word occurs in — a document must contain
    # ALL the words for the phrase to possibly match (adjacency isn't
    # checked yet, this is just a pre-filter).
    doc_id_sets = [{p.doc_id for p in postings} for postings in postings_lists]
    candidate_docs = set.intersection(*doc_id_sets)

    result: set[str] = set()
    for doc_id in candidate_docs:
        position_sets = [
            set(next(p.positions for p in postings if p.doc_id == doc_id))
            for postings in postings_lists
        ]
        first_word_positions = position_sets[0]
        for start in first_word_positions:
            if all(
                (start + offset) in position_sets[offset] for offset in range(1, len(words))
            ):
                result.add(doc_id)
                break
    return result


def collect_terms(node: QueryNode) -> list[str]:
    """Flattens every Term/Phrase leaf in the AST into a plain word list.

    Acts as the bridge to BM25 scoring: evaluate() only gives us the
    matching doc_id SET (no ranking), while bm25_score() expects a plain
    word list. This function closes that gap.

    The query's AND/OR structure is DELIBERATELY ignored here — only
    which words appear in the query is collected. For example, in
    "cat OR dog" both are included in scoring: a document that only
    contains "cat" gets tf=0 for "dog", and bm25_score() already zeroes
    out that term's contribution — no special-case code needed. The real
    meaning of AND/OR/phrase is already applied by evaluate() when
    deciding "which documents enter the candidate set"; this function
    just produces the word list needed to rank those candidates.
    """
    if isinstance(node, Term):
        return [node.word]
    if isinstance(node, Phrase):
        return list(node.words)
    if isinstance(node, And | Or):
        return collect_terms(node.left) + collect_terms(node.right)
    raise TypeError(f"Unknown query node: {node!r}")
