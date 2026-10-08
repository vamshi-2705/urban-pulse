"""Central logging utility for UrbanPulse Geospatial AI Engine."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from config.settings import get_config

_LOGGING_INITIALIZED = False


def setup_logging(
    level: Optional[str] = None,
    log_file: Optional[Path | str] = None,
    log_to_console: bool = True,
    force: bool = False,
) -> None:
    """
    Initialize the root logger and configure handlers based on settings.

    Args:
        level: Optional log level override (e.g. 'DEBUG', 'INFO').
        log_file: Optional path override for file logs.
        log_to_console: Whether to attach console StreamHandler.
    """
    global _LOGGING_INITIALIZED

    cfg = get_config()
    log_level_name = level or cfg.logging.level
    log_level = getattr(logging, log_level_name.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # If already initialized and not forced, return
    if _LOGGING_INITIALIZED and not force:
        return

    formatter = logging.Formatter(
        fmt=cfg.logging.format,
        datefmt=cfg.logging.date_format,
    )

    if force:
        # Clear existing handlers to prevent duplicate streams
        root_logger.handlers.clear()

    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # Determine file handler target
    target_file = Path(log_file) if log_file else cfg.logging.log_file
    target_file.parent.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        filename=target_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    _LOGGING_INITIALIZED = True


def get_logger(name: str) -> logging.Logger:
    """
    Obtain a named logger configured with the UrbanPulse logging format.

    Args:
        name: Name of the logger (conventionally __name__).

    Returns:
        logging.Logger instance.
    """
    if not _LOGGING_INITIALIZED:
        setup_logging()
    return logging.getLogger(name)
