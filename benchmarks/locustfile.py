"""Locust load-test scenario.

A realistic read-heavy mix: 90% GET /search, 10% POST /index (roughly how
most search engines see traffic in practice). On the search side, two
kinds of queries are DELIBERATELY mixed:
  - 60% chance of a query from a small "popular query" pool (to genuinely
    exercise cache hits — to see the effect of the cache-aside pattern,
    the same queries need to be asked repeatedly)
  - 40% chance of a random SINGLE word (a cache miss, forcing a real
    shard computation) — a single word is used on purpose: writing two
    words side by side with a space (e.g. "cat dog") is a parse error
    under the parser's rule (see docs/known-limitations.md), and that
    would pollute the "search latency" measurement with meaningless 400
    errors.

At the start of the test (the `test_start` event, ONCE, not once per
user) a small synthetic corpus is indexed. A Wikipedia-scale corpus isn't
needed here — the load test measures throughput/latency, not relevance.

There's no real Redis in this environment (see docs/known-limitations.md);
the live server will try to connect to `redis://localhost:6379/0`, fail,
and SearchCache will silently swallow that and run without a cache (the
behavior it was designed and tested for). So this run reflects the
"cacheless" scenario — which is fine, since the actual goal here is
measuring how the SQLite lock behaves under real concurrent load, and
that doesn't need the cache.

IMPORTANT environment note (see docs/known-limitations.md): in this
particular development environment, every HTTP connection opened from
Python (requests/http.client, doesn't matter which) carries a fixed ~4
second delay — curl.exe is unaffected, and a raw TCP connection is also
fast; only Python's HTTP request/response cycle is affected. Measured:
this delay OVERLAPS across concurrent requests (10 parallel requests
still take a total of ~4.2s, not 41s) — so it's not a real server
bottleneck, just a fixed environment artifact specific to this session.
Because of this, the absolute latency numbers Locust reports in this
environment do NOT reflect the real application latency — what's
meaningful is how the p99/p50 RATIO changes as load increases (a relative
comparison), not the absolute values.
"""

import concurrent.futures
import random

import requests
from locust import HttpUser, between, events, task

WORD_POOL = [
    "kedi", "köpek", "kuş", "balık", "aslan", "kaplan", "ayı", "tilki",
    "orman", "deniz", "gökyüzü", "güneş", "yıldız", "bulut", "yağmur",
    "şehir", "sokak", "araba", "bilgisayar", "kitap", "müzik",
    "sanat", "bilim", "teknoloji", "doğa", "hayvan", "bitki", "çiçek",
]  # fmt: skip

POPULAR_QUERIES = ["kedi", "köpek", "kedi OR köpek", "kedi AND köpek", '"kedi köpek"']

SEED_DOCUMENT_COUNT = 200


def _random_sentence(word_count: int = 6) -> str:
    return " ".join(random.choices(WORD_POOL, k=word_count))


@events.test_start.add_listener
def _seed_corpus(environment, **kwargs) -> None:
    # Deliberately PARALLEL: every HTTP connection opened from Python in
    # this development environment carries a fixed delay (see
    # docs/known-limitations.md) — 200 sequential requests would take
    # minutes. Since this delay overlaps across concurrent requests
    # (measured and confirmed), seeding via a ThreadPoolExecutor brings it
    # down to seconds.
    def _seed_one(i: int) -> None:
        requests.post(
            f"{environment.host}/index",
            json={"doc_id": f"seed-{i}", "text": _random_sentence()},
            timeout=30,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as pool:
        list(pool.map(_seed_one, range(SEED_DOCUMENT_COUNT)))


class SearchUser(HttpUser):
    wait_time = between(0.05, 0.3)

    @task(9)
    def search(self) -> None:
        if random.random() < 0.6:
            query = random.choice(POPULAR_QUERIES)
        else:
            query = random.choice(WORD_POOL)  # single word, always valid syntax
        self.client.get("/search", params={"q": query, "limit": 10}, name="/search")

    @task(1)
    def index_document(self) -> None:
        doc_id = f"load-{random.randint(0, 10_000_000)}"
        self.client.post(
            "/index",
            json={"doc_id": doc_id, "text": _random_sentence()},
            name="/index",
        )
