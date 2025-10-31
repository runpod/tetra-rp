"""Ignore pattern matching utilities for Flash build."""

import logging
from pathlib import Path
from typing import List

import pathspec

log = logging.getLogger(__name__)


def parse_ignore_file(file_path: Path) -> List[str]:
    """
    Parse an ignore file and return list of patterns.

    Args:
        file_path: Path to ignore file (.flashignore or .gitignore)

    Returns:
        List of pattern strings
    """
    if not file_path.exists():
        return []

    try:
        content = file_path.read_text()
        patterns = []

        for line in content.splitlines():
            line = line.strip()
            # Skip empty lines and comments
            if line and not line.startswith("#"):
                patterns.append(line)

        return patterns

    except Exception as e:
        log.warning(f"Failed to read {file_path.name}: {e}")
        return []


def load_ignore_patterns(project_dir: Path) -> pathspec.PathSpec:
    """
    Load ignore patterns from .flashignore and .gitignore files.

    Args:
        project_dir: Flash project directory

    Returns:
        PathSpec object for pattern matching
    """
    patterns = []

    # Load .flashignore
    flashignore = project_dir / ".flashignore"
    if flashignore.exists():
        flash_patterns = parse_ignore_file(flashignore)
        patterns.extend(flash_patterns)
        log.debug(f"Loaded {len(flash_patterns)} patterns from .flashignore")

    # Load .gitignore
    gitignore = project_dir / ".gitignore"
    if gitignore.exists():
        git_patterns = parse_ignore_file(gitignore)
        patterns.extend(git_patterns)
        log.debug(f"Loaded {len(git_patterns)} patterns from .gitignore")

    # Always exclude build artifacts
    always_ignore = [
        ".build/",
        ".tetra/",
        "*.tar.gz",
        ".git/",
    ]
    patterns.extend(always_ignore)

    # Create PathSpec with gitwildmatch pattern (gitignore-style)
    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


def should_ignore(file_path: Path, spec: pathspec.PathSpec, base_dir: Path) -> bool:
    """
    Check if a file should be ignored based on patterns.

    Args:
        file_path: File path to check
        spec: PathSpec object with ignore patterns
        base_dir: Base directory for relative path calculation

    Returns:
        True if file should be ignored
    """
    try:
        # Get relative path for pattern matching
        rel_path = file_path.relative_to(base_dir)

        # Check if file matches any ignore pattern
        return spec.match_file(str(rel_path))

    except ValueError:
        # file_path is not relative to base_dir
        return False


def get_file_tree(
    directory: Path, spec: pathspec.PathSpec, base_dir: Path | None = None
) -> List[Path]:
    """
    Recursively collect all files in directory excluding ignored patterns.

    Args:
        directory: Directory to scan
        spec: PathSpec object with ignore patterns
        base_dir: Base directory for relative paths (defaults to directory)

    Returns:
        List of file paths that should be included
    """
    if base_dir is None:
        base_dir = directory

    files = []

    try:
        for item in directory.iterdir():
            # Check if should ignore
            if should_ignore(item, spec, base_dir):
                log.debug(f"Ignoring: {item.relative_to(base_dir)}")
                continue

            if item.is_file():
                files.append(item)
            elif item.is_dir():
                # Recursively collect files from subdirectory
                files.extend(get_file_tree(item, spec, base_dir))

    except PermissionError as e:
        log.warning(f"Permission denied: {directory} - {e}")

    return files
