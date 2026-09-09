"""Faz 10 testleri: JSON log formatlayıcı ve yardımcı fonksiyonlar.

Gerçek stdout çıktısını yakalamak yerine (handler import anında sys.stdout
referansını sabitliyor, pytest'in capsys'i bunu değiştiremez) doğrudan
JsonFormatter.format() çağrısının ürettiği string'i ve istek_logla()'nın
oluşturduğu LogRecord'un attribute'larını (caplog ile) doğruluyoruz.
"""

import json
import logging

from shardsearch.api.logging_config import JsonFormatter, istek_logla


def _kayit_olustur(ekstra: dict | None = None) -> logging.LogRecord:
    logger = logging.getLogger("test_formatter")
    return logger.makeRecord(
        "test_formatter", logging.INFO, __file__, 0, "mesaj", (), None, extra=ekstra
    )


def test_json_formatter_gecerli_json_uretir() -> None:
    cikti = JsonFormatter().format(_kayit_olustur())
    ayristirilmis = json.loads(cikti)  # geçerli JSON değilse burada patlar
    assert ayristirilmis["mesaj"] == "mesaj"
    assert ayristirilmis["seviye"] == "INFO"
    assert "zaman" in ayristirilmis


def test_json_formatter_ekstra_alanlari_tasir() -> None:
    kayit = _kayit_olustur(ekstra={"endpoint": "/search", "sure_ms": 12.3})
    cikti = json.loads(JsonFormatter().format(kayit))
    assert cikti["endpoint"] == "/search"
    assert cikti["sure_ms"] == 12.3


def test_json_formatter_turkce_karakterleri_bozmadan_yazar() -> None:
    kayit = _kayit_olustur(ekstra={"sorgu": "kedi AND köpek"})
    cikti = JsonFormatter().format(kayit)
    assert "köpek" in cikti  # ensure_ascii=False: ö değil, gerçek harf


def test_istek_logla_beklenen_alanlarla_cagirir(caplog) -> None:
    logger = logging.getLogger("test_istek_logla")
    logger.setLevel(logging.INFO)
    with caplog.at_level(logging.INFO, logger="test_istek_logla"):
        istek_logla(
            logger,
            endpoint="/index",
            metod="POST",
            sure_ms=5.0,
            durum_kodu=201,
            belge_id="d01",
        )

    assert len(caplog.records) == 1
    kayit = caplog.records[0]
    assert kayit.endpoint == "/index"
    assert kayit.metod == "POST"
    assert kayit.sure_ms == 5.0
    assert kayit.durum_kodu == 201
    assert kayit.belge_id == "d01"
