"""Project skeleton creation utilities."""

from fnmatch import fnmatch
from pathlib import Path
from typing import List

# Patterns to ignore during skeleton operations
IGNORE_PATTERNS = {
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".DS_Store",
    "Thumbs.db",
    ".git",
    ".pytest_cache",
    "*.egg-info",
}


def _should_ignore(path: Path) -> bool:
    """
    Check if path matches any ignore pattern.

    Args:
        path: Path to check

    Returns:
        True if path should be ignored, False otherwise
    """
    for pattern in IGNORE_PATTERNS:
        # Check if any path component matches the pattern
        if fnmatch(path.name, pattern):
            return True
        if any(fnmatch(part, pattern) for part in path.parts):
            return True
    return False


def detect_file_conflicts(project_dir: Path) -> List[Path]:
    """
    Detect files that would be overwritten when creating project skeleton.

    Args:
        project_dir: Project directory path to check

    Returns:
        List of file paths that already exist and would be overwritten
    """
    conflicts: List[Path] = []

    # Get template directory path
    template_dir = Path(__file__).parent / "skeleton_template"

    if not template_dir.exists():
        return conflicts

    def check_conflicts_recursive(src_dir: Path) -> None:
        """Recursively check for file conflicts."""
        for item in src_dir.iterdir():
            if _should_ignore(item):
                continue

            relative_path = item.relative_to(template_dir)
            target_file = project_dir / relative_path

            if item.is_dir():
                check_conflicts_recursive(item)
            elif item.is_file():
                if target_file.exists():
                    conflicts.append(relative_path)

    # Start recursive conflict check
    check_conflicts_recursive(template_dir)

    return conflicts


def _copy_template_file(
    item: Path,
    template_dir: Path,
    project_dir: Path,
    force: bool,
    created_files: List[str],
) -> None:
    """
    Copy a single template file with substitutions.

    Args:
        item: Source file path
        template_dir: Template directory base path
        project_dir: Target project directory
        force: Overwrite existing files
        created_files: List to append created file paths to
    """
    relative_path = item.relative_to(template_dir)
    target_path = project_dir / relative_path

    # Skip existing files unless force is True
    if target_path.exists() and not force:
        return

    # Create parent directories if needed
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Read content and handle template substitutions
    try:
        content = item.read_text()

        # Replace {{project_name}} placeholder
        if "{{project_name}}" in content:
            content = content.replace("{{project_name}}", project_dir.name)

        # Write file
        target_path.write_text(content)
        created_files.append(str(relative_path))
    except UnicodeDecodeError:
        # Handle binary files (just copy bytes)
        target_path.write_bytes(item.read_bytes())
        created_files.append(str(relative_path))


def _copy_directory_recursive(
    src_dir: Path,
    template_dir: Path,
    project_dir: Path,
    force: bool,
    created_files: List[str],
) -> None:
    """
    Recursively copy directory contents, including hidden files.

    Args:
        src_dir: Source directory to copy from
        template_dir: Template directory base path
        project_dir: Target project directory
        force: Overwrite existing files
        created_files: List to append created file paths to
    """
    for item in src_dir.iterdir():
        # Skip ignored items
        if _should_ignore(item):
            continue

        if item.is_dir():
            # Create target directory and recurse
            relative_path = item.relative_to(template_dir)
            target_path = project_dir / relative_path
            target_path.mkdir(parents=True, exist_ok=True)
            _copy_directory_recursive(
                item, template_dir, project_dir, force, created_files
            )
        elif item.is_file():
            _copy_template_file(item, template_dir, project_dir, force, created_files)


def create_project_skeleton(project_dir: Path, force: bool = False) -> List[str]:
    """
    Create Flash project skeleton from template directory.

    Args:
        project_dir: Project directory path
        force: Overwrite existing files

    Returns:
        List of created file paths
    """
    created_files: List[str] = []

    # Get template directory path
    template_dir = Path(__file__).parent / "skeleton_template"

    if not template_dir.exists():
        raise FileNotFoundError(f"Template directory not found: {template_dir}")

    # Create project directory
    project_dir.mkdir(parents=True, exist_ok=True)

    # Start recursive copy
    _copy_directory_recursive(
        template_dir, template_dir, project_dir, force, created_files
    )

    return created_files
