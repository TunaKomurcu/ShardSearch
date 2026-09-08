"""Faz 5 testleri: ayrıştırma ağacı bir ters indekse karşı doğru
belge_id kümesini üretiyor mu — özellikle ifade (phrase) eşleştirmesinin
gerçekten ARDIŞIKLIK aradığını (sadece "kelimeler aynı belgede geçiyor"
değil) doğrulayan negatif bir test dahil.
"""

from shardsearch.index import TersIndeks
from shardsearch.query import ayristir, degerlendir


def _test_indeksi() -> TersIndeks:
    indeks = TersIndeks()
    indeks.belge_ekle("d01", "kedi köpek ile oynuyor")  # "kedi köpek" bitişik
    indeks.belge_ekle("d02", "köpek ve kedi parkta yürüyor")  # ikisi de var, bitişik DEĞİL
    indeks.belge_ekle("d03", "balık havuzda yüzüyor")  # ne kedi ne köpek
    indeks.belge_ekle("d04", "kedi uyuyor, köpek de uyuyor")  # ikisi de var, bitişik değil
    indeks.belge_ekle("d05", "kuş ve kedi köpek üçü de bahçede")  # "kedi köpek" bitişik
    return indeks


def test_terim_eslesen_belgeleri_dondurur() -> None:
    indeks = _test_indeksi()
    assert degerlendir(ayristir("kedi"), indeks) == {"d01", "d02", "d04", "d05"}


def test_ve_kesisim_alir() -> None:
    indeks = _test_indeksi()
    # "kedi" ve "balık" hiçbir belgede birlikte geçmiyor
    assert degerlendir(ayristir("kedi AND balık"), indeks) == set()
    # "kedi" ve "köpek" d01, d02, d04, d05'te birlikte geçiyor
    assert degerlendir(ayristir("kedi AND köpek"), indeks) == {"d01", "d02", "d04", "d05"}


def test_veya_birlesim_alir() -> None:
    indeks = _test_indeksi()
    assert degerlendir(ayristir("balık OR kuş"), indeks) == {"d03", "d05"}


def test_ifade_sadece_ardisik_gectigi_belgelerde_eslesir() -> None:
    indeks = _test_indeksi()
    # "kedi" ve "köpek" d01,d02,d04,d05'te birlikte geçiyor ama SADECE
    # d01 ve d05'te birbirine BİTİŞİK geçiyor. d02/d04'te aralarında başka
    # kelimeler var — ifade eşleşmesi bunları elemeli.
    assert degerlendir(ayristir('"kedi köpek"'), indeks) == {"d01", "d05"}


def test_ifade_hicbir_yerde_ardisik_gecmiyorsa_bos() -> None:
    indeks = _test_indeksi()
    assert degerlendir(ayristir('"köpek kedi"'), indeks) == set()


def test_ifade_bilinmeyen_kelime_icerirse_bos() -> None:
    indeks = _test_indeksi()
    assert degerlendir(ayristir('"kedi olmayankelime"'), indeks) == set()


def test_parantezli_karmasik_sorgu() -> None:
    indeks = _test_indeksi()
    # "kedi köpek" (bitişik) OR balık -> d01, d05, d03
    beklenen = {"d01", "d05", "d03"}
    assert degerlendir(ayristir('"kedi köpek" OR balık'), indeks) == beklenen


def test_ve_oncelik_or_dan_once_uygulanir() -> None:
    indeks = _test_indeksi()
    # "kedi AND köpek OR balık" -> (kedi AND köpek) OR balık
    # kedi AND köpek (kesişim, ardışıklık aranmaz) = {d01,d02,d04,d05}, OR balık {d03}
    beklenen = {"d01", "d02", "d03", "d04", "d05"}
    assert degerlendir(ayristir("kedi AND köpek OR balık"), indeks) == beklenen
