"""Faz 3 testleri: BM25 formülünün her parçası ayrı ayrı doğrulanıyor.

Beklenen değerler, formül doğrudan burada (math.log ile) tekrar yazılarak
elle hesaplandı — src/scoring/bm25.py'deki fonksiyonları çağırıp
kendi kendine doğrulama (tautoloji) yapılmıyor.
"""

import math

import pytest

from shardsearch.index import TersIndeks
from shardsearch.scoring.bm25 import (
    bm25_skoru,
    bm25_terim_skoru,
    sirala,
    terim_frekansi,
    ters_belge_frekansi,
    uzunluk_normalizasyonu,
)


def _test_indeksi() -> TersIndeks:
    # a: 4 token, b: 3 token, c: 5 token -> toplam 12, ortalama 4.0
    indeks = TersIndeks()
    indeks.belge_ekle("a", "kedi kedi köpek hayvan")
    indeks.belge_ekle("b", "köpek kuş hayvan")
    indeks.belge_ekle("c", "kedi kuş balık balık hayvan")
    return indeks


@pytest.mark.parametrize(
    ("token", "belge_id", "beklenen"),
    [
        ("kedi", "a", 2),
        ("kedi", "b", 0),
        ("kedi", "c", 1),
        ("balık", "c", 2),
        ("hayvan", "a", 1),
        ("olmayankelime", "a", 0),
    ],
)
def test_terim_frekansi(token: str, belge_id: str, beklenen: int) -> None:
    assert terim_frekansi(_test_indeksi(), token, belge_id) == beklenen


@pytest.mark.parametrize(
    ("token", "beklenen_n"),
    [
        ("kedi", 2),  # a, c
        ("köpek", 2),  # a, b
        ("kuş", 2),  # b, c
        ("balık", 1),  # sadece c
        ("hayvan", 3),  # a, b, c
        ("olmayankelime", 0),  # hiçbir belgede yok
    ],
)
def test_ters_belge_frekansi(token: str, beklenen_n: int) -> None:
    N = 3
    beklenen = math.log(1 + (N - beklenen_n + 0.5) / (beklenen_n + 0.5))
    assert ters_belge_frekansi(_test_indeksi(), token) == pytest.approx(beklenen)


@pytest.mark.parametrize(
    ("uzunluk", "ortalama", "b", "beklenen"),
    [
        (4, 4.0, 0.75, 1.0),
        (3, 4.0, 0.75, 0.8125),
        (5, 4.0, 0.75, 1.1875),
        (0, 0.0, 0.75, 0.25),  # ortalama sıfırsa ZeroDivisionError yerine 1-b dönmeli
    ],
)
def test_uzunluk_normalizasyonu(
    uzunluk: int, ortalama: float, b: float, beklenen: float
) -> None:
    assert uzunluk_normalizasyonu(uzunluk, ortalama, b) == pytest.approx(beklenen)


def test_bm25_terim_skoru() -> None:
    # idf * (tf * (k1+1)) / (tf + k1*norm) = 0.5 * (2*2.5) / (2 + 1.5*1.0)
    assert bm25_terim_skoru(tf=2, idf=0.5, norm=1.0, k1=1.5) == pytest.approx(2.5 / 3.5)


def test_bm25_skoru_coklu_terim_toplanir() -> None:
    indeks = _test_indeksi()
    N = 3
    idf_kedi = math.log(1 + (N - 2 + 0.5) / (2 + 0.5))
    idf_hayvan = math.log(1 + (N - 3 + 0.5) / (3 + 0.5))
    norm_a = 1 - 0.75 + 0.75 * (4 / 4.0)  # a'nın uzunluğu (4) ortalamaya (4.0) eşit -> 1.0

    beklenen = idf_kedi * (2 * 2.5) / (2 + 1.5 * norm_a) + idf_hayvan * (1 * 2.5) / (
        1 + 1.5 * norm_a
    )

    assert bm25_skoru(indeks, ["kedi", "hayvan"], "a") == pytest.approx(beklenen)


def test_bm25_skoru_ortak_token_yoksa_sifir() -> None:
    indeks = _test_indeksi()
    assert bm25_skoru(indeks, ["olmayankelime"], "a") == 0.0


def test_sirala_sadece_ilgili_belgeleri_dogru_sirada_dondurur() -> None:
    indeks = _test_indeksi()

    skor_a = bm25_skoru(indeks, ["kedi"], "a")
    skor_c = bm25_skoru(indeks, ["kedi"], "c")
    beklenen_sira = sorted([("a", skor_a), ("c", skor_c)], key=lambda cift: cift[1], reverse=True)

    sonuc = sirala(indeks, "kedi")

    # "b" belgesinde "kedi" hiç geçmiyor, sonuçta hiç görünmemeli
    assert [belge_id for belge_id, _ in sonuc] == [belge_id for belge_id, _ in beklenen_sira]
    assert [skor for _, skor in sonuc] == pytest.approx([skor for _, skor in beklenen_sira])


def test_sirala_hic_eslesme_yoksa_bos_liste_doner() -> None:
    indeks = _test_indeksi()
    assert sirala(indeks, "olmayankelime") == []
