"""FastAPI wrapper — with structured-log observability.

Flow:
  POST /index -> ConsistentHash.find_shard() locates the right shard,
                 only that shard's SqliteInvertedIndex is written to,
                 then SearchCache.invalidate() invalidates the ENTIRE
                 search cache (see the "generation counter" note in
                 cache.py).
  GET  /search?q=...
      -> SearchCache.get() is checked first
      -> on a cache miss, distributed_search(): a parallel query
         (asyncio.to_thread) to every shard, results merged globally
      -> the result is only written to the cache if ALL shards
         succeeded (failed_shards is empty) — so a broken shard's
         incomplete result never gets cached as if it were the
         permanent "correct answer"

Every request is logged in JSON by a middleware (see logging_config.py)
— duration, status code, and for `/search` also cache hit/miss and any
failed-shard information. Percentile (p50/p95/p99) metrics are NOT
computed here — rather than build a metrics system into the app itself,
those come from Locust's own load-test report (see
benchmarks/locustfile.py).

The number and identity of shards are loaded statically from
`config/shards.json`. Each shard lives in its own SQLite file
(`data/<shard_id>.db`).

`_create_redis_client()` is deliberately its own function: tests replace
it with `monkeypatch` to return a `fakeredis.FakeRedis` instead of
connecting to a real Redis (see tests/unit/test_api.py) — `fakeredis` is
never imported in this file (see tests/unit/test_fakeredis_isolation.py).
"""

import asyncio
import logging
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import redis
from fastapi import FastAPI, HTTPException, Query, Request

from shardsearch.api.cache import SearchCache
from shardsearch.api.logging_config import LOGGER_NAME, log_request, setup_logging
from shardsearch.api.schemas import (
    AddDocumentRequest,
    AddDocumentResponse,
    SearchResponse,
    SearchResult,
)
from shardsearch.distributed import distributed_search
from shardsearch.query import QueryError
from shardsearch.sharding import ConsistentHash, load_shards
from shardsearch.storage import SqliteInvertedIndex

_DEFAULT_DATA_DIR = "data"
_DEFAULT_REDIS_URL = "redis://localhost:6379/0"

setup_logging()
_logger = logging.getLogger(LOGGER_NAME)


def _create_redis_client() -> redis.Redis:
    redis_url = os.environ.get("SHARDSEARCH_REDIS_URL", _DEFAULT_REDIS_URL)
    # Found during a real load test: when Redis is unreachable (connection
    # refused), redis-py's default behavior can take several seconds to
    # raise ConnectionError in some environments — SearchCache swallows
    # this error (search doesn't crash, which is the right design) but
    # every request pays that hidden delay; since a /search cache miss
    # makes 3 SEPARATE Redis calls (generation + get + set, see cache.py)
    # this cost multiplies. A short socket timeout (a common production
    # value too) makes "give up quickly when the cache is unreachable"
    # genuinely fast — the missing piece of the "not on the critical path"
    # guarantee the cache design already promised.
    return redis.from_url(
        redis_url, decode_responses=True, socket_connect_timeout=0.2, socket_timeout=0.2
    )


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    data_dir = Path(os.environ.get("SHARDSEARCH_DATA_DIR", _DEFAULT_DATA_DIR))
    data_dir.mkdir(parents=True, exist_ok=True)

    shard_ids = load_shards()
    app.state.shards = {
        shard_id: SqliteInvertedIndex(data_dir / f"{shard_id}.db") for shard_id in shard_ids
    }
    app.state.consistent_hash = ConsistentHash(shard_ids)
    app.state.cache = SearchCache(_create_redis_client())
    yield
    for index in app.state.shards.values():
        index.close()


app = FastAPI(title="ShardSearch", lifespan=_lifespan)


@app.middleware("http")
async def _log_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000

    extra: dict[str, object] = {}
    if request.url.path == "/search":
        extra["query"] = request.query_params.get("q")
        extra["limit"] = request.query_params.get("limit")
        extra["cache_hit"] = getattr(request.state, "cache_hit", None)
        extra["failed_shards"] = getattr(request.state, "failed_shards", None)

    log_request(
        _logger,
        endpoint=request.url.path,
        method=request.method,
        duration_ms=duration_ms,
        status_code=response.status_code,
        **extra,
    )
    return response


@app.post("/index", response_model=AddDocumentResponse, status_code=201)
async def add_document(request: AddDocumentRequest) -> AddDocumentResponse:
    # This route is async so its blocking work runs through the same
    # asyncio.to_thread mechanism distributed_search() (fan_out.py) uses
    # for shard queries, rather than a separate thread pool for
    # synchronous routes — avoiding two different thread pools competing
    # under concurrent load.
    shard_id = app.state.consistent_hash.find_shard(request.doc_id)
    await asyncio.to_thread(app.state.shards[shard_id].add_document, request.doc_id, request.text)
    await asyncio.to_thread(app.state.cache.invalidate)
    return AddDocumentResponse(doc_id=request.doc_id, status="indexed")


@app.get("/search", response_model=SearchResponse)
async def search(request: Request, q: str, limit: int = Query(default=10, gt=0)) -> SearchResponse:
    # cache.get()/set() are called through asyncio.to_thread rather than
    # directly — a direct synchronous call would block the single event
    # loop thread for the duration of the Redis round-trip, preventing
    # ANY other request from being processed in the meantime under
    # concurrent load.
    cached = await asyncio.to_thread(app.state.cache.get, q, limit)
    if cached is not None:
        request.state.cache_hit = True
        request.state.failed_shards = []
        return SearchResponse(**cached)

    request.state.cache_hit = False
    try:
        result = await distributed_search(app.state.shards, q, limit)
    except QueryError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    results = []
    for doc_id, score in result.results:
        shard_id = app.state.consistent_hash.find_shard(doc_id)
        text = app.state.shards[shard_id].document_text(doc_id)
        results.append(SearchResult(doc_id=doc_id, score=score, text=text))

    response = SearchResponse(query=q, results=results, failed_shards=result.failed_shards)
    request.state.failed_shards = result.failed_shards

    if not response.failed_shards:
        await asyncio.to_thread(app.state.cache.set, q, limit, response.model_dump())

    return response
