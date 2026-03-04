"""
Structured Logging Adapter
============================
Provides structured, JSON-capable logging with context binding.
Uses `structlog` when available, falls back to stdlib `logging`.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

_HAS_STRUCTLOG = False
try:
    import structlog

    _HAS_STRUCTLOG = True
except ImportError:
    pass


def get_logger(name: str = "matchmaker", **initial_context: Any):
    """Get a structured logger.

    If structlog is installed it returns a BoundLogger; otherwise a
    stdlib Logger wrapped with a thin JSON formatter.
    """
    if _HAS_STRUCTLOG:
        return _get_structlog_logger(name, **initial_context)
    return _get_stdlib_logger(name, **initial_context)


def _get_structlog_logger(name: str, **context: Any):
    """Configure and return a structlog BoundLogger."""
    import structlog

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            (
                structlog.dev.ConsoleRenderer()
                if os.environ.get("LOG_FORMAT", "json") != "json"
                else structlog.processors.JSONRenderer()
            ),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(os.environ.get("LOG_LEVEL", "INFO").upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    return structlog.get_logger(name, **context)


class _JSONFormatter(logging.Formatter):
    """Custom JSON formatter for stdlib logging."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "context"):
            entry["context"] = record.context
        if record.exc_info and record.exc_info[1]:
            entry["exception"] = str(record.exc_info[1])
        return json.dumps(entry)


class _ContextAdapter(logging.LoggerAdapter):
    """Logger adapter that carries a bound context dict."""

    def process(self, msg, kwargs):
        extra = kwargs.setdefault("extra", {})
        extra["context"] = self.extra
        return msg, kwargs

    def bind(self, **new_context: Any) -> "_ContextAdapter":
        """Return a new adapter with additional context."""
        merged = {**self.extra, **new_context}
        return _ContextAdapter(self.logger, merged)


def _get_stdlib_logger(name: str, **context: Any) -> _ContextAdapter:
    """Set up a stdlib logger with JSON formatting."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        log_format = os.environ.get("LOG_FORMAT", "json")
        if log_format == "json":
            handler.setFormatter(_JSONFormatter())
        else:
            handler.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
            )
        logger.addHandler(handler)

    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    logger.setLevel(logging.getLevelName(level_name))

    return _ContextAdapter(logger, context)
