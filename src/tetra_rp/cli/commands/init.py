"""Project initialization command."""

import typer
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
import questionary

from tetra_rp.config import get_paths
from ..utils.skeleton import create_project_skeleton, get_available_templates

console = Console()


def init_command(
    template: Optional[str] = typer.Option(
        None, "--template", "-t", help="Project template to use"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing files"),
):
    """Create skeleton application with starter files."""

    # Check if we're already in a Tetra project
    paths = get_paths()
    if paths.tetra_dir.exists() and not force:
        console.print("Already in a Tetra project directory")
        console.print("Use --force to overwrite existing configuration")
        raise typer.Exit(1)

    # Get available templates
    available_templates = get_available_templates()

    # Interactive template selection if not provided
    if not template:
        template_choices = []
        for name, info in available_templates.items():
            template_choices.append(f"{name} - {info['description']}")

        try:
            selected = questionary.select(
                "Choose a project template:", choices=template_choices
            ).ask()

            if not selected:
                console.print("Template selection cancelled")
                raise typer.Exit(1)

            template = selected.split(" - ")[0]
        except KeyboardInterrupt:
            console.print("\nTemplate selection cancelled")
            raise typer.Exit(1)

    # Validate template choice
    if template not in available_templates:
        console.print(f"Unknown template: {template}")
        console.print("Available templates:")
        for name, info in available_templates.items():
            console.print(f"  • {name} - {info['description']}")
        raise typer.Exit(1)

    # Create project skeleton
    template_info = available_templates[template]

    with console.status(f"Creating project with {template} template..."):
        created_files = create_project_skeleton(template, template_info, force)

    # Success output
    panel_content = f"Project initialized with [bold]{template}[/bold] template\n\n"
    panel_content += "Created files:\n"
    for file_path in created_files:
        panel_content += f"  • {file_path}\n"

    console.print(Panel(panel_content, title="Project Initialized", expand=False))

    # Next steps
    console.print("\n[bold]Next steps:[/bold]")
    steps_table = Table(show_header=False, box=None, padding=(0, 1))
    steps_table.add_column("Step", style="bold cyan")
    steps_table.add_column("Description")

    steps_table.add_row("1.", "Edit .env with your RunPod API key")
    steps_table.add_row("2.", "Install dependencies: pip install -r requirements.txt")
    steps_table.add_row("3.", "Run your project: flash run")

    console.print(steps_table)
