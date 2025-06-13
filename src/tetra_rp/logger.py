import inspect
import logging
import os
import sys
from typing import Union, Optional


def setup_logging(
    level: Union[int, str] = logging.INFO, stream=sys.stdout, fmt: Optional[str] = None
):
    """
    Sets up the root logger with a stream handler and basic formatting.
    Does nothing if handlers are already configured.
    """
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    if fmt is None:
        if level == logging.DEBUG:
            fmt = "%(asctime)s | %(levelname)-5s | %(name)s | %(filename)s:%(lineno)d | %(message)s"
        else:
            # Default format for INFO level and above
            fmt = "%(asctime)s | %(levelname)-5s | %(message)s"

    root_logger = logging.getLogger()
    if not root_logger.hasHandlers():
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter(fmt))
        root_logger.setLevel(level)
        root_logger.addHandler(handler)

    # Optionally allow log level override via env var
    env_level = os.environ.get("LOG_LEVEL")
    if env_level:
        root_logger.setLevel(env_level.upper())


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Returns a logger. If no name is provided, it infers the caller's module name.
    """
    if name is None:
        # Get the caller's module name.
        frame = inspect.stack()[1]
        module = inspect.getmodule(frame[0])
        name = module.__name__ if module else "__main__"

    return logging.getLogger(name)


setup_logging(os.environ.get("LOG_LEVEL", "INFO"))
