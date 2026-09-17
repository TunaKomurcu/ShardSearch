# MVP Summary (through Phase 6)

A checkpoint note from before moving into Phase 7: what each phase up to
this point covered, and which scope decisions were made deliberately —
so anyone looking at this repo later (including future us) can quickly
answer "why did we stop here, why are we continuing from here."

## What was built so far

| Phase | What | Where |
|---|---|---|
| 0 | Project skeleton, uv, pytest, ruff | — |
| 1 | Turkish-aware tokenizer (İ/ı distinction, apostrophe rule) | `src/shardsearch/tokenizer/` |
| 2 | In-memory inverted index (sorted postings, upsert) | `src/shardsearch/index/` |
| 3 | BM25 scoring (TF/IDF/length norm as separate functions) | `src/shardsearch/scoring/` |
| 4 | Persistent storage with SQLite (same interface, disk-backed) | `src/shardsearch/storage/` |
| 5 | Boolean query parser (AND/OR precedence, phrase matching) | `src/shardsearch/query/` |
| 6 | FastAPI MVP: `POST /index`, `GET /search` — wires everything together | `src/shardsearch/api/` |

Result: on a single machine, over a real HTTP request, a search engine
running on our own tokenizer + inverted index + BM25 + boolean query
parser. `rank_bm25` is only ever used in `tests/validation/` as a
reference — it never enters `src/` (an automated guard test enforces
this).

## Deliberately left out of scope (avoiding over-engineering)

These weren't "forgotten" — they were deliberately deferred in SPEC.md or
during phase sign-off, and aren't needed for the current single-node MVP:

- **Microservice architecture / separate processes** — a single FastAPI
  process, a single SQLite file. Sharding (Phase 7) and distributed query
  (Phase 8) introduce the idea of "multiple shards," but still on one
  machine, without an orchestration layer like Kubernetes/Docker Compose.
- **Kubernetes / containerization** — SPEC.md's stretch list mentions
  "Dockerizing" but K8s was never planned; this is a search-engine-
  mechanics learning project, not a deployment/infrastructure one.
- **Connection pooling / real concurrency optimization** — in Phase 6,
  SQLite access was serialized behind a single `threading.Lock`. This was
  measured under real Locust load in Phase 10 and RESOLVED: there was
  significant latency growth under concurrent load, but the root cause
  wasn't this `threading.Lock` — it was Redis calls inside the `/search`
  route directly blocking the event loop. Wrapping them in
  `asyncio.to_thread` eliminated the latency growth entirely (27→945
  requests/60s). Details: `docs/postmortems.md`, item 6. The
  `threading.Lock` itself still isn't optimized at the connection-pool
  level, but it turned out not to be the real bottleneck.
- **Authentication, multi-tenancy, rate limiting** — explicitly out of
  scope per SPEC.md: "this is a technical demo, not a production SaaS."
- **A custom B-tree/LSM-tree, a custom HNSW, advanced Turkish
  morphology** — all marked in SPEC.md as "use an off-the-shelf tool or
  don't do it at all."
- **Result snippets / highlighting** — `/search` currently returns the
  full document text rather than a short, highlighted snippet as
  production would. A deliberate Phase 6 MVP shortcut (see the comment on
  `SearchResult.text`).
- **Queries without operators (implicit AND/OR)** — see
  `docs/known-limitations.md`; to be revisited after real Phase 6 usage.

## Why we're continuing from here

The MVP's goal was never "a finished product" but **proving every
component works correctly on a single node** — the phases after this
(7: sharding, 8: distributed query) build on this single-node foundation.
Phase 8's DoD ("distributed search across 3 shards, consistent with
single-node results") is defined relative to the single-node behavior
established here.
