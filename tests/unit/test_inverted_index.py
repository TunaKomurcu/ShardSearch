"""Faz 2 testleri: TersIndeks doğru postings üretiyor mu.

Beklenen frekans/pozisyon değerleri, her belgenin tokenize() çıktısı elle
çıkarılarak hesaplandı (bkz. Faz 2 planı).
"""

from shardsearch.index import Posting, TersIndeks

# 12 kısa belgeden oluşan küçük test korpusu. "kedi" kelimesi kasıtlı
# olarak farklı belgelerde farklı frekans/pozisyonlarda geçecek şekilde
# seçildi, geri kalanlar postings listesine gürültü katmak için var.
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

# Elle hesaplanan beklenen "kedi" postings'i, belge_id'ye göre sıralı.
BEKLENEN_KEDI_POSTINGS = [
    Posting("d01", 2, [0, 4]),
    Posting("d03", 1, [0]),
    Posting("d07", 2, [3, 5]),
    Posting("d10", 1, [0]),
]


def _indeks_olustur(sirali_belge_idleri: list[str]) -> TersIndeks:
    indeks = TersIndeks()
    for belge_id in sirali_belge_idleri:
        indeks.belge_ekle(belge_id, KORPUS[belge_id])
    return indeks


def test_bilinen_kelimenin_postingsleri_dogru() -> None:
    indeks = _indeks_olustur(list(KORPUS))
    assert indeks.postings_getir("kedi") == BEKLENEN_KEDI_POSTINGS


def test_postings_belge_id_karisik_sirayla_eklense_de_sirali_donuyor() -> None:
    # d07, d01, d10, d03 sırasıyla eklendi ama postings hep belge_id sıralı olmalı —
    # Faz 5/Faz 8'in sıralı-birleştirme varsayımı bu davranışa dayanıyor.
    karisik_sira = [
        "d07", "d02", "d01", "d10", "d05", "d03", "d04", "d06", "d08", "d09", "d11", "d12",
    ]
    indeks = _indeks_olustur(karisik_sira)
    assert indeks.postings_getir("kedi") == BEKLENEN_KEDI_POSTINGS


def test_bilinmeyen_token_bos_liste_doner() -> None:
    indeks = _indeks_olustur(list(KORPUS))
    assert indeks.postings_getir("boyle_bir_kelime_yok") == []


def test_ayni_belge_id_ile_tekrar_ekleme_upsert_yapar() -> None:
    indeks = TersIndeks()
    indeks.belge_ekle("up1", "Kedi köpek kuş.")

    # İlk halinde üç token da up1'i içeriyor olmalı
    assert indeks.postings_getir("kedi") == [Posting("up1", 1, [0])]
    assert indeks.postings_getir("köpek") == [Posting("up1", 1, [1])]
    assert indeks.postings_getir("kuş") == [Posting("up1", 1, [2])]

    # Aynı belge_id ile yeniden eklendiğinde eski içerik tamamen silinmeli
    indeks.belge_ekle("up1", "Kuş ve balık.")

    # Eski içerikte olup yeni içerikte olmayan token'lar için up1 tamamen kaybolmalı
    assert indeks.postings_getir("kedi") == []
    assert indeks.postings_getir("köpek") == []

    # Yeni içerikteki token'lar güncel pozisyonlarla görünmeli
    assert indeks.postings_getir("kuş") == [Posting("up1", 1, [0])]
    assert indeks.postings_getir("balık") == [Posting("up1", 1, [2])]
