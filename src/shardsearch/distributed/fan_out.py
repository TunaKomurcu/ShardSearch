"""Parallel search across multiple shards (fan-out) + result merging.

sqlite3 is a synchronous/blocking library with no native asyncio support.
So each shard query is handed off to a separate thread via
`asyncio.to_thread()` — just writing `async def` and `await` isn't
enough on its own; real parallelism comes from delegating blocking I/O to
a thread pool. Without `asyncio.to_thread()`, `asyncio.gather` would
still query the shards SEQUENTIALLY, because none of them would contain
an `await` point that yields the event loop.

IDF is computed LOCALLY per shard (see shardsearch.scoring.bm25) — the
same default behavior as Elasticsearch, avoiding a second round-trip to
gather global statistics. This can cause small deviations from single-node
results. OBSERVATION (see the deliberately unbalanced distribution test in
tests/unit/test_fan_out.py): the size of the deviation depends on how
balanced the TERM DISTRIBUTION is across shards — if most documents
containing a term happen to land on a single shard (unlikely under normal
consistent-hashing distribution, but possible with small corpora or an
unlucky hash spread), that shard's local N is small, so the term's local
IDF diverges noticeably from the global IDF. This effect shrinks in
large, term-balanced corpora (the law of large numbers).

Fault tolerance: if a shard errors out during a query (connection issue,
etc.) the ENTIRE search does not fail — that shard's documents drop out
of the result NOT silently, but explicitly reported in `failed_shards`.
So the client gets a partial result that says "these shard(s) couldn't
answer," not just "fewer results than expected, cause unknown."
"""

import asyncio
from dataclasses import dataclass, field

from shardsearch.query import collect_terms, evaluate, parse
from shardsearch.query.ast import QueryNode
from shardsearch.scoring.bm25 import bm25_score
from shardsearch.storage import SqliteInvertedIndex


@dataclass
class DistributedResult:
    results: list[tuple[str, float]]
    failed_shards: list[str] = field(default_factory=list)


def _query_shard(
    index: SqliteInvertedIndex, tree: QueryNode, query_terms: list[str]
) -> list[tuple[str, float]]:
    """SYNCHRONOUS query against a single shard — called via asyncio.to_thread."""
    candidate_docs = evaluate(tree, index)
    return [(doc_id, bm25_score(index, query_terms, doc_id)) for doc_id in candidate_docs]


async def _query_shard_safely(
    shard_id: str, index: SqliteInvertedIndex, tree: QueryNode, query_terms: list[str]
) -> tuple[str, list[tuple[str, float]], Exception | None]:
    try:
        result = await asyncio.to_thread(_query_shard, index, tree, query_terms)
        return shard_id, result, None
    except Exception as error:  # deliberately broad: whatever the failure
        # mark this shard as "failed", don't let it affect the other shards' results.
        return shard_id, [], error


async def distributed_search(
    shards: dict[str, SqliteInvertedIndex], query: str, limit: int = 10
) -> DistributedResult:
    """Sends `query` to every shard in parallel, merges the results by
    global BM25 score, and returns the top `limit` in descending order.

    `parse()` is deliberately called only ONCE here (not per shard) —
    a query parse error (QueryError) is a client error independent of the
    shards, and isn't swallowed here so the caller (the API route) can
    handle it normally.
    """
    tree = parse(query)
    query_terms = collect_terms(tree)

    tasks = [
        _query_shard_safely(shard_id, index, tree, query_terms)
        for shard_id, index in shards.items()
    ]
    raw_results = await asyncio.gather(*tasks)

    all_results: list[tuple[str, float]] = []
    failed_shards: list[str] = []
    for shard_id, result, error in raw_results:
        if error is not None:
            failed_shards.append(shard_id)
            continue
        all_results.extend(result)

    all_results.sort(key=lambda pair: (-pair[1], pair[0]))
    return DistributedResult(results=all_results[:limit], failed_shards=failed_shards)
