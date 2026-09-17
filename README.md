# ShardSearch

A distributed-capable text search engine, built from scratch — a
**learning project**.

This is not a production-ready Elasticsearch alternative. The goal is to
truly understand how search engines work by building the core
mechanisms — an inverted index, BM25 ranking, sharding via consistent
hashing, and distributed query fan-out with asyncio — by hand, instead of
wrapping an off-the-shelf library around them.

- Project scope, out-of-scope decisions, and architecture: [SPEC.md](SPEC.md)
- Phase-by-phase roadmap and "definition of done" criteria: [PHASES.md](PHASES.md)
- Concrete bugs found along the way, root causes, and fixes: [docs/postmortems.md](docs/postmortems.md)
- What each phase built and why: [docs/mvp-summary.md](docs/mvp-summary.md), [docs/phase-8-distributed-status.md](docs/phase-8-distributed-status.md)
- Known gaps and deliberate approximations: [docs/known-limitations.md](docs/known-limitations.md)

## Status

All 10 planned phases (0-10) are complete: a Turkish-aware tokenizer, an
inverted index (in-memory and SQLite-backed), a from-scratch BM25 ranker
validated against `rank_bm25`, a boolean query parser (AND/OR/phrase), a
FastAPI HTTP layer, consistent-hashing-based sharding, async distributed
query fan-out, a Redis cache-aside layer, and structured logging verified
under real Locust load. See [PHASES.md](PHASES.md) for details.

## Architecture

```
Indexing path:
  Document → Tokenizer (ours) → Inverted Index Builder (ours) → SQLite (off-the-shelf storage)

Query path:
  Client → FastAPI (off-the-shelf) → Query Parser (ours) → fan-out to shards (ours, asyncio)
    → [Shard 1, Shard 2, Shard 3] (each computes its own BM25) → Result merge (ours)
    → Redis cache (off-the-shelf) → Response
```

## Setup

Dependency management is done with [uv](https://github.com/astral-sh/uv).

```bash
uv sync
uv run pytest
```

## Running the API

```bash
uv run uvicorn shardsearch.api.app:app --reload
```

```bash
curl -X POST localhost:8000/index -H "Content-Type: application/json" \
  -d '{"doc_id": "d01", "text": "Kedi masada uyuyor."}'

curl "localhost:8000/search?q=kedi"
```

## Load testing

```bash
uv sync --group loadtest
uv run locust -f benchmarks/locustfile.py --host http://localhost:8000
```
