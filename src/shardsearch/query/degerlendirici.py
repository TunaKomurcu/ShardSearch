"""Ayrıştırma ağacını bir ters indekse karşı çalıştırıp eşleşen belge_id
kümesini üretir.

`indeks` parametresi kasıtlı olarak duck-typed: hem TersIndeks (Faz 2)
hem SqliteTersIndeks (Faz 4) `postings_getir()` metoduna sahip olduğu
için ikisiyle de çalışır, tip kontrolü yapılmıyor.
"""

from typing import Protocol

from shardsearch.query.ast import Ifade, SorguDugumu, Terim, Ve, Veya


class _PostingsKaynagi(Protocol):
    def postings_getir(self, token: str) -> list: ...


def degerlendir(dugum: SorguDugumu, indeks: _PostingsKaynagi) -> set[str]:
    if isinstance(dugum, Terim):
        return {p.belge_id for p in indeks.postings_getir(dugum.kelime)}

    if isinstance(dugum, Ifade):
        return _ifade_esles(dugum, indeks)

    if isinstance(dugum, Ve):
        return degerlendir(dugum.sol, indeks) & degerlendir(dugum.sag, indeks)

    if isinstance(dugum, Veya):
        return degerlendir(dugum.sol, indeks) | degerlendir(dugum.sag, indeks)

    raise TypeError(f"Bilinmeyen sorgu düğümü: {dugum!r}")


def _ifade_esles(ifade: Ifade, indeks: _PostingsKaynagi) -> set[str]:
    kelimeler = ifade.kelimeler
    if not kelimeler:
        return set()

    postings_listeleri = [indeks.postings_getir(kelime) for kelime in kelimeler]
    if any(not postings for postings in postings_listeleri):
        return set()  # kelimelerden biri hiçbir belgede geçmiyorsa ifade de geçemez

    # Her kelimenin geçtiği belge_id kümeleri — ifadenin geçebilmesi için
    # bir belgenin kelimelerin TAMAMINI içermesi gerekir (ardışıklık henüz
    # kontrol edilmedi, bu sadece bir ön eleme).
    belge_id_kumeleri = [{p.belge_id for p in postings} for postings in postings_listeleri]
    aday_belgeler = set.intersection(*belge_id_kumeleri)

    sonuc: set[str] = set()
    for belge_id in aday_belgeler:
        pozisyon_kumeleri = [
            set(next(p.pozisyonlar for p in postings if p.belge_id == belge_id))
            for postings in postings_listeleri
        ]
        ilk_kelimenin_pozisyonlari = pozisyon_kumeleri[0]
        for baslangic in ilk_kelimenin_pozisyonlari:
            if all(
                (baslangic + ofset) in pozisyon_kumeleri[ofset]
                for ofset in range(1, len(kelimeler))
            ):
                sonuc.add(belge_id)
                break
    return sonuc


def terimleri_topla(dugum: SorguDugumu) -> list[str]:
    """AST'deki tüm Terim/Ifade yapraklarını düz bir kelime listesine çevirir.

    BM25 skorlaması için köprü görevi görür: degerlendir() bize sadece
    eşleşen belge_id KÜMESİNİ verir (sıralama yok), bm25_skoru() ise düz
    bir kelime listesi bekler. Bu fonksiyon ikisi arasındaki farkı kapatır.

    Sorgunun AND/OR yapısı burada BİLEREK yok sayılır — sadece hangi
    kelimelerin sorguda geçtiği toplanır. Örneğin "kedi OR köpek"
    sorgusunda ikisi de skora dahil edilir: bir belge sadece "kedi"
    içeriyorsa "köpek" için tf=0 olur ve bm25_skoru() o terimin katkısını
    zaten sıfırlar — ayrı bir özel durum koduna gerek yok. AND/OR/phrase'in
    asıl anlamı zaten degerlendir() ile "hangi belgeler aday kümesine
    girer" kararında uygulanmış oluyor; bu fonksiyon sadece o adayları
    sıralamak için gereken kelime listesini üretir.
    """
    if isinstance(dugum, Terim):
        return [dugum.kelime]
    if isinstance(dugum, Ifade):
        return list(dugum.kelimeler)
    if isinstance(dugum, Ve | Veya):
        return terimleri_topla(dugum.sol) + terimleri_topla(dugum.sag)
    raise TypeError(f"Bilinmeyen sorgu düğümü: {dugum!r}")
