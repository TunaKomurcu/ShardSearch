"""End-to-end FastAPI tests: indexing and search over real HTTP requests.

TestClient runs the real route/dependency/lifespan flow over ASGI (no
mocking) — it just doesn't open a real TCP socket. Verification over a
real socket (uvicorn + curl) was also done manually.

`app` uses ALL shards from `config/shards.json` (not a single file) —
these tests don't assume which document lands on which shard, they only
verify the end-to-end result is correct. Each test uses its own temporary
data directory (via the SHARDSEARCH_DATA_DIR env var) so tests never see
each other's data.

`fakeredis` stands in for a real Redis (no real Redis/Docker/WSL in this
environment, see docs/known-limitations.md). `fakeredis` is imported ONLY
in this test file — `app.py`'s `_create_redis_client()` function is
replaced via `monkeypatch`, so `fakeredis` never enters `src/` (see
test_fakeredis_isolation.py).
"""

import logging
import time

import fakeredis
import pytest
from fastapi.testclient import TestClient

import shardsearch.api.app as app_module
import shardsearch.distributed.fan_out as fan_out_module
from shardsearch.api.app import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    # _lifespan() re-reads these env vars/factory and rebuilds app.state
    # from scratch every time a `with TestClient(...)` block is entered
    # (i.e. on every test) — so there's no need to reimport the module
    # between tests; each test gets its own temp data directory and
    # isolated fakeredis instance.
    monkeypatch.setenv("SHARDSEARCH_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        "shardsearch.api.app._create_redis_client",
        lambda: fakeredis.FakeRedis(decode_responses=True),
    )

    with TestClient(app) as test_client:
        yield test_client


def test_add_document_returns_201(client: TestClient) -> None:
    response = client.post("/index", json={"doc_id": "d01", "text": "Kedi masada uyuyor."})
    assert response.status_code == 201
    assert response.json() == {"doc_id": "d01", "status": "indexed"}


def test_end_to_end_index_and_search(client: TestClient) -> None:
    client.post("/index", json={"doc_id": "d01", "text": "Kedi masada uyuyor."})
    client.post("/index", json={"doc_id": "d02", "text": "Köpek bahçede koşuyor."})
    client.post("/index", json={"doc_id": "d03", "text": "Kedi ve köpek birlikte oynuyor."})

    response = client.get("/search", params={"q": "kedi"})
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "kedi"
    doc_ids = [result["doc_id"] for result in body["results"]]
    assert set(doc_ids) == {"d01", "d03"}
    assert "d02" not in doc_ids


def test_search_and_or_phrase_work_together(client: TestClient) -> None:
    client.post("/index", json={"doc_id": "d01", "text": "kedi köpek ile oynuyor"})
    client.post("/index", json={"doc_id": "d02", "text": "köpek ve kedi parkta yürüyor"})
    client.post("/index", json={"doc_id": "d03", "text": "balık havuzda yüzüyor"})

    # "kedi köpek" (adjacent phrase) only occurs in d01; d02 has the words
    # but not adjacent, so it should be excluded.
    response = client.get("/search", params={"q": '"kedi köpek" OR balık'})
    doc_ids = {result["doc_id"] for result in response.json()["results"]}
    assert doc_ids == {"d01", "d03"}


def test_search_results_are_sorted_by_score_descending(client: TestClient) -> None:
    client.post("/index", json={"doc_id": "d01", "text": "kedi kedi kedi"})
    client.post("/index", json={"doc_id": "d02", "text": "kedi ile ilgisiz uzun bir cümle"})

    response = client.get("/search", params={"q": "kedi"})
    results = response.json()["results"]
    scores = [result["score"] for result in results]
    assert scores == sorted(scores, reverse=True)
    # d01 mentions "kedi" 3 times, so its higher tf should rank it above d02
    assert results[0]["doc_id"] == "d01"


