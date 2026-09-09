"""Faz 8 testleri: fan-out + birleştirme, yerel IDF sapması, hata toleransı.

Tek-node "karşılaştırma temeli" için bm25.sirala() (Faz 3) KULLANILMIYOR —
o fonksiyon AND/OR/phrase'i hiç bilmiyor, ham sorguyu bag-of-words olarak
tokenize edip OR mantığıyla eşleştiriyor (Faz 5 boolean parser'ı Faz 6'da
API'ye entegre edilirken sirala() değil, ayristir()+degerlendir()+
bm25_skoru() üçlüsü kullanıldı — bkz. app.py). Bu üçlüyü tek-node'a karşı
da AYNEN dagitik_ara()'nın kullandığı gibi çalıştırmanın en temiz yolu:
tek-node'u TEK ELEMANLI bir "shard sözlüğü" olarak dagitik_ara()'ya
vermek. Böylece iki taraf da BİREBİR aynı kod yolunu kullanıyor, tek fark
şardla sayısı — karşılaştırma gerçekten elma-elma oluyor.
"""

import asyncio

import pytest

from shardsearch.distributed import dagitik_ara
from shardsearch.scoring.bm25 import ters_belge_frekansi
from shardsearch.sharding import TutarliHash
from shardsearch.storage import SqliteTersIndeks

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


def _tek_node_olustur() -> SqliteTersIndeks:
    indeks = SqliteTersIndeks(":memory:")
    for belge_id, metin in KORPUS.items():
        indeks.belge_ekle(belge_id, metin)
    return indeks


def _dengeli_shardlara_dagit(shard_idler: list[str]) -> dict[str, SqliteTersIndeks]:
    halka = TutarliHash(shard_idler)
    shardlar = {shard_id: SqliteTersIndeks(":memory:") for shard_id in shard_idler}
    for belge_id, metin in KORPUS.items():
        shardlar[halka.shard_bul(belge_id)].belge_ekle(belge_id, metin)
    return shardlar


@pytest.mark.parametrize(
    "sorgu",
    ["kedi", "kedi OR köpek", "kedi AND köpek", "kuş", "hayvandır", '"bir hayvandır"'],
)
def test_dengeli_dagitimda_aday_kumesi_tek_node_ile_birebir_ayni(sorgu: str) -> None:
    """Aday belge KÜMESİ (hangi belgeler eşleşiyor), IDF'den bağımsızdır —
    degerlendir()'in AND/OR/phrase mantığı sadece postings varlığına ve
    pozisyonlarına bakar, hiç skor hesaplamaz. Bu yüzden bu eşitlik ŞANSA
    değil, algoritmanın yapısına bağlı: HER ZAMAN doğru olmalı. Sıralama
    (ORDER) farklı olabilir — bkz. aşağıdaki ayrı gözlem testi.
    """
    tek_node = {"tek": _tek_node_olustur()}
    shardlar = _dengeli_shardlara_dagit(["shard-0", "shard-1", "shard-2"])

    tek_node_sonuc = asyncio.run(dagitik_ara(tek_node, sorgu, limit=100))
    dagitik_sonuc = asyncio.run(dagitik_ara(shardlar, sorgu, limit=100))

    tek_node_kume = {belge_id for belge_id, _ in tek_node_sonuc.sonuclar}
    dagitik_kume = {belge_id for belge_id, _ in dagitik_sonuc.sonuclar}
    assert dagitik_kume == tek_node_kume


def test_dengeli_dagitimda_bile_yerel_idf_siralamayi_degistirebilir() -> None:
    """GÖZLEM: sadece 12 belgelik küçük bir korpuda, consistent hashing ile
    3 shard'a DENGELİ dağıtılmış veride bile sıralama tek-node'dan sapabilir.

    "kedi OR köpek" sorgusunda: d02 (sadece "köpek" içeriyor) tek-node'da
    2. sırada, ama dağıtık sonuçta 4. sıraya düşüyor — çünkü d02'nin
    bulunduğu shard'da "köpek" görece daha "yaygın" göründüğü için o
    shard'ın yerel IDF'si düşük çıkıyor. Bu SPEC.md'nin Faz 8 testinde
    beklediği tam olarak bu: "IDF farkından kaynaklanan sapmalar
    açıklanabilir mi". Cevap: evet, açıklanabilir — ama YOK DEĞİL. Büyük,
    terim dağılımı dengeli korpuslarda bu etkinin küçüleceği beklenir
    (büyük sayılar yasası), küçük korpuslarda büyütecin altında görünür.
    """
    sorgu = "kedi OR köpek"
    tek_node = {"tek": _tek_node_olustur()}
    shardlar = _dengeli_shardlara_dagit(["shard-0", "shard-1", "shard-2"])

    tek_node_sira = [b for b, _ in asyncio.run(dagitik_ara(tek_node, sorgu, limit=100)).sonuclar]
    dagitik_sira = [b for b, _ in asyncio.run(dagitik_ara(shardlar, sorgu, limit=100)).sonuclar]

    assert tek_node_sira != dagitik_sira, "beklenen sapma bu korpuda gözlenemedi"
    assert tek_node_sira.index("d02") < dagitik_sira.index("d02")


