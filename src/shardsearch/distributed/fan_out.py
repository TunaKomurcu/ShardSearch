"""Çoklu shard üzerinde paralel arama (fan-out) + sonuç birleştirme.

sqlite3 senkron/bloklayan bir kütüphanedir, native asyncio desteği yoktur.
Bu yüzden her shard sorgusu `asyncio.to_thread()` ile ayrı bir thread'e
devrediliyor — sadece `async def` yazıp `await` etmek yetmez: gerçek
paralellik, bloklayan I/O'nun bir thread pool'a devredilmesiyle gelir.
`asyncio.to_thread()` olmasaydı `asyncio.gather` yine de shard'ları
SIRAYLA sorgulardı, çünkü hiçbiri event loop'u bırakacak bir `await`
noktası içermezdi.

IDF her shard'da YEREL hesaplanıyor (bkz. shardsearch.scoring.bm25) —
Elasticsearch'ün varsayılan davranışı ile aynı, global istatistik toplamak
için ikinci bir round-trip yok. Bu, tek-node sonuçlarından küçük
sapmalara yol açabilir. GÖZLEM (bkz. tests/unit/test_fan_out.py'deki
kasıtlı dengesiz dağıtım testi): sapmanın büyüklüğü shard'lar arası TERİM
DAĞILIMININ dengesine bağlı — bir terimi içeren belgelerin çoğu tek bir
shard'da toplanmışsa (doğal consistent-hashing dağılımında beklenmez ama
küçük korpuslarda ya da kötü şanslı hash dağılımında olabilir), o
shard'ın yerel N'i küçük olduğu için terimin yerel IDF'si global IDF'den
belirgin şekilde sapar. Büyük, terim dağılımı dengeli korpuslarda bu etki
küçülür (büyük sayılar yasası).

Hata toleransı: bir shard sorgu sırasında hata verirse (bağlantı sorunu,
vb.) TÜM arama başarısız olmaz — o shard'ın belgeleri sonuçtan SESSİZCE
DEĞİL, `basarisiz_shardlar` listesinde AÇIKÇA raporlanarak düşer. Yani bu
istemciye "az sonuç ama neden az olduğu bilinmiyor" değil, "şu shard(lar)
cevap veremedi" bilgisini taşıyan kısmi bir sonuçtur.
"""

import asyncio
from dataclasses import dataclass, field

from shardsearch.query import ayristir, degerlendir, terimleri_topla
from shardsearch.query.ast import SorguDugumu
from shardsearch.scoring.bm25 import bm25_skoru
from shardsearch.storage import SqliteTersIndeks


@dataclass
class DagitikSonuc:
    sonuclar: list[tuple[str, float]]
    basarisiz_shardlar: list[str] = field(default_factory=list)


def _shard_sorgula(
    indeks: SqliteTersIndeks, agac: SorguDugumu, sorgu_terimleri: list[str]
) -> list[tuple[str, float]]:
    """Tek bir shard'da SENKRON sorgulama — asyncio.to_thread ile çağrılır."""
    aday_belgeler = degerlendir(agac, indeks)
    return [
        (belge_id, bm25_skoru(indeks, sorgu_terimleri, belge_id)) for belge_id in aday_belgeler
    ]


async def _shard_sorgula_guvenli(
    shard_id: str, indeks: SqliteTersIndeks, agac: SorguDugumu, sorgu_terimleri: list[str]
) -> tuple[str, list[tuple[str, float]], Exception | None]:
    try:
        sonuc = await asyncio.to_thread(_shard_sorgula, indeks, agac, sorgu_terimleri)
        return shard_id, sonuc, None
    except Exception as hata:  # kasıtlı geniş yakalama: hangi hata olursa olsun
        # bu shard'ı "başarısız" say, diğer shard'ların sonucunu etkilemesin.
        return shard_id, [], hata


async def dagitik_ara(
    shardlar: dict[str, SqliteTersIndeks], sorgu: str, limit: int = 10
) -> DagitikSonuc:
    """`sorgu`yu tüm shard'lara paralel gönderir, sonuçları global BM25
    skoruna göre birleştirip azalan sırada `limit` kadar döner.

    `ayristir()` burada bilerek sadece BİR KEZ çağrılıyor (her shard için
    değil) — sorgu ayrıştırma hatası (SorguHatasi) shard'lardan bağımsız
    bir istemci hatasıdır, çağıran (API route) bunu normal şekilde
    yakalayabilsin diye burada yutulmuyor.
    """
    agac = ayristir(sorgu)
    sorgu_terimleri = terimleri_topla(agac)

    gorevler = [
        _shard_sorgula_guvenli(shard_id, indeks, agac, sorgu_terimleri)
        for shard_id, indeks in shardlar.items()
    ]
    sonuclar_ham = await asyncio.gather(*gorevler)

    tum_sonuclar: list[tuple[str, float]] = []
    basarisiz_shardlar: list[str] = []
    for shard_id, sonuc, hata in sonuclar_ham:
        if hata is not None:
            basarisiz_shardlar.append(shard_id)
            continue
        tum_sonuclar.extend(sonuc)

    tum_sonuclar.sort(key=lambda cift: (-cift[1], cift[0]))
    return DagitikSonuc(sonuclar=tum_sonuclar[:limit], basarisiz_shardlar=basarisiz_shardlar)
