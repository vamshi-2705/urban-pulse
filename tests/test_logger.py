"""Tests verifying logging functionality."""

import logging
from pathlib import Path
from geospatial.logger import get_logger, setup_logging
from config.settings import get_config


def test_logger_initialization():
    """Verify that get_logger produces a functioning logger instance."""
    logger = get_logger("test_module")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_module"


def test_logging_execution(tmp_path: Path):
    """Verify logger writes messages without throwing exceptions."""
    test_log_file = tmp_path / "test_run.log"
    setup_logging(level="DEBUG", log_file=test_log_file, force=True)
    logger = get_logger("test_writer")

    logger.debug("Debug test message")
    logger.info("Info test message")
    logger.warning("Warning test message")

    # Flush all handlers to ensure buffer is written to disk
    for handler in logging.getLogger().handlers:
        handler.flush()

    assert test_log_file.exists()
    content = test_log_file.read_text(encoding="utf-8")
    assert "Info test message" in content
