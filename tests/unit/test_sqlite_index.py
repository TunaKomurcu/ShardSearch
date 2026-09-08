"""Faz 4 testleri: SqliteTersIndeks, TersIndeks ile aynı davranışı SQLite
üzerinde tekrarlıyor mu — ve asıl DoD: bağlantı kapanıp yeniden açıldığında
veri bellekten değil diskten mi geliyor.

Davranış testleri (postings, upsert, bilinmeyen token, istatistikler)
Faz 2/3'teki TersIndeks testleriyle aynı korpus/beklentileri kullanır —
iki backend'in gerçekten aynı sözleşmeye uyduğunu göstermek için.
"""

import pytest

from shardsearch.index import Posting
from shardsearch.storage import SqliteTersIndeks


def _bellekte_indeks() -> SqliteTersIndeks:
    return SqliteTersIndeks(":memory:")


def test_postings_dogru_ve_belge_id_sirali() -> None:
    indeks = _bellekte_indeks()
    indeks.belge_ekle("d01", "Kedi masada uyuyor, sonra kedi yere atladı.")
    indeks.belge_ekle("d03", "Kedi ve köpek birlikte oynuyor.")
    indeks.belge_ekle("d07", "Bugün sokakta bir kedi gördüm, kedi çok sevimliydi.")
    indeks.belge_ekle("d10", "Kedi ve kuş bazen dost olabilir.")
    indeks.belge_ekle("d02", "Köpek bahçede koşuyor.")  # "kedi" içermiyor, gürültü

    assert indeks.postings_getir("kedi") == [
        Posting("d01", 2, [0, 4]),
        Posting("d03", 1, [0]),
        Posting("d07", 2, [3, 5]),
        Posting("d10", 1, [0]),
    ]


def test_bilinmeyen_token_bos_liste_doner() -> None:
    indeks = _bellekte_indeks()
    indeks.belge_ekle("d01", "Kedi masada uyuyor.")
    assert indeks.postings_getir("boyle_bir_kelime_yok") == []


def test_ayni_belge_id_ile_tekrar_ekleme_upsert_yapar() -> None:
    indeks = _bellekte_indeks()
    indeks.belge_ekle("up1", "Kedi köpek kuş.")

    assert indeks.postings_getir("kedi") == [Posting("up1", 1, [0])]
    assert indeks.postings_getir("köpek") == [Posting("up1", 1, [1])]

    indeks.belge_ekle("up1", "Kuş ve balık.")

    assert indeks.postings_getir("kedi") == []
    assert indeks.postings_getir("köpek") == []
    assert indeks.postings_getir("kuş") == [Posting("up1", 1, [0])]
    assert indeks.postings_getir("balık") == [Posting("up1", 1, [2])]


def test_belge_sayisi_ve_uzunluk_istatistikleri() -> None:
    indeks = _bellekte_indeks()
    assert indeks.belge_sayisi() == 0
    assert indeks.ortalama_belge_uzunlugu() == 0.0

    indeks.belge_ekle("x", "kedi kedi köpek")  # 3 token
    indeks.belge_ekle("y", "köpek kuş")  # 2 token
    indeks.belge_ekle("z", "kedi kuş balık balık hayvan")  # 5 token

    assert indeks.belge_sayisi() == 3
    assert indeks.belge_uzunlugu("x") == 3
    assert indeks.belge_uzunlugu("y") == 2
    assert indeks.belge_uzunlugu("z") == 5
    assert indeks.ortalama_belge_uzunlugu() == pytest.approx(10 / 3)

    indeks.belge_ekle("y", "köpek")  # 2 token -> 1 token
    assert indeks.belge_sayisi() == 3
    assert indeks.belge_uzunlugu("y") == 1
    assert indeks.ortalama_belge_uzunlugu() == pytest.approx(9 / 3)


def test_olmayan_belgenin_uzunlugu_keyerror_verir() -> None:
    indeks = _bellekte_indeks()
    with pytest.raises(KeyError):
        indeks.belge_uzunlugu("olmayan_belge")


def test_olmayan_belgenin_metni_keyerror_verir() -> None:
    indeks = _bellekte_indeks()
    with pytest.raises(KeyError):
        indeks.belge_metni("olmayan_belge")


def test_belge_metni_saklanir_ve_upsert_ile_guncellenir() -> None:
    indeks = _bellekte_indeks()
    indeks.belge_ekle("d01", "Kedi masada uyuyor.")
    assert indeks.belge_metni("d01") == "Kedi masada uyuyor."

    indeks.belge_ekle("d01", "Köpek bahçede koşuyor.")
    assert indeks.belge_metni("d01") == "Köpek bahçede koşuyor."


def test_disk_kalicidir_yeniden_baslatinca_bellekten_degil_diskten_yuklenir(tmp_path) -> None:
    veritabani_yolu = tmp_path / "test_indeks.db"

    # "Uygulama" ilk kez açılıyor, belgeleri indeksliyor, sonra kapanıyor.
    ilk_calistirma = SqliteTersIndeks(veritabani_yolu)
    ilk_calistirma.belge_ekle("d01", "Kedi masada uyuyor, sonra kedi yere atladı.")
    ilk_calistirma.belge_ekle("d02", "Köpek bahçede koşuyor.")
    ilk_calistirma.belge_ekle("d03", "Kedi ve köpek birlikte oynuyor.")
    ilk_calistirma.kapat()

    # "Uygulama" yeniden başlıyor — YENİ bir SqliteTersIndeks nesnesi, aynı
    # dosyayı açıyor. belge_ekle() BİR DAHA çağrılmıyor: veri gerçekten
    # diskten geliyorsa postings burada da doğru çıkmalı.
    ikinci_calistirma = SqliteTersIndeks(veritabani_yolu)

    assert ikinci_calistirma.postings_getir("kedi") == [
        Posting("d01", 2, [0, 4]),
        Posting("d03", 1, [0]),
    ]
    assert ikinci_calistirma.belge_sayisi() == 3
    assert ikinci_calistirma.belge_uzunlugu("d02") == 3
    assert ikinci_calistirma.ortalama_belge_uzunlugu() == pytest.approx((7 + 3 + 5) / 3)

    ikinci_calistirma.kapat()
