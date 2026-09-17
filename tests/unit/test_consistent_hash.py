"""Phase 7 tests: does consistent hashing distribute correctly, and does
resharding move a minimal amount of data.

Synthetic IDs are deliberately generated SEQUENTIALLY ("doc-0", "doc-1",
...) rather than randomly. The goal isn't to hide this but to prove the
opposite: thanks to sha256's avalanche effect, even sequential/patterned
IDs spread out into unrelated hash values. With a weak hash function
(e.g. simple summation), sequential IDs could cluster on the ring and
cause an uneven distribution — this test's real purpose is to show the
choice of sha256 genuinely eliminates that risk.
"""

import pytest

from shardsearch.sharding import ConsistentHash


def _generate_synthetic_ids(count: int) -> list[str]:
    return [f"doc-{i}" for i in range(count)]


def test_the_same_id_always_returns_the_same_shard() -> None:
    ring = ConsistentHash(["shard-0", "shard-1", "shard-2"])
    first_result = ring.find_shard("doc-42")
    for _ in range(10):
        assert ring.find_shard("doc-42") == first_result


def test_returns_a_valid_shard() -> None:
    shards = ["shard-0", "shard-1", "shard-2"]
    ring = ConsistentHash(shards)
    for doc_id in _generate_synthetic_ids(200):
        assert ring.find_shard(doc_id) in shards


def test_an_empty_ring_raises_an_error() -> None:
    ring = ConsistentHash([])
    with pytest.raises(ValueError):
        ring.find_shard("doc-1")


def test_distribution_stats_stay_within_a_reasonable_range() -> None:
    shards = ["shard-0", "shard-1", "shard-2", "shard-3", "shard-4"]
    ring = ConsistentHash(shards, virtual_node_count=100)
    ids = _generate_synthetic_ids(10_000)

    counts: dict[str, int] = dict.fromkeys(shards, 0)
    for doc_id in ids:
        counts[ring.find_shard(doc_id)] += 1

    average = len(ids) / len(shards)
    for shard_id, count in counts.items():
        ratio = count / average
        assert 0.70 <= ratio <= 1.30, f"{shard_id} is unbalanced: {count} docs (ratio={ratio:.2f})"


def test_resharding_only_moves_keys_from_old_shards_to_the_new_one() -> None:
    """The property that sets consistent hashing apart from naive
    hash(id) % N: when a new shard is added, ONLY some keys move from the
    old shards to the NEW shard — there must be NO movement between two
    old shards. Naive mod-N hashing reshuffles nearly every key when a
    shard is added; this test proves that exact failure mode does NOT
    happen here.
    """
    old_shards = ["shard-0", "shard-1", "shard-2"]
    ring = ConsistentHash(old_shards)
    ids = _generate_synthetic_ids(5_000)

    old_assignment = {doc_id: ring.find_shard(doc_id) for doc_id in ids}

    ring.add_shard("shard-3")
    new_assignment = {doc_id: ring.find_shard(doc_id) for doc_id in ids}

    moved = 0
    for doc_id in ids:
        old = old_assignment[doc_id]
        new = new_assignment[doc_id]
        if old != new:
            moved += 1
            # Critical check: movement can ONLY be from an old shard to
            # the NEW shard, never between two old shards.
            assert new == "shard-3", (
                f"{doc_id} moved from an old shard ({old}) to another "
                f"old shard ({new}) — a symptom of naive rehashing"
            )

    # Theoretical expectation: roughly 1/(N+1) = 1/4 = 25% moves to the new shard.
    move_ratio = moved / len(ids)
    assert 0.15 <= move_ratio <= 0.35, f"move ratio is far from expected: {move_ratio:.2%}"


def test_removing_a_shard_only_redistributes_that_shards_data() -> None:
    shards = ["shard-0", "shard-1", "shard-2", "shard-3"]
    ring = ConsistentHash(shards)
    ids = _generate_synthetic_ids(5_000)

    old_assignment = {doc_id: ring.find_shard(doc_id) for doc_id in ids}
    ring.remove_shard("shard-3")
    new_assignment = {doc_id: ring.find_shard(doc_id) for doc_id in ids}

    for doc_id in ids:
        old = old_assignment[doc_id]
        new = new_assignment[doc_id]
        if old != "shard-3":
            # No document outside shard-3 should have moved
            assert new == old, f"{doc_id} moved unnecessarily: {old} -> {new}"
        else:
            # Documents that were on shard-3 must now be on one of the remaining 3 shards
            assert new != "shard-3"


def test_distribution_improves_as_virtual_node_count_grows() -> None:
    shards = ["shard-0", "shard-1", "shard-2"]
    ids = _generate_synthetic_ids(3_000)

    def compute_variance(virtual_node_count: int) -> float:
        ring = ConsistentHash(shards, virtual_node_count=virtual_node_count)
        counts: dict[str, int] = dict.fromkeys(shards, 0)
        for doc_id in ids:
            counts[ring.find_shard(doc_id)] += 1
        average = len(ids) / len(shards)
        return sum((count - average) ** 2 for count in counts.values()) / len(shards)

    # With very few virtual nodes, distribution is mostly luck;
    # 100 should be noticeably more balanced.
    variance_few_nodes = compute_variance(1)
    variance_many_nodes = compute_variance(100)
    assert variance_many_nodes < variance_few_nodes
