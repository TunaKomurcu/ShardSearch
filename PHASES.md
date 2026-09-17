# PHASES.md — Phase-by-Phase Roadmap

Each phase builds on the previous one. A phase's "Definition of Done" had
to be met before moving to the next.

## Phase 0: Setup ✅ (Done)
- Project skeleton (`src/`, `tests/`, `benchmarks/`, `docs/` directories)
- Dependency management setup (uv)
- pytest, ruff setup
- **Definition of Done:** `pytest` runs cleanly (even with an empty test
  suite), `git init` done

## Phase 1: Tokenizer ✅ (Done)
- Splitting text into tokens, lowercasing (with Turkish İ/ı awareness —
  `.lower()` gets this wrong in Turkish, handled deliberately), stripping
  punctuation/digits
- **Test:** at least 10 different Turkish sentences + edge cases
  (uppercase İ, apostrophe words — "Türkiye'nin", text containing digits)
- **Definition of Done:** every test sentence produces the expected token
  list

## Phase 2: Inverted Index (in-memory) ✅ (Done)
- `token → [(doc_id, frequency, [positions])]` data structure
- **Test:** on a small test corpus (10-20 sentences), a known word is
  found in the right documents with the right frequency
- **Definition of Done:** the postings list matches a hand-computed
  expected value exactly

## Phase 3: BM25 Scoring ✅ (Done)
- TF, IDF, document length normalization — each part of the formula its
  own function, its own test
- **Validation:** compare scores on the same corpus against `rank_bm25`
  (used only in `tests/validation/`)
- **Definition of Done:** our own ranking shows strong correlation with
  the reference library's (top 5 results in the same order, or an
  explainable difference)

## Phase 4: Persistent Storage (SQLite) ✅ (Done)
- A read/write layer persisting the inverted index to SQLite
- **Definition of Done:** the index survives an application restart,
  loaded from disk rather than memory

## Phase 5: Query Parser ✅ (Done)
- `AND`/`OR` boolean logic, `"phrase matching"` (using position
  information)
- **Test:** operator precedence is explicitly tested (`a AND b OR c` —
  which order is it evaluated in)
- **Definition of Done:** a complex query string parses into the correct
  parse tree

## Phase 6: FastAPI Wrapper — FIRST WORKING MVP ✅ (Done)
- `POST /index` (add document), `GET /search` (search) endpoints
- **Definition of Done:** end-to-end, single-node search works over a
  real HTTP request — a "working product" exists at this point

## Phase 7: Sharding ✅ (Done)
- Document distribution via consistent hashing
- **Test:** are documents evenly distributed across shards (distribution
  stats); does changing the shard count (resharding) move a minimal
  amount of data
- **Definition of Done:** data distributed across N shards can be
  correctly located by shard

## Phase 8: Distributed Query (Fan-out + Merge) ✅ (Done)
- Parallel shard querying via asyncio, results merged and globally
  ranked
- **Test:** comparing distributed results against single-node results —
  are deviations caused by IDF differences explainable
- **Definition of Done:** distributed search across 3 shards produces
  results consistent with single-node search

## Phase 9: Cache Layer ✅ (Done)
- Caching frequent queries with Redis (cache-aside pattern)
- **Definition of Done:** the same query returns measurably faster the
  second time

## Phase 10: Observability + Load Testing ✅ (Done)
- Structured logging, query duration metrics (p50/p95/p99)
- Load testing with Locust
- **Definition of Done:** a Locust report + p50/p95/p99 chart obtained

## Phase 11 (Stretch — optional, time permitting)
- Advanced Turkish stemming with Zemberek
- Hybrid (BM25 + semantic) search with `hnswlib`/`faiss`
- Dockerizing, basic CI/CD setup

---

## Expected Output at the End of Each Phase

1. Working, tested code
2. A short summary: which design decisions were made in this phase, and why
3. The corresponding item checked off in `PHASES.md`
