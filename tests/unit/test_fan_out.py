"""Phase 8 tests: fan-out + merge, local IDF deviation, fault tolerance.

`bm25.rank()` is NOT used as the single-node "baseline" for comparison —
that function doesn't know about AND/OR/phrase at all, it tokenizes the
raw query as a bag of words and matches with OR logic (when the boolean
parser was wired into the API, app.py uses parse()+evaluate()+
bm25_score() instead of rank()). The cleanest way to run that same triple
against a single node exactly as distributed_search() does: feed the
single node into distributed_search() as a "shard dict" with just ONE
entry. That way both sides run through the EXACT same code path, the
only difference being the number of shards — a genuine apples-to-apples
comparison.
"""

import asyncio

import pytest

from shardsearch.distributed import distributed_search
from shardsearch.scoring.bm25 import inverse_document_frequency
from shardsearch.sharding import ConsistentHash
from shardsearch.storage import SqliteInvertedIndex

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


def _build_single_node() -> SqliteInvertedIndex:
    index = SqliteInvertedIndex(":memory:")
    for doc_id, text in CORPUS.items():
        index.add_document(doc_id, text)
    return index


def _distribute_evenly_across_shards(shard_ids: list[str]) -> dict[str, SqliteInvertedIndex]:
    ring = ConsistentHash(shard_ids)
    shards = {shard_id: SqliteInvertedIndex(":memory:") for shard_id in shard_ids}
    for doc_id, text in CORPUS.items():
        shards[ring.find_shard(doc_id)].add_document(doc_id, text)
    return shards


@pytest.mark.parametrize(
    "query",
    ["kedi", "kedi OR köpek", "kedi AND köpek", "kuş", "hayvandır", '"bir hayvandır"'],
)
def test_candidate_set_is_identical_to_single_node_under_even_distribution(query: str) -> None:
    """The candidate document SET (which documents match) is independent
    of IDF — evaluate()'s AND/OR/phrase logic only looks at whether and
    where postings exist, it never computes a score. So this equality
    isn't a matter of luck, it follows from the algorithm's structure: it
    should ALWAYS hold. The ORDER can differ — see the separate
    observational test below.
    """
    single_node = {"single": _build_single_node()}
    shards = _distribute_evenly_across_shards(["shard-0", "shard-1", "shard-2"])

    single_node_result = asyncio.run(distributed_search(single_node, query, limit=100))
    distributed_result = asyncio.run(distributed_search(shards, query, limit=100))

    single_node_set = {doc_id for doc_id, _ in single_node_result.results}
    distributed_set = {doc_id for doc_id, _ in distributed_result.results}
    assert distributed_set == single_node_set


def test_local_idf_can_shift_ranking_even_under_even_distribution() -> None:
    """OBSERVATION: even with only a 12-document corpus evenly distributed
    across 3 shards via consistent hashing, ranking can still deviate from
    single-node.

    For "kedi OR köpek": d02 (which only contains "köpek") ranks 2nd on a
    single node, but drops to 4th in the distributed result — because on
    d02's shard, "köpek" looks relatively more "common", so that shard's
    local IDF for it comes out lower. This is exactly what SPEC.md's
    Phase 8 test asks: "are deviations caused by the IDF difference
    explainable". Answer: yes, explainable — but not NONEXISTENT. In
    large, term-balanced corpora this effect is expected to shrink (the
    law of large numbers); in small corpora it shows up more clearly.
    """
    query = "kedi OR köpek"
    single_node = {"single": _build_single_node()}
    shards = _distribute_evenly_across_shards(["shard-0", "shard-1", "shard-2"])

    single_node_order = [
        d for d, _ in asyncio.run(distributed_search(single_node, query, limit=100)).results
    ]
    distributed_order = [
        d for d, _ in asyncio.run(distributed_search(shards, query, limit=100)).results
    ]

    assert single_node_order != distributed_order, (
        "expected deviation was not observed in this corpus"
    )
    assert single_node_order.index("d02") < distributed_order.index("d02")


def test_local_idf_deviation_is_much_larger_under_uneven_distribution() -> None:
    """A DELIBERATELY uneven scenario: the word "nadir" ("rare") appears in
    only 2 of 20 documents total (genuinely rare globally, deserving a
    high IDF). But instead of leaving these 2 documents to consistent
    hashing, we DELIBERATELY place them together on a tiny shard by
    themselves — on that shard, "nadir" appears in 100% of documents, so
    its local IDF drops to nearly zero. This is a much larger and fully
    PREDICTABLE deviation compared to the small one seen above under even
    distribution: the more imbalanced the distribution (the smaller the
    shard a term is concentrated on), the larger the deviation.
    """
    single_node = SqliteInvertedIndex(":memory:")
    rare_shard = SqliteInvertedIndex(":memory:")  # ONLY the 2 documents containing "nadir"
    other_shard = SqliteInvertedIndex(":memory:")  # the other 18 documents, no "nadir" at all

    for doc_id, text in [("r1", "nadir kelime burada"), ("r2", "nadir kelime burada da")]:
        single_node.add_document(doc_id, text)
        rare_shard.add_document(doc_id, text)

    for i in range(18):
        doc_id, text = f"n{i}", "alakasız sıradan bir cümle burada"
        single_node.add_document(doc_id, text)
        other_shard.add_document(doc_id, text)

    global_idf = inverse_document_frequency(single_node, "nadir")
    local_idf = inverse_document_frequency(rare_shard, "nadir")

    # globally "nadir" is in 2/20 documents -> high IDF; on rare_shard it's
    # 2/2 -> close to the lowest possible IDF. The deviation should be at
    # least 5x.
    assert local_idf < global_idf * 0.2, (
        f"expected large deviation was not observed: global={global_idf:.3f} local={local_idf:.3f}"
    )


def test_a_failed_shard_still_returns_partial_results_from_the_rest() -> None:
    healthy_shard = SqliteInvertedIndex(":memory:")
    healthy_shard.add_document("d01", "kedi masada uyuyor")
    healthy_shard.add_document("d02", "kedi bahçede oynuyor")

    broken_shard = SqliteInvertedIndex(":memory:")
    broken_shard.add_document("d03", "kedi çatıda geziniyor")
    broken_shard.close()  # guarantees an error is raised during the query

    shards = {"healthy": healthy_shard, "broken": broken_shard}
    result = asyncio.run(distributed_search(shards, "kedi", limit=10))

    assert result.failed_shards == ["broken"]

    # d03 (the ONLY document on the broken shard) never appears in the
    # result — but this isn't a SILENT data loss: failed_shards explicitly
    # reports which shard couldn't answer. The client isn't left wondering
    # "why are there fewer results", it knows exactly which shard failed.
    doc_ids = {doc_id for doc_id, _ in result.results}
    assert doc_ids == {"d01", "d02"}
    assert "d03" not in doc_ids


def test_if_all_shards_fail_the_result_is_empty_and_all_shards_are_reported() -> None:
    broken_1 = SqliteInvertedIndex(":memory:")
    broken_1.close()
    broken_2 = SqliteInvertedIndex(":memory:")
    broken_2.close()

    result = asyncio.run(distributed_search({"s1": broken_1, "s2": broken_2}, "kedi", limit=10))

    assert result.results == []
    assert set(result.failed_shards) == {"s1", "s2"}
