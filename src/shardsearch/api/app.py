"""FastAPI sarmalayıcı — Faz 8: gerçek dağıtık arama.

Akış:
  POST /index -> TutarliHash.shard_bul() ile doğru shard bulunur,
                 sadece o shard'ın SqliteTersIndeks'ine yazılır.
  GET  /search?q=...
      -> dagitik_ara(): tüm shard'lara paralel (asyncio.to_thread) sorgu,
         her shard kendi yerel BM25 skorunu hesaplar, sonuçlar global
         olarak birleştirilip sıralanır (bkz. shardsearch.distributed.fan_out)
      -> her sonuç için metin, TutarliHash ile doğru shard'a tekrar
         yönlendirilip o shard'dan okunur (belge tam olarak bir shard'da
         yaşıyor, arama sonucu "hangi shard'da" bilgisini taşımasa da
         TutarliHash deterministik olduğu için aynı sonucu tekrar üretir)

Shard sayısı ve kimlikleri `config/shards.json`'dan (Faz 7) statik olarak
yükleniyor. Her shard kendi SQLite dosyasında yaşıyor (`data/<shard_id>.db`).
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query

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


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    veri_dizini = Path(os.environ.get("SHARDSEARCH_DATA_DIR", _VARSAYILAN_VERI_DIZINI))
    veri_dizini.mkdir(parents=True, exist_ok=True)

    shard_idler = shardlari_yukle()
    app.state.shardlar = {
        shard_id: SqliteTersIndeks(veri_dizini / f"{shard_id}.db") for shard_id in shard_idler
    }
    app.state.tutarli_hash = TutarliHash(shard_idler)
    yield
    for indeks in app.state.shardlar.values():
        indeks.kapat()


app = FastAPI(title="ShardSearch", lifespan=_lifespan)


@app.post("/index", response_model=BelgeEkleYaniti, status_code=201)
def belge_ekle(istek: BelgeEkleIstegi) -> BelgeEkleYaniti:
    shard_id = app.state.tutarli_hash.shard_bul(istek.belge_id)
    app.state.shardlar[shard_id].belge_ekle(istek.belge_id, istek.metin)
    return BelgeEkleYaniti(belge_id=istek.belge_id, durum="eklendi")


@app.get("/search", response_model=AramaYaniti)
async def ara(q: str, limit: int = Query(default=10, gt=0)) -> AramaYaniti:
    try:
        sonuc = await dagitik_ara(app.state.shardlar, q, limit)
    except SorguHatasi as hata:
        raise HTTPException(status_code=400, detail=str(hata)) from hata

    sonuclar = []
    for belge_id, skor in sonuc.sonuclar:
        shard_id = app.state.tutarli_hash.shard_bul(belge_id)
        metin = app.state.shardlar[shard_id].belge_metni(belge_id)
        sonuclar.append(AramaSonucu(belge_id=belge_id, skor=skor, metin=metin))

    return AramaYaniti(sorgu=q, sonuclar=sonuclar, basarisiz_shardlar=sonuc.basarisiz_shardlar)
