from pathlib import Path


def discover_flash_project() -> tuple[Path, str]:
    """
    Discover Flash project directory and app name.
    Returns:
        Tuple of (project_dir, app_name)
    Raises:
        typer.Exit: If not in a Flash project directory
    """
    project_dir = Path.cwd()
    app_name = project_dir.name

    return project_dir, app_name
