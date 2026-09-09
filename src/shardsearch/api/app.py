"""FastAPI sarmalayıcı — Faz 9: cache-aside ile hızlandırılmış dağıtık arama.

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

Shard sayısı ve kimlikleri `config/shards.json`'dan (Faz 7) statik olarak
yükleniyor. Her shard kendi SQLite dosyasında yaşıyor (`data/<shard_id>.db`).

`_redis_istemcisi_olustur()` bilerek ayrı bir fonksiyon: testler gerçek
Redis'e bağlanmak yerine bunu `monkeypatch` ile `fakeredis.FakeRedis`
döndürecek şekilde değiştiriyor (bkz. tests/unit/test_api.py) — `fakeredis`
bu dosyada asla import edilmiyor (bkz. test_fakeredis_izolasyonu.py).
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import redis
from fastapi import FastAPI, HTTPException, Query

from shardsearch.api.cache import AramaCache
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


def _redis_istemcisi_olustur() -> redis.Redis:
    redis_url = os.environ.get("SHARDSEARCH_REDIS_URL", _VARSAYILAN_REDIS_URL)
    return redis.from_url(redis_url, decode_responses=True)


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


@app.post("/index", response_model=BelgeEkleYaniti, status_code=201)
def belge_ekle(istek: BelgeEkleIstegi) -> BelgeEkleYaniti:
    shard_id = app.state.tutarli_hash.shard_bul(istek.belge_id)
    app.state.shardlar[shard_id].belge_ekle(istek.belge_id, istek.metin)
    app.state.cache.gecersiz_kil()
    return BelgeEkleYaniti(belge_id=istek.belge_id, durum="eklendi")


@app.get("/search", response_model=AramaYaniti)
async def ara(q: str, limit: int = Query(default=10, gt=0)) -> AramaYaniti:
    onbellekteki = app.state.cache.getir(q, limit)
    if onbellekteki is not None:
        return AramaYaniti(**onbellekteki)

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

    if not yanit.basarisiz_shardlar:
        app.state.cache.kaydet(q, limit, yanit.model_dump())

    return yanit
