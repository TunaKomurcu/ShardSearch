# Postmortems: Real Bugs Found Across Phases 0-9

A follow-up to `docs/mvp-summary.md` and `docs/phase-8-distributed-status.md`
— but where those two focused on "what was built," this document focuses
specifically on **which real bugs were made, how they were found, and how
they were fixed**. The goal: to be able to say, in a CV/portfolio
conversation or when looking at a similar system in the future, "I've
seen this before, here's how it was solved."

In chronological order, the most instructive ones:

## 1. Process mistake: forgetting to open a phase branch (Phase 2)

**What happened:** Phase 2 (inverted index) was accidentally coded
directly on `main`, skipping the `phase-2-inverted-index` branch.

**How it was found:** noticed while checking `git branch` output after a
commit — not an automated tool, just the habit of "verify git state after
every phase."

**How it was fixed:** the commit was "moved" to a new branch (by pointing
`git branch phase-2-inverted-index` at the same commit), then `main` was
reset back to its prior state (right after Phase 1) with `git reset
--hard`. Since the commit was local and unpushed, there was no data-loss
risk — but making this fix required explicitly reasoning through *why*
it was safe (the commit remains reachable from the other branch).

**General lesson:** if discipline rules (like branch-per-phase) aren't
enforced automatically, catching and fixing violations requires a regular
"status check" habit — the reflex to catch a rule being broken matters as
much as the rule itself.

## 2. Undefined ranking/tie-break: undefined order in BM25 results (Phase 3)

**What happened:** the ranking function collected matching documents from
a Python `set`. When two documents had equal BM25 scores, which one came
first depended on the `set`'s internal hash ordering — deterministic
(same result every time within the same process) but **meaningless and
unpredictable**.

**How it was found:** in the comparison test against `rank_bm25`, the
query `"bir hayvandır"` produced an exact tie between two documents
(`d06`, `d08`); our ranking gave `[d08, d06]` while the reference library
gave `[d06, d08]` — the tests caught this.

**How it was fixed:** `scores.sort(key=lambda pair: (-pair[1], pair[0]))`
— when scores tie, sort ascending by `doc_id`, a deterministic and
explainable secondary sort key.

**General lesson:** "equal score" is an easy edge case to overlook;
producing an ordered result from a set/hash-based data structure without
a secondary sort key produces **undefined behavior** — not a crash, but
unreliable.

## 3. Test methodology bug: an apples-to-oranges comparison (Phase 8)

**What happened:** when comparing distributed search against single-node
search, the old Phase 3 `rank()` function was used as the single-node
"reference." But `rank()` has no idea about the Phase 5 AND/OR/phrase
parser at all — it tokenizes the raw query into a plain word list and
matches with bag-of-words OR logic. `distributed_search()`, meanwhile,
uses the `parse()`+`evaluate()`+`bm25_score()` triple. Result: on a phrase
query (`'"bir hayvandır"'`), the single-node "reference" leaked in an
irrelevant document (one containing only "bir" but not "hayvandır") — the
distributed search correctly excluded it. So the "bug" wasn't in the real
system, it was in the test methodology.

**How it was found:** the habit of manually inspecting intermediate
results (in a Python REPL) before writing the comparison test — noticing
an unexpected document in the result and asking "why is this here?"
surfaced it.

**How it was fixed:** the single-node "reference" was built by feeding
the SAME `distributed_search()` function a shard dictionary with just
**one entry**. That way both sides use the exact same code path (the same
parsing, the same matching, the same scoring) — the comparison became a
genuine apples-to-apples one.

**General lesson:** when building a "reference/baseline," make sure the
reference uses the **same business logic** as the system under test —
comparing two different code paths makes it impossible to tell whether a
difference is a real bug or just a methodology mismatch.

## 4. Name collision: a package shadowing its own submodule (Phase 9)

