"""Project skeleton creation utilities."""

from pathlib import Path
from typing import List


def detect_file_conflicts(project_dir: Path) -> List[Path]:
    """
    Detect files that would be overwritten when creating project skeleton.

    Args:
        project_dir: Project directory path to check

    Returns:
        List of file paths that already exist and would be overwritten
    """
    conflicts = []

    # Get template directory path
    template_dir = Path(__file__).parent / "skeleton_template"

    if not template_dir.exists():
        return conflicts

    # Check each template file against target directory
    for template_file in template_dir.rglob("*"):
        if template_file.is_file():
            relative_path = template_file.relative_to(template_dir)
            target_file = project_dir / relative_path

            if target_file.exists():
                conflicts.append(relative_path)

    return conflicts


def create_project_skeleton(project_dir: Path, force: bool = False) -> List[str]:
    """
    Create Flash project skeleton from template directory.

    Args:
        project_dir: Project directory path
        force: Overwrite existing files

    Returns:
        List of created file paths
    """
    created_files = []

    # Get template directory path
    template_dir = Path(__file__).parent / "skeleton_template"

    if not template_dir.exists():
        raise FileNotFoundError(f"Template directory not found: {template_dir}")

    # Create project directory
    project_dir.mkdir(parents=True, exist_ok=True)

    # Walk through template directory and copy files
    for template_file in template_dir.rglob("*"):
        if template_file.is_file():
            # Get relative path from template dir
            relative_path = template_file.relative_to(template_dir)
            target_file = project_dir / relative_path

            # Skip existing files unless force is True
            if target_file.exists() and not force:
                continue

            # Create parent directories if needed
            target_file.parent.mkdir(parents=True, exist_ok=True)

            # Read content and handle template substitutions
            content = template_file.read_text()

            # Replace {{project_name}} placeholder
            if "{{project_name}}" in content:
                content = content.replace("{{project_name}}", project_dir.name)

            # Write file
            target_file.write_text(content)
            created_files.append(str(relative_path))

    return created_files
