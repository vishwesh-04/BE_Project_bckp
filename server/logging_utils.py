from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(log_path: str, logger_name: str) -> logging.Logger:
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger()
    if not any(isinstance(handler, RotatingFileHandler) and handler.baseFilename == str(path) for handler in root_logger.handlers):
        file_handler = RotatingFileHandler(str(path), maxBytes=2_000_000, backupCount=5)
        file_handler.setFormatter(formatter)
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(stream_handler)

    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    return logger
