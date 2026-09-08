"""Bellek içi ters indeks.

Postings listeleri her zaman belge_id'ye göre SIRALI tutulur (ekleme
anında bisect ile doğru konuma yerleştirilir). Bunun nedeni bu fazda
değil, ileride: Faz 5'teki AND kesişimi ve Faz 8'deki dağıtık sonuç
birleştirmesi, iki sıralı listeyi O(n) taramayla kesiştirmeyi/birleştirmeyi
varsayacak. Sıralamayı en başta (ekleme anında) garanti etmek, o fazlarda
"zaten sıralı" varsayımını sorgusuz kullanabilmemizi sağlıyor.

belge_ekle() upsert'tür: aynı belge_id ile tekrar çağrılırsa, o belgeye ait
önceki tüm postings'ler silinip metin sıfırdan indekslenir — belge
güncellendiğinde eski haliyle yeni hali karışmasın diye.

Belge uzunlukları ve toplam uzunluk (Faz 3'te BM25'in ihtiyaç duyduğu
ortalama belge uzunluğu için) her ekleme/silmede artımlı olarak
güncellenir — ortalama_belge_uzunlugu() her çağrıda tüm belgeleri
tarayıp toplamak yerine O(1)'de tek bölme işlemiyle hesaplanır.
"""

import bisect

from shardsearch.index.postings import Posting
from shardsearch.tokenizer import tokenize


class TersIndeks:
    def __init__(self) -> None:
        self._index: dict[str, list[Posting]] = {}
        # upsert sırasında bir belgenin hangi token'larda postingi olduğunu
        # bulmak için: her token için tüm index'i taramamak amacıyla tutulur.
        self._belge_tokenlari: dict[str, set[str]] = {}
        self._belge_uzunluklari: dict[str, int] = {}
        self._toplam_belge_uzunlugu: int = 0

    def belge_ekle(self, belge_id: str, metin: str) -> None:
        if belge_id in self._belge_tokenlari:
            self._belgeyi_sil(belge_id)

        tokenler = tokenize(metin)
        pozisyonlar_by_token: dict[str, list[int]] = {}
        for pozisyon, token in enumerate(tokenler):
            pozisyonlar_by_token.setdefault(token, []).append(pozisyon)

        self._belge_tokenlari[belge_id] = set(pozisyonlar_by_token.keys())
        self._belge_uzunluklari[belge_id] = len(tokenler)
        self._toplam_belge_uzunlugu += len(tokenler)
        for token, pozisyonlar in pozisyonlar_by_token.items():
            postings = self._index.setdefault(token, [])
            yeni_posting = Posting(belge_id, len(pozisyonlar), pozisyonlar)
            idx = bisect.bisect_left(postings, belge_id, key=lambda p: p.belge_id)
            postings.insert(idx, yeni_posting)

    def _belgeyi_sil(self, belge_id: str) -> None:
        for token in self._belge_tokenlari[belge_id]:
            postings = [p for p in self._index[token] if p.belge_id != belge_id]
            if postings:
                self._index[token] = postings
            else:
                del self._index[token]
        del self._belge_tokenlari[belge_id]
        self._toplam_belge_uzunlugu -= self._belge_uzunluklari.pop(belge_id)

    def postings_getir(self, token: str) -> list[Posting]:
        return self._index.get(token, [])

    def belge_sayisi(self) -> int:
        return len(self._belge_tokenlari)

    def belge_uzunlugu(self, belge_id: str) -> int:
        return self._belge_uzunluklari[belge_id]

    def ortalama_belge_uzunlugu(self) -> float:
        if not self._belge_tokenlari:
            return 0.0
        return self._toplam_belge_uzunlugu / len(self._belge_tokenlari)
