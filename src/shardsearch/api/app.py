"""FastAPI sarmalayıcı — Faz 10: yapılandırılmış log ile gözlemlenebilirlik.

Akış:
  POST /index -> TutarliHash.shard_bul() ile doğru shard bulunur,
                 sadece o shard'ın SqliteTersIndeks'ine yazılır, sonra
                 AramaCache.gecersiz_kil() ile TÜM arama cache'i geçersiz
                 kılınır (bkz. cache.py'deki "kuşak sayacı" açıklaması).
  GET  /search?q=...
      -> önce AramaCache.getir() ile cache kontrol edilir
      -> cache miss ise dagitik_ara(): tüm shard'lara paralel
         (asyncio.to_thread) sorgu, sonuçlar global olarak birleştirilir
      -> SADECE tüm shard'lar başarılıysa (basarisiz_shardlar boşsa)
         sonuç cache'e yazılır — bozuk bir shard'ın eksik sonucu kalıcı
         "doğru cevap" gibi önbelleğe düşmesin diye

Her istek, bir middleware tarafından JSON formatında loglanıyor (bkz.
logging_config.py) — süre, durum kodu, `/search` için ayrıca cache
hit/miss ve başarısız shard bilgisi. Percentile (p50/p95/p99) metrikleri
BURADA hesaplanmıyor — bu uygulamanın kendi metrik sistemini kurmak yerine
Locust'un kendi yük testi raporundan alınıyor (bkz. benchmarks/locustfile.py).

Shard sayısı ve kimlikleri `config/shards.json`'dan (Faz 7) statik olarak
yükleniyor. Her shard kendi SQLite dosyasında yaşıyor (`data/<shard_id>.db`).

`_redis_istemcisi_olustur()` bilerek ayrı bir fonksiyon: testler gerçek
Redis'e bağlanmak yerine bunu `monkeypatch` ile `fakeredis.FakeRedis`
döndürecek şekilde değiştiriyor (bkz. tests/unit/test_api.py) — `fakeredis`
bu dosyada asla import edilmiyor (bkz. test_fakeredis_izolasyonu.py).
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

from shardsearch.api.cache import AramaCache
from shardsearch.api.logging_config import LOGGER_ADI, istek_logla, logging_kur
from shardsearch.api.semalar import (
    AramaSonucu,
    AramaYaniti,
    BelgeEkleIstegi,
    BelgeEkleYaniti,
)
from shardsearch.distributed import dagitik_ara
from shardsearch.query import SorguHatasi
from shardsearch.sharding import TutarliHash, shardlari_yukle
from shardsearch.storage import SqliteTersIndeks

_VARSAYILAN_VERI_DIZINI = "data"
_VARSAYILAN_REDIS_URL = "redis://localhost:6379/0"

logging_kur()
_logger = logging.getLogger(LOGGER_ADI)


def _redis_istemcisi_olustur() -> redis.Redis:
    redis_url = os.environ.get("SHARDSEARCH_REDIS_URL", _VARSAYILAN_REDIS_URL)
    # Faz 10'da gerçek yük testinde bulundu: Redis erişilemezse (bağlantı
    # reddedilirse) redis-py'nin varsayılan davranışı bu ortamda ~4 saniye
    # sonra ConnectionError fırlatıyor — AramaCache bu hatayı yutuyor
    # (arama çökmüyor, Faz 9'un tasarımı doğru) ama her istek bu gizli
    # gecikmeyi ödüyor; /search bir cache-miss'te kuşak+değer+kaydet için
    # 3 AYRI Redis çağrısı yaptığından (bkz. cache.py) bu üç katına
    # çıkıyor. Kısa bir socket timeout (üretimde de yaygın bir değer),
    # "cache erişilemezse hızlıca vazgeç" davranışını GERÇEKTEN hızlı hale
    # getiriyor — Faz 9'un zaten vaat ettiği "kritik yol değil" ilkesinin
    # eksik kalan parçası.
    return redis.from_url(
        redis_url, decode_responses=True, socket_connect_timeout=0.2, socket_timeout=0.2
    )


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    veri_dizini = Path(os.environ.get("SHARDSEARCH_DATA_DIR", _VARSAYILAN_VERI_DIZINI))
    veri_dizini.mkdir(parents=True, exist_ok=True)

    shard_idler = shardlari_yukle()
    app.state.shardlar = {
        shard_id: SqliteTersIndeks(veri_dizini / f"{shard_id}.db") for shard_id in shard_idler
    }
    app.state.tutarli_hash = TutarliHash(shard_idler)
    app.state.cache = AramaCache(_redis_istemcisi_olustur())
    yield
    for indeks in app.state.shardlar.values():
        indeks.kapat()


app = FastAPI(title="ShardSearch", lifespan=_lifespan)


@app.middleware("http")
async def _log_middleware(request: Request, call_next):
    baslangic = time.perf_counter()
    yanit = await call_next(request)
    sure_ms = (time.perf_counter() - baslangic) * 1000

    ekstra: dict[str, object] = {}
    if request.url.path == "/search":
        ekstra["sorgu"] = request.query_params.get("q")
        ekstra["limit"] = request.query_params.get("limit")
        ekstra["cache_hit"] = getattr(request.state, "cache_hit", None)
        ekstra["basarisiz_shardlar"] = getattr(request.state, "basarisiz_shardlar", None)

    istek_logla(
        _logger,
        endpoint=request.url.path,
        metod=request.method,
        sure_ms=sure_ms,
        durum_kodu=yanit.status_code,
        **ekstra,
    )
    return yanit


@app.post("/index", response_model=BelgeEkleYaniti, status_code=201)
async def belge_ekle(istek: BelgeEkleIstegi) -> BelgeEkleYaniti:
    # DENEY (Faz 10 sonrası performans soruşturması, bkz.
    # docs/known-limitations.md): önceden senkron (`def`) bir route'tu,
    # Starlette onu kendi anyio thread pool'unda çalıştırıyordu.
    # `dagitik_ara()` (fan_out.py) ise shard sorguları için AYRI bir
    # mekanizma (asyncio.to_thread, varsayılan asyncio executor)
    # kullanıyor. Bu route'u da async'e çevirip AYNI asyncio.to_thread
    # mekanizmasına taşımak, iki farklı thread pool'un çakışmasının
    # gerçek darboğaz nedeni olup olmadığını test ediyor.
    shard_id = app.state.tutarli_hash.shard_bul(istek.belge_id)
    await asyncio.to_thread(
        app.state.shardlar[shard_id].belge_ekle, istek.belge_id, istek.metin
    )
    await asyncio.to_thread(app.state.cache.gecersiz_kil)
    return BelgeEkleYaniti(belge_id=istek.belge_id, durum="eklendi")


@app.get("/search", response_model=AramaYaniti)
async def ara(request: Request, q: str, limit: int = Query(default=10, gt=0)) -> AramaYaniti:
    # DÜZELTME (Faz 10 sonrası performans soruşturması): bu route zaten
    # `async def`'ti ama cache.getir()/kaydet() DOĞRUDAN (senkron, hiç
    # to_thread'siz) çağrılıyordu — bu, tek event loop thread'ini Redis
    # çağrısı süresince BLOKE ediyordu, aynı anda başka HİÇBİR isteğin
    # işlenmesine izin vermeden. Bu muhtemelen kuyruk birikmesinin asıl
    # nedeniydi (thread pool çakışmasından daha doğrudan bir açıklama).
    onbellekteki = await asyncio.to_thread(app.state.cache.getir, q, limit)
    if onbellekteki is not None:
        request.state.cache_hit = True
        request.state.basarisiz_shardlar = []
        return AramaYaniti(**onbellekteki)

    request.state.cache_hit = False
    try:
        sonuc = await dagitik_ara(app.state.shardlar, q, limit)
    except SorguHatasi as hata:
        raise HTTPException(status_code=400, detail=str(hata)) from hata

    sonuclar = []
    for belge_id, skor in sonuc.sonuclar:
        shard_id = app.state.tutarli_hash.shard_bul(belge_id)
        metin = app.state.shardlar[shard_id].belge_metni(belge_id)
        sonuclar.append(AramaSonucu(belge_id=belge_id, skor=skor, metin=metin))

    yanit = AramaYaniti(sorgu=q, sonuclar=sonuclar, basarisiz_shardlar=sonuc.basarisiz_shardlar)
    request.state.basarisiz_shardlar = sonuc.basarisiz_shardlar

    if not yanit.basarisiz_shardlar:
        await asyncio.to_thread(app.state.cache.kaydet, q, limit, yanit.model_dump())

    return yanit