**What happened:** `shardsearch/api/__init__.py` contained the line `from
shardsearch.api.app import app` — the submodule's name ("app.py") and the
name of the variable exported from it ("app", the FastAPI object) were
the same. This overwrote the package's `app` ATTRIBUTE with the FastAPI
object. pytest's `monkeypatch.setattr("shardsearch.api.app._some_function",
...)` string-based resolution, which follows a dotted path through
attribute access, then found the FastAPI object instead of the module,
raising `AttributeError: 'FastAPI' object has no attribute
'_some_function'`.

**How it was found:** the error surfaced immediately on the first Phase 9
test run — seeing `obj = <FastAPI object>` in the traceback raised
suspicion of a name collision, confirmed by looking at
`shardsearch/api/__init__.py`.

**How it was fixed:** `__init__.py` was emptied (the re-export removed),
with a comment explaining why, so nobody "helpfully" adds that line back
in the future.

**General lesson:** in a Python package, the name exported from a
submodule should **never match the submodule's own name** — otherwise
package-level attribute access (especially tools that resolve a dotted
string dynamically: pytest monkeypatch, `importlib`, some DI containers)
finds the exported value instead of the module.

## 5. A classic distributed-systems trap: local IDF deviation (Phase 8)

This isn't a "bug" — it's a **deliberately accepted approximation** — but
it's on this list because it was measured and proven, which sets it apart
from the rest. BM25's IDF requires global corpus statistics; when each
shard computes it based only on its own documents (the same default as
Elasticsearch), ranking can deviate from single-node. Small under even
distribution (observed), more than 5x under a deliberately unbalanced
distribution (observed and proven with a dedicated test). Details:
`docs/phase-8-distributed-status.md`.

**General lesson:** "approximately correct but fast" decisions (like
Elasticsearch's local-IDF default) are common in real distributed
systems — what matters is being able to MEASURE the size of that
approximation and explain WHEN it grows, not ignoring it.

## 6. A "hidden" synchronous call blocking the event loop (Phase 10)

**What happened:** in Phase 10's real Locust load test, under concurrent
load (8-30 users), `/search` latency grew **without bound** (450ms → 25
seconds within 60 seconds) — a classic queue-buildup signature. The first
suspect was the `threading.Lock` inside `SqliteInvertedIndex`, flagged
since Phase 6 as "unknown how it behaves under real load."

**How it was found (and how the wrong suspect was ruled out):** an
isolated test first cleared the `threading.Lock` — 30 concurrent calls,
with both separate and shared Redis clients, completed in parallel and
fast (~0.45s) without touching `SqliteInvertedIndex` at all. This proved
the problem was NOT the locking mechanism, but didn't find the root
cause. Code review revealed the real one: even though the `GET /search`
route was `async def`, its `SearchCache.get()`/`set()` calls inside it
were made **directly, synchronously** — no `await`, no
`asyncio.to_thread`. When Redis was unreachable these calls took
~0.2-0.4s each (see the item below), and for that entire duration they
**completely blocked the single event loop thread** — with uvicorn
running a single worker, no other request could be processed at all
during that window.

**How it was fixed:** `cache.get()` and `cache.set()` calls were wrapped
in `asyncio.to_thread()` (alongside also converting `/index` to `async
def`). The same Locust scenario (30 users, 60s) was re-run: **27 requests
→ 945 requests** (a 35x increase), and latency became **flat and
predictable** instead of growing without bound (p50=1.7s, p99=1.8s,
max=1.9s — still carrying a fixed delay from the no-Redis scenario, but no
longer GROWING).

**A separate, earlier sub-issue found and fixed along the way:** during
the same investigation, it turned out that redis-py's handling of a
connection-refused state took roughly 4 seconds in this environment when
Redis was unreachable — reduced to ~0.4s by adding
`socket_connect_timeout`/`socket_timeout` (this alone did NOT fix the
event-loop-blocking issue, it only shortened each block's duration — the
real fix was never blocking the event loop in the first place).

**General lesson:** writing an `async def` route does not mean every call
inside it is non-blocking — `async def` only makes a route *able* to run
on the event loop; if a synchronous/blocking library (like redis-py) is
called inside it, that synchronous call STILL halts the entire event
loop. This is a good example of starting with a plausible-looking
hypothesis ("is the threading.Lock the bottleneck?"), ruling it out with
an isolated test, and reaching the real (more fundamental, more
instructive) cause through code review — the first suspect isn't always
the right one.
