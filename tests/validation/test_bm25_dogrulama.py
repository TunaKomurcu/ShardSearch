"""Faz 3 doğrulama: BM25 sıralamamızın rank_bm25 ile karşılaştırılması.

ÖNEMLİ — burada karşılaştırılan şey SAYISAL SKOR eşitliği DEĞİL, SIRALAMA
tutarlılığıdır. Bizim ters_belge_frekansi() fonksiyonumuz her zaman pozitif
olan ln(1 + (N-n+0.5)/(n+0.5)) formülünü kullanıyor; rank_bm25'in
BM25Okapi sınıfı ise klasik Robertson-Sparck Jones formülünü
(ln((N-n+0.5)/(n+0.5))) kullanır ve negatif çıkan değerleri sonradan bir
epsilon ile düzeltir (bkz. src/shardsearch/scoring/bm25.py'deki not). Bu
formül farkı yüzünden mutlak skorlar örtüşmez — SPEC.md'nin aradığı şey
zaten bu değil: "ilk 5 sonucun aynı sırada olması ya da farkın
açıklanabilir olması" (bkz. PHASES.md Faz 3).

rank_bm25 SADECE bu dosyada, referans olarak kullanılıyor — src/ içine
asla girmiyor (bkz. test_rank_bm25_izolasyonu.py). Bu grup kurulu değilse
(`uv sync --group validation` çalıştırılmadıysa) test dosyası atlanır.
"""

import pytest

rank_bm25 = pytest.importorskip("rank_bm25")

from shardsearch.index import TersIndeks  # noqa: E402
from shardsearch.scoring.bm25 import sirala  # noqa: E402
from shardsearch.tokenizer import tokenize  # noqa: E402

# Faz 2'deki 12 belgelik korpusun aynısı — Faz 2'den beri elle doğrulanmış,
# yeni bir korpus icat etmeye gerek yok.
KORPUS = {
    "d01": "Kedi masada uyuyor, sonra kedi yere atladı.",
    "d02": "Köpek bahçede koşuyor.",
    "d03": "Kedi ve köpek birlikte oynuyor.",
    "d04": "Kuşlar gökyüzünde uçuyor.",
    "d05": "Balıklar denizde yüzüyor.",
    "d06": "Aslan çok güçlü bir hayvandır.",
    "d07": "Bugün sokakta bir kedi gördüm, kedi çok sevimliydi.",
    "d08": "Fil çok büyük bir hayvandır.",
    "d09": "Kuş kanat çırpıp uçtu.",
    "d10": "Kedi ve kuş bazen dost olabilir.",
    "d11": "Ayı kışın uyur.",
    "d12": "Tilki kurnaz bir hayvandır.",
}


def _kendi_indeksimiz() -> TersIndeks:
    indeks = TersIndeks()
    for belge_id, metin in KORPUS.items():
        indeks.belge_ekle(belge_id, metin)
    return indeks


def _rank_bm25_referansi() -> tuple[list[str], "rank_bm25.BM25Okapi"]:
    belge_idler = list(KORPUS)
    tokenlanmis = [tokenize(KORPUS[belge_id]) for belge_id in belge_idler]
    return belge_idler, rank_bm25.BM25Okapi(tokenlanmis)


@pytest.mark.parametrize(
    "sorgu",
    ["kedi", "hayvan", "kedi köpek", "kuş", "bir hayvandır"],
)
def test_siralama_rank_bm25_ile_tutarli(sorgu: str) -> None:
    bizim_sonuc = sirala(_kendi_indeksimiz(), sorgu)
    bizim_ilk_5 = [belge_id for belge_id, _ in bizim_sonuc[:5]]

    belge_idler, referans = _rank_bm25_referansi()
    referans_skorlari = referans.get_scores(tokenize(sorgu))
    referans_sirali = sorted(
        zip(belge_idler, referans_skorlari), key=lambda cift: cift[1], reverse=True
    )
    referans_ilk_5 = [belge_id for belge_id, skor in referans_sirali[:5] if skor > 0]

    assert bizim_ilk_5 == referans_ilk_5
