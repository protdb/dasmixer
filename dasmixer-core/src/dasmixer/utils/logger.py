"""Logging configuration for DASMixer.

DASMixer uses a single named logger ``dasmixer`` with a console handler
attached at import time. All module loggers should be obtained via either:

- ``from dasmixer.utils.logger import logger`` — returns the ``dasmixer``
  logger (shared).
- ``logging.getLogger("dasmixer.<sub>")`` — a child of ``dasmixer`` that
  propagates upward.
- ``logging.getLogger(__name__)`` — works too, since all DASMixer modules
  are under the ``dasmixer`` namespace.

Runtime configuration (level, file handler) is applied by
``dasmixer.gui.views.settings_view._apply_logging_config`` based on the
user's ``AppConfig``. The console handler here uses level ``NOTSET`` so it
never filters independently — the logger level is the sole gatekeeper and
can be changed at runtime without re-creating handlers.
"""

import logging
import sys
from pathlib import Path

_APP_LOGGER_NAME = "dasmixer"


def setup_logger(
    name: str = _APP_LOGGER_NAME,
    level: int = logging.INFO,
    log_file: Path | str | None = None
) -> logging.Logger:
    """
    Setup application logger.

    Creates a named logger with a console handler (stdout). The handler is
    created with level ``NOTSET`` so it does not filter independently —
    the logger level (settable at runtime) is the sole gatekeeper.

    Args:
        name: Logger name (default ``"dasmixer"``).
        level: Initial logging level (overridden by AppConfig at startup).
        log_file: Optional log file path.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Prevent duplicate handlers on re-import
    if logger.handlers:
        return logger

    # Console handler — level NOTSET delegates to the logger level
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.NOTSET)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (optional — also uses NOTSET to delegate)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.NOTSET)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# Default logger — created once at import time with a console handler.
# Runtime level / file handler are applied by _apply_logging_config().
logger = setup_logger()
