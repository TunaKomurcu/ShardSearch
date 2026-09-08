"""Faz 7 testleri: consistent hashing doğru dağıtıyor mu ve resharding
minimum veri yer değiştirmesiyle mi çalışıyor.

Sentetik ID'ler kasıtlı olarak ARDIŞIK üretildi ("belge-0", "belge-1", ...)
— rastgele ID değil. Amaç bunu gizlemek değil, tam tersini kanıtlamak:
sha256'nın avalanche etkisi sayesinde ardışık/örüntülü ID'ler bile
birbiriyle ilgisiz hash değerlerine dağılır. Zayıf bir hash fonksiyonuyla
(ör. basit toplama tabanlı) ardışık ID'ler halkada kümelenip dengesiz
dağılıma yol açabilirdi — bu testin asıl amacı sha256 seçiminin bu riski
gerçekten ortadan kaldırdığını göstermek.
"""

import pytest

from shardsearch.sharding import TutarliHash


def _sentetik_id_uret(adet: int) -> list[str]:
    return [f"belge-{i}" for i in range(adet)]


def test_ayni_id_hep_ayni_shard_donuyor() -> None:
    halka = TutarliHash(["shard-0", "shard-1", "shard-2"])
    ilk_sonuc = halka.shard_bul("belge-42")
    for _ in range(10):
        assert halka.shard_bul("belge-42") == ilk_sonuc


def test_gecerli_bir_shard_donuyor() -> None:
    shardlar = ["shard-0", "shard-1", "shard-2"]
    halka = TutarliHash(shardlar)
    for belge_id in _sentetik_id_uret(200):
        assert halka.shard_bul(belge_id) in shardlar


def test_halka_bossa_hata_verir() -> None:
    halka = TutarliHash([])
    with pytest.raises(ValueError):
        halka.shard_bul("belge-1")


def test_dagilim_istatistigi_makul_aralikta() -> None:
    shardlar = ["shard-0", "shard-1", "shard-2", "shard-3", "shard-4"]
    halka = TutarliHash(shardlar, sanal_dugum_sayisi=100)
    idler = _sentetik_id_uret(10_000)

    sayaçlar: dict[str, int] = dict.fromkeys(shardlar, 0)
    for belge_id in idler:
        sayaçlar[halka.shard_bul(belge_id)] += 1

    ortalama = len(idler) / len(shardlar)
    for shard_id, sayi in sayaçlar.items():
        oran = sayi / ortalama
        assert 0.70 <= oran <= 1.30, f"{shard_id} dengesiz: {sayi} belge (oran={oran:.2f})"


def test_resharding_sadece_eskiden_yeniye_gecis_olur() -> None:
    """Tutarlı hash'i naive hash(id) % N'den ayıran asıl özellik:
    yeni bir shard eklendiğinde SADECE bazı anahtarlar eski
    shard'lardan YENİ shard'a taşınır — iki eski shard arasında hiçbir
    yer değiştirme OLMAMALIDIR. Naive mod-N hashleme yeni shard
    eklendiğinde neredeyse tüm anahtarları karıştırır; bu test tam
    olarak bunun OLMADIĞINI kanıtlıyor.
    """
    eski_shardlar = ["shard-0", "shard-1", "shard-2"]
    halka = TutarliHash(eski_shardlar)
    idler = _sentetik_id_uret(5_000)

    eski_atama = {belge_id: halka.shard_bul(belge_id) for belge_id in idler}

    halka.shard_ekle("shard-3")
    yeni_atama = {belge_id: halka.shard_bul(belge_id) for belge_id in idler}

    tasinanlar = 0
    for belge_id in idler:
        eski = eski_atama[belge_id]
        yeni = yeni_atama[belge_id]
        if eski != yeni:
            tasinanlar += 1
            # Kritik doğrulama: taşınma SADECE eski bir shard'dan YENİ
            # shard'a olabilir, iki eski shard arasında asla.
            assert yeni == "shard-3", (
                f"{belge_id} eski bir shard'dan ({eski}) başka bir eski "
                f"shard'a ({yeni}) taşınmış — bu naive rehashing'in belirtisi"
            )

    # Teorik beklenti: yaklaşık 1/(N+1) = 1/4 = %25'i yeni shard'a taşınır.
    tasinma_orani = tasinanlar / len(idler)
    assert 0.15 <= tasinma_orani <= 0.35, f"taşınma oranı beklenenden uzak: {tasinma_orani:.2%}"


def test_shard_cikarinca_sadece_o_shardin_verisi_dagilir() -> None:
    shardlar = ["shard-0", "shard-1", "shard-2", "shard-3"]
    halka = TutarliHash(shardlar)
    idler = _sentetik_id_uret(5_000)

    eski_atama = {belge_id: halka.shard_bul(belge_id) for belge_id in idler}
    halka.shard_cikar("shard-3")
    yeni_atama = {belge_id: halka.shard_bul(belge_id) for belge_id in idler}

    for belge_id in idler:
        eski = eski_atama[belge_id]
        yeni = yeni_atama[belge_id]
        if eski != "shard-3":
            # shard-3'te olmayan hiçbir belge yer değiştirmemeli
            assert yeni == eski, f"{belge_id} gereksiz yere taşınmış: {eski} -> {yeni}"
        else:
            # shard-3'teki belgeler artık kalan 3 shard'dan birine gitmeli
            assert yeni != "shard-3"


def test_sanal_dugum_sayisi_arttikca_dagilim_iyilesir() -> None:
    shardlar = ["shard-0", "shard-1", "shard-2"]
    idler = _sentetik_id_uret(3_000)

    def varyans_hesapla(sanal_dugum_sayisi: int) -> float:
        halka = TutarliHash(shardlar, sanal_dugum_sayisi=sanal_dugum_sayisi)
        sayaçlar: dict[str, int] = dict.fromkeys(shardlar, 0)
        for belge_id in idler:
            sayaçlar[halka.shard_bul(belge_id)] += 1
        ortalama = len(idler) / len(shardlar)
        return sum((sayi - ortalama) ** 2 for sayi in sayaçlar.values()) / len(shardlar)

    # Çok az sanal düğümle dağılım şansa kalır, 100 ile belirgin daha dengeli olmalı.
    varyans_az_dugum = varyans_hesapla(1)
    varyans_cok_dugum = varyans_hesapla(100)
    assert varyans_cok_dugum < varyans_az_dugum
