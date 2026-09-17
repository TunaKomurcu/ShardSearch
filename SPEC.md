# SPEC.md — ShardSearch Project Specification

## Purpose

Build a distributed-capable text search engine from scratch. This is
**not a production-ready Elasticsearch alternative** — the goal is to
truly understand the core mechanisms of search engines (inverted index,
BM25, sharding, distributed result merging) by building them by hand.
Priority: **understood code, not just working code.**

## Why this project?

- Learn concepts previously only "used as a library" (hash tables, BM25,
  consistent hashing, asyncio, sharding) by actually building the
  underlying mechanism
- No domain knowledge required — purely focused on engineering depth
- Move BM25/hybrid retrieval experience from "I use it" to "I know why it
  works that way"

## In Scope — Built From Scratch

1. **Tokenizer** — Turkish-aware, simple rule-based (not advanced
   morphological analysis)
2. **Inverted Index** — a token → (doc_id, frequency, position list) data
   structure
3. **BM25 Ranking Algorithm** — TF, IDF, document length normalization,
   implemented by hand
4. **Query Parser** — AND/OR boolean logic + phrase matching
5. **Sharding** — document distribution via consistent hashing
6. **Distributed Query** — parallel shard querying with asyncio (fan-out)
   + result merging

## Out of Scope — Off-the-Shelf Tools or Not Done at All

| Component | Decision | Rationale |
|---|---|---|
| Web/API layer | Use FastAPI | That's exactly what the framework is for — writing an HTTP server from scratch is out of scope |
| Persistent storage | Use SQLite | Writing a B-tree/LSM-tree is a separate, huge project on its own |
| Query cache | Use Redis | Caching mechanics were already covered in a separate course, no need to rebuild from scratch here |
| Cluster coordination | Static, config-file-based shard assignment | Dynamic consensus protocols like Raft/Paxos are out of scope |
| Turkish morphological analysis | Start with simple rules, optional Zemberek later | Building Turkish stemming from scratch is a separate NLP research project |
| Vector/semantic search | Optional stretch goal, use `hnswlib`/`faiss` | Writing your own HNSW is out of scope |
| Authentication, multi-tenancy | None | This is a technical demo, not a production SaaS |

## Architecture (high level)

```
Indexing path:
  Document → Tokenizer (ours) → Inverted Index Builder (ours) → SQLite (off-the-shelf storage)

Query path:
  Client → FastAPI (off-the-shelf) → Query Parser (ours) → fan-out to shards (ours, asyncio)
    → [Shard 1, Shard 2, Shard 3] (each computes its own BM25) → Result merge (ours)
    → Redis cache (off-the-shelf) → Response
```

## Tech Stack

- Python 3.12, fully type-hinted
- FastAPI (API layer)
- SQLite (persistent storage)
- Redis (query cache)
- pytest (testing), Locust (load testing)
- asyncio (distributed fan-out)

## Validation Strategy (critical — especially important for this project)

How do we know our own BM25 implementation is **correct**? "Works"
(doesn't error) and "works correctly" (produces the right result) are
very different things. Solution: on the same small test corpus, we write
a **comparison test** against scores produced by the `rank_bm25` library.
This library is never integrated into the main code — it's used only in
a separate validation/comparison file, purely as a reference.

## Reference Dataset

Rather than random/synthetic data, a **real Turkish text corpus** is used
(e.g. 200-500 articles from Turkish Wikipedia) for validation and
eyeballing relevance — so that "relevance" carries real meaning and
results can be sanity-checked by hand.

## Success Criteria

- End-to-end, single-node search working over a real HTTP request
- Distributed search across 3 shards, consistent with single-node results
  (within explainable differences)
- Load-tested with Locust, p50/p95/p99 latency metrics measured