def test_search_returns_document_text(client: TestClient) -> None:
    client.post("/index", json={"doc_id": "d01", "text": "Kedi masada uyuyor."})
    response = client.get("/search", params={"q": "kedi"})
    assert response.json()["results"][0]["text"] == "Kedi masada uyuyor."


def test_search_with_no_matches_returns_an_empty_list(client: TestClient) -> None:
    client.post("/index", json={"doc_id": "d01", "text": "Kedi masada uyuyor."})
    response = client.get("/search", params={"q": "nonexistentword"})
    assert response.status_code == 200
    assert response.json()["results"] == []


def test_search_with_an_invalid_query_returns_400(client: TestClient) -> None:
    client.post("/index", json={"doc_id": "d01", "text": "Kedi masada uyuyor."})
    # implicit juxtaposition, no operator
    response = client.get("/search", params={"q": "kedi köpek"})
    assert response.status_code == 400


def test_search_limit_parameter_caps_the_result_count(client: TestClient) -> None:
    for i in range(5):
        client.post("/index", json={"doc_id": f"d{i}", "text": "kedi köpek kuş"})

    response = client.get("/search", params={"q": "kedi", "limit": 2})
    assert len(response.json()["results"]) == 2


@pytest.mark.parametrize("invalid_limit", [0, -1])
def test_search_with_an_invalid_limit_returns_422(client: TestClient, invalid_limit: int) -> None:
    response = client.get("/search", params={"q": "kedi", "limit": invalid_limit})
    assert response.status_code == 422


def test_indexing_the_same_doc_id_again_performs_an_upsert(client: TestClient) -> None:
    client.post("/index", json={"doc_id": "d01", "text": "Kedi masada uyuyor."})
    client.post("/index", json={"doc_id": "d01", "text": "Köpek bahçede koşuyor."})

    response = client.get("/search", params={"q": "kedi"})
    assert response.json()["results"] == []

    response = client.get("/search", params={"q": "köpek"})
    doc_ids = {result["doc_id"] for result in response.json()["results"]}
    assert doc_ids == {"d01"}


def _count_distributed_search_calls(monkeypatch) -> dict[str, int]:
    """Counts how many times `distributed_search` is ACTUALLY called — on
    a cache hit this function should never be called, which is a more
    reliable proof that "the cache genuinely did its job" than timing.
    """
    counter = {"n": 0}
    original = app_module.distributed_search

    async def counting(*args, **kwargs):
        counter["n"] += 1
        return await original(*args, **kwargs)

    monkeypatch.setattr(app_module, "distributed_search", counting)
    return counter


def test_second_identical_search_never_reaches_the_shards(client: TestClient, monkeypatch) -> None:
    client.post("/index", json={"doc_id": "d01", "text": "kedi masada uyuyor"})
    counter = _count_distributed_search_calls(monkeypatch)

    client.get("/search", params={"q": "kedi"})
    client.get("/search", params={"q": "kedi"})

    assert counter["n"] == 1


def test_second_identical_search_is_measurably_faster(client: TestClient, monkeypatch) -> None:
    # :memory: SQLite is already very fast, so a real timing difference
    # could get lost in noise — the shard query is deliberately slowed
    # down to reliably produce the "measurable" difference the DoD asks for.
    client.post("/index", json={"doc_id": "d01", "text": "kedi masada uyuyor"})
    original_query = fan_out_module._query_shard

    def slow_query(*args, **kwargs):
        time.sleep(0.05)
        return original_query(*args, **kwargs)

    monkeypatch.setattr(fan_out_module, "_query_shard", slow_query)

    start = time.perf_counter()
    client.get("/search", params={"q": "kedi"})
    first_duration = time.perf_counter() - start

    start = time.perf_counter()
    client.get("/search", params={"q": "kedi"})
    second_duration = time.perf_counter() - start

    assert second_duration < first_duration / 2, (
        f"the cached request should have been at least 2x faster: first={first_duration:.4f}s "
        f"second={second_duration:.4f}s"
    )


