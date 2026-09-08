"""Faz 5 testleri: sorgu dizgisi doğru ayrıştırma ağacına çevriliyor mu.

Öncelik kuralı: AND, OR'dan daha sıkı bağlanır — "a AND b OR c" her zaman
"(a AND b) OR c" olmalı, "a AND (b OR c)" DEĞİL. Bu SQL/genel programlama
dili kuralıyla tutarlı, kullanıcı için en az şaşırtıcı seçenek.
"""

import pytest

from shardsearch.query import Ifade, SorguHatasi, Terim, Ve, Veya, ayristir


def test_tek_terim() -> None:
    assert ayristir("kedi") == Terim("kedi")


def test_ve_ifadesi() -> None:
    assert ayristir("kedi AND köpek") == Ve(Terim("kedi"), Terim("köpek"))


def test_veya_ifadesi() -> None:
    assert ayristir("kedi OR köpek") == Veya(Terim("kedi"), Terim("köpek"))


def test_and_or_kucuk_harfle_de_calisir() -> None:
    assert ayristir("kedi and köpek") == Ve(Terim("kedi"), Terim("köpek"))
    assert ayristir("kedi or köpek") == Veya(Terim("kedi"), Terim("köpek"))


def test_oncelik_and_or_dan_once_degerlendirilir() -> None:
    # "a AND b OR c" -> "(a AND b) OR c" — AND daha sıkı bağlanır.
    beklenen = Veya(Ve(Terim("a"), Terim("b")), Terim("c"))
    assert ayristir("a AND b OR c") == beklenen


def test_oncelik_diger_taraftan_da_gecerli() -> None:
    # "a OR b AND c" -> "a OR (b AND c)" — aynı kuralın simetrik sonucu.
    beklenen = Veya(Terim("a"), Ve(Terim("b"), Terim("c")))
    assert ayristir("a OR b AND c") == beklenen


def test_parantez_onceligi_degistirebilir() -> None:
    beklenen = Ve(Terim("a"), Veya(Terim("b"), Terim("c")))
    assert ayristir("a AND (b OR c)") == beklenen


def test_ic_ice_parantez() -> None:
    beklenen = Veya(Ve(Terim("a"), Terim("b")), Ve(Terim("c"), Terim("d")))
    assert ayristir("(a AND b) OR (c AND d)") == beklenen


def test_ifade_ayristirma() -> None:
    assert ayristir('"kedi köpek"') == Ifade(("kedi", "köpek"))


def test_ifade_turkce_normalize_edilir() -> None:
    # İfade içeriği de tokenize() ile geçiyor: Türkçe İ/ı ve noktalama kuralı
    assert ayristir('"İstanbul, Ankara"') == Ifade(("istanbul", "ankara"))


def test_ifade_ve_terim_birlikte() -> None:
    beklenen = Ve(Ifade(("kedi", "köpek")), Terim("balık"))
    assert ayristir('"kedi köpek" AND balık') == beklenen


def test_terim_turkce_normalize_edilir() -> None:
    assert ayristir("İSTANBUL") == Terim("istanbul")


def test_karmasik_sorgu() -> None:
    # "a AND b OR "c d" AND (e OR f)"
    # -> (a AND b) OR ("c d" AND (e OR f))
    beklenen = Veya(
        Ve(Terim("a"), Terim("b")),
        Ve(Ifade(("c", "d")), Veya(Terim("e"), Terim("f"))),
    )
    assert ayristir('a AND b OR "c d" AND (e OR f)') == beklenen


@pytest.mark.parametrize(
    "sorgu",
    [
        "kedi köpek",  # operatörsüz yan yana yazım — bilinçli olarak desteklenmiyor
        "kedi AND",  # eksik ikinci terim
        "AND kedi",  # eksik ilk terim
        "(kedi AND köpek",  # kapanmamış parantez
        "kedi AND köpek)",  # fazladan kapanış parantezi
        "",  # boş sorgu
        "   ",  # sadece boşluk
    ],
)
def test_gecersiz_sorgular_hata_verir(sorgu: str) -> None:
    with pytest.raises(SorguHatasi):
        ayristir(sorgu)
