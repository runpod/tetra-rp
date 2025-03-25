# logger_util.py
import logging
import inspect


def setup_logging(level=logging.INFO, fmt=None):
    if fmt is None:
        fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(level=level, format=fmt)


def get_logger(name=None):
    """
    Returns a logger. If no name is provided, it infers the caller's module name.
    """
    if name is None:
        # Get the caller's module name.
        frame = inspect.stack()[1]
        module = inspect.getmodule(frame[0])
        name = module.__name__ if module else "__main__"
    return logging.getLogger(name)