def test_adding_a_new_document_invalidates_the_cache(client: TestClient, monkeypatch) -> None:
    client.post("/index", json={"doc_id": "d01", "text": "kedi masada uyuyor"})
    counter = _count_distributed_search_calls(monkeypatch)

    client.get("/search", params={"q": "kedi"})  # cache miss
    client.get("/search", params={"q": "kedi"})  # cache hit
    assert counter["n"] == 1

    # Adding a new document should invalidate the ENTIRE cache, even
    # though it has nothing to do with the "kedi" query (see the
    # generation-counter note in cache.py).
    client.post("/index", json={"doc_id": "d02", "text": "alakasız bir cümle"})

    client.get("/search", params={"q": "kedi"})  # should be a cache miss again
    assert counter["n"] == 2


def test_a_partially_failed_result_is_not_cached(client: TestClient, monkeypatch) -> None:
    client.post("/index", json={"doc_id": "d01", "text": "kedi masada uyuyor"})

    # Deliberately break one shard — regardless of whether this document
    # lives on it, every shard is queried, so failed_shards will be non-empty.
    first_shard_id = next(iter(app.state.shards))
    app.state.shards[first_shard_id].close()

    response1 = client.get("/search", params={"q": "kedi"})
    assert response1.json()["failed_shards"] == [first_shard_id]

    counter = _count_distributed_search_calls(monkeypatch)
    response2 = client.get("/search", params={"q": "kedi"})

    # Since it wasn't cached, the second identical request must have
    # ACTUALLY reached the shards too (counter is 1, not 0) — a partially
    # failed result never gets cached as if it were the permanent
    # "correct answer".
    assert counter["n"] == 1
    assert response2.json()["failed_shards"] == [first_shard_id]


def test_search_request_produces_a_structured_log(client: TestClient, caplog) -> None:
    client.post("/index", json={"doc_id": "d01", "text": "kedi masada uyuyor"})

    with caplog.at_level(logging.INFO, logger="shardsearch"):
        client.get("/search", params={"q": "kedi", "limit": 5})

    search_records = [r for r in caplog.records if getattr(r, "endpoint", None) == "/search"]
    assert len(search_records) == 1
    record = search_records[0]
    assert record.method == "GET"
    assert record.status_code == 200
    assert record.query == "kedi"
    assert record.cache_hit is False  # first call, should be a cache miss
    assert record.failed_shards == []
    assert record.duration_ms >= 0


def test_second_identical_search_shows_cache_hit_true_in_the_log(
    client: TestClient, caplog
) -> None:
    client.post("/index", json={"doc_id": "d01", "text": "kedi masada uyuyor"})
    client.get("/search", params={"q": "kedi"})  # cache miss, warm-up
    caplog.clear()  # caplog.records accumulates across the whole test, not reset by at_level

    with caplog.at_level(logging.INFO, logger="shardsearch"):
        client.get("/search", params={"q": "kedi"})

    search_records = [r for r in caplog.records if getattr(r, "endpoint", None) == "/search"]
    assert len(search_records) == 1
    assert search_records[0].cache_hit is True


def test_invalid_query_log_shows_status_code_400(client: TestClient, caplog) -> None:
    with caplog.at_level(logging.INFO, logger="shardsearch"):
        client.get("/search", params={"q": "kedi köpek"})  # implicit juxtaposition, no operator

    search_records = [r for r in caplog.records if getattr(r, "endpoint", None) == "/search"]
    assert len(search_records) == 1
    assert search_records[0].status_code == 400


def test_index_request_produces_a_structured_log(client: TestClient, caplog) -> None:
    with caplog.at_level(logging.INFO, logger="shardsearch"):
        client.post("/index", json={"doc_id": "d01", "text": "kedi masada uyuyor"})

    index_records = [r for r in caplog.records if getattr(r, "endpoint", None) == "/index"]
    assert len(index_records) == 1
    assert index_records[0].method == "POST"
    assert index_records[0].status_code == 201
