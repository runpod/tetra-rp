from __future__ import annotations

import logging
import os
import sys
import tarfile
from pathlib import Path

logger = logging.getLogger(__name__)


def _safe_extract_tar(tar: tarfile.TarFile, target_dir: Path) -> None:
    target_dir_resolved = target_dir.resolve()

    for member in tar.getmembers():
        member_path = (target_dir / member.name).resolve()
        if (
            not str(member_path).startswith(str(target_dir_resolved) + os.sep)
            and member_path != target_dir_resolved
        ):
            raise ValueError(f"unsafe tar member path: {member.name}")

    tar.extractall(path=target_dir)


def _canonical_project_artifact_path() -> Path:
    return Path(os.getenv("FLASH_BUILD_ARTIFACT_PATH", "/root/.runpod/archive.tar.gz"))


def unpack_app_from_volume(
    *,
    app_dir: str | Path = "/app",
) -> bool:
    """extract the build artifact from the volume into /app.

    returns true if we installed (or verified) an artifact, false if nothing was found.
    """

    app_dir_path = Path(app_dir)
    app_dir_path.mkdir(parents=True, exist_ok=True)

    # ensure /app is importable
    app_dir_str = str(app_dir_path)
    if app_dir_str not in sys.path:
        sys.path.insert(0, app_dir_str)

    artifact = _canonical_project_artifact_path()

    if not artifact.exists() or not artifact.is_file():
        raise FileNotFoundError(f"flash build artifact not found at {artifact}")

    try:
        with tarfile.open(artifact, mode="r:*") as tf:
            _safe_extract_tar(tf, app_dir_path)
    except Exception as e:
        raise RuntimeError(f"failed to extract flash artifact: {e}") from e

    return True
