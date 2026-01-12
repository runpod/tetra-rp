"""tests for runtime bootstrap."""

from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest

from tetra_rp.runtime.unpack_volume import _safe_extract_tar, unpack_app_from_volume


def _write_tar_gz(path: Path, files: dict[str, bytes]) -> None:
    with tarfile.open(path, mode="w:gz") as tf:
        for name, data in files.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))


def test_finds_archive_via_env_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    app_dir = tmp_path / "app"
    shadow_dir = tmp_path / "shadow"
    shadow_dir.mkdir()

    artifact = shadow_dir / "archive.tar.gz"
    _write_tar_gz(
        artifact,
        {
            "flash_manifest.json": b'{"version":"1.0"}\n',
            "ok.txt": b"ok\n",
        },
    )

    monkeypatch.setenv("FLASH_BUILD_ARTIFACT_PATH", str(artifact))
    ok = unpack_app_from_volume(app_dir=app_dir)
    assert ok is True
    assert (app_dir / "ok.txt").read_text() == "ok\n"


def test_rejects_path_traversal(tmp_path: Path):
    app_dir = tmp_path / "app"
    app_dir.mkdir()

    artifact = tmp_path / "evil.tar.gz"
    _write_tar_gz(
        artifact,
        {
            "../evil.txt": b"nope\n",
        },
    )

    with tarfile.open(artifact, mode="r:gz") as tf:
        with pytest.raises(ValueError, match="unsafe tar member path"):
            _safe_extract_tar(tf, app_dir)
