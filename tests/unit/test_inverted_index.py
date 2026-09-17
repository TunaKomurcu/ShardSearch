"""Phase 2 tests: does InvertedIndex produce correct postings.

Expected frequency/position values were computed by hand by walking
through tokenize()'s output for each document.
"""

import pytest

from shardsearch.index import InvertedIndex, Posting

# A small 12-document test corpus. "cat" ("kedi") was deliberately chosen
# to appear in different documents with different frequencies/positions;
# the rest exist to add noise to the postings list.
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

# Hand-computed expected postings for "kedi" ("cat"), sorted by doc_id.
EXPECTED_KEDI_POSTINGS = [
    Posting("d01", 2, [0, 4]),
    Posting("d03", 1, [0]),
    Posting("d07", 2, [3, 5]),
    Posting("d10", 1, [0]),
]


def _build_index(ordered_doc_ids: list[str]) -> InvertedIndex:
    index = InvertedIndex()
    for doc_id in ordered_doc_ids:
        index.add_document(doc_id, CORPUS[doc_id])
    return index


def test_known_word_postings_are_correct() -> None:
    index = _build_index(list(CORPUS))
    assert index.get_postings("kedi") == EXPECTED_KEDI_POSTINGS


def test_postings_stay_sorted_regardless_of_insertion_order() -> None:
    # d07, d01, d10, d03 are added in this order but postings must always
    # be sorted by doc_id — the sorted-merge assumption used later in the
    # query evaluator and distributed search relies on this.
    shuffled_order = [
        "d07", "d02", "d01", "d10", "d05", "d03", "d04", "d06", "d08", "d09", "d11", "d12",
    ]
    index = _build_index(shuffled_order)
    assert index.get_postings("kedi") == EXPECTED_KEDI_POSTINGS


def test_unknown_token_returns_empty_list() -> None:
    index = _build_index(list(CORPUS))
    assert index.get_postings("no_such_word") == []


def test_readding_the_same_doc_id_performs_an_upsert() -> None:
    index = InvertedIndex()
    index.add_document("up1", "Kedi köpek kuş.")

    # In its first version, all three tokens should have a posting for up1
    assert index.get_postings("kedi") == [Posting("up1", 1, [0])]
    assert index.get_postings("köpek") == [Posting("up1", 1, [1])]
    assert index.get_postings("kuş") == [Posting("up1", 1, [2])]

    # Re-adding with the same doc_id must fully remove the old content
    index.add_document("up1", "Kuş ve balık.")

    # Tokens that were in the old content but not the new one should lose up1 entirely
    assert index.get_postings("kedi") == []
    assert index.get_postings("köpek") == []

    # Tokens from the new content should appear with updated positions
    assert index.get_postings("kuş") == [Posting("up1", 1, [0])]
    assert index.get_postings("balık") == [Posting("up1", 1, [2])]


def test_document_count_and_length_stats() -> None:
    index = InvertedIndex()
    assert index.document_count() == 0
    assert index.average_document_length() == 0.0

    index.add_document("x", "kedi kedi köpek")  # 3 tokens
    index.add_document("y", "köpek kuş")  # 2 tokens
    index.add_document("z", "kedi kuş balık balık hayvan")  # 5 tokens

    assert index.document_count() == 3
    assert index.document_length("x") == 3
    assert index.document_length("y") == 2
    assert index.document_length("z") == 5
    assert index.average_document_length() == pytest.approx(10 / 3)

    # After an upsert, stats should update and the old length subtracted from the total
    index.add_document("y", "köpek")  # 2 tokens -> 1 token
    assert index.document_count() == 3
    assert index.document_length("y") == 1
    assert index.average_document_length() == pytest.approx(9 / 3)


def test_document_text_is_stored_and_updated_on_upsert() -> None:
    index = InvertedIndex()
    index.add_document("d01", "Kedi masada uyuyor.")
    assert index.document_text("d01") == "Kedi masada uyuyor."

    index.add_document("d01", "Köpek bahçede koşuyor.")
    assert index.document_text("d01") == "Köpek bahçede koşuyor."
