"""Faz 6/8/9 testleri: FastAPI uçtan uca — HTTP isteğiyle indeksleme ve arama.

TestClient, ASGI üzerinden gerçek route/dependency/lifespan akışını
çalıştırır (mock yok) — sadece gerçek bir TCP soketi açmıyor. Gerçek
soket üzerinden (uvicorn + curl) doğrulama ayrıca elle yapıldı (bkz. Faz
6 özeti).

Faz 8'den itibaren `app`, `config/shards.json`'daki TÜM shard'ları
kullanıyor (tek dosya değil) — bu testler hangi belgenin hangi shard'a
düştüğünü bilerek varsaymıyor, sadece uçtan uca doğru sonucu doğruluyor.
Her test kendi geçici veri dizinini kullanır (SHARDSEARCH_DATA_DIR env
değişkeni ile) — testler birbirinin verisini görmesin diye.

Faz 9'dan itibaren gerçek Redis yerine `fakeredis` kullanılıyor (ortamda
gerçek Redis/Docker/WSL yok, bkz. docs/known-limitations.md). `fakeredis`
SADECE bu test dosyasında import ediliyor — `app.py`'deki
`_redis_istemcisi_olustur()` fonksiyonu `monkeypatch` ile değiştiriliyor,
`fakeredis` hiçbir zaman `src/` içine girmiyor (bkz.
test_fakeredis_izolasyonu.py).
"""

import time

import fakeredis
import pytest
from fastapi.testclient import TestClient

import shardsearch.api.app as app_modulu
import shardsearch.distributed.fan_out as fan_out_modulu
from shardsearch.api.app import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    # _lifespan(), bu env değişkenlerini/factory'yi her `with TestClient(...)`
    # bloğuna girişte (yani her testte) yeniden okuyup app.state'i baştan
    # kuruyor — bu yüzden testler arasında modülü yeniden import etmeye
    # gerek yok, her test kendi geçici veri dizini + izole fakeredis'iyle
    # çalışır.
    monkeypatch.setenv("SHARDSEARCH_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        "shardsearch.api.app._redis_istemcisi_olustur",
        lambda: fakeredis.FakeRedis(decode_responses=True),
    )

    with TestClient(app) as test_client:
        yield test_client


def test_belge_ekle_201_doner(client: TestClient) -> None:
    yanit = client.post("/index", json={"belge_id": "d01", "metin": "Kedi masada uyuyor."})
    assert yanit.status_code == 201
    assert yanit.json() == {"belge_id": "d01", "durum": "eklendi"}


def test_ucdan_uca_indeksle_ve_ara(client: TestClient) -> None:
    client.post("/index", json={"belge_id": "d01", "metin": "Kedi masada uyuyor."})
    client.post("/index", json={"belge_id": "d02", "metin": "Köpek bahçede koşuyor."})
    client.post("/index", json={"belge_id": "d03", "metin": "Kedi ve köpek birlikte oynuyor."})

    yanit = client.get("/search", params={"q": "kedi"})
    assert yanit.status_code == 200
    govde = yanit.json()
    assert govde["sorgu"] == "kedi"
    belge_idler = [sonuc["belge_id"] for sonuc in govde["sonuclar"]]
    assert set(belge_idler) == {"d01", "d03"}
    assert "d02" not in belge_idler


def test_arama_and_or_phrase_birlikte_calisir(client: TestClient) -> None:
    client.post("/index", json={"belge_id": "d01", "metin": "kedi köpek ile oynuyor"})
    client.post("/index", json={"belge_id": "d02", "metin": "köpek ve kedi parkta yürüyor"})
    client.post("/index", json={"belge_id": "d03", "metin": "balık havuzda yüzüyor"})

    # "kedi köpek" (bitişik ifade) sadece d01'de geçiyor; d02'de kelimeler var
    # ama bitişik değil, bu yüzden sonuçta olmamalı.
    yanit = client.get("/search", params={"q": '"kedi köpek" OR balık'})
    belge_idler = {sonuc["belge_id"] for sonuc in yanit.json()["sonuclar"]}
    assert belge_idler == {"d01", "d03"}


