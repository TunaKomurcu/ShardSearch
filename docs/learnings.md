# Learnings: ShardSearch, From Phase 0 to Here

This is the project's closing document — a summary and general takeaway
from the journey from Phase 0 (project skeleton) to Phase 10
(observability + load testing, the last planned phase in PHASES.md).
`docs/postmortems.md` focused on "which bugs were found, how were they
fixed"; this document steps back and looks at **why these bugs would have
stayed invisible if we'd used off-the-shelf tools as black boxes** — which
was the whole point of the project.

## What was built (summary)

11 phases were planned, 10 (0-10) were completed — Phase 11 (Zemberek,
hybrid vector search, Docker) was already marked optional/stretch in
SPEC.md and was deliberately skipped (low learning leverage; hybrid
search experience was already covered by prior work experience). Both of
SPEC.md's major success criteria were met:

- **End of Phase 6:** end-to-end, single-node search works over a real
  HTTP request.
- **End of Phase 8:** distributed search across 3 shards produces results
  consistent with single-node search (within explainable differences).

Detailed phase-by-phase summaries: `docs/mvp-summary.md` (Phases 0-6) and
`docs/phase-8-distributed-status.md` (Phases 7-8).

## Real bugs found (summary — details in docs/postmortems.md)

1. **Forgetting to open a phase branch** (Phase 2) — a process
   discipline issue, fixed with `git reset --hard` + moving the branch.
2. **Undefined tie-break** (Phase 3) — the order of equally-scored
   documents depended on a `set`'s hash order; made deterministic with a
   `(-score, doc_id)` secondary key.
3. **Apples-to-oranges test comparison** (Phase 8) — distributed search
   was being compared against an old function that had no idea about the
   Phase 5 boolean parser; fixed by feeding the single-node reference
   through the same `distributed_search()` (with a single shard).
4. **A package shadowing its own submodule** (Phase 9) — an export in
   `__init__.py` sharing a name with its submodule broke dotted-path
   attribute resolution (including pytest monkeypatch).
5. **Distributed local IDF deviation** (Phase 8) — a deliberate
   approximation, measured and proven (small under even distribution,
   more than 5x under an unbalanced one).
6. **A hidden synchronous call blocking the event loop** (Phase 10) —
   synchronous Redis calls inside an `async def` route halted the entire
   event loop; would never have surfaced without a real Locust load test.

## "Using a black box" vs. "building it from scratch," in concrete terms

The project's starting premise was: *experience the difference between
"it works" (doesn't error) and "it works correctly" (understanding why it
works).* That difference showed up concretely, differently, in every
phase:

**Tokenizer (Phase 1):** with a library, we'd have just called `.lower()`
and moved on. Building it from scratch forced us to notice that Python's
`str.lower()` turns `'I'` into `'i'` (should be `'ı'`) and `'İ'` into
`'i̇'` (a combining character) — a concrete lesson that the very notion of
"lowercasing" is language-dependent in Unicode.

**Inverted index (Phase 2):** a search library would have hidden this
entirely. Building it from scratch showed that keeping the postings list
SORTED needs to be a design decision made up front (so the intersection/
merge algorithms in Phases 5/8 can run in O(n)) — not a "sort" bolted on
at the end.

**BM25 (Phase 3):** we could have just written `from rank_bm25 import
BM25Okapi`. Writing it ourselves meant directly experiencing that the
classic (Robertson-Sparck Jones) IDF formula can go NEGATIVE, that real
libraries patch this with an epsilon, and that we could instead choose a
variant of the formula that's positive by construction (and how that
choice affects ranking tests).

**SQLite storage (Phase 4):** an ORM would have managed indexes for us.
Designing the schema by hand meant seeing that a `(token, doc_id)` primary
key only helps searches that start with the token, and that searching by
`doc_id` alone (for upsert deletion) needs a SEPARATE index — the SQL
counterpart of the in-memory version's Python dict.

**Query parser (Phase 5):** a regex or off-the-shelf parser would have
left operator precedence hidden "somewhere." Writing the recursive-
descent grammar by hand showed that AND binding tighter than OR isn't a
"rule" imposed from outside, it's a natural CONSEQUENCE of the grammar's
STRUCTURE (or → and → term) — no separate precedence table needed at all.

**Sharding (Phase 7):** we could have just written `hash(id) % N`.
Building consistent hashing by hand made concrete WHY virtual nodes are
needed (PROVEN by measuring distribution variance, not just asserted) and
WHY resharding should only allow old→new moves and never old→old moves
(verified by testing).

**Distributed query (Phase 8):** with Elasticsearch we'd have read a
documentation line saying "uses local IDF" and taken it on faith. Building
it ourselves let us measure the SIZE of that approximation with our own
hands (small under even distribution, 5x under a deliberately unbalanced
one) and prove it.

**Cache (Phase 9):** we'd read the line "cache invalidation is one of the
two hard problems in computer science." Building our own cache-aside
layer meant confronting, FOR THIS SYSTEM SPECIFICALLY, the fact that
"selective invalidation is impossible because BM25 statistics are global"
and arriving at the generation-counter solution OURSELVES — a library
would have made that decision for us and hidden it.

**Observability + load testing (Phase 10) — the deepest lesson:** if
we'd treated FastAPI as a "black box" and assumed writing `async def` was
sufficient on its own, this project would never have looked any different
from a finished "working" product — tests would pass, single curl
requests would return fast. Only a REAL, CONCURRENT load test (and a
willingness to rule out a "reasonable" first suspect like
threading.Lock with an isolated test) revealed that a synchronous call
inside `async def` was halting the entire event loop. This was the
clearest proof of the gap between "thinking you understand" and "actually
understanding" — exactly what SPEC.md set out to pursue from the start.

## Closing

This project never aimed to be a "production-ready Elasticsearch
alternative" (SPEC.md, line 5). The goal was to build search-engine
mechanics by truly understanding them. Of the 6 real things found, 5 were
bugs that got fixed (git branch, tie-break, apples-to-oranges comparison,
`__init__.py` shadowing, event-loop blocking); 1 (local IDF deviation)
was a deliberately accepted and MEASURED approximation. None of them were
left on a "works, therefore correct" assumption.
