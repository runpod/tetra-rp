"""Project initialization command."""

from pathlib import Path
from typing import Optional
import asyncio

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..utils.skeleton import create_project_skeleton, detect_file_conflicts
from tetra_rp.core.resources.app import FlashApp

console = Console()

def init_command(
    project_name: Optional[str] = typer.Argument(
        None, help="Project name or '.' for current directory"
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
        asyncio.run(init_app(actual_project_name))
        create_project_skeleton(project_dir, should_overwrite)

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
    panel_content += "  ├── .env.example\n"
    panel_content += "  ├── requirements.txt\n"
    panel_content += "  └── README.md\n"

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

    steps_table.add_row(f"{step_num}.", "pip install -r requirements.txt")
    step_num += 1
    steps_table.add_row(f"{step_num}.", "cp .env.example .env")
    step_num += 1
    steps_table.add_row(f"{step_num}.", "Add your RUNPOD_API_KEY to .env")
    step_num += 1
    steps_table.add_row(f"{step_num}.", "flash run")

    console.print(steps_table)

    console.print("\n[bold]Get your API key:[/bold]")
    console.print("  https://docs.runpod.io/get-started/api-keys")
    console.print("\nVisit http://localhost:8888/docs after running")
    console.print("\nCheck out the README.md for more")

async def init_app(app_name: str):
      try:
          app = await FlashApp.create(app_name)
          await app.create_environment("dev")
          return app
      except Exception as exc:
          msg = str(exc)
          if "Flash app with name" in msg and "already exists" in msg:
              raise typer.BadParameter(f"Flash app with name {app_name} already exists in your account. Choose a different name or delete the existing app to continue.")
          if "Flash env with name" in msg and "already exists" in msg:
              raise typer.BadParameter(f"Flash app with name {app_name} already exists in your account. Choose a different name or delete the existing app to continue.")
          raise  