def test_arama_sonuclari_skora_gore_azalan_siralanir(client: TestClient) -> None:
    client.post("/index", json={"belge_id": "d01", "metin": "kedi kedi kedi"})
    client.post("/index", json={"belge_id": "d02", "metin": "kedi ile ilgisiz uzun bir cümle"})

    yanit = client.get("/search", params={"q": "kedi"})
    sonuclar = yanit.json()["sonuclar"]
    skorlar = [sonuc["skor"] for sonuc in sonuclar]
    assert skorlar == sorted(skorlar, reverse=True)
    # kedi 3 kez geçen d01, tf daha yüksek olduğu için d02'den önde olmalı
    assert sonuclar[0]["belge_id"] == "d01"


def test_arama_metni_dondurur(client: TestClient) -> None:
    client.post("/index", json={"belge_id": "d01", "metin": "Kedi masada uyuyor."})
    yanit = client.get("/search", params={"q": "kedi"})
    assert yanit.json()["sonuclar"][0]["metin"] == "Kedi masada uyuyor."


def test_arama_hicbir_sonuc_yoksa_bos_liste_doner(client: TestClient) -> None:
    client.post("/index", json={"belge_id": "d01", "metin": "Kedi masada uyuyor."})
    yanit = client.get("/search", params={"q": "olmayankelime"})
    assert yanit.status_code == 200
    assert yanit.json()["sonuclar"] == []


def test_arama_gecersiz_sorgu_400_doner(client: TestClient) -> None:
    client.post("/index", json={"belge_id": "d01", "metin": "Kedi masada uyuyor."})
    yanit = client.get("/search", params={"q": "kedi köpek"})  # operatörsüz yan yana yazım
    assert yanit.status_code == 400


def test_arama_limit_parametresi_sonuc_sayisini_sinirlar(client: TestClient) -> None:
    for i in range(5):
        client.post("/index", json={"belge_id": f"d{i}", "metin": "kedi köpek kuş"})

    yanit = client.get("/search", params={"q": "kedi", "limit": 2})
    assert len(yanit.json()["sonuclar"]) == 2


@pytest.mark.parametrize("gecersiz_limit", [0, -1])
def test_arama_gecersiz_limit_422_doner(client: TestClient, gecersiz_limit: int) -> None:
    yanit = client.get("/search", params={"q": "kedi", "limit": gecersiz_limit})
    assert yanit.status_code == 422


def test_ayni_belge_id_ile_index_upsert_yapar(client: TestClient) -> None:
    client.post("/index", json={"belge_id": "d01", "metin": "Kedi masada uyuyor."})
    client.post("/index", json={"belge_id": "d01", "metin": "Köpek bahçede koşuyor."})

    yanit = client.get("/search", params={"q": "kedi"})
    assert yanit.json()["sonuclar"] == []

    yanit = client.get("/search", params={"q": "köpek"})
    belge_idler = {sonuc["belge_id"] for sonuc in yanit.json()["sonuclar"]}
    assert belge_idler == {"d01"}


def _dagitik_ara_cagri_sayaci(monkeypatch) -> dict[str, int]:
    """`dagitik_ara`'nın kaç kez GERÇEKTEN çağrıldığını sayar — bir cache
    hit'te bu fonksiyon hiç çağrılmamalı, bu yüzden zamanlamadan daha
    güvenilir bir "cache gerçekten iş yaptı mı" kanıtı.
    """
    sayac = {"n": 0}
    orijinal = app_modulu.dagitik_ara

    async def sayan(*args, **kwargs):
        sayac["n"] += 1
        return await orijinal(*args, **kwargs)

    monkeypatch.setattr(app_modulu, "dagitik_ara", sayan)
    return sayac


