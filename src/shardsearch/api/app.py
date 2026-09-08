"""FastAPI sarmalayıcı — Faz 6 MVP.

Akış:
  POST /index -> SqliteTersIndeks.belge_ekle()
  GET  /search?q=...
      -> ayristir()      : sorgu metnini AST'ye çevirir
      -> degerlendir()   : AST + indeks -> eşleşen belge_id kümesi (AND/OR/phrase)
      -> terimleri_topla(): AST -> BM25 için düz kelime listesi
      -> bm25_skoru()    : her aday belge için skor
      -> azalan skora göre sıralanmış sonuç listesi

Kalıcı depolama olarak SqliteTersIndeks kullanılıyor — SPEC.md'nin mimari
diyagramında zaten böyle tanımlı (Ters İndeks Kurucu -> SQLite), yeni bir
karar değil, orada verilmiş kararın uygulanması. Tek bir paylaşılan
bağlantı `lifespan` ile açılıp kapatılıyor; thread-safety detayları için
bkz. SqliteTersIndeks'in docstring'i.
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query

from shardsearch.api.semalar import (
    AramaSonucu,
    AramaYaniti,
    BelgeEkleIstegi,
    BelgeEkleYaniti,
)
from shardsearch.query import SorguHatasi, ayristir, degerlendir, terimleri_topla
from shardsearch.scoring.bm25 import bm25_skoru
from shardsearch.storage import SqliteTersIndeks

_VARSAYILAN_VERITABANI_YOLU = "data/index.db"


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    veritabani_yolu = os.environ.get("SHARDSEARCH_DB_PATH", _VARSAYILAN_VERITABANI_YOLU)
    app.state.indeks = SqliteTersIndeks(veritabani_yolu)
    yield
    app.state.indeks.kapat()


app = FastAPI(title="ShardSearch", lifespan=_lifespan)


@app.post("/index", response_model=BelgeEkleYaniti, status_code=201)
def belge_ekle(istek: BelgeEkleIstegi) -> BelgeEkleYaniti:
    app.state.indeks.belge_ekle(istek.belge_id, istek.metin)
    return BelgeEkleYaniti(belge_id=istek.belge_id, durum="eklendi")


@app.get("/search", response_model=AramaYaniti)
def ara(q: str, limit: int = Query(default=10, gt=0)) -> AramaYaniti:
    indeks = app.state.indeks
    try:
        agac = ayristir(q)
    except SorguHatasi as hata:
        raise HTTPException(status_code=400, detail=str(hata)) from hata

    aday_belgeler = degerlendir(agac, indeks)
    sorgu_terimleri = terimleri_topla(agac)

    skorlar = [
        (belge_id, bm25_skoru(indeks, sorgu_terimleri, belge_id)) for belge_id in aday_belgeler
    ]
    skorlar.sort(key=lambda cift: (-cift[1], cift[0]))

    sonuclar = [
        AramaSonucu(belge_id=belge_id, skor=skor, metin=indeks.belge_metni(belge_id))
        for belge_id, skor in skorlar[:limit]
    ]
    return AramaYaniti(sorgu=q, sonuclar=sonuclar)
