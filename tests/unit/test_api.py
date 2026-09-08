"""Faz 6 testleri: FastAPI uçtan uca — HTTP isteğiyle indeksleme ve arama.

TestClient, ASGI üzerinden gerçek route/dependency/lifespan akışını
çalıştırır (mock yok) — sadece gerçek bir TCP soketi açmıyor. Gerçek
soket üzerinden (uvicorn + curl) doğrulama ayrıca elle yapıldı (bkz. Faz
6 özeti).

Her test kendi geçici SQLite dosyasını kullanır (SHARDSEARCH_DB_PATH env
değişkeni ile) — testler birbirinin verisini görmesin diye.
"""

import pytest
from fastapi.testclient import TestClient

from shardsearch.api.app import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    # _lifespan(), SHARDSEARCH_DB_PATH'i her `with TestClient(...)` bloğuna
    # girişte (yani her testte) yeniden okuyup app.state.indeks'i baştan
    # kuruyor — bu yüzden testler arasında modülü yeniden import etmeye
    # gerek yok, sadece env değişkenini context'e girmeden önce ayarlamak
    # yeterli, her test kendi geçici DB dosyasıyla izole çalışır.
    veritabani_yolu = tmp_path / "test_api.db"
    monkeypatch.setenv("SHARDSEARCH_DB_PATH", str(veritabani_yolu))

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