def test_ikinci_ozdes_arama_shardlara_hic_gitmiyor(client: TestClient, monkeypatch) -> None:
    client.post("/index", json={"belge_id": "d01", "metin": "kedi masada uyuyor"})
    sayac = _dagitik_ara_cagri_sayaci(monkeypatch)

    client.get("/search", params={"q": "kedi"})
    client.get("/search", params={"q": "kedi"})

    assert sayac["n"] == 1


def test_ikinci_ozdes_arama_olculebilir_sekilde_daha_hizli(
    client: TestClient, monkeypatch
) -> None:
    # :memory: SQLite zaten çok hızlı olduğu için gerçek zamanlama farkı
    # gürültüde kaybolabilir — bu yüzden shard sorgusunu kasıtlı olarak
    # yavaşlatıp DoD'nin istediği "ölçülebilir" farkı güvenilir şekilde
    # üretiyoruz.
    client.post("/index", json={"belge_id": "d01", "metin": "kedi masada uyuyor"})
    orijinal_sorgula = fan_out_modulu._shard_sorgula

    def yavas_sorgula(*args, **kwargs):
        time.sleep(0.05)
        return orijinal_sorgula(*args, **kwargs)

    monkeypatch.setattr(fan_out_modulu, "_shard_sorgula", yavas_sorgula)

    baslangic = time.perf_counter()
    client.get("/search", params={"q": "kedi"})
    ilk_sure = time.perf_counter() - baslangic

    baslangic = time.perf_counter()
    client.get("/search", params={"q": "kedi"})
    ikinci_sure = time.perf_counter() - baslangic

    assert ikinci_sure < ilk_sure / 2, (
        f"cache'li istek en az 2 kat hızlı olmalıydı: ilk={ilk_sure:.4f}s "
        f"ikinci={ikinci_sure:.4f}s"
    )


def test_yeni_belge_eklenince_cache_gecersiz_olur(client: TestClient, monkeypatch) -> None:
    client.post("/index", json={"belge_id": "d01", "metin": "kedi masada uyuyor"})
    sayac = _dagitik_ara_cagri_sayaci(monkeypatch)

    client.get("/search", params={"q": "kedi"})  # cache miss
    client.get("/search", params={"q": "kedi"})  # cache hit
    assert sayac["n"] == 1

    # Yeni bir belge eklemek, "kedi" sorgusuyla hiç ilgisi olmasa bile
    # TÜM cache'i geçersiz kılmalı (bkz. cache.py'deki kuşak sayacı notu).
    client.post("/index", json={"belge_id": "d02", "metin": "alakasız bir cümle"})

    client.get("/search", params={"q": "kedi"})  # cache miss'e dönmeli
    assert sayac["n"] == 2


def test_kismi_basarisiz_sonuc_cachelenmiyor(client: TestClient, monkeypatch) -> None:
    client.post("/index", json={"belge_id": "d01", "metin": "kedi masada uyuyor"})

    # Bir shard'ı bilerek bozuyoruz — bu belge o shard'da olsun ya da
    # olmasın, TÜM shard'lar sorgulandığı için basarisiz_shardlar dolacak.
    ilk_shard_id = next(iter(app.state.shardlar))
    app.state.shardlar[ilk_shard_id].kapat()

    yanit1 = client.get("/search", params={"q": "kedi"})
    assert yanit1.json()["basarisiz_shardlar"] == [ilk_shard_id]

    sayac = _dagitik_ara_cagri_sayaci(monkeypatch)
    yanit2 = client.get("/search", params={"q": "kedi"})

    # Cache'lenmediği için ikinci özdeş istek de GERÇEKTEN shard'lara gitmiş
    # olmalı (sayaç 0 değil 1) — kısmi başarısız bir sonuç kalıcı "doğru
    # cevap" gibi önbelleğe düşmüyor.
    assert sayac["n"] == 1
    assert yanit2.json()["basarisiz_shardlar"] == [ilk_shard_id]
