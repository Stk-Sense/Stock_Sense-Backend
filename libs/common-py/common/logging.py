"""Structured JSON logging with correlation IDs."""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Optional

_correlation_id_ctx: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> Optional[str]:
    """Return the current correlation ID in context."""
    return _correlation_id_ctx.get()


def set_correlation_id(correlation_id: Optional[str]) -> None:
    """Set the correlation ID in context."""
    _correlation_id_ctx.set(correlation_id)


class JSONFormatter(logging.Formatter):
    """Formats log records as structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": get_correlation_id() or getattr(record, "correlation_id", None),
        }

        # Include exception info if present
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # Include custom extra fields passed in record.__dict__
        standard_keys = {
            "args", "asctime", "created", "exc_info", "exc_text", "filename", "funcName",
            "levelname", "levelno", "lineno", "module", "msecs", "msg", "name",
            "pathname", "process", "processName", "relativeCreated", "stack_info",
            "thread", "threadName", "correlation_id",
        }
        extras = {k: v for k, v in record.__dict__.items() if k not in standard_keys}
        if extras:
            payload["extra"] = extras

        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger with the structured JSON formatter."""
    root_logger = logging.getLogger()
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)

    # Remove existing handlers to avoid duplicates
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)
