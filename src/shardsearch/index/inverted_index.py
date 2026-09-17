"""In-memory inverted index.

Postings lists are always kept SORTED by doc_id (new entries are placed
at the right position with bisect on insert). The reason isn't needed by
this phase itself, but by later ones: the AND intersection in the query
evaluator and the distributed result merge both assume two sorted lists
can be intersected/merged in O(n). Guaranteeing the order at insert time
means those later stages can rely on "already sorted" without re-checking.

add_document() is an upsert: calling it again with the same doc_id
removes every previous posting for that document and re-indexes the text
from scratch, so an updated document's old and new content never mix.

Document lengths and the running total length (needed for BM25's average
document length) are updated incrementally on every add/remove —
average_document_length() is a single O(1) division instead of scanning
every document on each call.
"""

import bisect

from shardsearch.index.postings import Posting
from shardsearch.tokenizer import tokenize


class InvertedIndex:
    def __init__(self) -> None:
        self._index: dict[str, list[Posting]] = {}
        # Tracks which tokens a document has postings for, so upsert can
        # remove them without scanning the whole index for every token.
        self._document_tokens: dict[str, set[str]] = {}
        self._document_lengths: dict[str, int] = {}
        self._document_texts: dict[str, str] = {}
        self._total_document_length: int = 0

    def add_document(self, doc_id: str, text: str) -> None:
        if doc_id in self._document_tokens:
            self._remove_document(doc_id)

        tokens = tokenize(text)
        positions_by_token: dict[str, list[int]] = {}
        for position, token in enumerate(tokens):
            positions_by_token.setdefault(token, []).append(position)

        self._document_tokens[doc_id] = set(positions_by_token.keys())
        self._document_lengths[doc_id] = len(tokens)
        self._document_texts[doc_id] = text
        self._total_document_length += len(tokens)
        for token, positions in positions_by_token.items():
            postings = self._index.setdefault(token, [])
            new_posting = Posting(doc_id, len(positions), positions)
            idx = bisect.bisect_left(postings, doc_id, key=lambda p: p.doc_id)
            postings.insert(idx, new_posting)

    def _remove_document(self, doc_id: str) -> None:
        for token in self._document_tokens[doc_id]:
            postings = [p for p in self._index[token] if p.doc_id != doc_id]
            if postings:
                self._index[token] = postings
            else:
                del self._index[token]
        del self._document_tokens[doc_id]
        self._total_document_length -= self._document_lengths.pop(doc_id)
        del self._document_texts[doc_id]

    def get_postings(self, token: str) -> list[Posting]:
        return self._index.get(token, [])

    def document_count(self) -> int:
        return len(self._document_tokens)

    def document_length(self, doc_id: str) -> int:
        return self._document_lengths[doc_id]

    def document_text(self, doc_id: str) -> str:
        return self._document_texts[doc_id]

    def average_document_length(self) -> float:
        if not self._document_tokens:
            return 0.0
        return self._total_document_length / len(self._document_tokens)
