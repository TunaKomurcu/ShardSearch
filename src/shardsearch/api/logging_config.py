"""Structured (JSON) logging.

Rather than adding a new dependency (structlog, python-json-logger,
etc.), Python's built-in `logging` module is used with a custom
`Formatter` — formatting a log line as JSON really just means turning a
dict into a line with `json.dumps`, not complex enough to need a separate
library, and more in the spirit of understanding it from scratch.

Why stdout: in a containerized/production environment this is the
default place a log collection system (e.g. a log shipper) reads from —
writing to a file and managing rotation is out of scope here.
"""

import json
import logging
import sys
from typing import Any

LOGGER_NAME = "shardsearch"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line: dict[str, Any] = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        # Fields added via logger.info(..., extra={...}) (endpoint,
        # duration_ms, etc.) end up mixed in among LogRecord's normal
        # attributes — diff against the "expected" attribute set to tell
        # them apart.
        standard_fields = logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()
        for key, value in record.__dict__.items():
            if key not in standard_fields:
                line[key] = value
        return json.dumps(line, ensure_ascii=False, default=str)


def setup_logging() -> None:
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return  # already set up (e.g. avoid re-adding handlers across repeated test calls)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def log_request(
    logger: logging.Logger,
    *,
    endpoint: str,
    method: str,
    duration_ms: float,
    status_code: int,
    **extra: Any,
) -> None:
    logger.info(
        "request",
        extra={
            "endpoint": endpoint,
            "method": method,
            "duration_ms": round(duration_ms, 2),
            "status_code": status_code,
            **extra,
        },
    )
