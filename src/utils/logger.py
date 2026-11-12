"""
Logging helpers.

The whole application shares one logger tree rooted at ``inventory_optimization``.
Call :func:`setup_logging` once at program start (``main.py`` does this); every
module then simply uses ``logger = get_logger(__name__)``.

Messages go to the console (plain text) and, optionally, to one log file per day.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

ROOT_LOGGER_NAME = "inventory_optimization"

_FILE_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def setup_logging(log_dir: Optional[Path] = None, level: int = logging.INFO) -> logging.Logger:
    """Configure console (and optional daily file) output for the application."""
    root = logging.getLogger(ROOT_LOGGER_NAME)
    root.setLevel(level)
    root.handlers.clear()
    root.propagate = False

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(console)

    if log_dir is not None:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{datetime.now():%Y-%m-%d}.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(_FILE_FORMAT, "%Y-%m-%d %H:%M:%S"))
        root.addHandler(file_handler)

    return root


def get_logger(name: str) -> logging.Logger:
    """Return a child logger. Falls back to console-only logging if not set up yet."""
    if not logging.getLogger(ROOT_LOGGER_NAME).handlers:
        setup_logging()
    short_name = name.split(".")[-1]
    return logging.getLogger(f"{ROOT_LOGGER_NAME}.{short_name}")
