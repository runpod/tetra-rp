"""Project initialization command."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..utils.skeleton import create_project_skeleton, detect_file_conflicts
from ..utils.conda import (
    check_conda_available,
    create_conda_environment,
    install_packages_in_env,
    environment_exists,
    get_activation_command,
)

console = Console()

# Required packages for flash run to work smoothly
REQUIRED_PACKAGES = [
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
    "python-dotenv>=1.0.0",
    "pydantic>=2.0.0",
    "aiohttp>=3.9.0",
]


def init_command(
    project_name: Optional[str] = typer.Argument(
        None, help="Project name or '.' for current directory"
    ),
    no_env: bool = typer.Option(
        False, "--no-env", help="Skip conda environment creation"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing files"),
):
    """Create new Flash project with Flash Server and GPU workers."""

    # Determine target directory and initialization mode
    if project_name is None or project_name == ".":
        # Initialize in current directory
        project_dir = Path.cwd()
        is_current_dir = True
        # Use current directory name as project name
        actual_project_name = project_dir.name
    else:
        # Create new directory
        project_dir = Path(project_name)
        is_current_dir = False
        actual_project_name = project_name

    # Create project directory if needed
    if not is_current_dir:
        project_dir.mkdir(parents=True, exist_ok=True)

    # Check for file conflicts in target directory
    conflicts = detect_file_conflicts(project_dir)
    should_overwrite = force  # Start with force flag value

    if conflicts and not force:
        # Show warning and prompt user
        console.print(
            Panel(
                "[yellow]Warning: The following files will be overwritten:[/yellow]\n\n"
                + "\n".join(f"  • {conflict}" for conflict in conflicts),
                title="File Conflicts Detected",
                expand=False,
            )
        )

        # Prompt user for confirmation
        proceed = typer.confirm("Continue and overwrite these files?", default=False)
        if not proceed:
            console.print("[yellow]Initialization aborted.[/yellow]")
            raise typer.Exit(0)

        # User confirmed, so we should overwrite
        should_overwrite = True

    # Create project skeleton
    status_msg = (
        "Initializing Flash project in current directory..."
        if is_current_dir
        else f"Creating Flash project '{project_name}'..."
    )
    with console.status(status_msg):
        create_project_skeleton(project_dir, should_overwrite)

    # Create conda environment if requested
    env_created = False
    if not no_env:
        if not check_conda_available():
            console.print(
                "[yellow]Warning: conda not found. Skipping environment creation.[/yellow]"
            )
            console.print(
                "Install Miniconda or Anaconda, or use --no-env flag to skip this step."
            )
        else:
            # Check if environment already exists
            if environment_exists(actual_project_name):
                console.print(
                    f"[yellow]Conda environment '{actual_project_name}' already exists. Skipping creation.[/yellow]"
                )
                env_created = True
            else:
                # Create conda environment
                with console.status(
                    f"Creating conda environment '{actual_project_name}'..."
                ):
                    success, message = create_conda_environment(actual_project_name)

                if not success:
                    console.print(f"[yellow]Warning: {message}[/yellow]")
                    console.print(
                        "You can manually create the environment and install dependencies."
                    )
                else:
                    env_created = True

                    # Install required packages
                    with console.status("Installing dependencies..."):
                        success, message = install_packages_in_env(
                            actual_project_name, REQUIRED_PACKAGES, use_pip=True
                        )

                    if not success:
                        console.print(f"[yellow]Warning: {message}[/yellow]")
                        console.print(
                            "You can manually install dependencies: pip install -r requirements.txt"
                        )

    # Success output
    if is_current_dir:
        panel_content = f"Flash project '[bold]{actual_project_name}[/bold]' initialized in current directory!\n\n"
        panel_content += "Project structure:\n"
        panel_content += "  ./\n"
    else:
        panel_content = f"Flash project '[bold]{actual_project_name}[/bold]' created successfully!\n\n"
        panel_content += "Project structure:\n"
        panel_content += f"  {actual_project_name}/\n"

    panel_content += "  ├── main.py              # Flash Server (FastAPI)\n"
    panel_content += "  ├── workers/\n"
    panel_content += "  │   ├── gpu/             # GPU worker\n"
    panel_content += "  │   └── cpu/             # CPU worker\n"
    panel_content += "  ├── .env\n"
    panel_content += "  ├── requirements.txt\n"
    panel_content += "  └── README.md\n"

    if env_created:
        panel_content += f"\nConda environment '[bold]{actual_project_name}[/bold]' created and configured"

    title = "Project Initialized" if is_current_dir else "Project Created"
    console.print(Panel(panel_content, title=title, expand=False))

    # Next steps
    console.print("\n[bold]Next steps:[/bold]")
    steps_table = Table(show_header=False, box=None, padding=(0, 1))
    steps_table.add_column("Step", style="bold cyan")
    steps_table.add_column("Description")

    step_num = 1
    if not is_current_dir:
        steps_table.add_row(f"{step_num}.", f"cd {actual_project_name}")
        step_num += 1

    if env_created:
        steps_table.add_row(
            f"{step_num}.", f"{get_activation_command(actual_project_name)}"
        )
        step_num += 1
        steps_table.add_row(f"{step_num}.", "Add your RUNPOD_API_KEY to .env")
        step_num += 1
        steps_table.add_row(f"{step_num}.", "flash run")
    else:
        steps_table.add_row(f"{step_num}.", "pip install -r requirements.txt")
        step_num += 1
        steps_table.add_row(f"{step_num}.", "Add your RUNPOD_API_KEY to .env")
        step_num += 1
        steps_table.add_row(f"{step_num}.", "flash run")

    console.print(steps_table)
