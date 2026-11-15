"""Logging setup: one format, secrets redacted, optional JSON output.

LOG_LEVEL   DEBUG | INFO (default) | WARNING | ERROR   (DEBUG also logs query text)
LOG_FORMAT  text (default) | json
"""
import json
import logging
import os
from typing import Iterable


class RedactingFilter(logging.Filter):
    """Replaces any configured secret that ends up in a log message or traceback."""

    def __init__(self, secrets: Iterable[str]):
        super().__init__()
        self._secrets = [s for s in secrets if s and len(s) >= 4]

    def filter(self, record: logging.LogRecord) -> bool:
        if self._secrets:
            msg = record.getMessage()
            for s in self._secrets:
                msg = msg.replace(s, "[REDACTED]")
            record.msg, record.args = msg, None
            if record.exc_info:                      # tracebacks can contain secrets too
                record.exc_text = self.formatter_text(record)
                for s in self._secrets:
                    record.exc_text = record.exc_text.replace(s, "[REDACTED]")
        return True

    @staticmethod
    def formatter_text(record: logging.LogRecord) -> str:
        return logging.Formatter().formatException(record.exc_info)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {"time": self.formatTime(record), "level": record.levelname,
                "logger": record.name, "message": record.getMessage()}
        for key in ("request_id", "method", "path", "status", "duration_ms", "error_type"):
            if hasattr(record, key):
                data[key] = getattr(record, key)
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data)


def setup_logging(secrets: Iterable[str] = ()) -> None:
    handler = logging.StreamHandler()
    if os.getenv("LOG_FORMAT", "text").lower() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    handler.addFilter(RedactingFilter(secrets))
    handler._nl_filter = True                      # marks ours, so repeated calls don't stack handlers
    root = logging.getLogger()
    root.handlers[:] = [h for h in root.handlers if not getattr(h, "_nl_filter", False)] + [handler]
    root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    logging.getLogger("httpx").setLevel(logging.WARNING)   # httpx logs full URLs at INFO
