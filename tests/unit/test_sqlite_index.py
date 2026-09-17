"""Phase 4 tests: does SqliteInvertedIndex replicate InvertedIndex's
behavior on top of SQLite — and the key DoD: does data survive a
connection close and reopen, coming back from disk rather than memory.

Behavioral tests (postings, upsert, unknown token, stats) use the same
corpus/expectations as the InvertedIndex tests, to show both backends
genuinely honor the same contract.
"""

import pytest

from shardsearch.index import Posting
from shardsearch.storage import SqliteInvertedIndex


def _in_memory_index() -> SqliteInvertedIndex:
    return SqliteInvertedIndex(":memory:")


def test_postings_are_correct_and_sorted_by_doc_id() -> None:
    index = _in_memory_index()
    index.add_document("d01", "Kedi masada uyuyor, sonra kedi yere atladı.")
    index.add_document("d03", "Kedi ve köpek birlikte oynuyor.")
    index.add_document("d07", "Bugün sokakta bir kedi gördüm, kedi çok sevimliydi.")
    index.add_document("d10", "Kedi ve kuş bazen dost olabilir.")
    index.add_document("d02", "Köpek bahçede koşuyor.")  # doesn't contain "kedi", just noise

    assert index.get_postings("kedi") == [
        Posting("d01", 2, [0, 4]),
        Posting("d03", 1, [0]),
        Posting("d07", 2, [3, 5]),
        Posting("d10", 1, [0]),
    ]


def test_unknown_token_returns_empty_list() -> None:
    index = _in_memory_index()
    index.add_document("d01", "Kedi masada uyuyor.")
    assert index.get_postings("no_such_word") == []


def test_readding_the_same_doc_id_performs_an_upsert() -> None:
    index = _in_memory_index()
    index.add_document("up1", "Kedi köpek kuş.")

    assert index.get_postings("kedi") == [Posting("up1", 1, [0])]
    assert index.get_postings("köpek") == [Posting("up1", 1, [1])]

    index.add_document("up1", "Kuş ve balık.")

    assert index.get_postings("kedi") == []
    assert index.get_postings("köpek") == []
    assert index.get_postings("kuş") == [Posting("up1", 1, [0])]
    assert index.get_postings("balık") == [Posting("up1", 1, [2])]


def test_document_count_and_length_stats() -> None:
    index = _in_memory_index()
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

    index.add_document("y", "köpek")  # 2 tokens -> 1 token
    assert index.document_count() == 3
    assert index.document_length("y") == 1
    assert index.average_document_length() == pytest.approx(9 / 3)


def test_length_of_nonexistent_document_raises_keyerror() -> None:
    index = _in_memory_index()
    with pytest.raises(KeyError):
        index.document_length("nonexistent_doc")


def test_text_of_nonexistent_document_raises_keyerror() -> None:
    index = _in_memory_index()
    with pytest.raises(KeyError):
        index.document_text("nonexistent_doc")


def test_document_text_is_stored_and_updated_on_upsert() -> None:
    index = _in_memory_index()
    index.add_document("d01", "Kedi masada uyuyor.")
    assert index.document_text("d01") == "Kedi masada uyuyor."

    index.add_document("d01", "Köpek bahçede koşuyor.")
    assert index.document_text("d01") == "Köpek bahçede koşuyor."


def test_disk_persistence_survives_a_restart_loading_from_disk_not_memory(tmp_path) -> None:
    db_path = tmp_path / "test_index.db"

    # The "application" starts for the first time, indexes documents, then shuts down.
    first_run = SqliteInvertedIndex(db_path)
    first_run.add_document("d01", "Kedi masada uyuyor, sonra kedi yere atladı.")
    first_run.add_document("d02", "Köpek bahçede koşuyor.")
    first_run.add_document("d03", "Kedi ve köpek birlikte oynuyor.")
    first_run.close()

    # The "application" restarts — a NEW SqliteInvertedIndex object opens
    # the same file. add_document() is NOT called again: if the data is
    # genuinely coming from disk, the postings should be correct here too.
    second_run = SqliteInvertedIndex(db_path)

    assert second_run.get_postings("kedi") == [
        Posting("d01", 2, [0, 4]),
        Posting("d03", 1, [0]),
    ]
    assert second_run.document_count() == 3
    assert second_run.document_length("d02") == 3
    assert second_run.average_document_length() == pytest.approx((7 + 3 + 5) / 3)

    second_run.close()
