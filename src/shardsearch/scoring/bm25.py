"""BM25 sıralama algoritması — sıfırdan implementasyon.

Formülün her parçası (TF, IDF, uzunluk normalizasyonu, tekil terim skoru)
ayrı fonksiyon olarak tutuluyor ki her biri bağımsız test edilebilsin.

IDF için klasik Robertson-Sparck Jones formülü (ln((N-n+0.5)/(n+0.5)))
bir terim belgelerin yarısından fazlasında geçtiğinde negatif değer
üretebilir; `rank_bm25` kütüphanesi bunu sonradan bir epsilon ile
yamalıyor. Biz bunun yerine baştan pozitif garanti eden
ln(1 + (N-n+0.5)/(n+0.5)) varyantını kullanıyoruz. Bu yüzden
tests/validation/'daki karşılaştırma SAYISAL SKOR eşitliği değil,
SIRALAMA tutarlılığı arıyor (bkz. o dosyadaki not).
"""

import math

from shardsearch.index import TersIndeks
from shardsearch.tokenizer import tokenize

K1_VARSAYILAN = 1.5
B_VARSAYILAN = 0.75


def terim_frekansi(indeks: TersIndeks, token: str, belge_id: str) -> int:
    for posting in indeks.postings_getir(token):
        if posting.belge_id == belge_id:
            return posting.frekans
    return 0


def ters_belge_frekansi(indeks: TersIndeks, token: str) -> float:
    n = len(indeks.postings_getir(token))
    N = indeks.belge_sayisi()
    return math.log(1 + (N - n + 0.5) / (n + 0.5))


def uzunluk_normalizasyonu(
    belge_uzunlugu: int, ortalama_belge_uzunlugu: float, b: float = B_VARSAYILAN
) -> float:
    if ortalama_belge_uzunlugu == 0:
        return 1 - b
    return 1 - b + b * (belge_uzunlugu / ortalama_belge_uzunlugu)


def bm25_terim_skoru(tf: int, idf: float, norm: float, k1: float = K1_VARSAYILAN) -> float:
    return idf * (tf * (k1 + 1)) / (tf + k1 * norm)


def bm25_skoru(
    indeks: TersIndeks,
    sorgu_tokenlari: list[str],
    belge_id: str,
    k1: float = K1_VARSAYILAN,
    b: float = B_VARSAYILAN,
) -> float:
    norm = uzunluk_normalizasyonu(
        indeks.belge_uzunlugu(belge_id), indeks.ortalama_belge_uzunlugu(), b
    )

    toplam = 0.0
    for token in sorgu_tokenlari:
        tf = terim_frekansi(indeks, token, belge_id)
        if tf == 0:
            continue
        idf = ters_belge_frekansi(indeks, token)
        toplam += bm25_terim_skoru(tf, idf, norm, k1)
    return toplam


def sirala(
    indeks: TersIndeks, sorgu: str, k1: float = K1_VARSAYILAN, b: float = B_VARSAYILAN
) -> list[tuple[str, float]]:
    """Sorguyla en az bir ortak token'ı olan belgeleri BM25 skoruna göre
    azalan sırada döner. Hiçbir sorgu token'ını içermeyen belgeler skoru
    sıfır olacağından listeye hiç girmez.

    Eşit skorlu belgeler belge_id'ye göre artan sırada gelir. Adaylar bir
    `set`'ten toplandığı için doğal iterasyon sırası tanımsızdır — ikincil
    sıralama anahtarı olmadan eşit skorlarda sonuç, hash sırasına göre
    keyfi (ve run'dan run'a öngörülemez) olurdu.
    """
    sorgu_tokenlari = tokenize(sorgu)

    ilgili_belgeler: set[str] = set()
    for token in sorgu_tokenlari:
        for posting in indeks.postings_getir(token):
            ilgili_belgeler.add(posting.belge_id)

    skorlar = [
        (belge_id, bm25_skoru(indeks, sorgu_tokenlari, belge_id, k1, b))
        for belge_id in ilgili_belgeler
    ]
    skorlar.sort(key=lambda cift: (-cift[1], cift[0]))
    return skorlar
