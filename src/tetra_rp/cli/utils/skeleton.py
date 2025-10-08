"""Project skeleton creation utilities."""

from pathlib import Path
from typing import Dict, List, Any

from tetra_rp.config import get_paths


def get_template_directory() -> Path:
    """Get the path to the templates directory."""
    return Path(__file__).parent.parent / "templates"


def load_template_files(template_name: str) -> Dict[str, Any]:
    """Load template files from filesystem."""
    template_dir = get_template_directory() / template_name

    if not template_dir.exists():
        raise ValueError(f"Template '{template_name}' not found in {template_dir}")

    files = {}

    # Load all files from the template directory
    for file_path in template_dir.iterdir():
        if file_path.is_file():
            relative_path = file_path.name

            # Special handling for config.json - return as callable that generates tetra config
            if file_path.name == "config.json":
                config_content = file_path.read_text()
                files[".tetra/config.json"] = lambda content=config_content: content
            else:
                files[relative_path] = file_path.read_text()

    return files


def get_available_templates() -> Dict[str, Dict[str, Any]]:
    """Get available project templates from filesystem."""
    template_dir = get_template_directory()
    templates = {}

    # Template descriptions
    descriptions = {
        "basic": "Simple remote function example",
        "advanced": "Multi-function project with dependencies",
        "gpu-compute": "GPU-optimized compute workload",
        "web-api": "FastAPI web service deployment",
    }

    # Discover templates from filesystem
    for template_path in template_dir.iterdir():
        if template_path.is_dir():
            template_name = template_path.name
            try:
                templates[template_name] = {
                    "description": descriptions.get(
                        template_name, f"{template_name} template"
                    ),
                    "files": load_template_files(template_name),
                }
            except Exception as e:
                print(f"Warning: Failed to load template '{template_name}': {e}")

    return templates


def create_project_skeleton(
    template_name: str, template_info: Dict[str, Any], force: bool = False
) -> List[str]:
    """Create project skeleton from template."""
    created_files = []

    # Create .tetra directory using centralized config
    paths = get_paths()
    paths.ensure_tetra_dir()

    # Create files from template
    for file_path, content in template_info["files"].items():
        path = Path(file_path)

        # Create parent directories if needed
        path.parent.mkdir(parents=True, exist_ok=True)

        # Skip existing files unless force is True
        if path.exists() and not force:
            continue

        # Get content (could be string or callable)
        if callable(content):
            file_content = content()
        else:
            file_content = content

        # Write file
        with open(path, "w") as f:
            f.write(file_content)

        created_files.append(str(path))

    return created_files
