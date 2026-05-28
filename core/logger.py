"""Logging setup."""

from __future__ import annotations

import logging
import sys

from config import LOG_LEVEL


def setup_logger(name: str = "jarvis") -> logging.Logger:
    """Configure and return the application logger."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    logger.addHandler(handler)
    return logger
