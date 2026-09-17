"""Phase 10 tests: the JSON log formatter and its helper functions.

Rather than capturing real stdout (the handler pins a reference to
sys.stdout at import time, which pytest's capsys can't intercept), we
directly verify the string produced by JsonFormatter.format() and the
attributes of the LogRecord that log_request() builds (via caplog).
"""

import json
import logging

from shardsearch.api.logging_config import JsonFormatter, log_request


def _make_record(extra: dict | None = None) -> logging.LogRecord:
    logger = logging.getLogger("test_formatter")
    return logger.makeRecord(
        "test_formatter", logging.INFO, __file__, 0, "message", (), None, extra=extra
    )


def test_json_formatter_produces_valid_json() -> None:
    output = JsonFormatter().format(_make_record())
    parsed = json.loads(output)  # blows up here if not valid JSON
    assert parsed["message"] == "message"
    assert parsed["level"] == "INFO"
    assert "time" in parsed


def test_json_formatter_carries_extra_fields() -> None:
    record = _make_record(extra={"endpoint": "/search", "duration_ms": 12.3})
    output = json.loads(JsonFormatter().format(record))
    assert output["endpoint"] == "/search"
    assert output["duration_ms"] == 12.3


def test_json_formatter_writes_turkish_characters_without_mangling_them() -> None:
    record = _make_record(extra={"query": "kedi AND köpek"})
    output = JsonFormatter().format(record)
    assert "köpek" in output  # ensure_ascii=False: a real letter, not an escape sequence


def test_log_request_is_called_with_the_expected_fields(caplog) -> None:
    logger = logging.getLogger("test_log_request")
    logger.setLevel(logging.INFO)
    with caplog.at_level(logging.INFO, logger="test_log_request"):
        log_request(
            logger,
            endpoint="/index",
            method="POST",
            duration_ms=5.0,
            status_code=201,
            doc_id="d01",
        )

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.endpoint == "/index"
    assert record.method == "POST"
    assert record.duration_ms == 5.0
    assert record.status_code == 201
    assert record.doc_id == "d01"
