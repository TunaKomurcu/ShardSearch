# Known Limitations

- **Hyphenated compound words (Phase 1 tokenizer):** `tokenize()` silently
  drops every non-letter character except the apostrophe, rather than
  using it as a split point. So hyphenated words like
  `"anayasa-mahkemesi"` collapse into a single token,
  `"anayasamahkemesi"`. Deliberately deferred for now — revisit once
  real-world corpus use surfaces how often this actually causes problems.

- **Implicit juxtaposition (Phase 5 query parser):** a query like
  `"kedi köpek"` (no `AND`/`OR` between the words) raises a **parse
  error** — no implicit AND/OR is assumed. A deliberate choice, staying
  true to the spec's "understood code" priority rather than adding a
  silent assumption. Worth revisiting after real usage, to see whether
  users actually need it.

- **The Redis cache has not been verified against a real Redis:** the
  development environment had no real Redis server, Docker, or working
  WSL available (virtualization was disabled). `SearchCache`
  (`src/shardsearch/api/cache.py`) is written against redis-py's real API
  and is expected to behave identically against a real Redis server, but
  both the automated tests and manual verification during development
  used `fakeredis` (an in-memory library that mimics the redis-py
  protocol). Real network round-trips, connection-drop/timeout behavior,
  and real TTL expiry timing were never exercised. Once a real Redis or
  Docker setup is available, the same test suite
  (`tests/unit/test_cache.py`, the cache-related tests in
  `tests/unit/test_api.py`) should be re-run against it by pointing
  `SHARDSEARCH_REDIS_URL` at a real server, and this note can be closed.
