"""Consistent hashing for document -> shard assignment.

The ring: for each shard, `virtual_node_count` virtual points are hashed
and placed onto a ring (a list of hash values kept sorted). A key's
(doc_id's) shard is the one owned by the first virtual node encountered
going clockwise from the key's own hash (found in O(log n) via bisect) —
the same sorted-list-plus-bisect pattern used for postings lists.

Why virtual nodes: representing each real shard by a single point on the
ring would mean that, with only 3-5 shards, the random distribution of
hashes lets some shards claim a much bigger "arc" than others, causing
uneven data distribution. Representing each shard by `virtual_node_count`
(default 100) different points lets the law of large numbers pull the
arcs toward balance.

Why hashlib.sha256, NOT Python's built-in hash(): `hash()` on a str is
randomly salted with PYTHONHASHSEED on every process start — the same
doc_id would land on a DIFFERENT shard every time the server restarts.
sha256 is deterministic (same input -> same output, across processes and
machines), so "which shard is document X on" has a stable, reproducible
answer. Cryptographic security doesn't matter here, only good
distribution (the avalanche effect) and determinism — sha256 turns even
sequential-looking IDs (e.g. "doc-1", "doc-2") into unrelated, spread-out
hash values.
"""

import bisect
import hashlib


def _hash(value: str) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest(), 16)


class ConsistentHash:
    def __init__(self, shards: list[str], virtual_node_count: int = 100) -> None:
        self._virtual_node_count = virtual_node_count
        self._ring_values: list[int] = []
        self._ring_shards: list[str] = []
        self._shards: set[str] = set()
        for shard_id in shards:
            self.add_shard(shard_id)

    def add_shard(self, shard_id: str) -> None:
        if shard_id in self._shards:
            return
        self._shards.add(shard_id)
        for i in range(self._virtual_node_count):
            hash_value = _hash(f"{shard_id}#{i}")
            idx = bisect.bisect_left(self._ring_values, hash_value)
            self._ring_values.insert(idx, hash_value)
            self._ring_shards.insert(idx, shard_id)

    def remove_shard(self, shard_id: str) -> None:
        if shard_id not in self._shards:
            return
        self._shards.discard(shard_id)
        remaining = [
            (value, sid)
            for value, sid in zip(self._ring_values, self._ring_shards, strict=True)
            if sid != shard_id
        ]
        self._ring_values = [value for value, _ in remaining]
        self._ring_shards = [sid for _, sid in remaining]

    def find_shard(self, doc_id: str) -> str:
        if not self._ring_values:
            raise ValueError("The ring has no shards")
        hash_value = _hash(doc_id)
        idx = bisect.bisect_left(self._ring_values, hash_value)
        if idx == len(self._ring_values):
            idx = 0  # the ring wraps: past the last node loops back to the first
        return self._ring_shards[idx]
