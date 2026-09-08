"""Ters indeksin SQLite üzerinde kalıcı hali.

TersIndeks (Faz 2) ile BİREBİR AYNI metot yüzeyini sunar (belge_ekle,
postings_getir, belge_sayisi, belge_uzunlugu, ortalama_belge_uzunlugu) —
tek fark, veri bellekte bir dict'te değil diskte üç tabloda tutuluyor.
Resmi bir Protocol/ABC tanımlanmadı; şimdilik duck-typing yeterli, iki
backend'i gerçekten birbirinin yerine geçirmemiz gereken bir faza
gelince (muhtemelen Faz 6/7) formalleştiririz.

Şema:
- belgeler(belge_id PK, uzunluk): her belgenin token sayısı.
- postings(token, belge_id, frekans, pozisyonlar), PK(token, belge_id):
  bu birincil anahtar aynı zamanda (token, belge_id) sırasıyla bir index
  oluşturur, bu yüzden "WHERE token=? ORDER BY belge_id" sorgusu ekstra
  sıralama yapmadan index taramasıyla zaten sıralı döner — bellek içi
  versiyondaki bisect'in SQLite karşılığı.
- meta(id=0 tek satır, toplam_belge_sayisi, toplam_belge_uzunlugu): bu
  olmasa belge_sayisi()/ortalama_belge_uzunlugu() her çağrıda COUNT(*)/
  SUM(uzunluk) ile tüm belgeler tablosunu taramak zorunda kalırdı — Faz
  3'te bilinçli kaçındığımız O(n) hesaplamaya SQLite'ta geri dönmüş
  oluruz. Bunun yerine her belge_ekle/upsert'te aynı transaction içinde
  bu tek satır artımlı güncellenir, okuma O(1) kalır.
"""

import json
import sqlite3
from pathlib import Path

from shardsearch.index.postings import Posting
from shardsearch.tokenizer import tokenize

_SEMA = """
CREATE TABLE IF NOT EXISTS belgeler (
    belge_id TEXT PRIMARY KEY,
    uzunluk INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS postings (
    token TEXT NOT NULL,
    belge_id TEXT NOT NULL,
    frekans INTEGER NOT NULL,
    pozisyonlar TEXT NOT NULL,
    PRIMARY KEY (token, belge_id)
);

-- (token, belge_id) birincil anahtarı sadece token'la başlayan aramalarda
-- (WHERE token=?) verimlidir — bir index, sütunlarının SOLDAN itibaren
-- sıralı bir ön ekiyle arama yapıldığında kullanılabilir. belge_id TEK
-- BAŞINA aranırken (upsert sırasında "bu belgenin tüm postings'lerini
-- sil" için) o composite index işe yaramaz, SQLite tüm postings
-- tablosunu taramak zorunda kalır. Bu yüzden belge_id üzerinde ayrı bir
-- index gerekiyor — bellek içi versiyondaki _belge_tokenlari haritasının
-- (orada Python dict, burada SQLite index) aynı amaca hizmet eden karşılığı.
CREATE INDEX IF NOT EXISTS idx_postings_belge_id ON postings (belge_id);

CREATE TABLE IF NOT EXISTS meta (
    id INTEGER PRIMARY KEY CHECK (id = 0),
    toplam_belge_sayisi INTEGER NOT NULL,
    toplam_belge_uzunlugu INTEGER NOT NULL
);
"""


class SqliteTersIndeks:
    def __init__(self, veritabani_yolu: str | Path) -> None:
        self._conn = sqlite3.connect(veritabani_yolu)
        self._conn.executescript(_SEMA)
        self._conn.execute(
            "INSERT OR IGNORE INTO meta (id, toplam_belge_sayisi, toplam_belge_uzunlugu) "
            "VALUES (0, 0, 0)"
        )
        self._conn.commit()

    def belge_ekle(self, belge_id: str, metin: str) -> None:
        with self._conn:
            var_mi = self._conn.execute(
                "SELECT 1 FROM belgeler WHERE belge_id = ?", (belge_id,)
            ).fetchone()
            if var_mi is not None:
                self._belgeyi_sil(belge_id)

            tokenler = tokenize(metin)
            pozisyonlar_by_token: dict[str, list[int]] = {}
            for pozisyon, token in enumerate(tokenler):
                pozisyonlar_by_token.setdefault(token, []).append(pozisyon)

            self._conn.execute(
                "INSERT INTO belgeler (belge_id, uzunluk) VALUES (?, ?)",
                (belge_id, len(tokenler)),
            )
            self._conn.executemany(
                "INSERT INTO postings (token, belge_id, frekans, pozisyonlar) "
                "VALUES (?, ?, ?, ?)",
                [
                    (token, belge_id, len(pozisyonlar), json.dumps(pozisyonlar))
                    for token, pozisyonlar in pozisyonlar_by_token.items()
                ],
            )
            self._meta_guncelle(sayisi_delta=1, uzunluk_delta=len(tokenler))

    def _belgeyi_sil(self, belge_id: str) -> None:
        eski_uzunluk = self._conn.execute(
            "SELECT uzunluk FROM belgeler WHERE belge_id = ?", (belge_id,)
        ).fetchone()[0]
        self._conn.execute("DELETE FROM postings WHERE belge_id = ?", (belge_id,))
        self._conn.execute("DELETE FROM belgeler WHERE belge_id = ?", (belge_id,))
        self._meta_guncelle(sayisi_delta=-1, uzunluk_delta=-eski_uzunluk)

    def _meta_guncelle(self, sayisi_delta: int, uzunluk_delta: int) -> None:
        self._conn.execute(
            "UPDATE meta SET toplam_belge_sayisi = toplam_belge_sayisi + ?, "
            "toplam_belge_uzunlugu = toplam_belge_uzunlugu + ? WHERE id = 0",
            (sayisi_delta, uzunluk_delta),
        )

    def postings_getir(self, token: str) -> list[Posting]:
        satirlar = self._conn.execute(
            "SELECT belge_id, frekans, pozisyonlar FROM postings "
            "WHERE token = ? ORDER BY belge_id",
            (token,),
        ).fetchall()
        return [
            Posting(belge_id, frekans, json.loads(pozisyonlar))
            for belge_id, frekans, pozisyonlar in satirlar
        ]

    def belge_sayisi(self) -> int:
        (deger,) = self._conn.execute(
            "SELECT toplam_belge_sayisi FROM meta WHERE id = 0"
        ).fetchone()
        return deger

    def belge_uzunlugu(self, belge_id: str) -> int:
        satir = self._conn.execute(
            "SELECT uzunluk FROM belgeler WHERE belge_id = ?", (belge_id,)
        ).fetchone()
        if satir is None:
            raise KeyError(belge_id)
        return satir[0]

    def ortalama_belge_uzunlugu(self) -> float:
        sayisi, uzunluk = self._conn.execute(
            "SELECT toplam_belge_sayisi, toplam_belge_uzunlugu FROM meta WHERE id = 0"
        ).fetchone()
        if sayisi == 0:
            return 0.0
        return uzunluk / sayisi

    def kapat(self) -> None:
        self._conn.close()
