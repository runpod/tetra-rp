"""Project initialization command."""

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..utils.skeleton import create_project_skeleton
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
    project_name: str = typer.Argument(..., help="Project name"),
    no_env: bool = typer.Option(
        False, "--no-env", help="Skip conda environment creation"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Overwrite existing directory"
    ),
):
    """Create new Flash project with Flash Server and GPU workers."""

    # Create project directory
    project_dir = Path(project_name)

    if project_dir.exists() and not force:
        console.print(f"Directory '{project_name}' already exists")
        console.print("Use --force to overwrite")
        raise typer.Exit(1)

    # Create project directory
    project_dir.mkdir(parents=True, exist_ok=True)

    with console.status(f"Creating Flash project '{project_name}'..."):
        create_project_skeleton(project_dir, force)

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
            if environment_exists(project_name):
                console.print(
                    f"[yellow]Conda environment '{project_name}' already exists. Skipping creation.[/yellow]"
                )
                env_created = True
            else:
                # Create conda environment
                with console.status(f"Creating conda environment '{project_name}'..."):
                    success, message = create_conda_environment(project_name)

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
                            project_name, REQUIRED_PACKAGES, use_pip=True
                        )

                    if not success:
                        console.print(f"[yellow]Warning: {message}[/yellow]")
                        console.print(
                            "You can manually install dependencies: pip install -r requirements.txt"
                        )

    # Success output
    panel_content = (
        f"Flash project '[bold]{project_name}[/bold]' created successfully!\n\n"
    )
    panel_content += "Project structure:\n"
    panel_content += f"  {project_name}/\n"
    panel_content += "  ├── main.py              # Flash Server (FastAPI)\n"
    panel_content += "  ├── workers/             # GPU workers\n"
    panel_content += "  │   └── example_worker.py\n"
    panel_content += "  ├── .env.example\n"
    panel_content += "  ├── requirements.txt\n"
    panel_content += "  └── README.md\n"

    if env_created:
        panel_content += (
            f"\nConda environment '[bold]{project_name}[/bold]' created and configured"
        )

    console.print(Panel(panel_content, title="Project Created", expand=False))

    # Next steps
    console.print("\n[bold]Next steps:[/bold]")
    steps_table = Table(show_header=False, box=None, padding=(0, 1))
    steps_table.add_column("Step", style="bold cyan")
    steps_table.add_column("Description")

    steps_table.add_row("1.", f"cd {project_name}")

    if env_created:
        steps_table.add_row("2.", f"{get_activation_command(project_name)}")
        steps_table.add_row("3.", "cp .env.example .env  # Add your RUNPOD_API_KEY")
        steps_table.add_row("4.", "flash run")
    else:
        steps_table.add_row("2.", "pip install -r requirements.txt")
        steps_table.add_row("3.", "cp .env.example .env  # Add your RUNPOD_API_KEY")
        steps_table.add_row("4.", "flash run")

    console.print(steps_table)
