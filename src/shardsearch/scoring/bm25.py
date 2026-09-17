"""BM25 ranking algorithm — implemented from scratch.

Each piece of the formula (TF, IDF, length normalization, per-term score)
is kept as its own function so each can be tested independently.

The classic Robertson-Sparck Jones IDF formula (ln((N-n+0.5)/(n+0.5)))
can produce a negative value when a term appears in more than half the
documents; the `rank_bm25` library patches this after the fact with an
epsilon. We instead use the ln(1 + (N-n+0.5)/(n+0.5)) variant, which is
positive by construction. Because of this, the comparison in
tests/validation/ checks RANKING consistency rather than exact numeric
score equality (see the note in that file).
"""

import math

from shardsearch.index import InvertedIndex
from shardsearch.tokenizer import tokenize

DEFAULT_K1 = 1.5
DEFAULT_B = 0.75


def term_frequency(index: InvertedIndex, token: str, doc_id: str) -> int:
    for posting in index.get_postings(token):
        if posting.doc_id == doc_id:
            return posting.frequency
    return 0


def inverse_document_frequency(index: InvertedIndex, token: str) -> float:
    n = len(index.get_postings(token))
    N = index.document_count()
    return math.log(1 + (N - n + 0.5) / (n + 0.5))


def length_normalization(
    document_length: int, average_document_length: float, b: float = DEFAULT_B
) -> float:
    if average_document_length == 0:
        return 1 - b
    return 1 - b + b * (document_length / average_document_length)


def bm25_term_score(tf: int, idf: float, norm: float, k1: float = DEFAULT_K1) -> float:
    return idf * (tf * (k1 + 1)) / (tf + k1 * norm)


def bm25_score(
    index: InvertedIndex,
    query_tokens: list[str],
    doc_id: str,
    k1: float = DEFAULT_K1,
    b: float = DEFAULT_B,
) -> float:
    norm = length_normalization(
        index.document_length(doc_id), index.average_document_length(), b
    )

    total = 0.0
    for token in query_tokens:
        tf = term_frequency(index, token, doc_id)
        if tf == 0:
            continue
        idf = inverse_document_frequency(index, token)
        total += bm25_term_score(tf, idf, norm, k1)
    return total


def rank(
    index: InvertedIndex, query: str, k1: float = DEFAULT_K1, b: float = DEFAULT_B
) -> list[tuple[str, float]]:
    """Returns documents that share at least one token with the query,
    sorted by BM25 score in descending order. Documents that contain none
    of the query tokens have a score of zero and never enter the list.

    Documents with equal scores come back sorted by doc_id ascending.
    Candidates are collected from a `set`, whose natural iteration order
    is undefined — without a secondary sort key, ties would come out in
    an arbitrary (and run-to-run unpredictable) hash order.
    """
    query_tokens = tokenize(query)

    relevant_docs: set[str] = set()
    for token in query_tokens:
        for posting in index.get_postings(token):
            relevant_docs.add(posting.doc_id)

    scores = [
        (doc_id, bm25_score(index, query_tokens, doc_id, k1, b)) for doc_id in relevant_docs
    ]
    scores.sort(key=lambda pair: (-pair[1], pair[0]))
    return scores
