"""
Centralized logging configuration.

Sets up structured console logging with timestamps, log levels,
and module names. The log level is controlled by the LOG_LEVEL
setting in config.py.

Usage:
    from app.logging_config import setup_logging
    setup_logging()
"""

import logging
import sys
from typing import Optional


def setup_logging(level: Optional[str] = None) -> None:
    """
    Configure application-wide logging.

    Args:
        level: Override log level (e.g. "DEBUG", "INFO"). When None,
               the value is read from the Settings object so this
               function can also be called early in tests.
    """
    # Import here to avoid circular import during early startup
    from app.config import settings

    log_level_str = (level or settings.LOG_LEVEL).upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    log_format = (
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )
    date_format = "%Y-%m-%d %H:%M:%S"

    # Remove any handlers that libraries (e.g. uvicorn) may have
    # attached before we configure, so we own the format.
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    formatter = logging.Formatter(fmt=log_format, datefmt=date_format)
    handler.setFormatter(formatter)

    root_logger.setLevel(log_level)
    root_logger.addHandler(handler)

    # Quieten noisy third-party loggers in non-debug modes
    if log_level > logging.DEBUG:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger.

    Convenience wrapper so callers don't need to import the stdlib
    logging module separately.

    Example:
        logger = get_logger(__name__)
        logger.info("Application started")
    """
    return logging.getLogger(name)
