"""Phase 3 validation: comparing our BM25 ranking against rank_bm25.

IMPORTANT — what's being compared here is NOT numeric score equality, but
RANKING consistency. Our own inverse_document_frequency() function always
uses the positive-by-construction ln(1 + (N-n+0.5)/(n+0.5)) formula;
rank_bm25's BM25Okapi class uses the classic Robertson-Sparck Jones
formula (ln((N-n+0.5)/(n+0.5))) and patches negative values afterward with
an epsilon (see the note in src/shardsearch/scoring/bm25.py). Because of
this formula difference, absolute scores don't line up — and that's not
what SPEC.md is after anyway: "the top 5 results are in the same order,
or the difference is explainable" (see PHASES.md, Phase 3).

rank_bm25 is used ONLY in this file, as a reference — it never enters
src/ (see test_rank_bm25_isolation.py). If this dependency group isn't
installed (`uv sync --group validation` wasn't run), this test file is
skipped.
"""

import pytest

rank_bm25 = pytest.importorskip("rank_bm25")

from shardsearch.index import InvertedIndex  # noqa: E402
from shardsearch.scoring.bm25 import rank  # noqa: E402
from shardsearch.tokenizer import tokenize  # noqa: E402

# Same 12-document corpus as the inverted index tests — already verified
# by hand there, no need to invent a new one.
CORPUS = {
    "d01": "Kedi masada uyuyor, sonra kedi yere atladı.",
    "d02": "Köpek bahçede koşuyor.",
    "d03": "Kedi ve köpek birlikte oynuyor.",
    "d04": "Kuşlar gökyüzünde uçuyor.",
    "d05": "Balıklar denizde yüzüyor.",
    "d06": "Aslan çok güçlü bir hayvandır.",
    "d07": "Bugün sokakta bir kedi gördüm, kedi çok sevimliydi.",
    "d08": "Fil çok büyük bir hayvandır.",
    "d09": "Kuş kanat çırpıp uçtu.",
    "d10": "Kedi ve kuş bazen dost olabilir.",
    "d11": "Ayı kışın uyur.",
    "d12": "Tilki kurnaz bir hayvandır.",
}


def _our_index() -> InvertedIndex:
    index = InvertedIndex()
    for doc_id, text in CORPUS.items():
        index.add_document(doc_id, text)
    return index


def _rank_bm25_reference() -> tuple[list[str], "rank_bm25.BM25Okapi"]:
    doc_ids = list(CORPUS)
    tokenized = [tokenize(CORPUS[doc_id]) for doc_id in doc_ids]
    return doc_ids, rank_bm25.BM25Okapi(tokenized)


@pytest.mark.parametrize(
    "query",
    ["kedi", "hayvan", "kedi köpek", "kuş", "bir hayvandır"],
)
def test_ranking_is_consistent_with_rank_bm25(query: str) -> None:
    our_result = rank(_our_index(), query)
    our_top_5 = [doc_id for doc_id, _ in our_result[:5]]

    doc_ids, reference = _rank_bm25_reference()
    reference_scores = reference.get_scores(tokenize(query))
    reference_sorted = sorted(
        zip(doc_ids, reference_scores), key=lambda pair: pair[1], reverse=True
    )
    reference_top_5 = [doc_id for doc_id, score in reference_sorted[:5] if score > 0]

    assert our_top_5 == reference_top_5
