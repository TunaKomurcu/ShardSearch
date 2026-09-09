"""Faz 10: Locust yük testi senaryosu.

Gerçekçi bir okuma-ağırlıklı dağılım: %90 GET /search, %10 POST /index
(çoğu arama motorunun gerçek trafiği bu şekildedir). Arama tarafında
BİLEREK iki tür sorgu karıştırılıyor:
  - %60 ihtimalle küçük bir "popüler sorgu" havuzundan (cache hit'i
    gerçekten sınamak için — Faz 9'un cache-aside'ının etkisini görmek
    istiyorsak, hep aynı sorguları tekrar tekrar sormamız lazım)
  - %40 ihtimalle rastgele TEK kelimelik bir sorgu (cache miss, gerçek
    shard hesaplamasını zorlar) — bilerek TEK kelime seçildi, iki kelimeyi
    boşlukla yan yana yazmak (ör. "kedi köpek") Faz 5'in kuralı gereği
    parse hatası verir (bkz. docs/known-limitations.md), yük testinin
    "arama gecikmesi" ölçümünü anlamsız 400 hatalarıyla kirletmesin diye.

Test başında (`test_start` event'i, HER kullanıcıda değil TEK SEFER)
küçük bir sentetik korpus indeksleniyor. Wikipedia korpusu gerekmiyor —
yük testi hacim/gecikme ölçüyor, alaka düzeyini değil.

Bu ortamda gerçek Redis yok (bkz. docs/known-limitations.md); canlı
sunucu `redis://localhost:6379/0`'a bağlanmaya çalışıp başarısız olacak
ve AramaCache bunu sessizce yutup cache'siz çalışacak (Faz 9'un
tasarladığı, test ettiği davranış). Yani bu koşu "cache'siz" senaryoyu
yansıtıyor — asıl amaç zaten threading.Lock'un gerçek eşzamanlı yük
altındaki davranışını ölçmek, bunun için cache'e ihtiyaç yok.

ÖNEMLİ ortam notu (bkz. docs/known-limitations.md): bu geliştirme
oturumunda Python'dan (requests/http.client, fark etmiyor) başlatılan HER
HTTP bağlantısına ~4 saniyelik sabit bir gecikme biniyor — curl.exe
etkilenmiyor, ham TCP bağlantısı da hızlı, sadece Python'un HTTP
istek/yanıt döngüsü etkileniyor. Ölçüldü: bu gecikme EŞZAMANLI isteklerde
ÇAKIŞIYOR (10 paralel istek de toplam ~4.2sn sürüyor, 41sn değil) — yani
gerçek bir sunucu darboğazı değil, bu oturuma özgü sabit bir ortam
artefaktı. Bu yüzden mutlak gecikme sayıları (Locust'un raporladığı ham
ms değerleri) bu ortamda GERÇEK UYGULAMA GECİKMESİNİ YANSITMIYOR — asıl
anlamlı olan, yükün artmasıyla p99/p50 ORANININ nasıl değiştiği (göreli
karşılaştırma), mutlak değerler değil.
"""

import concurrent.futures
import random

import requests
from locust import HttpUser, between, events, task

KELIME_HAVUZU = [
    "kedi", "köpek", "kuş", "balık", "aslan", "kaplan", "ayı", "tilki",
    "orman", "deniz", "gökyüzü", "güneş", "yıldız", "bulut", "yağmur",
    "şehir", "sokak", "araba", "bilgisayar", "kitap", "müzik",
    "sanat", "bilim", "teknoloji", "doğa", "hayvan", "bitki", "çiçek",
]  # fmt: skip

POPULER_SORGULAR = ["kedi", "köpek", "kedi OR köpek", "kedi AND köpek", '"kedi köpek"']

TOHUM_BELGE_SAYISI = 200


def _rastgele_cumle(kelime_sayisi: int = 6) -> str:
    return " ".join(random.choices(KELIME_HAVUZU, k=kelime_sayisi))


@events.test_start.add_listener
def _corpus_tohumla(environment, **kwargs) -> None:
    # Bilerek PARALEL: bu geliştirme ortamında Python'dan başlatılan her
    # HTTP bağlantısına sabit bir gecikme biniyor (bkz.
    # docs/known-limitations.md) — sıralı 200 istek dakikalarca sürerdi.
    # Bu gecikme eşzamanlı isteklerde ÇAKIŞTIĞI için (ölçülüp doğrulandı)
    # ThreadPoolExecutor ile paralel atmak tohumlamayı saniyelere indiriyor.
    def _tek_tohum(i: int) -> None:
        requests.post(
            f"{environment.host}/index",
            json={"belge_id": f"tohum-{i}", "metin": _rastgele_cumle()},
            timeout=30,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as havuz:
        list(havuz.map(_tek_tohum, range(TOHUM_BELGE_SAYISI)))


class AramaKullanicisi(HttpUser):
    wait_time = between(0.05, 0.3)

    @task(9)
    def ara(self) -> None:
        if random.random() < 0.6:
            sorgu = random.choice(POPULER_SORGULAR)
        else:
            sorgu = random.choice(KELIME_HAVUZU)  # tek kelime, her zaman geçerli sözdizimi
        self.client.get("/search", params={"q": sorgu, "limit": 10}, name="/search")

    @task(1)
    def index_belge(self) -> None:
        belge_id = f"yuk-{random.randint(0, 10_000_000)}"
        self.client.post(
            "/index",
            json={"belge_id": belge_id, "metin": _rastgele_cumle()},
            name="/index",
        )
