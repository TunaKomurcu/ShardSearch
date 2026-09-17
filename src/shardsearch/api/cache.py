"""Cache-aside pattern backed by Redis.

Redis is marked "use an off-the-shelf tool" in SPEC.md (caching mechanics
were already covered in a separate course, no need to build them from
scratch here) — this file only uses the redis-py client, Redis itself is
never reimplemented.

Why the cache key includes a "generation" counter: BM25's IDF and average
document length are statistics over the ENTIRE corpus — adding a single
new document can, in theory, change the score of a query totally unrelated
to that document (global N and avgdl changed). So there's no precise
answer to "which cache entries were affected by this new document" — in
practice, the whole cache needs to be invalidated. Rather than deleting
keys one by one (via Redis's KEYS/SCAN, which is O(n) and risky in
production since it scans the entire keyspace), a generation counter is
used: it's incremented by 1 on every write and folded into the cache key.
Once the counter changes, old keys become invisible automatically (never
read again) and expire on their own via TTL. An O(1) invalidation — a
single INCR.

If Redis is UNREACHABLE, search must NOT crash: the cache is an
optimization, not on the critical path. So every Redis call catches and
swallows RedisError — the caller (app.py) always sees "no cache" (None /
no-op), never a leaking exception.
"""

import json
from typing import Any

import redis

_TTL_SECONDS = 300  # enough for a "measurably faster" DoD; no need to keep it longer
_GENERATION_KEY = "search:generation"


class SearchCache:
    def __init__(self, redis_client: redis.Redis) -> None:
        self._redis = redis_client

    def _generation(self) -> int:
        try:
            value = self._redis.get(_GENERATION_KEY)
        except redis.exceptions.RedisError:
            return 0
        return int(value) if value is not None else 0

    def _key(self, query: str, limit: int) -> str:
        return f"search:v{self._generation()}:{query}:{limit}"

    def get(self, query: str, limit: int) -> dict[str, Any] | None:
        try:
            raw = self._redis.get(self._key(query, limit))
        except redis.exceptions.RedisError:
            return None
        if raw is None:
            return None
        return json.loads(raw)

    def set(self, query: str, limit: int, result: dict[str, Any]) -> None:
        try:
            self._redis.set(self._key(query, limit), json.dumps(result), ex=_TTL_SECONDS)
        except redis.exceptions.RedisError:
            pass

    def invalidate(self) -> None:
        """Called when a new document is indexed — bumps the generation
        counter, invalidating ALL previous cache entries in one O(1) step.
        """
        try:
            self._redis.incr(_GENERATION_KEY)
        except redis.exceptions.RedisError:
            pass
