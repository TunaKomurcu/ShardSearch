"""Faz 10: yapılandırılmış (JSON) log.

Yeni bir bağımlılık (structlog, python-json-logger vb.) eklemek yerine
Python'un yerleşik `logging` modülünü özel bir `Formatter` ile
kullanıyoruz — JSON log formatlamak aslında sadece bir dict'i
`json.dumps` ile satıra çevirmekten ibaret, ayrı bir kütüphane
gerektirecek kadar karmaşık değil, ve "sıfırdan anlama" hedefiyle daha
uyumlu.

Neden stdout: bu bir konteynerize/prod ortamda log toplama sisteminin
(ör. bir log shipper) stdin'den okuyacağı varsayılan yer — dosyaya yazıp
rotasyon yönetmek bu fazın kapsamı değil.
"""

import json
import logging
import sys
from typing import Any

LOGGER_ADI = "shardsearch"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        satir: dict[str, Any] = {
            "zaman": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "seviye": record.levelname,
            "mesaj": record.getMessage(),
        }
        # logger.info(..., extra={...}) ile eklenen alanlar (endpoint,
        # sure_ms, vb.) LogRecord'un normal attribute'ları arasına
        # karışır — bunları ayırt etmek için "beklenen" attribute
        # kümesiyle farkını alıyoruz.
        standart_alanlar = logging.LogRecord(
            "", 0, "", 0, "", (), None
        ).__dict__.keys()
        for anahtar, deger in record.__dict__.items():
            if anahtar not in standart_alanlar:
                satir[anahtar] = deger
        return json.dumps(satir, ensure_ascii=False, default=str)


def logging_kur() -> None:
    logger = logging.getLogger(LOGGER_ADI)
    if logger.handlers:
        return  # zaten kurulmuş (ör. testlerde tekrar tekrar çağrılmasın)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def istek_logla(
    logger: logging.Logger,
    *,
    endpoint: str,
    metod: str,
    sure_ms: float,
    durum_kodu: int,
    **ekstra: Any,
) -> None:
    logger.info(
        "istek",
        extra={
            "endpoint": endpoint,
            "metod": metod,
            "sure_ms": round(sure_ms, 2),
            "durum_kodu": durum_kodu,
            **ekstra,
        },
    )
