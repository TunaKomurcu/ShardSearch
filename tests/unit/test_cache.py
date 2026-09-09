"""Faz 9 testleri: AramaCache doğrudan fakeredis'e karşı.

redis-py ve fakeredis aynı API yüzeyini paylaştığı için AramaCache
kodunun kendisi hiçbir zaman fakeredis'e özel bir şey bilmiyor —
gerçek Redis'e karşı da birebir aynı şekilde çalışır (bkz. app.py'nin
docstring'i, henüz gerçek Redis'e karşı doğrulanmadı — bkz.
docs/known-limitations.md).
"""

import fakeredis
import pytest

from shardsearch.api.cache import AramaCache


@pytest.fixture
def cache() -> AramaCache:
    return AramaCache(fakeredis.FakeRedis(decode_responses=True))


def test_olmayan_anahtar_none_doner(cache: AramaCache) -> None:
    assert cache.getir("kedi", 10) is None


def test_kaydedilen_deger_geri_okunur(cache: AramaCache) -> None:
    cache.kaydet("kedi", 10, {"sorgu": "kedi", "sonuclar": []})
    assert cache.getir("kedi", 10) == {"sorgu": "kedi", "sonuclar": []}


def test_farkli_limit_farkli_anahtar_demektir(cache: AramaCache) -> None:
    cache.kaydet("kedi", 10, {"sorgu": "kedi", "sonuclar": ["a"]})
    assert cache.getir("kedi", 5) is None


def test_gecersiz_kil_eski_anahtari_gorunmez_yapar(cache: AramaCache) -> None:
    cache.kaydet("kedi", 10, {"sorgu": "kedi", "sonuclar": ["a"]})
    assert cache.getir("kedi", 10) is not None

    cache.gecersiz_kil()

    assert cache.getir("kedi", 10) is None


def test_gecersiz_kil_sadece_o_ana_kadarki_yazilanlari_etkiler() -> None:
    cache = AramaCache(fakeredis.FakeRedis(decode_responses=True))
    cache.kaydet("eski", 10, {"sorgu": "eski", "sonuclar": []})
    cache.gecersiz_kil()
    cache.kaydet("yeni", 10, {"sorgu": "yeni", "sonuclar": []})

    assert cache.getir("eski", 10) is None
    assert cache.getir("yeni", 10) is not None


def test_ttl_ayarlanir(cache: AramaCache) -> None:
    cache.kaydet("kedi", 10, {"sorgu": "kedi", "sonuclar": []})
    ttl = cache._redis.ttl(cache._anahtar("kedi", 10))
    assert 0 < ttl <= 300
