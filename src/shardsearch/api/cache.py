"""Faz 9: Redis ile cache-aside deseni.

Redis, SPEC.md'de "hazır araç kullan" olarak işaretli (cache mekanizması
ayrı bir derste zaten işlendi, sıfırdan yazılmayacak) — burada sadece
redis-py istemcisi kullanılıyor, Redis'in kendisi sıfırdan yazılmıyor.

Cache anahtarı NEDEN bir "kuşak" (generation) sayacı içeriyor: BM25'in
IDF'i ve ortalama belge uzunluğu TÜM korpusa bağlı istatistiklerdir —
yeni bir belge eklendiğinde, o belgeyle hiç ilgisi olmayan bir sorgunun
bile skorları teorik olarak değişebilir (global N ve avgdl değişti). Bu
yüzden "hangi cache girdileri bu yeni belgeden etkilendi" sorusunun kesin
bir cevabı yok — pratikte TÜM cache'i geçersiz kılmak gerekiyor. Bunu tek
tek anahtar silerek (Redis'in KEYS/SCAN komutlarıyla, O(n) ve prod'da
riskli — tüm anahtar uzayını tarar) yapmak yerine, bir kuşak sayacı
kullanıyoruz: her yazmada bu sayaç 1 artırılır ve cache anahtarına dahil
edilir. Sayaç değişince eski anahtarlar otomatik "görünmez" olur (bir
daha hiç okunmaz), TTL ile zamanla kendiliğinden silinirler. O(1) bir
invalidation — tek bir INCR.

Redis ERİŞİLEMEZSE arama ÇÖKMEMELİ: cache bir optimizasyon, kritik yol
değil. Bu yüzden tüm Redis çağrıları RedisError'ı yakalayıp yutuyor —
çağıran taraf (app.py) her zaman "cache yok" (None / no-op) muamelesi
görür, asla bir istisna sızmaz.
"""

import json
from typing import Any

import redis

_TTL_SANIYE = 300  # DoD "ölçülebilir hızlanma" için yeterli; uzun tutmaya gerek yok
_KUSAK_ANAHTARI = "arama:kusak"


class AramaCache:
    def __init__(self, redis_istemcisi: redis.Redis) -> None:
        self._redis = redis_istemcisi

    def _kusak(self) -> int:
        try:
            deger = self._redis.get(_KUSAK_ANAHTARI)
        except redis.exceptions.RedisError:
            return 0
        return int(deger) if deger is not None else 0

    def _anahtar(self, sorgu: str, limit: int) -> str:
        return f"arama:v{self._kusak()}:{sorgu}:{limit}"

    def getir(self, sorgu: str, limit: int) -> dict[str, Any] | None:
        try:
            ham = self._redis.get(self._anahtar(sorgu, limit))
        except redis.exceptions.RedisError:
            return None
        if ham is None:
            return None
        return json.loads(ham)

    def kaydet(self, sorgu: str, limit: int, sonuc: dict[str, Any]) -> None:
        try:
            self._redis.set(self._anahtar(sorgu, limit), json.dumps(sonuc), ex=_TTL_SANIYE)
        except redis.exceptions.RedisError:
            pass

    def gecersiz_kil(self) -> None:
        """Yeni bir belge eklendiğinde çağrılır — kuşak sayacını artırarak
        TÜM önceki cache girdilerini tek seferde (O(1)) geçersiz kılar.
        """
        try:
            self._redis.incr(_KUSAK_ANAHTARI)
        except redis.exceptions.RedisError:
            pass
