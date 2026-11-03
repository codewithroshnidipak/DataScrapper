"""
Logger Module
Configures dual logging to console and rotating log file.
"""

import sys
import logging
from logging.handlers import RotatingFileHandler
from settings import LOG_LEVEL, LOG_FILE_PATH

def setup_logger(name: str = "LeadScraper") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    logger.propagate = False

    if not logger.handlers:
        formatter = logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        # File Handler (5 MB max, 3 backups)
        file_handler = RotatingFileHandler(
            LOG_FILE_PATH,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
        logger.addHandler(file_handler)

        # Console Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
        logger.addHandler(console_handler)

    return logger

logger = setup_logger()

