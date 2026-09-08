"""Consistent hashing ile belge -> shard ataması.

Halka (ring) mantığı: her shard için `sanal_dugum_sayisi` kadar sanal
nokta hesaplanıp bir halkaya (hash değerine göre sıralı liste) yerleştirilir.
Bir anahtarın (belge_id) shard'ı, o anahtarın hash'inden BAŞLAYIP halkada
saat yönünde ilk rastlanan sanal düğümün ait olduğu shard'dır (bisect ile
O(log n)). Bu, Faz 2'deki postings listesinin sıralı tutulup bisect ile
aranmasıyla aynı desen.

Neden sanal düğüm: tek bir gerçek shard'ı halkada tek noktayla temsil
etseydik, sadece 3-5 shard varken hash'lerin rastgele dağılımı yüzünden
bazı shard'lar halkada çok daha büyük bir "yay" kaplar, dengesiz veri
dağılımına yol açardı. Her shard'ı `sanal_dugum_sayisi` (varsayılan 100)
farklı noktayla temsil etmek, büyük sayılar yasası sayesinde yayların
toplamda dengeye yakınsamasını sağlar.

Neden hashlib.sha256, Python'un yerleşik hash() DEĞİL: `hash()` str
için her process başlangıcında PYTHONHASHSEED ile rastgele tuzlanır —
aynı belge_id, sunucu her yeniden başladığında FARKLI bir shard'a
düşerdi. sha256 deterministiktir (aynı girdi -> hep aynı çıktı, süreçler
ve makineler arası), bu yüzden "belge X hangi shard'da" sorusu kalıcı
ve tekrarlanabilir bir cevaba sahip olur. Kriptografik güvenlik burada
önemli değil, sadece iyi dağılım (avalanche etkisi) ve determinizm önemli
— sha256 ardışık görünen ID'leri (ör. "belge-1", "belge-2") bile
birbiriyle ilgisiz, yayılmış hash değerlerine çevirir.
"""

import bisect
import hashlib


def _hashla(deger: str) -> int:
    return int(hashlib.sha256(deger.encode("utf-8")).hexdigest(), 16)


class TutarliHash:
    def __init__(self, shardlar: list[str], sanal_dugum_sayisi: int = 100) -> None:
        self._sanal_dugum_sayisi = sanal_dugum_sayisi
        self._halka_degerleri: list[int] = []
        self._halka_shardlari: list[str] = []
        self._shardlar: set[str] = set()
        for shard_id in shardlar:
            self.shard_ekle(shard_id)

    def shard_ekle(self, shard_id: str) -> None:
        if shard_id in self._shardlar:
            return
        self._shardlar.add(shard_id)
        for i in range(self._sanal_dugum_sayisi):
            hash_degeri = _hashla(f"{shard_id}#{i}")
            idx = bisect.bisect_left(self._halka_degerleri, hash_degeri)
            self._halka_degerleri.insert(idx, hash_degeri)
            self._halka_shardlari.insert(idx, shard_id)

    def shard_cikar(self, shard_id: str) -> None:
        if shard_id not in self._shardlar:
            return
        self._shardlar.discard(shard_id)
        kalanlar = [
            (deger, sid)
            for deger, sid in zip(self._halka_degerleri, self._halka_shardlari, strict=True)
            if sid != shard_id
        ]
        self._halka_degerleri = [deger for deger, _ in kalanlar]
        self._halka_shardlari = [sid for _, sid in kalanlar]

    def shard_bul(self, belge_id: str) -> str:
        if not self._halka_degerleri:
            raise ValueError("Halkada hiç shard yok")
        hash_degeri = _hashla(belge_id)
        idx = bisect.bisect_left(self._halka_degerleri, hash_degeri)
        if idx == len(self._halka_degerleri):
            idx = 0  # halka sarmalı: son düğümden sonrası ilk düğüme döner
        return self._halka_shardlari[idx]
