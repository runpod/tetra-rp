"""Configuration management for tetra-rp CLI."""

from pathlib import Path
from typing import NamedTuple


class TetraPaths(NamedTuple):
    """Paths for tetra-rp configuration and data."""

    tetra_dir: Path
    config_file: Path
    deployments_file: Path

    def ensure_tetra_dir(self) -> None:
        """Ensure the .tetra directory exists."""
        self.tetra_dir.mkdir(exist_ok=True)


def get_paths() -> TetraPaths:
    """Get standardized paths for tetra-rp configuration."""
    tetra_dir = Path.cwd() / ".tetra"
    config_file = tetra_dir / "config.json"
    deployments_file = tetra_dir / "deployments.json"

    return TetraPaths(
        tetra_dir=tetra_dir,
        config_file=config_file,
        deployments_file=deployments_file,
    )