def test_dengesiz_dagitimda_yerel_idf_sapmasi_cok_daha_buyuk() -> None:
    """KASITLI dengesiz senaryo: "nadir" kelimesi toplamda 20 belgeden
    SADECE 2'sinde geçiyor (global olarak gerçekten nadir, yüksek IDF hak
    ediyor). Ama bu 2 belgeyi consistent hashing'in eline bırakmak yerine
    BİLEREK küçücük bir shard'a (sadece bu 2 belge) topluyoruz — o
    shard'da "nadir" belgelerin YÜZDE 100'ünde geçiyor, yerel IDF neredeyse
    sıfıra iner. Bu, dengeli dağıtımda gördüğümüz (yukarıdaki test) küçük
    sapmadan çok daha büyük ve tamamen ÖNGÖRÜLEBİLİR bir sapma: dengesizlik
    ne kadar büyürse (shard küçüldükçe, bir terim o shard'da orantısız
    "yaygın" göründükçe) sapma da o kadar büyür.
    """
    tek_node = SqliteTersIndeks(":memory:")
    shard_nadir = SqliteTersIndeks(":memory:")  # SADECE "nadir" içeren 2 belge
    shard_diger = SqliteTersIndeks(":memory:")  # geri kalan 18 belge, "nadir" hiç yok

    for belge_id, metin in [("r1", "nadir kelime burada"), ("r2", "nadir kelime burada da")]:
        tek_node.belge_ekle(belge_id, metin)
        shard_nadir.belge_ekle(belge_id, metin)

    for i in range(18):
        belge_id, metin = f"n{i}", "alakasız sıradan bir cümle burada"
        tek_node.belge_ekle(belge_id, metin)
        shard_diger.belge_ekle(belge_id, metin)

    global_idf = ters_belge_frekansi(tek_node, "nadir")
    yerel_idf = ters_belge_frekansi(shard_nadir, "nadir")

    # global'de "nadir" 2/20 belgede -> yüksek IDF; shard_nadir'de 2/2 ->
    # neredeyse en düşük mümkün IDF. Sapma en az 5 kat olmalı.
    assert yerel_idf < global_idf * 0.2, (
        f"beklenen büyük sapma gözlenmedi: global={global_idf:.3f} yerel={yerel_idf:.3f}"
    )


def test_bir_shard_basarisiz_olursa_digerlerinden_kismi_sonuc_doner() -> None:
    saglam_shard = SqliteTersIndeks(":memory:")
    saglam_shard.belge_ekle("d01", "kedi masada uyuyor")
    saglam_shard.belge_ekle("d02", "kedi bahçede oynuyor")

    bozuk_shard = SqliteTersIndeks(":memory:")
    bozuk_shard.belge_ekle("d03", "kedi çatıda geziniyor")
    bozuk_shard.kapat()  # sorgu sırasında hata fırlamasını garantiler

    shardlar = {"saglam": saglam_shard, "bozuk": bozuk_shard}
    sonuc = asyncio.run(dagitik_ara(shardlar, "kedi", limit=10))

    assert sonuc.basarisiz_shardlar == ["bozuk"]

    # d03 (bozuk shard'daki TEK belge) sonuçta hiç görünmüyor — ama bu
    # SESSİZ bir veri kaybı DEĞİL: basarisiz_shardlar listesi hangi
    # shard'ın cevap veremediğini AÇIKÇA raporluyor. İstemci "sonuç azdı
    # ama nedenini bilmiyorum" durumunda kalmıyor, tam tersine "şu shard
    # cevap vermedi" bilgisine sahip oluyor.
    belge_idler = {belge_id for belge_id, _ in sonuc.sonuclar}
    assert belge_idler == {"d01", "d02"}
    assert "d03" not in belge_idler


def test_tum_shardlar_basarisiz_olursa_bos_sonuc_ve_tum_shardlar_raporlanir() -> None:
    bozuk_1 = SqliteTersIndeks(":memory:")
    bozuk_1.kapat()
    bozuk_2 = SqliteTersIndeks(":memory:")
    bozuk_2.kapat()

    sonuc = asyncio.run(dagitik_ara({"s1": bozuk_1, "s2": bozuk_2}, "kedi", limit=10))

    assert sonuc.sonuclar == []
    assert set(sonuc.basarisiz_shardlar) == {"s1", "s2"}
