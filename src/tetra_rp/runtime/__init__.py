"""flash runtime utilities for production execution."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_UNPACKED = False


def _should_unpack_from_volume() -> bool:
    if os.getenv("FLASH_DISABLE_UNPACK") in {"1", "true", "yes"}:
        return False

    # only do this on runpod; local imports during build/tests should not touch /app
    if not (os.getenv("RUNPOD_POD_ID") or os.getenv("RUNPOD_ENDPOINT_ID")):
        return False

    return True


def _maybe_unpack() -> None:
    global _UNPACKED
    if _UNPACKED:
        return
    if not _should_unpack_from_volume():
        return

    _UNPACKED = True

    try:
        from tetra_rp.runtime.unpack_volume import unpack_app_from_volume

        unpack_app_from_volume()
    except Exception as e:
        logger.error("flash bootstrap from shadow failed: %s", e, exc_info=True)


_maybe_unpack()
