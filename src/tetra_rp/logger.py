import logging
import os
import sys
from typing import Union, Optional

# Import Rich UI components with fallback
try:
    from .core.utils.rich_ui import get_rich_handler, is_rich_enabled

    RICH_UI_AVAILABLE = True
except ImportError:
    RICH_UI_AVAILABLE = False


def setup_logging(
    level: Union[int, str] = logging.INFO, stream=sys.stdout, fmt: Optional[str] = None
):
    """
    Sets up the root logger with a stream handler and basic formatting.
    Uses Rich handler if available and enabled, otherwise falls back to standard logging.
    Does nothing if handlers are already configured.
    """
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    if not root_logger.hasHandlers():
        # Use Rich handler if available and enabled
        if RICH_UI_AVAILABLE and is_rich_enabled():
            handler = get_rich_handler()
            # When Rich UI is enabled, reduce log verbosity to focus on Rich output
            if level <= logging.INFO:
                level = logging.WARNING  # Only show warnings and errors
        else:
            # Fallback to standard handler
            if fmt is None:
                if level == logging.DEBUG:
                    fmt = "%(asctime)s | %(levelname)-5s | %(name)s | %(filename)s:%(lineno)d | %(message)s"
                else:
                    # Default format for INFO level and above
                    fmt = "%(asctime)s | %(levelname)-5s | %(message)s"

            handler = logging.StreamHandler(stream)
            handler.setFormatter(logging.Formatter(fmt))

        root_logger.setLevel(level)
        root_logger.addHandler(handler)

    # Optionally allow log level override via env var
    env_level = os.environ.get("LOG_LEVEL")
    if env_level:
        root_logger.setLevel(env_level.upper())
    elif RICH_UI_AVAILABLE and is_rich_enabled():
        # Suppress routine logs when Rich UI is active, unless explicitly overridden
        if not os.environ.get("LOG_LEVEL"):
            root_logger.setLevel(logging.WARNING)
            # Also suppress specific noisy loggers
            for logger_name in [
                "tetra_rp",
                "serverless",
                "resource_manager",
                "LiveServerlessStub",
                "asyncio",
            ]:
                specific_logger = logging.getLogger(logger_name)
                specific_logger.setLevel(logging.WARNING)

            # Add global filter to catch any remaining debug messages
            from .core.utils.rich_ui import RichLoggingFilter

            global_filter = RichLoggingFilter()
            root_logger.addFilter(global_filter)
