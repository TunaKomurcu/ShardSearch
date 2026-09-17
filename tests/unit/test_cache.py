"""Phase 9 tests: SearchCache directly against fakeredis.

Since redis-py and fakeredis share the same API surface, SearchCache's
code never knows anything fakeredis-specific — it works identically
against a real Redis (see app.py's docstring; not yet verified against a
real Redis, see docs/known-limitations.md).
"""

import fakeredis
import pytest

from shardsearch.api.cache import SearchCache


@pytest.fixture
def cache() -> SearchCache:
    return SearchCache(fakeredis.FakeRedis(decode_responses=True))


def test_missing_key_returns_none(cache: SearchCache) -> None:
    assert cache.get("kedi", 10) is None


def test_a_stored_value_is_read_back(cache: SearchCache) -> None:
    cache.set("kedi", 10, {"query": "kedi", "results": []})
    assert cache.get("kedi", 10) == {"query": "kedi", "results": []}


def test_a_different_limit_means_a_different_key(cache: SearchCache) -> None:
    cache.set("kedi", 10, {"query": "kedi", "results": ["a"]})
    assert cache.get("kedi", 5) is None


def test_invalidate_makes_the_old_key_invisible(cache: SearchCache) -> None:
    cache.set("kedi", 10, {"query": "kedi", "results": ["a"]})
    assert cache.get("kedi", 10) is not None

    cache.invalidate()

    assert cache.get("kedi", 10) is None


def test_invalidate_only_affects_entries_written_before_it() -> None:
    cache = SearchCache(fakeredis.FakeRedis(decode_responses=True))
    cache.set("old", 10, {"query": "old", "results": []})
    cache.invalidate()
    cache.set("new", 10, {"query": "new", "results": []})

    assert cache.get("old", 10) is None
    assert cache.get("new", 10) is not None


def test_ttl_is_set(cache: SearchCache) -> None:
    cache.set("kedi", 10, {"query": "kedi", "results": []})
    ttl = cache._redis.ttl(cache._key("kedi", 10))
    assert 0 < ttl <= 300
