# Status After Phase 8: The System Is Now Genuinely Distributed

A follow-up to `docs/mvp-summary.md`. Phases 0-6 built a single-node MVP;
Phases 7-8 made the system genuinely distributed: multiple independent
SQLite files (shards), document distribution via consistent hashing,
parallel querying via asyncio. This document answers, at a glance, "what
did we build, what guarantees hold, what deliberate approximations exist"
at this point.

## What changed (relative to the Phase 6 MVP)

| | Phase 6 (single-node MVP) | After Phase 8 |
|---|---|---|
| Storage | One `SqliteInvertedIndex`, one `.db` file | N independent `SqliteInvertedIndex` instances, `data/<shard_id>.db` |
| `/index` | Writes directly to the single index | Routed to the correct shard via `ConsistentHash.find_shard()` |
| `/search` | `evaluate()`+`bm25_score()` on a single index | Parallel across all shards via `asyncio.to_thread`, results merged |
| Failure handling | Single point of failure — the index crashing takes search down | Partial failure is tolerated and reported via `failed_shards` |

## What's guaranteed: candidate document set consistency

`evaluate()` (AND/OR/phrase matching) only looks at the **existence and
position** of postings, it never computes a score. So the answer to
"which documents match a query" is **completely independent** of how many
shards the data is split across — a guarantee based on the algorithm's
structure, not luck.
`tests/unit/test_fan_out.py::test_candidate_set_is_identical_to_single_node_under_even_distribution`
verifies this across 6 different query types (single term, AND, OR,
phrase).

## Deliberate approximation: local (per-shard) IDF

BM25's IDF requires global corpus statistics (total document count,
number of documents containing the term). Each shard computes IDF based
ONLY on ITS OWN documents (the same default behavior as Elasticsearch —
no second round-trip to gather global statistics). Result: **ranking**
(the relative order of scores) can deviate from single-node, the
**candidate set** does not.

Two measured observations:

1. **Small deviation under even distribution:** even with a 12-document
   corpus evenly distributed across 3 shards via consistent hashing, a
   document's rank in "cat OR dog" can shift (from 2nd to 4th).
2. **Large deviation under uneven distribution:** if most documents
   containing a term end up concentrated on one (small) shard, that
   shard's local IDF can deviate from the global IDF by **more than 5x**
   — because the term looks disproportionately "common" on that small
   shard.

**Cause and effect were proven, not just claimed:** the size of the
deviation is directly proportional to how unbalanced the term
distribution is across shards — expected to shrink in large,
term-balanced corpora (the law of large numbers), and to show up more
clearly in small/unbalanced ones. Details and tests:
`src/shardsearch/distributed/fan_out.py`'s docstring,
`tests/unit/test_fan_out.py`.

## Not yet done (next phases)

- **Cache** — frequently repeated queries hit every shard again each time.
- **Observability / load testing** — how the thread-safety lock (see
  `docs/mvp-summary.md`) behaves under real concurrent load is still
  unknown.
- **Live resharding** — Phase 7 proved mathematically that resharding
  moves a minimal amount of data, but actually redistributing data (from
  existing `.db` files) when a shard is added/removed in a running API
  was never implemented — this was outside SPEC.md's scope too, a
  possible future stretch.
