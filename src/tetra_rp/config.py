"""Configuration management for tetra-rp CLI."""

from pathlib import Path
from typing import NamedTuple


class FlashPaths(NamedTuple):
    """Paths for Flash CLI configuration and data."""

    flash_dir: Path
    config_file: Path
    deployments_file: Path

    def ensure_flash_dir(self) -> None:
        """Ensure the .flash directory exists."""
        self.flash_dir.mkdir(exist_ok=True)


def get_paths() -> FlashPaths:
    """Get standardized paths for Flash CLI configuration."""
    flash_dir = Path.cwd() / ".flash"
    config_file = flash_dir / "config.json"
    deployments_file = flash_dir / "deployments.json"

    return FlashPaths(
        flash_dir=flash_dir,
        config_file=config_file,
        deployments_file=deployments_file,
    )
